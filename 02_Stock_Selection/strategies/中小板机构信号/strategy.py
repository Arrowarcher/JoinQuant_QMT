# -*- coding: utf-8 -*-
"""
中小板机构信号策略 - 结合小市值策略和机构建仓信号
"""

# 导入函数库
from jqdata import *
from jqlib.technical_analysis import *
import pandas as pd
import numpy as np

# 导入通知库
try:
    from notification_lib import *
    NOTIFICATION_AVAILABLE = True
except ImportError:
    NOTIFICATION_AVAILABLE = False
    log.warning("通知库未找到，将跳过通知功能")

# 策略配置 - 混合优化版
STRATEGY_CONFIG = {
    'basic_filter': {
        'enabled': True,
        'universe_index': "399101.XSHE",  # 中小板
        'buy_stock_count': 3,            # 固定持仓数量
        'candidate_multiplier': 3,        # 候选股票倍数
        'exclude_st': True,
        'exclude_suspended': True,
        'exclude_limit_up': True,
        'exclude_limit_down': True
    },
    'institutional_signal': {
        'enabled': True,
        'volume_ratio_min': 1.1,         # 温和放量（放宽）
        'volume_ratio_max': 3.0,          # 放宽上限
        'price_change_min': 0.005,       # 稳步上涨（放宽）
        'price_change_max': 0.12,        # 放宽上限
        'consecutive_days': 2,            # 连续上涨天数（放宽）
        'min_signals': 1,                 # 最少满足信号数量（放宽）
        'use_scoring': True,              # 使用评分系统
        'fallback_enabled': True          # 启用备选方案
    },
    'technical_confirmation': {
        'enabled': False,
        'ma_period': 5,                  # 使用5日均线
        'price_above_ma': True           # 价格站上均线
    },
    'risk_control': {
        'enabled': True,
        'max_stocks': 3,                 # 最大持仓数量
        'position_limit': 0.35,          # 单只股票最大仓位
        'min_position': 0.25             # 单只股票最小仓位
    },
    'notification': {
        'email_enabled': False,         # 邮件通知（需要配置）
        'html_enabled': True,          # HTML邮件通知（需要配置）
        'wechat_enabled': False        # 微信通知（需要配置）
    }
}

def initialize(context):
    """
    初始化策略
    """
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 设置避免未来数据
    set_option("avoid_future_data", True)
    # 输出内容到日志
    log.info('中小板机构信号策略初始化开始')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    
    # 策略配置
    g.config = STRATEGY_CONFIG
    
    # 股票池和选股结果
    g.security_universe_index = g.config['basic_filter']['universe_index']
    g.buy_stock_count = g.config['basic_filter']['buy_stock_count']
    g.ma_period = g.config['technical_confirmation']['ma_period']
    
    # 选股结果存储
    g.selected_stocks = []
    g.last_selection_date = None
    
    # 设置运行频率
    run_daily(my_trade, time='14:30', reference_security='000300.XSHG')
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
    # 设置手续费
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, 
                            close_commission=0.0003, min_commission=5), type='stock')
    
    # 设置通知配置
    if NOTIFICATION_AVAILABLE:
        # 示例邮件配置（需要用户自己配置）
        set_email_config({
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 587,
            'sender_email': '',
            'sender_password': '',
            'recipients':  []
        })
        
        # 示例微信配置（需要用户自己配置）
        # set_wechat_config({
        #     'webhook_url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY'
        # })
        
        log.info("通知配置设置完成")
    
    log.info("中小板机构信号策略初始化完成")
    log.info("策略配置: %s" % g.config)

def my_trade(context):
    """
    主要交易逻辑 - 结合两个策略的优点
    """
    # 记录策略虚拟时间（回测时间）
    strategy_datetime = context.current_dt
    
    log.info("=== 开始混合优化选股 ===")
    
    # 1. 基础筛选 - 使用strategy.py的简洁逻辑
    basic_candidates = run_basic_filter(context)
    log.info("基础筛选结果: %d 只股票" % len(basic_candidates))
    
    if not basic_candidates:
        log.info("基础筛选无候选股票")
        return
    
    # 2. 机构建仓信号筛选 - 使用optimized_backtest_strategy.py的逻辑
    institutional_candidates = run_institutional_signal_filter(context, basic_candidates)
    log.info("机构信号筛选结果: %d 只股票" % len(institutional_candidates))
    
    if not institutional_candidates:
        log.info("机构信号筛选无候选股票")
        return
    
    # 3. 技术面确认 - 使用strategy.py的MA逻辑
    technical_candidates = run_technical_confirmation(context, institutional_candidates)
    log.info("技术面确认结果: %d 只股票" % len(technical_candidates))
    
    if not technical_candidates:
        log.info("技术面确认无候选股票")
        return
    
    # 4. 最终选股 - 限制数量
    final_stocks = technical_candidates[:g.buy_stock_count]
    log.info("最终选股结果: %d 只股票。股票代码: %s" % (len(final_stocks), ", ".join(final_stocks)))
    
    # 5. 执行调仓 - 使用strategy.py的简单逻辑
    adjust_position(context, final_stocks)
    
    # 6. 发送交易信号通知
    if NOTIFICATION_AVAILABLE:
        send_trading_signal_notification(context, final_stocks, strategy_datetime)

def run_basic_filter(context):
    """
    基础筛选 - 使用strategy.py的简洁逻辑
    """
    config = g.config['basic_filter']
    
    try:
        # 获取中小板股票
        check_out_lists = get_index_stocks(g.security_universe_index)
        
        # 按流通市值升序排列，选择候选股票
        q = query(valuation.code).filter(
            valuation.code.in_(check_out_lists)
        ).order_by(
            valuation.circulating_market_cap.asc()
        ).limit(
            g.buy_stock_count * config['candidate_multiplier']
        )
        
        check_out_lists = list(get_fundamentals(q).code)
        log.info("按市值排序后候选股票: %d 只" % len(check_out_lists))
        
        # 过滤三停及ST股票
        check_out_lists = filter_st_stock(check_out_lists)
        if config['exclude_limit_up']:
            check_out_lists = filter_limitup_stock(context, check_out_lists)
        if config['exclude_limit_down']:
            check_out_lists = filter_limitdown_stock(context, check_out_lists)
        if config['exclude_suspended']:
            check_out_lists = filter_paused_stock(check_out_lists)
        
        log.info("基础筛选完成: %d 只候选股票" % len(check_out_lists))
        return check_out_lists
        
    except Exception as e:
        log.error(f"基础筛选出错: {e}")
        return []

def run_institutional_signal_filter(context, candidates):
    """
    机构建仓信号筛选 - 优化版本，使用评分系统和备选方案
    """
    config = g.config['institutional_signal']
    
    if not config['enabled']:
        return candidates
    
    try:
        # 使用评分系统
        if config.get('use_scoring', False):
            return run_institutional_signal_scoring(context, candidates)
        else:
            return run_institutional_signal_strict(context, candidates)
        
    except Exception as e:
        log.error(f"机构建仓信号筛选出错: {e}")
        return candidates

def run_institutional_signal_scoring(context, candidates):
    """
    机构建仓信号评分筛选 - 更灵活的方式
    """
    config = g.config['institutional_signal']
    
    try:
        stock_scores = []
        
        for stock in candidates:
            try:
                # 获取最近5日数据
                hist = get_price(stock, count=5, frequency='daily', 
                               fields=['close', 'volume', 'high', 'low'])
                
                if len(hist) < 5:
                    continue
                
                # 计算各项指标
                volume_ratio = hist['volume'][-1] / hist['volume'][-5:].mean()
                price_change = (hist['close'][-1] - hist['close'][-5]) / hist['close'][-5]
                
                # 计算连续上涨天数
                positive_days = 0
                for i in range(1, len(hist)):
                    if hist['close'][i] > hist['close'][i-1]:
                        positive_days += 1
                
                # 计算综合评分
                score = calculate_institutional_score(volume_ratio, price_change, positive_days, config)
                
                if score > 0:
                    stock_scores.append((stock, score))
                    log.info("股票 %s 机构信号评分: %.2f" % (stock, score))
                    
            except Exception as e:
                continue
        
        # 按评分排序
        stock_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 选择评分最高的股票
        max_select = min(len(stock_scores), g.buy_stock_count * 2)  # 选择前N只
        selected_stocks = [stock for stock, score in stock_scores[:max_select]]
        
        log.info("机构建仓信号评分筛选: 从 %d 只股票中筛选出 %d 只候选股票" % (len(candidates), len(selected_stocks)))
        
        # 如果没有股票满足条件，使用备选方案
        if not selected_stocks and config.get('fallback_enabled', False):
            log.info("机构信号筛选无结果，启用备选方案")
            return run_fallback_selection(context, candidates)
        
        return selected_stocks
        
    except Exception as e:
        log.error(f"机构建仓信号评分筛选出错: {e}")
        return candidates

def calculate_institutional_score(volume_ratio, price_change, positive_days, config):
    """
    计算机构建仓信号评分
    """
    score = 0
    
    # 1. 成交量评分 (40%)
    if config['volume_ratio_min'] <= volume_ratio <= config['volume_ratio_max']:
        score += 40  # 温和放量
    elif volume_ratio > config['volume_ratio_max']:
        score += 20  # 放量但可能过度
    elif volume_ratio >= 1.0:
        score += 10  # 基本放量
    
    # 2. 价格变化评分 (40%)
    if config['price_change_min'] <= price_change <= config['price_change_max']:
        score += 40  # 稳步上涨
    elif price_change > config['price_change_max']:
        score += 20  # 上涨但可能过度
    elif price_change >= 0:
        score += 10  # 基本上涨
    
    # 3. 连续上涨评分 (20%)
    if positive_days >= config['consecutive_days']:
        score += 20  # 连续上涨
    elif positive_days >= 1:
        score += 10  # 部分上涨
    
    return score

def run_fallback_selection(context, candidates):
    """
    备选方案 - 当机构信号筛选无结果时使用
    """
    try:
        log.info("执行备选方案：选择市值最小的股票")
        
        # 获取市值数据
        q = query(valuation.code, valuation.circulating_market_cap).filter(
            valuation.code.in_(candidates)
        ).order_by(valuation.circulating_market_cap.asc())
        
        df = get_fundamentals(q)
        if len(df) == 0:
            return candidates[:g.buy_stock_count]
        
        # 按市值排序，选择最小的几只
        sorted_stocks = list(df['code'])
        selected_stocks = sorted_stocks[:g.buy_stock_count]
        
        log.info("备选方案: 选择 %d 只市值最小的股票" % len(selected_stocks))
        return selected_stocks
        
    except Exception as e:
        log.error(f"备选方案出错: {e}")
        return candidates[:g.buy_stock_count]

def run_institutional_signal_strict(context, candidates):
    """
    严格的机构建仓信号筛选 - 原始逻辑
    """
    config = g.config['institutional_signal']
    
    try:
        selected_stocks = []
        
        for stock in candidates:
            try:
                # 获取最近5日数据
                hist = get_price(stock, count=5, frequency='daily', 
                               fields=['close', 'volume', 'high', 'low'])
                
                if len(hist) < 5:
                    continue
                
                # 计算量价指标
                volume_ratio = hist['volume'][-1] / hist['volume'][-5:].mean()
                price_change = (hist['close'][-1] - hist['close'][-5]) / hist['close'][-5]
                
                # 判断机构建仓信号
                institutional_signals = []
                
                # 温和放量
                if config['volume_ratio_min'] <= volume_ratio <= config['volume_ratio_max']:
                    institutional_signals.append("温和放量")
                
                # 稳步上涨
                if config['price_change_min'] <= price_change <= config['price_change_max']:
                    institutional_signals.append("稳步上涨")
                
                # 连续小阳线
                positive_days = 0
                for i in range(1, len(hist)):
                    if hist['close'][i] > hist['close'][i-1]:
                        positive_days += 1
                
                if positive_days >= config['consecutive_days']:
                    institutional_signals.append("连续小阳线")
                
                # 综合评分
                if len(institutional_signals) >= config['min_signals']:
                    selected_stocks.append(stock)
                    log.info("股票 %s 满足机构信号: %s" % (stock, institutional_signals))
                    
            except Exception as e:
                continue
        
        log.info("机构建仓信号筛选: 从 %d 只股票中筛选出 %d 只候选股票" % (len(candidates), len(selected_stocks)))
        return selected_stocks
        
    except Exception as e:
        log.error(f"机构建仓信号筛选出错: {e}")
        return candidates

def run_technical_confirmation(context, candidates):
    """
    技术面确认 - 使用strategy.py的MA逻辑
    """
    config = g.config['technical_confirmation']
    
    if not config['enabled']:
        return candidates
    
    try:
        selected_stocks = []
        
        for stock in candidates:
            try:
                # 使用strategy.py的MA条件逻辑
                if check_ma_condition(stock):
                    selected_stocks.append(stock)
                    log.info("股票 %s 满足MA条件" % stock)
                    
            except Exception as e:
                continue
        
        log.info("技术面确认: 从 %d 只股票中筛选出 %d 只候选股票" % (len(candidates), len(selected_stocks)))
        return selected_stocks
        
    except Exception as e:
        log.error(f"技术面确认出错: {e}")
        return candidates

def check_ma_condition(stock):
    """
    检查MA条件 - 使用strategy.py的逻辑
    """
    try:
        now = context.current_dt
        end_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # 获取历史数据计算MA
        bars = get_bars(stock, g.ma_period + 5, unit='1d', fields=['close'], 
                       end_dt=end_time, include_now=False)
        if len(bars) < g.ma_period:
            return False
        
        # 手动计算MA
        close_prices = bars['close']
        MA_value = close_prices[-g.ma_period:].mean()
        
        # 获取当前价格
        current_bars = get_bars(stock, 1, unit='1m', fields=['close'], 
                               end_dt=end_time, include_now=False)
        if len(current_bars) == 0:
            return False
        now_price = current_bars['close'][-1]
        
        # 当前价站上相应平均线
        return now_price > MA_value
        
    except Exception as e:
        return False

def adjust_position(context, buy_stocks):
    """
    调仓逻辑 - 使用strategy.py的简单逻辑
    """
    try:
        # 卖出不在目标持仓中的股票
        for stock in context.portfolio.positions:
            if stock not in buy_stocks:
                log.info("调出目标持仓 %s" % stock)
                position = context.portfolio.positions[stock]
                close_position(context, position)
            else:
                log.info("股票 %s 已在持仓中" % stock)
        
        # 根据股票数量分仓 - 使用strategy.py的等权重分配
        position_count = len(context.portfolio.positions)
        if g.buy_stock_count > position_count:
            value = context.portfolio.cash / (g.buy_stock_count - position_count)
            
            for stock in buy_stocks:
                if context.portfolio.positions[stock].total_amount == 0:
                    if open_position(context, stock, value):
                        if len(context.portfolio.positions) == g.buy_stock_count:
                            break
        
    except Exception as e:
        log.error(f"调仓出错: {e}")

def open_position(context, security, value):
    """
    开仓逻辑 - 使用strategy.py的逻辑
    """
    try:
        now = context.current_dt
        end_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # 获取历史数据计算MA
        bars = get_bars(security, g.ma_period + 5, unit='1d', fields=['close'], 
                       end_dt=end_time, include_now=False)
        if len(bars) < g.ma_period:
            return False
        
        # 手动计算MA
        close_prices = bars['close']
        MA_value = close_prices[-g.ma_period:].mean()
        
        # 获取当前价格
        current_bars = get_bars(security, 1, unit='1m', fields=['close'], 
                               end_dt=end_time, include_now=False)
        if len(current_bars) == 0:
            return False
        now_price = current_bars['close'][-1]
        
        # 当前价站上相应平均线后，才进行买入
        if now_price < MA_value: 
            return False
        
        order = order_target_value(security, value)
        if order != None and order.filled > 0:
            return True
        return False
        
    except Exception as e:
        log.error(f"开仓出错: {e}")
        return False

def close_position(context, position):
    """
    平仓逻辑 - 使用strategy.py的逻辑
    """
    try:
        security = position.security
        order = order_target_value(security, 0)
        if order != None:
            if order.status == OrderStatus.held and order.filled == order.amount:
                return True
        return False
        
    except Exception as e:
        log.error(f"平仓出错: {e}")
        return False

def after_market_close(context):
    """
    收盘后运行函数
    """
    log.info(str('函数运行时间(after_market_close):' + str(context.current_dt.time())))
    # 得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：' + str(_trade))
    
    
    log.info('一天结束')
    log.info('##############################################################')

# 以下函数复用strategy.py的实现
def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_st_stock(stock_list):
    """过滤ST股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]

def filter_limitup_stock(context, stock_list):
    """过滤涨停股票"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]

def filter_limitdown_stock(context, stock_list):
    """过滤跌停股票"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]

# ==================== 通知相关函数 ====================

def send_trading_signal_notification(context, selected_stocks, strategy_datetime=None):
    """
    发送交易信号通知 - 使用新的通知库
    """
    if not selected_stocks:
        return
    
    # 准备选股数据
    stocks_data = []
    for stock in selected_stocks:
        # 获取股票信息
        stock_info = get_security_info(stock)
        current_data = get_current_data()[stock]
        
        # 计算涨跌幅
        hist = get_price(stock, count=2, frequency='daily', fields=['close'])
        if len(hist) >= 2:
            change_pct = (hist['close'][-1] - hist['close'][-2]) / hist['close'][-2] * 100
        else:
            change_pct = 0
        
        stocks_data.append({
            'code': stock,
            'name': stock_info.display_name,
            'price': current_data.last_price,
            'change_pct': change_pct,
            'reason': '小市值+机构建仓信号'
        })
    
    # 准备策略时间信息
    strategy_time_info = ""
    if strategy_datetime:
        strategy_time_info = f"策略时间: {strategy_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    # 发送普通文本通知
    message = f"=== 中小板机构信号策略 选股结果 ===\n{strategy_time_info}推荐股票数量: {len(stocks_data)}只\n\n"
    for i, stock in enumerate(stocks_data, 1):
        message += f"{i}. {stock['name']} ({stock['code']})\n"
        message += f"   价格: ¥{stock['price']:.2f}, 涨跌幅: {stock['change_pct']:+.2f}%\n"
        message += f"   推荐理由: {stock['reason']}\n\n"
    message += "⚠️ 投资有风险，入市需谨慎"
    
    # 发送邮件通知
    if g.config['notification']['email_enabled']:
        send_email(message, context)
        log.info("邮件通知发送完成")
    # 聚宽通知
    send_message(message)
    # 发送微信通知
    if g.config['notification']['wechat_enabled']:
        send_wechat(message)
        log.info("微信通知发送完成")
    
    # 发送HTML邮件通知（包含选股数据和策略时间）
    if g.config['notification']['html_enabled']:
        send_html_email("中小板机构信号策略", context=context, selected_stocks=stocks_data)
        log.info("HTML邮件通知发送完成")

