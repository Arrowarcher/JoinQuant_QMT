# 克隆自聚宽文章：https://www.joinquant.com/post/61535
# 标题：中小板弱转强V2五年128倍收益年化140%
# 作者：空空儿
# 增强版：添加通知功能

# ========= 通知配置 =========
NOTIFICATION_CONFIG = {
    'enabled': True,  # 是否启用通知功能
    'trading_notification': True,  # 是否发送交易通知
    'daily_summary': True,  # 是否发送每日摘要
    'notification_format': 'markdown',  # 通知格式: 'html', 'markdown', 'text'
    'email_config': {
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 587,
            'sender_email': '',
            'sender_password': '',
            'recipients':  []
        },
}

import pandas as pd
import numpy as np
import datetime as dt
from datetime import datetime
from datetime import timedelta
from jqlib.technical_analysis import *
from jqdata import *

# 导入通知库
try:
    from notification_lib import *
    NOTIFICATION_AVAILABLE = True
except ImportError:
    NOTIFICATION_AVAILABLE = False
    log.warning("通知库未找到，将跳过通知功能")

def initialize(context):

    # ==========================全局参数设置============================
    # 策略基本参数
    g.stock_num = 4                # 每日最大买入股票数
    g.down = 0.4                   # 下引线比例
    g.avoid_jan_apr_dec = True     # 是否开启1、4、12月空仓规则
    # 技术指标参数
    g.ma_period = 10               # 均线周期
    g.volume_ratio_threshold = 10  # 成交量倍数上限（避免放量过大）
    # 卖出参数
    g.stop_loss_ma_period = 7      # 止损均线周期（MA7）
    # 国九条筛选参数
    g.min_operating_revenue = 1e8  # 国九条筛选：最小营业收入（元）
    g.min_net_profit = 0           # 最小净利润
    g.min_roe = 0                  # 最小净资产收益率
    g.min_roa = 0                  # 最小总资产收益率
    # 时间参数
    g.open_down_threshold = 0.95   # 开盘价相对于昨日收盘价的下限
    g.open_up_threshold = 1.01     # 开盘价相对于昨日收盘价的上限

    set_option('use_real_price', True)      # 使用真实价格   
    set_option('avoid_future_data', True)   # 开启防未来函数   
    set_slippage(FixedSlippage(0.0001))     # 滑点设置
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0001, close_commission=0.0001,
                             close_today_commission=0, min_commission=1), type='stock')

    g.today_list=[]  #当日观测股票
    g.buy_dates={}  #记录股票买入日期
    g.dieting_stocks = []  # 跌停股票列表（用于监控卖出）

    # 初始化通知相关变量
    g.last_notification_date = None
    g.daily_trading_summary = {
        'date': None,
        'trades': [],
        'performance': 0,
        'selected_stocks': [],
        'positions': []
    }

    run_daily(perpare,time="09:26")      # 筛选时间
    run_daily(buy,time="09:27")          # 买入时间
    run_daily(sell,time='13:00')         # 盘中卖出时间
    run_daily(sell,time='14:55')         # 尾盘卖出时间
    run_daily(check_dieting, time="every_bar") # 监控跌停板
    run_daily(print_date_separator, time="15:05") # 收盘后打印日期分隔线
    run_daily(send_daily_summary, time="15:10") # 发送每日摘要通知

    # 过滤系统订单日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    
    # 设置通知配置
    if NOTIFICATION_AVAILABLE and NOTIFICATION_CONFIG['enabled']:
        # 邮件配置
        set_email_config(NOTIFICATION_CONFIG['email_config'])
        
        log.info(f"中小板弱转强策略通知配置设置完成 - 格式: {NOTIFICATION_CONFIG['notification_format']}")
    
def perpare(context):#筛选
    # 检查是否在1、4、12月空仓期
    if g.avoid_jan_apr_dec and is_avoid_period(context):
        log.info("当前处于1、4、12月空仓期，今日不交易")
        g.today_list = []
        return
        
    g.dieting=[]
    current_data = get_current_data()
    g.yesterday_high_dict = {}
    g.today_list=[]
    stk_list=get_st(context)
    
    # 记录初始成分股数量
    initial_constituents = len(stk_list)
    
    # 国九条筛选
    stk_list=GJT_filter_stocks(stk_list)
    if len(stk_list)==0:
        return
    
    # 技术指标筛选
    stk_list=filter_stocks(context,stk_list)
    if len(stk_list)==0:
        return
    
    # 弱转强模式筛选（昨日不涨停，前日涨停）
    stk_list=rzq_list(context,stk_list)
    if len(stk_list)==0:
        return

    # 获取前一日收盘价
    df = get_price(
        stk_list,
        end_date=context.previous_date,
        frequency='daily',
        fields=['close'],
        count=1,
        panel=False,
        fill_paused=False,
        skip_paused=True
    ).set_index('code')
    
    # 添加当前开盘价，并处理可能的异常
    open_now_values = []
    for s in stk_list:
        try:
            open_now_values.append(current_data[s].day_open)
        except KeyError as e:
            log.info(f"警告: 股票 {s} 的数据不可用, 错误: {e}")
            open_now_values.append(None)
    
    df['open_now'] = open_now_values
    
    # 移除那些 'open_now' 是 None 的行
    df = df.dropna(subset=['open_now'])
    
    # 筛选开盘价在设定范围内的股票
    df = df[(df['open_now'] / df['close']) < g.open_up_threshold]
    df = df[(df['open_now'] / df['close']) > g.open_down_threshold]
    
    # 更新 stk_list
    stk_list = list(df.index)
    
    # 排除已持仓的股票
    hold_list = list(context.portfolio.positions)
    stk_list = list(set(stk_list) - set(hold_list))
    
    if len(stk_list) == 0:
        return
    
    # 获取估值数据（包括换手率等）
    df_val = get_valuation(
        stk_list,
        start_date=context.previous_date,
        end_date=context.previous_date,
        fields=['turnover_ratio', 'market_cap', 'circulating_market_cap']
    )
    
    # 确保两个DataFrame的code列都是字符串类型
    df.index = df.index.astype(str)
    df_val['code'] = df_val['code'].astype(str)
    
    # 使用 pd.merge 进行合并
    df_combined = pd.merge(df.reset_index(), df_val, on='code')
    
    # 新增因子：换手率 * 开盘/收盘比值
    df_combined['factor'] = df_combined['turnover_ratio'] * (df_combined['open_now'] / df_combined['close'])
    
    # 按照该因子从大到小排序
    df_sorted = df_combined.sort_values(by='factor', ascending=False)
    
    # 更新今日选股列表
    g.today_list = list(df_sorted['code'])
    
    # 记录选股信息到通知摘要
    g.daily_trading_summary['date'] = context.current_dt.strftime('%Y-%m-%d')
    g.daily_trading_summary['selected_stocks'] = []
    
    # 构建选股详情
    for i, code in enumerate(g.today_list[:10]):  # 只记录前10只
        try:
            stock_info = get_security_info(code)
            stock_name = stock_info.display_name
            current_data = get_current_data()
            current_price = current_data[code].last_price
            # 计算当日涨跌幅
            if hasattr(current_data[code], 'day_open') and current_data[code].day_open and current_data[code].day_open != 0:
                change_pct = (current_price / current_data[code].day_open - 1) * 100
            else:
                change_pct = 0
            
            g.daily_trading_summary['selected_stocks'].append({
                'name': stock_name,
                'code': code,
                'price': current_price,
                'change_pct': change_pct,
                'rank': i + 1,
                'reason': f"弱转强模式，排名第{i+1}位"
            })
        except Exception as e:
            log.warning(f"获取股票信息失败 {code}: {e}")
    
    # 打印成分股和候选股数量
    remaining_positions = g.stock_num - len(hold_list)
    log.info(f"今日成分股数量：{initial_constituents}只，候选股票数量：{len(g.today_list)}只，可买仓位：{remaining_positions}个")
    
    # 如果候选股数量小于等于10只，打印所有候选股名称
    if len(g.today_list) <= 10 and len(g.today_list) > 0:
        try:
            stock_names = [get_security_info(code).display_name + f"({code})" for code in g.today_list]
            log.info(f"候选股票：{', '.join(stock_names)}")
        except:
            log.info(f"候选股票：{', '.join(g.today_list)}")
    elif len(g.today_list) > 10:
        try:
            stock_names = [get_security_info(code).display_name + f"({code})" for code in g.today_list[:10]]
            log.info(f"前10只候选股票：{', '.join(stock_names)}")
        except:
            log.info(f"前10只候选股票：{', '.join(g.today_list[:10])}")

def sell(context):
    hold_list = list(context.portfolio.positions)
    if not hold_list:
        return
    
        
    current_data = get_current_data()
    yesterday = context.previous_date
    
    # T+1规则：过滤当日买入的股票，不能卖出
    sellable_stocks = []
    for stock in hold_list:
        if stock in g.buy_dates and g.buy_dates[stock] == context.current_dt.date():
            continue  # 当日买入的股票，不能卖出
        sellable_stocks.append(stock)
    
    if not sellable_stocks:
        return
    
    # 批量获取持仓股票的历史数据（包括止损均线）
    # 获取过去stop_loss_ma_period+1天的数据
    hist_data = get_price(
        sellable_stocks,
        end_date=yesterday,
        frequency='daily',
        fields=['close'],
        count=g.stop_loss_ma_period + 1,  # 使用全局参数
        panel=False
    )
    
    # 计算止损均线
    ma_data = hist_data.groupby('code')['close'].apply(lambda x: x.rolling(g.stop_loss_ma_period).mean().iloc[-1]).to_dict()  # 使用全局参数
    
    # 批量获取昨日涨停数据
    df_history = get_price(
        sellable_stocks,
        end_date=yesterday,
        frequency='daily',
        fields=['close', 'high_limit'],
        count=1,
        panel=False
    )
    
    df_history['avg_cost'] = [context.portfolio.positions[s].avg_cost for s in sellable_stocks]
    df_history['price'] = [context.portfolio.positions[s].price for s in sellable_stocks]
    df_history['high_limit'] = [current_data[s].high_limit for s in sellable_stocks]
    df_history['low_limit'] = [current_data[s].low_limit for s in sellable_stocks]
    df_history['last_price'] = [current_data[s].last_price for s in sellable_stocks]
    df_history['ma'] = [ma_data.get(s, 0) for s in sellable_stocks]  # 添加均线数据
    # 添加可平仓数量检查
    df_history['closeable_amount'] = [context.portfolio.positions[s].closeable_amount for s in sellable_stocks]
    
    # 条件1：未涨停
    cond1 = (df_history['last_price'] != df_history['high_limit'])
    
    # 条件2.1：价格跌破均线
    cond2_1 = df_history['last_price'] < df_history['ma']
    
    # 条件2.2：盈利超过0%
    ret_matrix = (df_history['price'] / df_history['avg_cost'] - 1) * 100
    cond2_2 = ret_matrix > 0
    
    # 条件2.3：昨日涨停
    cond2_3 = (df_history['close'] == df_history['high_limit'])
    
    # 组合卖出条件（逻辑或运算）
    sell_condition = cond1 & (cond2_1 | cond2_2 | cond2_3)
    
    # 生成卖出列表（过滤无效订单）
    sell_list = df_history[
        sell_condition & 
        (df_history['last_price'] > df_history['low_limit']) &
        (df_history['closeable_amount'] > 0)  # 确保有可平仓数量
    ].code.tolist()
    
    # 批量下单
    for s in sell_list:
        position = context.portfolio.positions[s]
        if position.closeable_amount > 0 and current_data[s].last_price > current_data[s].low_limit:
            # 在执行卖出前获取持仓信息
            avg_cost = position.avg_cost
            current_price = position.price
            # 获取股票名称
            try:
                stock_name = get_security_info(s).display_name
            except:
                stock_name = s
            
            # 计算盈亏
            profit_pct = (current_price / avg_cost - 1) * 100 if avg_cost != 0 else 0
            
            # 执行卖出
            order_target_value(s, 0)
            log.info(f'卖出 {stock_name}({s}) | 成本价:{avg_cost:.2f} 现价:{current_price:.2f}')
            
            # 记录卖出交易到通知摘要
            trade_info = {
                'action': '卖出',
                'stock': s,
                'stock_name': stock_name,
                'avg_cost': avg_cost,
                'current_price': current_price,
                'profit_pct': profit_pct,
                'reason': '止损或止盈卖出',
                'notified': False,  # 标记未通知
                'timestamp': context.current_dt.strftime('%H:%M:%S')
            }
            g.daily_trading_summary['trades'].append(trade_info)
            
    
    # 发送交易通知（只有实际发生卖出操作时才发送）
    if sell_list and NOTIFICATION_AVAILABLE and NOTIFICATION_CONFIG['enabled'] and NOTIFICATION_CONFIG['trading_notification']:
        send_trading_notification(context)

def buy(context):
    # 检查是否在1、4、12月空仓期
    if g.avoid_jan_apr_dec and is_avoid_period(context):
        return
    
    
    #1 4 12月空仓
    
    #target=g.today_list
    target=filter_stocks_by_b_s(context,g.today_list)
    
    hold_list = list(context.portfolio.positions)
    num=g.stock_num-len(hold_list)
    if num==0:
        return
    target=[x for x in target  if x not in  hold_list][:num]
    if len(target) > 0:
        # 分配资金（等权重买入）
        value=context.portfolio.available_cash
        cash_per_stock = value / num
        current_data = get_current_data()  # 实时数据对象
        for stock in target:
            # 排除停牌和涨跌停无法交易的股票
            if current_data[stock].paused or \
            current_data[stock].last_price==current_data[stock].low_limit or \
            current_data[stock].last_price==current_data[stock].high_limit:
                continue
            # 获取股票名称
            try:
                stock_name = get_security_info(stock).display_name
            except:
                stock_name = stock
            
            # 获取当前价格
            current_price = current_data[stock].last_price
            
            order_value(stock, cash_per_stock)  # 按金额买入[6](@ref)
            log.info (f"买入 {stock_name}({stock})")
            # 记录买入日期
            g.buy_dates[stock] = context.current_dt.date()
            
            # 记录买入交易到通知摘要
            trade_info = {
                'action': '买入',
                'stock': stock,
                'stock_name': stock_name,
                'amount': cash_per_stock,
                'price': current_price,
                'reason': '弱转强模式选股',
                'notified': False,  # 标记未通知
                'timestamp': context.current_dt.strftime('%H:%M:%S')
            }
            g.daily_trading_summary['trades'].append(trade_info)
            
    
    # 发送交易通知（只有实际发生买入操作时才发送）
    if target and len(target) > 0 and NOTIFICATION_AVAILABLE and NOTIFICATION_CONFIG['enabled'] and NOTIFICATION_CONFIG['trading_notification']:
        send_trading_notification(context)
#----------------函数群--------------------------------------------------/    

# 添加空仓期判断函数
def is_avoid_period(context):
    """判断是否在1、4、12月空仓期"""
    today_str = context.current_dt.strftime('%m-%d')
    avoid_periods = [
        ('01-15', '01-31'),
        ('04-15', '04-30'),
        ('12-15', '12-31')
    ]
    
    for start, end in avoid_periods:
        if start <= today_str <= end:
            return True
    return False

def filter_stocks_by_b_s(context,stock_list):
    """
    返回b_s>0的股票
    """
    date= context.current_dt.strftime("%Y-%m-%d")
    
    valid_stocks = []  # 符合条件的股票列表
    auction_data = {}   # 存储股票对应的b_s值
    
    for stock in stock_list:

        # 获取当日集合竞价数据
        auction_df = get_call_auction(stock, start_date=date, end_date=date)
        
        if auction_df is None or auction_df.empty:
            continue
            
        # 使用.assign()避免链式赋值警告
        auction_df = auction_df.assign(
            sellmoney=lambda df: 
                df['a1_p']*df['a1_v'] + 
                df['a2_p']*df['a2_v'] + 
                df['a3_p']*df['a3_v'] + 
                df['a4_p']*df['a4_v'] + 
                df['a5_p']*df['a5_v'],
            
            buymoney=lambda df: 
                df['b1_p']*df['b1_v'] + 
                df['b2_p']*df['b2_v'] + 
                df['b3_p']*df['b3_v'] + 
                df['b4_p']*df['b4_v'] + 
                df['b5_p']*df['b5_v']
        )
        
        # 计算b_s值
        auction_df = auction_df.assign(
            b_s=lambda df: (df['buymoney'] - df['sellmoney']) / df['sellmoney']
        )
        
        # 只保留b_s > 0的股票
        if not auction_df.empty and auction_df['b_s'].iloc[0] > 0:
            valid_stocks.append(stock)
            auction_data[stock] = auction_df['b_s'].iloc[0]
        
    return valid_stocks

def today_is_between(context):
        today = context.current_dt.strftime('%m-%d')
        if ('01-01' <= today) and (today <= '12-31'):
            return True
        elif ('01-01' <= today) and (today <= '12-31'):
            return True     
        elif ('01-01' <= today) and (today <= '12-31'):
            return True 
        else:
            return False
            
##获取成分股并过滤ST股##               
def get_st(context):
    # 获取成分股指数
    stocks = get_index_stocks('399101.XSHE', date=context.previous_date)
    
    # 过滤ST股
    st_data = get_extras('is_st', stocks, count=1, end_date=context.previous_date)
    st_data = st_data.T
    st_data.columns = ['is_st']
    # 保留非ST股
    st_data = st_data[st_data['is_st'] == False]
    filtered_stocks = st_data.index.tolist()
    
    return filtered_stocks    

##处理日期相关函数##
def get_shifted_date(date, days, days_type='T'):
    #获取上一个自然日
    d_date = transform_date(date, 'd')
    yesterday = d_date + dt.timedelta(-1)
    #移动days个自然日
    if days_type == 'N':
        shifted_date = yesterday + dt.timedelta(days+1)
    #移动days个交易日
    if days_type == 'T':
        all_trade_days = [i.strftime('%Y-%m-%d') for i in list(get_all_trade_days())]
        #如果上一个自然日是交易日，根据其在交易日列表中的index计算平移后的交易日        
        if str(yesterday) in all_trade_days:
            shifted_date = all_trade_days[all_trade_days.index(str(yesterday)) + days + 1]
        #否则，从上一个自然日向前数，先找到最近一个交易日，再开始平移
        else:
            for i in range(100):
                last_trade_date = yesterday - dt.timedelta(i)
                if str(last_trade_date) in all_trade_days:
                    shifted_date = all_trade_days[all_trade_days.index(str(last_trade_date)) + days + 1]
                    break
                
    return str(shifted_date)
##处理日期相关函数##
def transform_date(date, date_type):
    if type(date) == str:
        str_date = date
        dt_date = dt.datetime.strptime(date, '%Y-%m-%d')
        d_date = dt_date.date()
    elif type(date) == dt.datetime:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = date
        d_date = dt_date.date()
    elif type(date) == dt.date:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = dt.datetime.strptime(str_date, '%Y-%m-%d')
        d_date = date
    dct = {'str':str_date, 'dt':dt_date, 'd':d_date}
    return dct[date_type]    
##筛选不涨停##   
def get_ever_hl_stock(initial_list, date):#
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','high','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna() #去除停牌
    cd2 = df['close'] != df['high_limit']
    df = df[cd2]
    hl_list = list(df.code)
    return hl_list        
##筛选出涨停的股票##
def get_hl_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','low','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna() #去除停牌
    df = df[df['close'] == df['high_limit']]
    hl_list = list(df.code)
    return hl_list

##筛选昨日不涨停的股票##
def rzq_list(context,initial_list): 
    # 文本日期
    date = context.previous_date #昨日
    date = transform_date(date, 'str')
    date_1=get_shifted_date(date, -1, 'T')#前日
    date_2=get_shifted_date(date, -2, 'T')#大前日
    # 昨日不涨停
    h1_list = get_ever_hl_stock(initial_list, date)
    # 前日涨停过滤
    elements_to_remove = get_hl_stock(initial_list, date_1)
    zb_list = [stock for stock in h1_list if stock  in elements_to_remove]

    return zb_list
    
##技术指标筛选##
def filter_stocks(context, stocks):
    yesterday = context.previous_date
    df = get_price(
        stocks,
        count=g.ma_period + 1,  # 使用全局参数
        frequency='1d',
        fields=['close', 'low', 'volume'],
        end_date=yesterday,
        panel=False
    ).reset_index()
    
    # 按股票分组处理
    valid_stocks = []
    for code, group in df.groupby('code'):
        if len(group) < g.ma_period + 1:  # 确保有足够的数据
            continue
            
        # 计算技术指标
        group = group.copy()
        group['ma'] = group['close'].rolling(g.ma_period).mean()  # 使用全局参数
        group['prev_low'] = group['low'].shift(1)
        group['prev_volume'] = group['volume'].shift(1)
        
        # 获取最后一行数据
        last_row = group.iloc[-1]
        
        # 检查条件
        conditions_met = (
            not pd.isna(last_row['ma']) and
            not pd.isna(last_row['prev_low']) and
            not pd.isna(last_row['prev_volume']) and
            last_row['close'] > last_row['prev_low'] and
            last_row['close'] > last_row['ma'] and
            last_row['volume'] > last_row['prev_volume'] and
            last_row['volume'] < g.volume_ratio_threshold * last_row['prev_volume'] and  # 使用全局参数
            last_row['close'] > 1
        )
        
        if conditions_met:
            valid_stocks.append(code)
    
    return valid_stocks
            

##国九条筛选##
def GJT_filter_stocks(stocks):
    # 国九更新：过滤近一年净利润为负且营业收入小于1亿的
    # 国九更新：过滤近一年期末净资产为负的 (经查询没有为负数的，所以直接pass这条)
    q = query(
        valuation.code,
        valuation.market_cap,  # 总市值 circulating_market_cap/market_cap
        income.np_parent_company_owners,  # 归属于母公司所有者的净利润
        income.net_profit,  # 净利润
        income.operating_revenue  # 营业收入
        #security_indicator.net_assets
    ).filter(
        valuation.code.in_(stocks),
        income.np_parent_company_owners > g.min_net_profit,  # 使用全局参数
        income.net_profit > g.min_net_profit,  # 使用全局参数
        income.operating_revenue > g.min_operating_revenue,  # 使用全局参数
        indicator.roe > g.min_roe,  # 使用全局参数
        indicator.roa > g.min_roa,  # 使用全局参数
    )
    df = get_fundamentals(q)

    final_list=list(df.code)
            
    return final_list

# 实时监控跌停板函数
def check_dieting(context):
    """监控持仓股，如果跌停打开则卖出"""
    # 初始化跌停股票列表
    if not hasattr(g, 'dieting_stocks'):
        g.dieting_stocks = []
        
    if len(g.dieting_stocks) == 0:
        # 检查是否有新的跌停股票
        current_data = get_current_data()
        for stock in list(context.portfolio.positions.keys()):
            position = context.portfolio.positions[stock]
            # 如果股票跌停且有可卖数量，加入监控列表
            if (current_data[stock].last_price <= current_data[stock].low_limit and 
                position.closeable_amount > 0 and 
                stock not in g.dieting_stocks):
                g.dieting_stocks.append(stock)
        return
        
    current_data = get_current_data()
    to_remove = []
    
    for stock in g.dieting_stocks:
        # 检查持仓是否存在且可卖
        if stock not in context.portfolio.positions:
            to_remove.append(stock)
            continue
            
        position = context.portfolio.positions[stock]
        if position.closeable_amount <= 0:
            continue
            
        # 如果跌停打开且当前价高于跌停价
        if (current_data[stock].last_price > current_data[stock].low_limit):
            # 获取股票名称和持仓信息
            try:
                stock_name = get_security_info(stock).display_name
            except:
                stock_name = stock
            cost_price = position.avg_cost
            current_price = current_data[stock].last_price
            
            # 避免除零错误
            if cost_price > 0:
                profit_rate = (current_price / cost_price - 1) * 100
                log.info(f"跌停打开，止损卖出：{stock_name}({stock}) | 成本价：{cost_price:.2f}元 | 现价：{current_price:.2f}元 | 盈亏：{profit_rate:+.2f}%")
            
            # 执行卖出
            order_target(stock, 0)
            
            # 记录跌停卖出交易到通知摘要
            trade_info = {
                'action': '卖出',
                'stock': stock,
                'stock_name': stock_name,
                'avg_cost': cost_price,
                'current_price': current_price,
                'profit_pct': profit_rate,
                'reason': '跌停打开止损',
                'notified': False,  # 标记未通知
                'timestamp': context.current_dt.strftime('%H:%M:%S')
            }
            g.daily_trading_summary['trades'].append(trade_info)
            
            
            # 记录跌停卖出信息，统一在最后发送通知
            
            to_remove.append(stock)
    
    # 发送交易通知（只有实际发生跌停卖出操作时才发送）
    if to_remove and NOTIFICATION_AVAILABLE and NOTIFICATION_CONFIG['enabled'] and NOTIFICATION_CONFIG['trading_notification']:
        send_trading_notification(context)
    
    # 从监控列表中移除已卖出的股票
    for stock in to_remove:
        if stock in g.dieting_stocks:
            g.dieting_stocks.remove(stock)

# 收盘后打印日期分隔线
def print_date_separator(context):
    log.info("=" * 60)

def cleanup_daily_data(context):
    """
    清理每日交易数据，避免数据累积
    无论是否启用通知功能都会执行清理
    """
    if hasattr(g, 'daily_trading_summary'):
        # 记录今日交易统计
        today_trades_count = len(g.daily_trading_summary['trades'])
        if today_trades_count > 0:
            log.info(f"今日交易记录: {today_trades_count}笔，已清理")
        
        # 重置每日交易摘要
        g.daily_trading_summary = {
            'date': None,
            'trades': [],
            'performance': 0,
            'selected_stocks': [],
            'positions': []
        }
        
        # 清理跌停监控列表
        if hasattr(g, 'dieting_stocks'):
            g.dieting_stocks = []
        
        # 清理选股列表
        if hasattr(g, 'today_list'):
            g.today_list = []
        
        # 清理买入日期记录（保留最近30天的记录）
        if hasattr(g, 'buy_dates'):
            current_date = context.current_dt.date()
            # 只保留最近30天的买入记录
            g.buy_dates = {
                stock: buy_date for stock, buy_date in g.buy_dates.items()
                if (current_date - buy_date).days <= 30
            }
        
        # 清理通知相关变量
        if hasattr(g, 'last_notification_date'):
            g.last_notification_date = None
        
        log.info("每日数据清理完成")

# ========= 通知相关函数 =========

def send_trading_notification(context):
    """
    发送本次操作汇总通知 - 使用 notified 字段区分当前操作和历史操作
    """
    if not NOTIFICATION_AVAILABLE or not NOTIFICATION_CONFIG['enabled'] or not NOTIFICATION_CONFIG['trading_notification']:
        return
    
    # 获取未通知的交易记录
    unnotified_trades = [t for t in g.daily_trading_summary['trades'] if not t.get('notified', False)]
    if not unnotified_trades:
        return
    
    # 获取已通知的历史交易
    notified_trades = [t for t in g.daily_trading_summary['trades'] if t.get('notified', False)]
    
    # 构建通知内容
    markdown_content = f"""# 🔄 交易操作通知

## 📊 策略时间
{context.current_dt.strftime('%Y-%m-%d %H:%M:%S')}

## 🎯 本次操作 ({len(unnotified_trades)}只)
"""
    
    # 添加本次操作详情
    total_profit = 0
    buy_count = 0
    sell_count = 0
    
    for trade in unnotified_trades:
        if trade['action'] == '买入':
            buy_count += 1
            markdown_content += f"### 🟢 {trade['stock_name']} ({trade['stock']})\n"
            markdown_content += f"- **操作**: 买入\n"
            markdown_content += f"- **买入价**: ¥{trade['price']:.2f}\n"
            markdown_content += f"- **买入金额**: ¥{trade['amount']:,.0f}\n"
            markdown_content += f"- **买入理由**: {trade['reason']}\n\n"
        
        elif trade['action'] == '卖出':
            sell_count += 1
            profit_emoji = "💰" if trade['profit_pct'] >= 0 else "📉"
            markdown_content += f"### 🔴 {trade['stock_name']} ({trade['stock']})\n"
            markdown_content += f"- **操作**: 卖出\n"
            markdown_content += f"- **成本价**: ¥{trade['avg_cost']:.2f}\n"
            markdown_content += f"- **卖出价**: ¥{trade['current_price']:.2f}\n"
            markdown_content += f"- **盈亏**: {profit_emoji} {trade['profit_pct']:+.2f}%\n"
            markdown_content += f"- **卖出理由**: {trade['reason']}\n\n"
            total_profit += trade['profit_pct']
    
    # 添加本次操作汇总
    markdown_content += f"## 📊 本次操作汇总\n"
    if buy_count > 0:
        markdown_content += f"- **买入股票**: {buy_count}只\n"
    if sell_count > 0:
        avg_profit = total_profit / sell_count if sell_count > 0 else 0
        profit_emoji = "💰" if avg_profit >= 0 else "📉"
        markdown_content += f"- **卖出股票**: {sell_count}只\n"
        markdown_content += f"- **平均盈亏**: {profit_emoji} {avg_profit:+.2f}%\n"
    
    # 添加今日历史操作（如果有）
    if notified_trades:
        markdown_content += f"\n## 📋 今日历史操作 ({len(notified_trades)}只)\n"
        for trade in notified_trades[-3:]:  # 只显示最近3次历史操作
            action_emoji = "🟢" if trade['action'] == '买入' else "🔴"
            if trade['action'] == '买入':
                markdown_content += f"- {action_emoji} **{trade['stock_name']}** 买入 ¥{trade['price']:.2f}\n"
            else:
                profit_emoji = "💰" if trade['profit_pct'] >= 0 else "📉"
                markdown_content += f"- {action_emoji} **{trade['stock_name']}** 卖出 {profit_emoji} {trade['profit_pct']:+.2f}%\n"
    
    markdown_content += """

## ⚠️ 风险提示
> 投资有风险，入市需谨慎
"""
    
    # 发送通知
    send_message(markdown_content)  # 聚宽内置通知
    
    # 发送统一格式通知
    operation_type = "买入" if buy_count > 0 else "卖出"
    send_unified_notification(
        content=markdown_content,
        subject=f"{operation_type}操作通知 - {len(unnotified_trades)}只股票",
        title="交易操作通知",
        format_type=NOTIFICATION_CONFIG['notification_format'],
        context=context
    )
    
    # 标记为已通知
    for trade in unnotified_trades:
        trade['notified'] = True
    
    log.info(f"本次交易操作通知发送完成 - {len(unnotified_trades)}只股票 (买入{buy_count}只, 卖出{sell_count}只)")

# 删除单个股票通知函数，改为汇总通知

def send_trading_signal_notification(context):
    """
    发送交易信号通知 - 优化版：在关键时点发送实时交易信号
    """
    if not NOTIFICATION_AVAILABLE or not NOTIFICATION_CONFIG['enabled'] or not NOTIFICATION_CONFIG['trading_notification']:
        return
    
    # 检查是否在1、4、12月空仓期
    if g.avoid_jan_apr_dec and is_avoid_period(context):
        log.info("当前处于空仓期，跳过交易信号通知")
        return
    
    # 获取当前时间，判断通知类型
    current_time = context.current_dt.strftime('%H:%M')
    
    # 获取实时交易信号
    current_positions = get_current_positions_info(context)
    today_signals = get_today_trading_signals(context)
    
    # 构建通知内容
    if current_time == "09:30":
        # 开盘后发送选股信号
        markdown_content = build_morning_signal_content(context, today_signals, current_positions)
        subject = "中小板弱转强策略 - 开盘交易信号"
    elif current_time == "13:30":
        # 午盘后发送持仓监控信号
        markdown_content = build_afternoon_signal_content(context, today_signals, current_positions)
        subject = "中小板弱转强策略 - 午盘交易信号"
    else:
        # 其他时间发送综合信号
        markdown_content = build_comprehensive_signal_content(context, today_signals, current_positions)
        subject = "中小板弱转强策略 - 实时交易信号"
    
    # 发送通知
    send_message(markdown_content)  # 聚宽内置通知
    
    # 发送统一格式通知
    send_unified_notification(
        content=markdown_content,
        subject=subject,
        title="实时交易信号通知",
        format_type=NOTIFICATION_CONFIG['notification_format'],
        context=context
    )
    
    log.info(f"交易信号通知发送完成 - 时间: {current_time}")

def send_stock_selection_notification(context):
    """
    发送选股通知 - 在筛选完成后立即发送
    """
    if not NOTIFICATION_AVAILABLE or not NOTIFICATION_CONFIG['enabled'] or not NOTIFICATION_CONFIG['trading_notification']:
        return
    
    # 检查是否在空仓期
    if g.avoid_jan_apr_dec and is_avoid_period(context):
        log.info("当前处于空仓期，跳过选股通知")
        return
    
    # 检查是否有候选股票
    if not hasattr(g, 'today_list') or not g.today_list:
        log.info("今日无候选股票，跳过选股通知")
        return
    
    # 构建选股通知内容
    markdown_content = f"""# 🎯 今日选股结果

## 📊 策略时间
{context.current_dt.strftime('%Y-%m-%d %H:%M:%S')}

## 🚀 选股完成
- **候选股票数量**: {len(g.today_list)}只
- **可买仓位**: {g.stock_num - len(context.portfolio.positions)}个
- **即将在09:27执行买入操作**

## 📈 推荐股票
"""
    
    # 添加选股信息
    current_data = get_current_data()
    for i, stock in enumerate(g.today_list[:5]):  # 只显示前5只
        try:
            stock_info = get_security_info(stock)
            current_price = current_data[stock].last_price
            
            # 计算当日涨跌幅
            if hasattr(current_data[stock], 'day_open') and current_data[stock].day_open and current_data[stock].day_open != 0:
                change_pct = (current_price / current_data[stock].day_open - 1) * 100
            else:
                change_pct = 0
            
            # 获取技术指标
            technical_info = get_technical_indicators_info(stock, context)
            
            markdown_content += f"### {i+1}. {stock_info.display_name} ({stock})\n"
            markdown_content += f"- **当前价格**: ¥{current_price:.2f} ({change_pct:+.2f}%)\n"
            markdown_content += f"- **推荐理由**: 弱转强模式，排名第{i+1}位\n"
            markdown_content += f"- **技术指标**: {technical_info}\n\n"
            
        except Exception as e:
            log.warning(f"获取股票信息失败 {stock}: {e}")
    
    # 添加市场分析
    market_analysis = get_market_analysis(context)
    if market_analysis:
        markdown_content += f"## 📊 市场分析\n"
        markdown_content += f"- **市场状态**: {market_analysis['market_status']}\n"
        markdown_content += f"- **选股难度**: {market_analysis['selection_difficulty']}\n"
        markdown_content += f"- **风险等级**: {market_analysis['risk_level']}\n"
        if market_analysis['tips']:
            markdown_content += f"- **操作建议**: {market_analysis['tips']}\n"
        markdown_content += "\n"
    
    markdown_content += """
## ⚠️ 重要提醒
> 🚨 **即将在09:27执行买入操作**
> 
> 请确认选股结果后准备执行
> 
> 投资有风险，入市需谨慎
"""
    
    # 发送通知
    send_message(markdown_content)  # 聚宽内置通知
    
    # 发送统一格式通知
    send_unified_notification(
        content=markdown_content,
        subject="今日选股结果 - 即将执行买入",
        title="选股结果通知",
        format_type=NOTIFICATION_CONFIG['notification_format'],
        context=context
    )
    
    log.info("选股通知发送完成")

def send_comprehensive_buy_notification(context):
    """
    发送综合开仓通知 - 包含选股数据和实际操作股票
    """
    try:
        # 构建综合通知内容
        markdown_content = f"""# 🎯 开仓通知

## 📊 策略时间
{context.current_dt.strftime('%Y-%m-%d %H:%M:%S')}

## 🚀 今日选股结果
- **候选股票数量**: {len(g.today_list)}只
- **可买仓位**: {g.stock_num - len(context.portfolio.positions)}个
"""
        
        # 添加选股信息（前5只）
        if hasattr(g, 'today_list') and g.today_list:
            current_data = get_current_data()
            markdown_content += "\n### 📈 今日选股（前5只）\n"
            for i, stock in enumerate(g.today_list[:5]):
                try:
                    stock_info = get_security_info(stock)
                    current_price = current_data[stock].last_price
                    
                    # 计算当日涨跌幅
                    if hasattr(current_data[stock], 'day_open') and current_data[stock].day_open and current_data[stock].day_open != 0:
                        change_pct = (current_price / current_data[stock].day_open - 1) * 100
                    else:
                        change_pct = 0
                    
                    markdown_content += f"{i+1}. **{stock_info.display_name}** ({stock}) - ¥{current_price:.2f} ({change_pct:+.2f}%)\n"
                except Exception as e:
                    markdown_content += f"{i+1}. **{stock}** - 数据获取失败\n"
        
        # 添加实际操作信息
        if hasattr(g, 'buy_notifications') and g.buy_notifications:
            markdown_content += f"\n## 🟢 实际买入操作\n"
            markdown_content += f"- **买入股票数量**: {len(g.buy_notifications)}只\n"
            markdown_content += f"- **总买入金额**: ¥{sum([item['amount'] for item in g.buy_notifications]):,.0f}\n\n"
            
            for i, buy_info in enumerate(g.buy_notifications):
                markdown_content += f"### {i+1}. {buy_info['stock_name']} ({buy_info['stock']})\n"
                markdown_content += f"- **买入价格**: ¥{buy_info['price']:.2f}\n"
                markdown_content += f"- **买入金额**: ¥{buy_info['amount']:,.0f}\n"
                markdown_content += f"- **买入理由**: 弱转强模式选股\n\n"
        else:
            markdown_content += "\n## 🟢 实际买入操作\n今日无买入操作\n\n"
        
        # 添加市场分析
        market_analysis = get_market_analysis(context)
        if market_analysis:
            markdown_content += f"## 📊 市场分析\n"
            markdown_content += f"- **市场状态**: {market_analysis['market_status']}\n"
            markdown_content += f"- **选股难度**: {market_analysis['selection_difficulty']}\n"
            markdown_content += f"- **风险等级**: {market_analysis['risk_level']}\n"
            if market_analysis['tips']:
                markdown_content += f"- **操作建议**: {market_analysis['tips']}\n"
            markdown_content += "\n"
    
        markdown_content += """
## ⚠️ 风险提示
> 本通知仅供参考，不构成投资建议
> 
> 投资有风险，入市需谨慎
"""
        
        # 发送通知
        send_message(markdown_content)  # 聚宽内置通知
        
        # 发送统一格式通知
        send_unified_notification(
            content=markdown_content,
            subject="开仓通知 - 今日选股与操作结果",
            title="开仓通知",
            format_type=NOTIFICATION_CONFIG['notification_format'],
            context=context
        )
        
        log.info("综合开仓通知发送完成")
        
        # 清空买入通知记录
        g.buy_notifications = []
        
    except Exception as e:
        log.warning(f"发送综合开仓通知失败: {e}")

# 保持原有策略逻辑，不添加复杂的紧急信号监控

def build_morning_signal_content(context, today_signals, current_positions):
    """
    构建早盘交易信号内容
    """
    markdown_content = f"""# 中小板弱转强策略 - 开盘交易信号

## 📊 策略时间
{context.current_dt.strftime('%Y-%m-%d %H:%M:%S')}

## 🌅 开盘选股信号
"""
    
    # 添加买入信号
    if today_signals['buy_signals']:
        markdown_content += f"### 🟢 今日推荐买入 ({len(today_signals['buy_signals'])}只)\n"
        for signal in today_signals['buy_signals']:
            markdown_content += f"- **{signal['name']}** ({signal['code']}) - ¥{signal['price']:.2f} ({signal['change_pct']:+.2f}%)\n"
            markdown_content += f"  💡 推荐理由: {signal['reason']}\n"
            markdown_content += f"  📊 技术指标: {signal['technical_info']}\n\n"
    else:
        markdown_content += "### 🟢 今日推荐买入\n今日无符合条件的买入信号\n\n"
    
    # 添加持仓监控
    if current_positions:
        markdown_content += f"### 💼 持仓监控 ({len(current_positions)}只)\n"
        for pos in current_positions:
            profit_emoji = "📈" if pos['profit_pct'] >= 0 else "📉"
            markdown_content += f"- **{pos['name']}** ({pos['code']}) - ¥{pos['price']:.2f} {profit_emoji} {pos['profit_pct']:+.2f}%\n"
            if pos['stop_loss_price']:
                markdown_content += f"  🛡️ 止损价: ¥{pos['stop_loss_price']:.2f}\n"
            markdown_content += "\n"
    
    # 添加市场分析
    market_analysis = get_market_analysis(context)
    if market_analysis:
        markdown_content += f"### 📈 市场分析\n"
        markdown_content += f"- **市场状态**: {market_analysis['market_status']}\n"
        markdown_content += f"- **选股难度**: {market_analysis['selection_difficulty']}\n"
        markdown_content += f"- **风险等级**: {market_analysis['risk_level']}\n"
        if market_analysis['tips']:
            markdown_content += f"- **操作建议**: {market_analysis['tips']}\n"
        markdown_content += "\n"
    
    markdown_content += """
## ⚠️ 风险提示
> 本信号仅供参考，不构成投资建议
> 
> 投资有风险，入市需谨慎
"""
    
    return markdown_content

def build_afternoon_signal_content(context, today_signals, current_positions):
    """
    构建午盘交易信号内容
    """
    markdown_content = f"""# 中小板弱转强策略 - 午盘交易信号

## 📊 策略时间
{context.current_dt.strftime('%Y-%m-%d %H:%M:%S')}

## 🌞 午盘持仓监控
"""
    
    # 添加卖出信号
    if today_signals['sell_signals']:
        markdown_content += f"### 🔴 建议卖出 ({len(today_signals['sell_signals'])}只)\n"
        for signal in today_signals['sell_signals']:
            profit_emoji = "💰" if signal['profit_pct'] >= 0 else "📉"
            markdown_content += f"- **{signal['name']}** ({signal['code']}) - ¥{signal['price']:.2f} {profit_emoji} {signal['profit_pct']:+.2f}%\n"
            markdown_content += f"  💡 卖出理由: {signal['reason']}\n\n"
    else:
        markdown_content += "### 🔴 建议卖出\n当前无卖出信号\n\n"
    
    # 添加持仓详情
    if current_positions:
        markdown_content += f"### 💼 持仓详情 ({len(current_positions)}只)\n"
        for pos in current_positions:
            profit_emoji = "📈" if pos['profit_pct'] >= 0 else "📉"
            markdown_content += f"- **{pos['name']}** ({pos['code']}) - ¥{pos['price']:.2f} {profit_emoji} {pos['profit_pct']:+.2f}%\n"
            markdown_content += f"  📊 持仓: {pos['quantity']}股 | 市值: ¥{pos['value']:,.0f}\n"
            if pos['stop_loss_price']:
                markdown_content += f"  🛡️ 止损价: ¥{pos['stop_loss_price']:.2f}\n"
            markdown_content += "\n"
    else:
        markdown_content += "### 💼 持仓详情\n当前无持仓\n\n"
    
    markdown_content += """
## ⚠️ 风险提示
> 午盘时段请密切关注持仓变化
> 
> 投资有风险，入市需谨慎
"""
    
    return markdown_content

def build_comprehensive_signal_content(context, today_signals, current_positions):
    """
    构建综合交易信号内容
    """
    markdown_content = f"""# 中小板弱转强策略 - 综合交易信号

## 📊 策略时间
{context.current_dt.strftime('%Y-%m-%d %H:%M:%S')}

## 🎯 综合交易信号
"""
    
    # 添加买入信号
    if today_signals['buy_signals']:
        markdown_content += f"### 🟢 买入信号 ({len(today_signals['buy_signals'])}只)\n"
        for signal in today_signals['buy_signals']:
            markdown_content += f"- **{signal['name']}** ({signal['code']}) - ¥{signal['price']:.2f} ({signal['change_pct']:+.2f}%)\n"
            markdown_content += f"  💡 推荐理由: {signal['reason']}\n"
            markdown_content += f"  📊 技术指标: {signal['technical_info']}\n\n"
    else:
        markdown_content += "### 🟢 买入信号\n当前无买入信号\n\n"
    
    # 添加卖出信号
    if today_signals['sell_signals']:
        markdown_content += f"### 🔴 卖出信号 ({len(today_signals['sell_signals'])}只)\n"
        for signal in today_signals['sell_signals']:
            profit_emoji = "💰" if signal['profit_pct'] >= 0 else "📉"
            markdown_content += f"- **{signal['name']}** ({signal['code']}) - ¥{signal['price']:.2f} {profit_emoji} {signal['profit_pct']:+.2f}%\n"
            markdown_content += f"  💡 卖出理由: {signal['reason']}\n\n"
    else:
        markdown_content += "### 🔴 卖出信号\n当前无卖出信号\n\n"
    
    # 添加持仓监控
    if current_positions:
        markdown_content += f"### 💼 持仓监控 ({len(current_positions)}只)\n"
        for pos in current_positions:
            profit_emoji = "📈" if pos['profit_pct'] >= 0 else "📉"
            markdown_content += f"- **{pos['name']}** ({pos['code']}) - ¥{pos['price']:.2f} {profit_emoji} {pos['profit_pct']:+.2f}%\n"
            markdown_content += f"  📊 持仓: {pos['quantity']}股 | 市值: ¥{pos['value']:,.0f}\n"
            if pos['stop_loss_price']:
                markdown_content += f"  🛡️ 止损价: ¥{pos['stop_loss_price']:.2f}\n"
            markdown_content += "\n"
    else:
        markdown_content += "### 💼 持仓监控\n当前无持仓\n\n"
    
    # 添加市场分析
    market_analysis = get_market_analysis(context)
    if market_analysis:
        markdown_content += f"### 📈 市场分析\n"
        markdown_content += f"- **市场状态**: {market_analysis['market_status']}\n"
        markdown_content += f"- **选股难度**: {market_analysis['selection_difficulty']}\n"
        markdown_content += f"- **风险等级**: {market_analysis['risk_level']}\n"
        if market_analysis['tips']:
            markdown_content += f"- **操作建议**: {market_analysis['tips']}\n"
        markdown_content += "\n"
    
    markdown_content += """
## ⚠️ 风险提示
> 本信号仅供参考，不构成投资建议
> 
> 投资有风险，入市需谨慎
> 
> 请根据自身风险承受能力谨慎决策
"""
    
    return markdown_content

def send_daily_summary(context):
    """
    发送每日摘要通知
    """
    if not NOTIFICATION_AVAILABLE or not NOTIFICATION_CONFIG['enabled'] or not NOTIFICATION_CONFIG['daily_summary']:
        # 即使不发送通知，也要清理数据
        cleanup_daily_data(context)
        return
    
    # 计算总收益率
    total_return = (context.portfolio.total_value / context.portfolio.starting_cash - 1) * 100
    
    # 构建持仓信息
    positions = []
    for stock, position in context.portfolio.positions.items():
        if position.total_amount > 0:
            try:
                stock_info = get_security_info(stock)
                current_price = position.price
                profit_pct = (current_price / position.avg_cost - 1) * 100 if position.avg_cost != 0 else 0
                
                positions.append({
                    'name': stock_info.display_name,
                    'code': stock,
                    'quantity': position.total_amount,
                    'price': current_price,
                    'avg_cost': position.avg_cost,
                    'profit_pct': profit_pct,
                    'value': position.value
                })
            except Exception as e:
                log.warning(f"获取持仓信息失败 {stock}: {e}")
    
    # 构建Markdown格式的摘要内容
    markdown_content = f"""# 中小板弱转强策略 - 每日摘要

## 📅 日期
{context.current_dt.strftime('%Y年%m月%d日')}

## 📊 账户总览
- **总资产**: ¥{context.portfolio.total_value:,.0f}
- **总收益率**: {total_return:+.2f}%
- **持仓数量**: {len(positions)}只股票

## 📈 选股情况
"""
    
    # 添加选股信息
    if g.daily_trading_summary['selected_stocks']:
        markdown_content += f"今日筛选出 {len(g.daily_trading_summary['selected_stocks'])} 只候选股票\n\n"
    else:
        markdown_content += "今日无符合条件的候选股票\n\n"
    
    # 添加交易记录
    if g.daily_trading_summary['trades']:
        markdown_content += "## 🔄 今日交易\n"
        for trade in g.daily_trading_summary['trades']:
            action_emoji = "🟢" if trade['action'] == '买入' else "🔴"
            if trade['action'] == '买入':
                markdown_content += f"- {action_emoji} **{trade['action']}**: {trade['stock_name']} ({trade['stock']}) - ¥{trade['price']:.2f}\n"
            else:
                profit_emoji = "💰" if trade['profit_pct'] >= 0 else "📉"
                markdown_content += f"- {action_emoji} **{trade['action']}**: {trade['stock_name']} ({trade['stock']}) - ¥{trade['current_price']:.2f} {profit_emoji} {trade['profit_pct']:+.2f}%\n"
        markdown_content += "\n"
    
    # 添加持仓详情
    if positions:
        markdown_content += "## 💼 持仓明细\n"
        markdown_content += "| 股票名称 | 代码 | 持仓数量 | 成本价 | 现价 | 盈亏 | 市值 |\n"
        markdown_content += "|----------|------|----------|--------|------|------|------|\n"
        
        for pos in positions:
            profit_emoji = "📈" if pos['profit_pct'] >= 0 else "📉"
            markdown_content += f"| {pos['name']} | {pos['code']} | {pos['quantity']} | ¥{pos['avg_cost']:.2f} | ¥{pos['price']:.2f} | {profit_emoji} {pos['profit_pct']:+.2f}% | ¥{pos['value']:,.0f} |\n"
    else:
        markdown_content += "## 💼 持仓明细\n当前无持仓\n"
    
    markdown_content += """
## ⚠️ 风险提示
> 本策略为量化投资策略，存在市场风险
> 
> 过往表现不代表未来收益
> 
> 投资有风险，入市需谨慎
"""
    
    # 发送通知
    send_message(markdown_content)  # 聚宽内置通知
    
    # 发送统一格式通知
    send_unified_notification(
        content=markdown_content,
        subject="中小板弱转强策略 - 每日摘要",
        title="每日摘要通知",
        format_type=NOTIFICATION_CONFIG['notification_format'],
        context=context
    )
    
    log.info("每日摘要通知发送完成")
    
    # 通知发送完成后清理数据
    cleanup_daily_data(context)

# ========= 实时交易信号生成函数 =========

def get_current_positions_info(context):
    """
    获取当前持仓信息
    """
    positions = []
    current_data = get_current_data()
    
    for stock, position in context.portfolio.positions.items():
        if position.total_amount > 0:
            try:
                stock_info = get_security_info(stock)
                current_price = position.price
                profit_pct = (current_price / position.avg_cost - 1) * 100 if position.avg_cost != 0 else 0
                
                # 计算止损价（基于MA7）
                stop_loss_price = calculate_stop_loss_price(stock, context)
                
                positions.append({
                    'name': stock_info.display_name,
                    'code': stock,
                    'quantity': position.total_amount,
                    'price': current_price,
                    'avg_cost': position.avg_cost,
                    'profit_pct': profit_pct,
                    'value': position.value,
                    'stop_loss_price': stop_loss_price
                })
            except Exception as e:
                log.warning(f"获取持仓信息失败 {stock}: {e}")
    
    return positions

def get_today_trading_signals(context):
    """
    获取今日交易信号
    """
    signals = {
        'buy_signals': [],
        'sell_signals': []
    }
    
    # 获取买入信号（今日选股结果）
    if hasattr(g, 'today_list') and g.today_list:
        current_data = get_current_data()
        for i, stock in enumerate(g.today_list[:5]):  # 只取前5只
            try:
                stock_info = get_security_info(stock)
                current_price = current_data[stock].last_price
                
                # 计算当日涨跌幅
                if hasattr(current_data[stock], 'day_open') and current_data[stock].day_open and current_data[stock].day_open != 0:
                    change_pct = (current_price / current_data[stock].day_open - 1) * 100
                else:
                    change_pct = 0
                
                # 获取技术指标信息
                technical_info = get_technical_indicators_info(stock, context)
                
                signals['buy_signals'].append({
                    'name': stock_info.display_name,
                    'code': stock,
                    'price': current_price,
                    'change_pct': change_pct,
                    'reason': f"弱转强模式，排名第{i+1}位",
                    'technical_info': technical_info
                })
            except Exception as e:
                log.warning(f"获取买入信号失败 {stock}: {e}")
    
    # 获取卖出信号（基于当前持仓的卖出条件）
    current_positions = get_current_positions_info(context)
    for pos in current_positions:
        sell_reason = check_sell_conditions(pos['code'], context)
        if sell_reason:
            signals['sell_signals'].append({
                'name': pos['name'],
                'code': pos['code'],
                'price': pos['price'],
                'profit_pct': pos['profit_pct'],
                'reason': sell_reason
            })
    
    return signals

def get_technical_indicators_info(stock, context):
    """
    获取技术指标信息
    """
    try:
        # 获取MA10
        hist_data = get_price(
            stock,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close'],
            count=g.ma_period,
            panel=False
        )
        
        if len(hist_data) >= g.ma_period:
            ma10 = hist_data['close'].mean()
            current_price = get_current_data()[stock].last_price
            
            # 判断价格与均线关系
            if current_price > ma10:
                ma_status = f"价格在MA{g.ma_period}之上"
            else:
                ma_status = f"价格在MA{g.ma_period}之下"
            
            return f"MA{g.ma_period}: ¥{ma10:.2f}, {ma_status}"
        else:
            return "技术指标数据不足"
    except Exception as e:
        return f"技术指标获取失败: {e}"

def calculate_stop_loss_price(stock, context):
    """
    计算止损价（基于MA7）
    """
    try:
        hist_data = get_price(
            stock,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close'],
            count=g.stop_loss_ma_period,
            panel=False
        )
        
        if len(hist_data) >= g.stop_loss_ma_period:
            ma7 = hist_data['close'].mean()
            return ma7
        else:
            return None
    except Exception as e:
        log.warning(f"计算止损价失败 {stock}: {e}")
        return None

def check_sell_conditions(stock, context):
    """
    检查卖出条件
    """
    try:
        current_data = get_current_data()
        position = context.portfolio.positions[stock]
        
        # 检查是否跌停
        if current_data[stock].last_price <= current_data[stock].low_limit:
            return "跌停板，建议止损"
        
        # 检查是否涨停
        if current_data[stock].last_price >= current_data[stock].high_limit:
            return "涨停板，可考虑获利了结"
        
        # 检查止损条件
        stop_loss_price = calculate_stop_loss_price(stock, context)
        if stop_loss_price and current_data[stock].last_price < stop_loss_price:
            return f"跌破止损线(MA{g.stop_loss_ma_period})"
        
        # 检查盈利情况
        profit_pct = (position.price / position.avg_cost - 1) * 100 if position.avg_cost != 0 else 0
        if profit_pct > 10:  # 盈利超过10%
            return f"盈利{profit_pct:.1f}%，可考虑获利了结"
        
        return None
    except Exception as e:
        log.warning(f"检查卖出条件失败 {stock}: {e}")
        return None

def get_market_analysis(context):
    """
    获取市场分析
    """
    try:
        # 获取市场指数数据
        index_data = get_price('000001.XSHG', count=5, frequency='daily', fields=['close'])
        if len(index_data) < 2:
            return None
        
        # 计算市场趋势
        recent_change = (index_data['close'].iloc[-1] - index_data['close'].iloc[-2]) / index_data['close'].iloc[-2] * 100
        
        # 判断市场状态
        if recent_change > 2:
            market_status = "强势上涨"
            risk_level = "中等"
            tips = "市场强势，可适当增加仓位"
        elif recent_change > 0:
            market_status = "温和上涨"
            risk_level = "低"
            tips = "市场稳定，适合正常操作"
        elif recent_change > -2:
            market_status = "震荡整理"
            risk_level = "中等"
            tips = "市场震荡，建议谨慎操作"
        else:
            market_status = "下跌调整"
            risk_level = "高"
            tips = "市场下跌，建议减仓观望"
        
        # 判断选股难度
        if hasattr(g, 'today_list'):
            candidate_count = len(g.today_list)
            if candidate_count > 10:
                selection_difficulty = "容易"
            elif candidate_count > 5:
                selection_difficulty = "中等"
            else:
                selection_difficulty = "困难"
        else:
            selection_difficulty = "未知"
        
        return {
            'market_status': market_status,
            'selection_difficulty': selection_difficulty,
            'risk_level': risk_level,
            'tips': tips
        }
    except Exception as e:
        log.warning(f"获取市场分析失败: {e}")
        return None
