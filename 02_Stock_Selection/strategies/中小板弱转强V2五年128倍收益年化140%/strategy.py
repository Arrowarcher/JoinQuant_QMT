# 克隆自聚宽文章：https://www.joinquant.com/post/61535
# 标题：中小板弱转强V2五年128倍收益年化140%
# 作者：空空儿

import pandas as pd
import numpy as np
import datetime as dt
from datetime import datetime
from datetime import timedelta
from jqlib.technical_analysis import *
from jqdata import *

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

    run_daily(perpare,time="09:26")      # 筛选时间
    run_daily(buy,time="09:27")          # 买入时间
    run_daily(sell,time='13:00')         # 盘中卖出时间
    run_daily(sell,time='14:55')         # 尾盘卖出时间
    run_daily(check_dieting, time="every_bar") # 监控跌停板
    run_daily(print_date_separator, time="15:05") # 收盘后打印日期分隔线

    # 过滤系统订单日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    
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
            # 执行卖出
            order_target_value(s, 0)
            log.info(f'卖出 {stock_name}({s}) | 成本价:{avg_cost:.2f} 现价:{current_price:.2f}')

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
            order_value(stock, cash_per_stock)  # 按金额买入[6](@ref)
            log.info (f"买入 {stock_name}({stock})")
            # 记录买入日期
            g.buy_dates[stock] = context.current_dt.date()
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
            to_remove.append(stock)
    
    # 从监控列表中移除已卖出的股票
    for stock in to_remove:
        if stock in g.dieting_stocks:
            g.dieting_stocks.remove(stock)

# 收盘后打印日期分隔线
def print_date_separator(context):
    log.info("=" * 60)
