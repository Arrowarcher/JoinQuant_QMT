# -*- coding: utf-8 -*-
import jqdata
import numpy as np
import pandas as pd
from datetime import timedelta

"""
微盘股 次日强势捕捉策略
核心：昨日涨停 + 放量 + 强势K线 + 主力净流入 -> 次日择时买入
风控：等权、止盈、止损、移动止损、持有天数上限
注意：
- 建议使用“分钟级”回测/模拟，才能在 09:35 买入、盘中执行移动止损
- 代码默认开启真实价格模式
"""

def initialize(context):
    # 真实价格撮合（动态复权模式），更接近真实成交
    set_option('use_real_price', True)

    # 参数区（建议先用默认，回测后再微调）
    g.CIRC_MCAP_LOW  = 8.0     # 微盘下界（亿元，流通市值）
    g.CIRC_MCAP_HIGH = 50.0    # 微盘上界（亿元，流通市值）
    g.MIN_LIST_DAYS  = 120     # 上市天数下限，规避次新股波动
    g.MIN_10D_AVG_TURNOVER = 2e7   # 近10日平均成交额下限（元）
    g.MAX_HOLDINGS   = 5       # 最多持有股票数（等权）
    g.VOL_RATIO_TH   = 1.8     # 昨日量能相对5日均量放大阈值
    g.BREAK_MAX_LOOKBACK = 5   # 突破过去N日最高价
    g.EPS = 1e-6               # 小数稳定

    # 打分权重（合计不必为1，内部会归一化）
    g.W_VOL     = 0.35         # 量能放大权重
    g.W_FLOW    = 0.30         # 主力净占比权重
    g.W_MOM     = 0.20         # 动量（近3日收益）权重
    g.W_PATTERN = 0.15         # K线形态权重

    # 买入/卖出控制
    g.BUY_TIME      = '09:35'  # 过集合竞价不稳定阶段
    g.WAIT_BREAKOUT = True     # 买入时机：是否等待当日5分钟高点突破
    g.BREAK_WINDOW  = 5        # 统计开盘后前N分钟的最高价作为突破价

    # 止盈止损（相对进场价）
    g.TP    = 0.10             # 止盈（+10%）
    g.SL    = 0.05             # 止损（-5%）
    g.TRAIL = 0.07             # 移动止损回撤（从最高价回撤7%触发）
    g.MAX_HOLD_DAYS = 5        # 最长持有天数（T+1计数）

    # 是否剔除科创板、创业板（20cm）品种（微盘流动性差，按需选择）
    g.EXCLUDE_KECHUANG = True  # 688
    g.EXCLUDE_CHUANGYE = False # 300

    # 运行调度：
    # 1) 开盘前：筛选候选 + 评分（使用昨天数据）
    run_daily(before_market_open, time='09:00')
    # 2) 每分钟：盘中执行买入、移动止损等
    run_daily(every_minute, time='every_bar')
    # 3) 收盘后：整理与记录
    run_daily(after_trading_end, time='15:30')

    # 运行变量
    g.watchlist = []           # 盘前挑选的候选（按分数排序）
    g.breakout_price = {}      # 当日突破价缓存（code->float）
    g.pos_info = {}            # 持仓信息：入场价、最高价、入场日
    g.today = None


def before_market_open(context):
    g.today = context.current_dt.date()
    # 1) 生成初步股票池：全A（剔除ST）
    all_stocks = list(get_all_securities(['stock'], date=g.today).index)
    is_st = get_extras('is_st', all_stocks, end_date=g.today, count=1).iloc[0]
    pool = [s for s in all_stocks if not is_st.get(s, True)]

    # 可选：剔除科创板 688 开头
    if g.EXCLUDE_KECHUANG:
        pool = [s for s in pool if not s.startswith('688')]

    # 可选：剔除创业板 300 开头
    if g.EXCLUDE_CHUANGYE:
        pool = [s for s in pool if not s.startswith('300')]

    # 2) 上市天数 ≥ MIN_LIST_DAYS
    pool = [s for s in pool if (g.today - get_security_info(s).start_date).days >= g.MIN_LIST_DAYS]

    if len(pool) == 0:
        g.watchlist = []
        return

    # 3) 微盘筛选（流通市值区间）
    val = get_valuation(pool, end_date=str(g.today), count=1,
                        fields=['code', 'day', 'circulating_market_cap', 'market_cap'])
    if val is None or val.empty:
        g.watchlist = []
        return

    val = val.drop_duplicates(subset=['code'], keep='last').set_index('code')
    pool = val[(val['circulating_market_cap'] >= g.CIRC_MCAP_LOW) &
            (val['circulating_market_cap'] <= g.CIRC_MCAP_HIGH)].index.tolist()

    if len(pool) == 0:
        g.watchlist = []
        return

    # 4) 近10日平均成交额下限，规避流动性过差
    try:
        bars = get_bars(pool, count=10, unit='1d', fields=['code', 'money'], include_now=False, df=True)
        avg_turn = bars.groupby('code')['money'].mean()
        pool = avg_turn[avg_turn >= g.MIN_10D_AVG_TURNOVER].index.tolist()
    except:
        pass

    if len(pool) == 0:
        g.watchlist = []
        return

    # 5) 基于昨日数据生成候选（涨停 + 放量 + 强K线 + 主力净流入）
    candidates = _select_candidates(context, pool)
    if not candidates:
        g.watchlist = []
        return

    # 6) 打分排序，取前若干的扩展池（比如前 30，用于盘中择时挑前 g.MAX_HOLDINGS）
    scored = _score_candidates(context, candidates)
    g.watchlist = [c for c, _ in scored[:max(g.MAX_HOLDINGS*6, 30)]]  # 备选更大，便于盘中过滤
    log.info('候选数量: %d' % len(g.watchlist))


def every_minute(context):
    # 当前时间
    dt = context.current_dt
    hhmm = dt.strftime('%H:%M')

    # 1) 记录当日开盘后前N分钟最高价（用于突破入场）
    _update_intraday_breakout_ref(context)

    # 2) 在 BUY_TIME 执行买入逻辑（只在该分钟触发一次）
    if hhmm == g.BUY_TIME:
        _try_open_positions(context)

    # 3) 盘中移动止损、止盈、硬止损（每分钟检查）
    _manage_positions_intraday(context)


def after_trading_end(context):
    # 清理非持仓的缓存
    held = set(context.portfolio.long_positions.keys())
    # 清理突破价缓存
    g.breakout_price = {c: p for c, p in g.breakout_price.items() if c in held}
    # 记录持仓信息
    for c, pos in context.portfolio.long_positions.items():
        info = g.pos_info.get(c, {})
        info['last_price'] = pos.price
        g.pos_info[c] = info

    # 日志概览
    log.info('收盘持仓: %s' % list(held))


# ------------------------ 选股与打分 ------------------------

def _select_candidates(context, pool):
    """
    返回满足基本条件的候选股列表（昨日涨停 + 放量 + K线强 + 主力净流入）
    """
    prev_date = context.previous_date
    res = []

    # 批量获取昨日资金流
    try:
        money_flow = get_money_flow(pool, end_date=str(prev_date), count=1)
        money_flow = money_flow.sort_values('date').drop_duplicates(['sec_code'], keep='last').set_index('sec_code')
    except:
        money_flow = pd.DataFrame()

    for s in pool:
        # 取6根K线（便于算5日均量、形态等）
        try:
            h = attribute_history(s, count=6, unit='1d',
                                fields=['open', 'close', 'high', 'low', 'volume', 'money', 'high_limit'],
                                skip_paused=True, df=True)
        except:
            continue
        if h is None or h.shape[0] < 6:
            continue

        last = h.iloc[-1]     # 昨日
        prev5 = h.iloc[-6:-1] # 昨日之前5天

        # 1) 涨停判定（接近涨停价）
        if last['close'] < last['high_limit'] * 0.997:  # 留出价差（避免误判）
            continue

        # 2) 量能放大（昨日相对过去5日均量）
        vol_ratio = last['volume'] / (prev5['volume'].mean() + g.EPS)
        if vol_ratio < g.VOL_RATIO_TH:
            continue

        # 3) K线强势：长阳 + 强实体占比 + 突破前高（简单形态）
        body = last['close'] - last['open']
        range_ = last['high'] - last['low'] + g.EPS
        if body <= 0:
            continue
        body_ratio = body / range_
        if body_ratio < 0.6:
            continue
        # 突破过去N日最高
        if last['close'] <= prev5['high'].tail(g.BREAK_MAX_LOOKBACK).max():
            continue

        # 4) 主力净占比（可选）
        flow_ok = True
        flow_score = 0.0
        if not money_flow.empty and s in money_flow.index:
            flow = money_flow.loc[s]
            net_pct_main = flow.get('net_pct_main', 0.0)  # %
            flow_ok = (net_pct_main is not None) and (net_pct_main > 0.0)
            flow_score = 0.0 if pd.isna(net_pct_main) else float(net_pct_main)
        if not flow_ok:
            continue

        res.append(s)

    return res


def _score_candidates(context, candidates):
    """
    对候选打分排序，返回 [(code, score), ...] 降序
    打分项：量能放大、主力净占比、3日动量、形态强度
    """
    prev_date = context.previous_date
    data = {'code': [], 'vol_ratio': [], 'net_pct_main': [], 'mom3': [], 'pattern': []}

    # 批量资金流
    try:
        money_flow = get_money_flow(candidates, end_date=str(prev_date), count=1)
        money_flow = money_flow.sort_values('date').drop_duplicates(['sec_code'], keep='last').set_index('sec_code')
    except:
        money_flow = pd.DataFrame()

    for s in candidates:
        try:
            h = attribute_history(s, count=7, unit='1d',
                                fields=['open','close','high','low','volume','money','high_limit'],
                                skip_paused=True, df=True)
        except:
            continue
        if h is None or h.shape[0] < 7:
            continue

        last = h.iloc[-1]
        prev5 = h.iloc[-6:-1]
        vol_ratio = last['volume'] / (prev5['volume'].mean() + g.EPS)

        # 近3日动量（含昨日），更强调强势延续
        ret3 = (h['close'].iloc[-1] / h['close'].iloc[-4] - 1.0)

        # 形态强度（0~1）：实体占比 + 长下影（更偏强）
        body = last['close'] - last['open']
        rng  = last['high'] - last['low'] + g.EPS
        body_ratio = max(0.0, body) / rng
        lower_shadow = (min(last['open'], last['close']) - last['low']) / rng
        pattern = 0.7*body_ratio + 0.3*lower_shadow

        # 主力净占比
        net_pct_main = 0.0
        if not money_flow.empty and s in money_flow.index:
            v = money_flow.loc[s].get('net_pct_main', 0.0)
            net_pct_main = 0.0 if pd.isna(v) else float(v)

        data['code'].append(s)
        data['vol_ratio'].append(vol_ratio)
        data['net_pct_main'].append(net_pct_main)
        data['mom3'].append(ret3)
        data['pattern'].append(pattern)

    if len(data['code']) == 0:
        return []

    df = pd.DataFrame(data).set_index('code')

    # 标准化
    def _z(x):
        m = x.mean()
        s = x.std()
        if s < 1e-8:
            return x*0
        return (x - m) / s

    z_vol     = _z(df['vol_ratio'])
    z_flow    = _z(df['net_pct_main'])
    z_mom3    = _z(df['mom3'])
    z_pattern = _z(df['pattern'])

    wsum = g.W_VOL + g.W_FLOW + g.W_MOM + g.W_PATTERN
    df['score'] = (g.W_VOL*z_vol +
                g.W_FLOW*z_flow +
                g.W_MOM*z_mom3 +
                g.W_PATTERN*z_pattern) / (wsum + 1e-9)

    ranked = df['score'].sort_values(ascending=False)
    return list(ranked.items())


# ------------------------ 盘中买入与风控 ------------------------

def _update_intraday_breakout_ref(context):
    """统计开盘后前N分钟的最高价，作为突破买入的参考"""
    held = set(context.portfolio.long_positions.keys())
    # 只对候选（未持有）标的记录突破参考价
    codes = [c for c in g.watchlist if c not in held]
    if not codes:
        return
    try:
        # 从开盘至当前分钟（含）取分钟K线，统计最高价
        now = context.current_dt
        # 用 include_now=True 保证包含当前bar
        bars = get_bars(codes, count=max(g.BREAK_WINDOW, 1), unit='1m',
                        fields=['code','high'], include_now=True, df=True)
        if bars is None or bars.empty:
            return
        # 近 N 分钟最高价
        hi = bars.groupby('code')['high'].max()
        for c, h in hi.items():
            g.breakout_price[c] = max(g.breakout_price.get(c, 0.0), float(h))
    except:
        pass


def _try_open_positions(context):
    """
    在指定时间点尝试开仓：
    - 等权买入 TopK 候选
    - 过滤：停牌、一字板、开盘即板、过度高开
    - 如等待突破：当前价 > 开盘后N分钟高点
    """
    if not g.watchlist:
        return

    current_data = get_current_data()
    held = set(context.portfolio.long_positions.keys())

    # 目标买入名单：按候选排序挑未持有的前K个，逐个评估买入条件
    buylist = []
    for c in g.watchlist:
        if len(buylist) >= g.MAX_HOLDINGS:
            break
        if c in held:
            continue
        cd = current_data[c]
        # 过滤：停牌、ST
        if cd.paused or cd.is_st:
            continue
        # 过滤：一字板/开盘即板（买不到或风险过大）
        if cd.last_price >= cd.high_limit * 0.999:
            continue
        # 过滤：开盘高开过大（例如 > +6%，可选）
        try:
            # 取当日开盘价
            day_open = cd.day_open
            if day_open and day_open > 0:
                gap = cd.last_price / day_open - 1.0
                if gap > 0.06:
                    continue
        except:
            pass

        # 若等待突破，需当前价 > 开盘后前N分钟最高价（g.breakout_price）
        if g.WAIT_BREAKOUT:
            bo = g.breakout_price.get(c, 0.0)
            if bo > 0 and cd.last_price <= bo * 1.000:
                continue

        buylist.append(c)

    if not buylist:
        return

    # 资金等权分配
    cash = context.portfolio.available_cash
    per_val = cash / len(buylist)
    if per_val <= 0:
        return

    for c in buylist:
        order_target_value(c, per_val)
        # 建立持仓信息
        g.pos_info[c] = {
            'entry_price': current_data[c].last_price,
            'highest': current_data[c].last_price,
            'entry_date': g.today
        }
        log.info('买入: %s, 目标资金: %.0f' % (c, per_val))


def _manage_positions_intraday(context):
    """
    盘中风控：
    - 硬止损、止盈
    - 移动止损（从最高回撤）
    - 持有天数上限（在14:50之后平仓）
    """
    now = context.current_dt
    hhmm = now.strftime('%H:%M')

    current_data = get_current_data()
    to_close = []

    for c, pos in context.portfolio.long_positions.items():
        lp = float(current_data[c].last_price)
        info = g.pos_info.get(c, None)
        if info is None:
            # 如果是历史持仓或者上次缓存丢失，补充
            g.pos_info[c] = {'entry_price': pos.avg_cost, 'highest': lp, 'entry_date': g.today}
            info = g.pos_info[c]

        # 更新最高价
        info['highest'] = max(info.get('highest', lp), lp)

        entry_price = info.get('entry_price', pos.avg_cost)
        highest = info.get('highest', lp)

        # 止盈/止损
        if entry_price > 0:
            up = lp / entry_price - 1.0
            if up >= g.TP:
                to_close.append((c, 'TP'))
                continue
            if up <= -g.SL:
                to_close.append((c, 'SL'))
                continue

        # 移动止损（从最高回撤）
        if highest > 0:
            draw = lp / highest - 1.0
            if draw <= -g.TRAIL:
                to_close.append((c, 'TRAIL'))
                continue

        # 持有天数上限（14:50之后统一处理，避免过早触发）
        if hhmm >= '14:50':
            # 以T+1计，entry_date+MAX_HOLD_DAYS-1是到期日
            hold_days = (g.today - info.get('entry_date', g.today)).days + 1
            if hold_days >= g.MAX_HOLD_DAYS:
                to_close.append((c, 'TIME'))

    # 执行平仓
    for c, reason in to_close:
        order_target_value(c, 0)
        if c in g.pos_info:
            del g.pos_info[c]
        if c in g.breakout_price:
            del g.breakout_price[c]
        log.info('卖出: %s, 原因: %s' % (c, reason))