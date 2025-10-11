# 克隆自聚宽文章：https://www.joinquant.com/post/61859
# 标题：三马V6.3 测试框架
# 作者：Cibo

"""
Cibo 三驾马车优化版
策略1：小市值策略
策略2：ETF反弹策略 (临时使用, 未找到合适的白马替换)
策略3：ETF轮动策略
实盘相关的指引:
https://www.joinquant.com/view/community/detail/4c8dda11f3ebda5ce562c2d3375a1740?type=1

v1.0 原始策略
v2.0 优化小市值新增行业分散, 优化基础白马为市场温度攻防白马, 优化ETF动量轮动新增降幅 5% 三日检测
v2.1 优化新增换手放量检测, 优化每日持仓打印, 优化卖出后的盈亏打印, 新增子策略收益独立展示
v2.2 优化新增 MCAD 大盘择时, 新增实盘启用配置
v3.0 优化小市值策略双市值筛选
v4.0 去除白马, 加入测试中证2000ETF下跌反弹策略
v4.1 修复止损无法卖出的bug
v5.0 小市值调整为群友迷妹的优化版本(类国九), 于v4.1相比, 长周期收益中幅降低回撤大幅降低, 短周期收益小幅降低, 回撤小幅增大
v5.1 新增成交额宽度防御检测, 对比v5.0长回测减少收益(70->63)和回撤(19->14), 降低风险
v6.0 策略2中证2000ETF策略拓展, 持仓时间调整(2->5), 增加后备选项到5个
v6.1 成交额检测新增缓存避免回测太久问题, hardcode 写死 18.1.1-25.9.25触发时间
v6.2 新增移动止损功能, 以持仓周期中最高点收益作为成本价, (不适用小市值, 更适合大波段趋势)
v6.3 交易时检查是否停牌, 停牌则不进行交易, 保持日志清洁
v7.0rc 测试小市值新增营收增长率+审计筛选
"""
import math
import prettytable
import numpy as np
import pandas as pd
from jqdata import *
from jqfactor import *
from prettytable import PrettyTable

# from nredistrade import *  # 导入实盘依赖

""" ====================== 基础配置 ====================== """


# 回测设置
def set_backtest():
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.001), type="fund")
    set_slippage(FixedSlippage(0.002), type="stock")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=3 / 10000,
        close_commission=3 / 10000,
        close_today_commission=0,
        min_commission=5,
    ), type="stock")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=3 / 10000,
        close_commission=3 / 10000,
        close_today_commission=0,
        min_commission=5
    ), type='fund')


# 参数设置
def set_params(context):
    # 策略名
    g.portfolio_value_proportion = [0.4, 0.2, 0.4]  # 小市值/ETF反弹/ETF轮动
    # g.portfolio_value_proportion = [0.5, 0, 0.5]  # 舍弃ETF反弹
    # g.portfolio_value_proportion = [0.35, 0.3, 0.35]  # 小市值/ETF反弹/ETF轮动
    # g.portfolio_value_proportion = [1, 0, 0]  # 测试小市值
    # g.portfolio_value_proportion = [0, 1, 0]  # 测试ETF反弹
    # g.portfolio_value_proportion = [0, 0, 1]  # 测试ETF轮动

    g.starting_cash = 500000  # 策略初始资金
    g.stock_strategy = {}  # 记录股票对应的策略, 反向映射方便检索
    g.strategy_holdings = {1: [], 2: [], 3: []}
    # 记录策略初始的金额, 用于计算各策略收益
    g.strategy_starting_cash = {
        1: g.starting_cash * g.portfolio_value_proportion[0],  # 小市值 初始资金
        2: g.starting_cash * g.portfolio_value_proportion[1],  # ETF反弹 初始资金
        3: g.starting_cash * g.portfolio_value_proportion[2],  # ETF轮动 初始资金
    }
    # 记录每日策略收益
    g.strategy_value_data = {}
    g.strategy_value = {
        1: g.starting_cash * g.portfolio_value_proportion[0],  # 小市值 初始资金
        2: g.starting_cash * g.portfolio_value_proportion[1],  # ETF反弹 初始资金
        3: g.starting_cash * g.portfolio_value_proportion[2],  # ETF轮动 初始资金
    }

    # 顶背离检查
    g.DBL_control = True  # 大盘顶背离记录（用于风险控制）
    g.dbl = []

    # 换手检测
    g.HV_control = True  # 放量换手检测，Ture是日频判断是否放量，False则不然

    # 止损检查
    g.run_stoploss = True  # 是否进行止损
    g.use_move_stoploss = False  # 是否使用移动止损, 不太适用, 先做保留
    g.stoploss_limit = 0.12  # 止损线
    g.stop_loss_tracking = {}  # 移动止损跟踪字典, 记录持仓最高收益价格

    # 异常处理窗口期检查
    g.check_after_no_buy = False  # 检查后不再买入时间
    g.no_buy_stocks = {}  # 检查卖出的股票
    g.no_buy_after_day = 5  # 止损后不买入的时间窗口

    # 成交额宽度检查
    g.check_defense = True  # 成交额宽度检查
    g.industries = ["组20"]  # 高位防御板块
    g.defense_signal = False
    g.cnt_defense_signal = []  # 择时次数
    g.cnt_bank_signal = []  # 组20择时次数
    g.history_defense_date_list = ['2018-01-10', '2018-01-11', '2018-01-12', '2018-01-15', '2018-01-16', '2018-01-17',
                                   '2018-01-18', '2018-01-19', '2018-01-22', '2018-01-23', '2018-01-24', '2018-01-25',
                                   '2018-01-26', '2018-01-29', '2018-01-30', '2018-01-31', '2018-02-01', '2018-02-02',
                                   '2018-02-05', '2018-02-06', '2018-02-07', '2018-02-08', '2018-02-09', '2018-02-12',
                                   '2019-04-22', '2019-04-23', '2019-04-24', '2019-04-25', '2019-04-26', '2019-04-29',
                                   '2019-04-30', '2019-05-06', '2019-05-07', '2019-07-29', '2019-07-30', '2019-07-31',
                                   '2019-08-01', '2019-08-02', '2019-09-25', '2019-09-26', '2019-09-27', '2019-09-30',
                                   '2019-10-08', '2019-10-25', '2019-10-28', '2019-10-29', '2019-10-30', '2019-10-31',
                                   '2019-11-01', '2019-11-04', '2019-11-05', '2019-11-06', '2019-11-07', '2019-11-08',
                                   '2019-11-11', '2019-11-12', '2019-11-13', '2019-11-14', '2019-11-15', '2019-11-18',
                                   '2019-11-19', '2019-11-20', '2019-11-21', '2019-11-22', '2019-11-25', '2019-11-26',
                                   '2019-11-27', '2019-11-28', '2019-11-29', '2019-12-02', '2019-12-03', '2019-12-04',
                                   '2019-12-05', '2020-01-21', '2020-01-22', '2020-01-23', '2020-02-03', '2020-02-04',
                                   '2020-02-05', '2020-02-06', '2020-02-07', '2020-02-10', '2020-02-11', '2020-02-12',
                                   '2020-02-13', '2020-02-14', '2020-02-17', '2020-02-18', '2020-02-19', '2020-02-20',
                                   '2020-02-21', '2020-06-12', '2020-06-15', '2020-06-16', '2020-06-17', '2020-06-18',
                                   '2020-06-24', '2020-06-29', '2020-06-30', '2020-07-01', '2020-07-02', '2020-07-03',
                                   '2020-07-06', '2020-07-07', '2020-10-15', '2020-10-16', '2020-10-19', '2020-10-20',
                                   '2020-10-21', '2020-10-22', '2020-10-23', '2020-10-29', '2020-10-30', '2020-11-02',
                                   '2020-11-03', '2020-11-04', '2020-11-05', '2020-11-06', '2020-11-09', '2020-11-10',
                                   '2020-11-11', '2020-11-12', '2020-11-13', '2020-11-16', '2020-11-17', '2020-12-04',
                                   '2020-12-07', '2020-12-08', '2020-12-09', '2020-12-10', '2020-12-11', '2020-12-14',
                                   '2020-12-15', '2020-12-16', '2020-12-17', '2020-12-18', '2020-12-21', '2020-12-22',
                                   '2020-12-23', '2020-12-24', '2020-12-25', '2020-12-28', '2020-12-29', '2020-12-30',
                                   '2020-12-31', '2021-01-04', '2021-01-05', '2021-01-06', '2021-01-07', '2021-01-08',
                                   '2021-01-11', '2021-01-12', '2021-01-13', '2021-01-14', '2021-01-15', '2021-01-18',
                                   '2021-01-19', '2021-01-20', '2021-01-21', '2021-01-22', '2021-01-25', '2021-01-26',
                                   '2021-01-27', '2021-01-28', '2021-01-29', '2021-02-02', '2021-02-03', '2021-02-04',
                                   '2021-02-05', '2021-02-08', '2021-02-09', '2021-02-10', '2021-02-18', '2021-02-19',
                                   '2021-06-28', '2021-06-29', '2021-06-30', '2021-07-01', '2021-07-02', '2021-07-05',
                                   '2021-07-06', '2021-07-07', '2021-07-08', '2021-07-09', '2021-07-12', '2021-07-13',
                                   '2021-07-14', '2021-07-15', '2021-07-16', '2021-07-19', '2021-07-20', '2021-07-21',
                                   '2021-07-22', '2021-07-23', '2021-07-26', '2021-07-27', '2021-07-28', '2021-07-29',
                                   '2021-07-30', '2021-08-02', '2021-08-03', '2021-08-04', '2021-08-05', '2021-08-06',
                                   '2021-08-09', '2021-08-10', '2021-09-15', '2021-09-16', '2021-09-17', '2021-09-22',
                                   '2021-09-23', '2021-09-24', '2021-09-27', '2021-09-28', '2021-09-29', '2021-09-30',
                                   '2021-10-20', '2021-10-21', '2021-10-22', '2021-10-25', '2021-10-26', '2021-10-27',
                                   '2021-10-28', '2021-10-29', '2021-11-01', '2021-11-02', '2021-11-03', '2021-12-08',
                                   '2021-12-09', '2021-12-10', '2021-12-13', '2021-12-14', '2021-12-15', '2022-07-06',
                                   '2022-07-07', '2022-07-08', '2022-07-11', '2022-07-12', '2022-07-13', '2022-07-14',
                                   '2022-07-15', '2022-07-18', '2022-09-15', '2022-09-16', '2022-09-19', '2022-09-20',
                                   '2022-09-21', '2022-09-22', '2022-09-23', '2022-09-26', '2022-09-27', '2022-09-28',
                                   '2022-09-29', '2022-09-30', '2022-10-10', '2022-10-11', '2022-10-12', '2022-10-13',
                                   '2022-12-14', '2022-12-15', '2022-12-16', '2022-12-19', '2022-12-20', '2022-12-21',
                                   '2022-12-22', '2022-12-23', '2022-12-26', '2022-12-27', '2022-12-28', '2022-12-29',
                                   '2022-12-30', '2023-01-03', '2023-01-04', '2023-01-10', '2023-01-11', '2023-01-12',
                                   '2023-01-13', '2023-01-16', '2023-01-17', '2023-03-03', '2023-03-06', '2023-03-07',
                                   '2023-03-08', '2023-03-09', '2023-03-10', '2023-03-13', '2023-03-14', '2023-03-15',
                                   '2023-03-16', '2023-03-17', '2023-03-20', '2023-03-21', '2023-03-22', '2023-03-23',
                                   '2023-03-24', '2023-03-27', '2023-03-28', '2023-03-29', '2023-03-30', '2023-03-31',
                                   '2023-04-03', '2023-04-04', '2023-04-06', '2023-04-07', '2023-04-10', '2023-04-11',
                                   '2023-04-12', '2023-04-13', '2023-04-14', '2023-04-17', '2023-04-18', '2023-04-19',
                                   '2023-04-20', '2023-04-21', '2023-04-24', '2023-04-25', '2023-04-26', '2023-04-27',
                                   '2023-04-28', '2023-05-04', '2023-05-05', '2023-06-20', '2023-06-21', '2023-06-26',
                                   '2023-06-27', '2023-08-07', '2023-08-08', '2023-08-09', '2023-08-10', '2023-08-11',
                                   '2023-08-14', '2023-08-15', '2023-08-16', '2023-08-17', '2023-08-18', '2023-12-11',
                                   '2023-12-12', '2023-12-13', '2023-12-14', '2023-12-15', '2023-12-18', '2023-12-19',
                                   '2023-12-20', '2023-12-21', '2023-12-22', '2023-12-25', '2023-12-26', '2023-12-27',
                                   '2023-12-28', '2023-12-29', '2024-05-23', '2024-05-24', '2024-05-27', '2024-05-28',
                                   '2024-05-29', '2024-05-30', '2024-05-31', '2024-06-03', '2024-06-04', '2024-06-05',
                                   '2024-06-06', '2024-06-07', '2024-06-11', '2024-06-12', '2024-06-13', '2024-06-14',
                                   '2024-06-17', '2024-06-18', '2024-06-19', '2024-06-20', '2024-06-21', '2024-06-24',
                                   '2024-06-25', '2024-06-26', '2024-06-27', '2024-06-28', '2024-07-01', '2024-07-02',
                                   '2024-07-03', '2024-07-04', '2024-07-05', '2024-07-08', '2024-07-09', '2024-07-10',
                                   '2024-07-11', '2024-07-12', '2024-07-15', '2024-07-16', '2024-07-17', '2024-07-18',
                                   '2024-07-19', '2024-07-22', '2024-07-23', '2024-07-24', '2024-07-25', '2024-07-26',
                                   '2024-07-29', '2024-12-19', '2024-12-20', '2024-12-23', '2024-12-24', '2024-12-25',
                                   '2024-12-26', '2024-12-27', '2024-12-30', '2024-12-31', '2025-01-02', '2025-01-03',
                                   '2025-01-06', '2025-01-07', '2025-01-08', '2025-01-09', '2025-01-10', '2025-01-13',
                                   '2025-01-14', '2025-01-15', '2025-01-16', '2025-01-17', '2025-01-20', '2025-01-21',
                                   '2025-01-22', '2025-01-23', '2025-01-24', '2025-06-16', '2025-06-17', '2025-06-18',
                                   '2025-06-19', '2025-06-20', '2025-06-23', '2025-06-24', '2025-06-25', '2025-06-26',
                                   '2025-06-27', '2025-06-30', '2025-07-01', '2025-08-01', '2025-08-04', '2025-08-29',
                                   '2025-09-01', '2025-09-02', '2025-09-03', '2025-09-04', '2025-09-05', '2025-09-08',
                                   '2025-09-09', '2025-09-10', '2025-09-11', '2025-09-12', '2025-09-15', '2025-09-16',
                                   '2025-09-17', '2025-09-18', '2025-09-19', '2025-09-22', '2025-09-23', '2025-09-24',
                                   '2025-09-25']

    # 策略1小市值策略变量
    g.up_price = 20  # 个股价格上限
    g.xsz_stock_num = 5  # 持股数量
    g.yesterday_HL_list = []  # 昨日涨停股票
    g.target_list = []  # 目标持仓股票
    g.min_mv = 5  # 最小市值(亿)
    g.max_mv = 50  # 最大市值(亿)

    # 策略2小市值策略变量
    g.limit_days = 2  # 最少持仓周期
    g.n_days = 5  # 持仓周期
    g.holding_days = 0
    g.buy_list = []
    g.etf_pool_2 = [
        '159536.XSHE',  # 中证2000
        '159629.XSHE',  # 中证1000
        '159922.XSHE',  # 中证500
        '159919.XSHE',  # 沪深300
        '159783.XSHE'  # 双创50
    ]  # etf池子，优先级从高到低

    # 策略3全局变量
    g.etf_pool_3 = [
        '518880.XSHG',  # 黄金ETF
        '513520.XSHG',  # 日经ETF
        '513100.XSHG',  # 纳指100
        '513020.XSHG',  # 港股科技

        '510180.XSHG',  # 上证180
        '511090.XSHG',  # 30年国债ETF
        '588120.XSHG',  # 科创板
        '159915.XSHE',  # 创业板

        '501018.XSHG',  # 南方原油
        '159980.XSHE',  # 有色ETF
    ]
    g.m_days = 25  # 动量参考天数
    g.m_score = 5  # 动量过滤分数
    g.stock_sum = 1  # 持有ETF数量


def initialize(context):
    set_backtest()  # 设置回测条件
    set_params(context)  # 设置参数
    # setup_redis_trade(context, 'strategy1')  # 设置实盘

    # 过滤日志
    log.set_level('order', 'error')
    # log.set_level('system', 'error')
    # log.set_level('strategy', 'error')

    # 每日开盘前检测大盘顶背离, 只针对策略1
    if g.DBL_control and g.portfolio_value_proportion[0]:
        run_daily(check_dbl, '9:31')  # 不要早于9点30, 否则会导致绘制的收益曲线无法拿到价格信息

    # 策略1 小市值策略
    if g.portfolio_value_proportion[0] > 0:
        run_weekly(xsz_adjustment, 1, '09:50')

    # 策略2 ETF反弹策略
    if g.portfolio_value_proportion[1] > 0:
        run_daily(strategy_2_sell, '14:49')
        run_daily(strategy_2_buy, '14:50')

    # 策略2 ETF轮动策略
    if g.portfolio_value_proportion[2] > 0:  # ETF轮动策略
        run_daily(trade, '10:00')

    # 换手检查
    if g.HV_control:
        run_daily(huanshou, '10:30')

    # 止损检查
    # run_daily(sell_stocks, '10:35')

    # 涨停板检查
    run_daily(check_limit_up, '14:00')

    # 成交额宽度检测, 只针对策略1
    if g.check_defense and g.portfolio_value_proportion[0]:
        run_daily(check_defense_trigger, '14:50')

    run_daily(make_record, '15:01')  # 记录各策略每日收益
    run_daily(print_summary, '15:02')  # 打印每日收益


""" ====================== 策略1: 小市值策略 ====================== """


# 选股模块(cibo基础版本, 双市值+行业分散)
def _xsz_get_stock_list(context):
    # 获取股票所属行业
    def filter_industry_stock(stock_list):
        result = get_industry(security=stock_list)
        selected_stocks = []
        industry_list = []
        for stock_code, info in result.items():
            industry_name = info['sw_l2']['industry_name']
            if industry_name not in industry_list:
                industry_list.append(industry_name)
                selected_stocks.append(stock_code)
                print(f"行业信息: {industry_name} (股票: {stock_code} {get_security_info(stock_code).display_name})")
                # 选取了 10 个不同行业的股票
                if len(industry_list) == 10:
                    break
        return selected_stocks

    initial_list = filter_stocks(context, get_index_stocks('399101.XSHE'))

    # 获取流通市值最小的50个股票
    q = query(valuation.code).filter(valuation.code.in_(initial_list)).order_by(
        valuation.circulating_market_cap.asc()).limit(50)
    initial_list = list(get_fundamentals(q).code)
    # 选取每股收益>0的股票
    # q = query(valuation.code, indicator.eps) \
    #     .filter(valuation.code.in_(initial_list)) \
    #     .filter(indicator.eps > 0) \
    #     .filter(valuation.market_cap > g.min_mv) \
    #     .filter(valuation.market_cap < g.max_mv) \
    #     .order_by(valuation.market_cap.asc())

    q = query(valuation.code).filter(valuation.code.in_(initial_list)).order_by(valuation.market_cap.asc())
    initial_list = list(get_fundamentals(q).code)
    initial_list = initial_list[:30]
    # 每个行业获取1个股票，总共获取g.stock_num个行业的股票
    final_list = filter_industry_stock(initial_list)[:g.xsz_stock_num]
    print('选出的股票:%s' % [f"{i} {get_security_info(i).display_name}" for i in final_list])
    return final_list


# 选股模块
def xsz_get_stock_list(context):
    """选股模块"""
    initial_list = filter_stocks(context, get_index_stocks('399101.XSHE'))

    # 修复：正确使用聚宽基本面表查询方式
    q = query(
        valuation.code,
        valuation.market_cap,
        income.np_parent_company_owners,
        income.net_profit,
        income.operating_revenue,
        valuation.turnover_ratio
    ).filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(g.min_mv, g.max_mv),
        income.np_parent_company_owners > 0,
        income.net_profit > 0,
        income.operating_revenue > 1e8,
        fundamentals.indicator.roe > 0.15,
        fundamentals.indicator.roa > 0.10,
        # indicator.inc_revenue_year_on_year > 0.20,  # v7 新增营收增长率, 屏蔽则为 v6
    ).order_by(valuation.market_cap.asc()).limit(50)
    df = get_fundamentals(q)
    if df.empty:
        return []
    final_list = list(df.code)
    # final_list = filter_audit_opinion(context, final_list)  # v7 新增过滤审计, 屏蔽则为 v6
    last_prices = history(1, '1d', 'close', final_list, df=False)
    # 价格过滤
    return [stock for stock in final_list if stock in context.portfolio.positions or last_prices[stock] <= g.up_price][
           :g.xsz_stock_num]


# 调整持仓
def xsz_adjustment(context):
    # 近期有顶背离信号时暂停调仓（规避系统性风险）
    if g.DBL_control and True in g.dbl[-10:]:
        print("近10日检测到大盘顶背离，暂停调仓以控制风险")
        return

    if g.check_defense and g.defense_signal:
        print("成交额宽度检查异常，暂停调仓以控制风险")
        return

    # 择时信号
    trading_signal = True  # 可交易信号
    month = context.current_dt.month
    # day = context.current_dt.day
    if month in [1, 4]:
        trading_signal = False
    # elif month in [3, 12] and day >= 16:
    #     trading_signal = False
    current_data = get_current_data()
    if not trading_signal:
        # 关键修复：只清空本策略持仓
        for stock in g.strategy_holdings[1][:]:
            if current_data[stock].paused:
                print(f"{stock} 停牌, 无法卖出")
            else:
                close_position(context, stock)
        print('小市值策略：空仓月份，已清仓')
        return

    g.target_list = xsz_get_stock_list(context)[:g.xsz_stock_num]
    print(f'小市值目标持仓: {g.target_list}')

    # 获取当前持仓
    current_holdings = g.strategy_holdings[1][:]

    # 卖出不在目标列表中的股票（除昨日涨停股）
    sell_list = [s for s in current_holdings if s not in g.target_list and s not in g.yesterday_HL_list]

    for stock in sell_list:
        if current_data[stock].paused:
            print(f"{stock} 停牌, 无法卖出")
        else:
            close_position(context, stock)
            print(f"小市值策略卖出: {stock}")

    # 计算可用资金（策略1专用部分）
    strategy_value = context.portfolio.total_value * g.portfolio_value_proportion[0]
    current_value = sum(
        [pos.value for pos in context.portfolio.positions.values() if pos.security in g.strategy_holdings[1]])
    available_cash = max(0, strategy_value - current_value)  # 确保非负

    # 买入新标的
    buy_list = [s for s in g.target_list if s not in current_holdings]
    if buy_list and available_cash > 0:
        cash_per_stock = available_cash / len(buy_list)
        for stock in buy_list:
            if open_position(context, stock, cash_per_stock, 1):
                print(f"小市值策略买入: {stock}, 金额: {cash_per_stock:.2f}")


""" ====================== 策略2: ETF反弹策略 ====================== """


# 原始中证2000策略
def zz_2000_trade(context):
    to_buy = False
    etf_index = "159536.XSHE"
    # 获取近3日的历史数据
    df = get_price(etf_index, end_date=context.previous_date, count=3, frequency='daily', fields=['high'])
    df = df.reset_index()
    if len(df) < 3:
        return

    pre3_high_max = df['high'].max()

    # 获取当前盘中实时数据
    current_data = get_current_data()
    today_open = current_data[etf_index].day_open
    today_close = current_data[etf_index].last_price

    # 策略条件判断，开盘相比最高价下跌2% & 最新价相比开盘价涨1%
    if today_open / pre3_high_max < 0.98 and today_close / today_open > 1.01:
        to_buy = True

    # 已经持仓, 检查是否继续持有
    if etf_index in context.portfolio.positions:
        position = context.portfolio.positions[etf_index]
        trade_date = position.init_time
        holding_days = len(get_trade_days(start_date=trade_date, end_date=context.current_dt)) - 1
        # 不符合却持仓超过2天, 清仓
        if not to_buy and holding_days >= 2:
            close_position(context, etf_index)
            print(f"卖出：{etf_index}, 持仓{holding_days}天")
    # 未持仓, 但符合条件, 进行买入
    elif to_buy:
        strategy_value = context.portfolio.total_value * g.portfolio_value_proportion[1]
        open_position(context, etf_index, strategy_value, 2)
        print(f"符合中证2000买入条件：{etf_index}")


def strategy_2_sell(context):
    g.buy_list = []
    sell_list = []
    sell_for_money_list = []
    # 获取近3日的历史数据
    for etf in g.etf_pool_2:
        df = get_price(etf, end_date=context.previous_date, count=4, frequency='daily', fields=['high', 'close'])
        df = df.reset_index()
        if len(df) < 4:
            return
        pre_high_max = df['high'].max()
        yestoday_close = df['close'].iloc[-1]
        # 获取当前盘中实时数据
        current_data = get_current_data()
        today_open = current_data[etf].day_open
        today_close = current_data[etf].last_price
        # 买入条件判断，开盘相比最高价下跌2% & 最新价相比开盘价涨1%
        if today_open / pre_high_max < 0.98 and today_close / today_open > 1.01:
            g.buy_list.append(etf)
        # 卖出条件判断，当前价格小于昨日收盘价
        if today_close < yestoday_close:
            sell_list.append(etf)

    # 保留最佳标的
    if g.buy_list:
        g.buy_list.sort(key=lambda x: g.etf_pool_2.index(x))
        selected_etf = g.buy_list[0]
        g.buy_list = [selected_etf]
        log.info(f"选出：{g.buy_list}")
        current_holdings = g.strategy_holdings[2]
        if current_holdings and g.etf_pool_2.index(current_holdings[0]) < g.etf_pool_2.index(selected_etf):
            # 如果有持仓，且持有的ETF不是高优先级ETF，则清仓
            sell_for_money_list.append(current_holdings[0])

    for etf in g.strategy_holdings[2]:
        position = context.portfolio.positions[etf]
        securities = position.security  # 股票代码
        trade_date = position.init_time
        holding_days = len(get_trade_days(start_date=trade_date, end_date=context.current_dt)) - 1
        if (securities in sell_list and holding_days >= g.limit_days) or (holding_days >= g.n_days) or \
                (securities in sell_for_money_list):
            close_position(context, securities)
            log.info(f"卖出：{securities}，持股{securities} {holding_days}天")
    if g.buy_list:
        print(f"存在反弹可购买选项: {g.buy_list}")
    else:
        print(f"策略2今日无反弹可购买选项")


def strategy_2_buy(context):
    g.buy_list = list(set(g.buy_list) - set(g.strategy_holdings[2]))
    if len(g.buy_list) > 0:
        cash = context.portfolio.total_value * g.portfolio_value_proportion[1]
        if cash < 100:
            log.warn(f'cash不足:{context.portfolio.available_cash}')
        else:
            cash = context.portfolio.total_value * g.portfolio_value_proportion[1]
            for etf in g.buy_list:
                print(f"符合策略2买入条件：{etf}")
                open_position(context, etf, cash, 2)


""" ====================== 策略3: ETF轮动策略 ====================== """


def get_etf_rank(etf_pool):
    data = pd.DataFrame(index=etf_pool, columns=["annualized_returns", "r2", "score"])
    current_data = get_current_data()
    print_data = {}
    for etf in etf_pool:
        # 获取数据
        df = attribute_history(etf, g.m_days, "1d", ["close", "high"])
        prices = np.append(df["close"].values, current_data[etf].last_price)

        # 设置参数
        y = np.log(prices)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))

        # 计算年化收益率
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1

        # 计算R2
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0

        # 计算得分
        score = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]
        data.loc[etf, "score"] = score

        pass_flag = 0
        # 过滤近3日跌幅超过5%的ETF
        if min(prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4]) < 0.95:
            data.loc[etf, "score"] = 0
            pass_flag = 1
        print_data[get_stock_name(etf)] = score
        # print(f"{etf} {get_stock_name(etf)} 得分: {score}   跌幅检测: {pass_flag}")

    # 过滤ETF，并按得分降序排列
    data = data.query(f"0 < score < {g.m_score}").sort_values(by="score", ascending=False)
    _ = [f"{i} {get_stock_name(i)} ({print_data[get_stock_name(i)]})" for i in data.index.tolist()[:4]]
    print(f"ETF动量评分排名: {' > '.join(_)}")
    return data.index.tolist()[:1]


# ETF交易
def trade(context):
    # 获取动量最高的ETF
    rank_df = get_etf_rank(g.etf_pool_3)
    if rank_df:
        select_etf = rank_df[0]
        current_etf = None

        # 检查当前持仓
        for asset in context.portfolio.positions:
            if asset in g.etf_pool_3:
                current_etf = asset
                break

        # 策略3专用资金
        strategy_cash = context.portfolio.total_value * g.portfolio_value_proportion[2]

        # 需要调仓的情况
        if current_etf and current_etf != select_etf:
            close_position(context, current_etf)  # 卖掉当前的
            open_position(context, select_etf, strategy_cash, 3)  # 买入新的
            print(f"ETF调仓: {current_etf} -> {select_etf}")

        # 首次买入或恢复持仓
        elif not current_etf and strategy_cash > 0:
            open_position(context, select_etf, strategy_cash, 3)  # 买入新的
            print(f"ETF建仓: {select_etf}")


""" ====================== 辅助的定时执行函数 ====================== """


# 大盘顶背离
def check_dbl(context):
    """
        大盘顶背离检测：通过MACD判断市场潜在反转风险
        目的：在大盘出现顶背离（上涨乏力）时提前减仓，规避系统性下跌
    """
    market_index = '399101.XSHE'

    def detect_divergence():
        """检测顶背离（价格新高但MACD指标走弱，预示趋势反转）
        条件：
        1. 价格创新高（后高>前高）
        2. MACD指标未创新高（后低<前低）
        3. MACD由正转负（趋势转弱）
        4. DIF处于下降趋势（近期均值<前期均值）
        """
        fast, slow, sign = 12, 26, 9  # MACD参数
        rows = (fast + slow + sign) * 5  # 确保足够数据量（约1年）
        # 获取历史收盘价数据
        grid = attribute_history(market_index, rows, fields=['close']).dropna()

        if len(grid) < rows:
            print(f"{market_index} 数据不足 {rows} 天，无法检测顶背离")
            return False

        try:
            # 计算MACD指标
            grid['dif'], grid['dea'], grid['macd'] = MACD(grid.close, fast, slow, sign)

            # 寻找死叉点（MACD由正转负的时刻）
            mask = (grid['macd'] < 0) & (grid['macd'].shift(1) >= 0)
            if mask.sum() < 2:  # 需要至少2个死叉点对比
                print(f"{market_index} 死叉点不足2个，无法检测顶背离")
                return False

            # 取最近两个死叉点（前一个与当前）
            key2, key1 = mask[mask].index[-2], mask[mask].index[-1]

            # 顶背离核心条件
            price_cond = grid.close[key2] < grid.close[key1]  # 价格创新高（后高>前高）
            dif_cond = grid.dif[key2] > grid.dif[key1] > 0  # DIF未创新高（后低<前高）且为正
            macd_cond = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]  # MACD由正转负

            # 趋势验证：DIF近期处于下降趋势（近10日均值<前10日均值）
            if len(grid['dif']) > 20:
                recent_avg = grid['dif'].iloc[-10:].mean()  # 近10日DIF均值
                prev_avg = grid['dif'].iloc[-20:-10].mean()  # 前10日DIF均值
                trend_cond = recent_avg < prev_avg
            else:
                trend_cond = False

            # print(f"{market_index} 顶背离检测: 价格创新高={price_cond}, DIF未新高={dif_cond}, "
            #       f"MACD转负={macd_cond}, DIF下降趋势={trend_cond}")
            return price_cond and dif_cond and macd_cond and trend_cond

        except Exception as e:
            print(f"{market_index} 顶背离检测错误: {e}")
            return False

    if detect_divergence():
        g.dbl.append(True)
        print(f"⚠️⚠️⚠️⚠️ 检测到{market_index}顶背离信号（价格新高但MACD走弱），清仓非涨停股票")

        # 仅保留当前涨停股（可能延续强势），清仓其他股票
        current_data = get_current_data()

        # 仅对小市值进行处理
        for stock in g.strategy_holdings[1]:
            # 当前未涨停的股票清仓
            if current_data[stock].last_price < current_data[stock].high_limit:
                print(f"{stock} 因大盘顶背离清仓（非涨停股）")
                close_position(context, stock)
    else:
        g.dbl.append(False)
        # print("未检测到大盘顶背离，市场趋势正常")


# 尾盘记录各个策略的收益
def make_record(context):
    positions = context.portfolio.positions
    if not positions:
        return
    current_data = get_current_data()
    g.strategy_value_data = {1: 0, 2: 0, 3: 0}
    # 复制一个昨天的记录进行累计
    copy_strategy_value = {
        1: g.strategy_value[1],
        2: g.strategy_value[2],
        3: g.strategy_value[3],
    }
    for stock, pos in positions.items():
        strategy_id = g.stock_strategy[stock]
        current_value = pos.total_amount * current_data[stock].last_price  # 当前价值
        cost_value = pos.total_amount * pos.avg_cost  # 成本价值
        pnl_value = current_value - cost_value  # 当前盈亏金额
        copy_strategy_value[strategy_id] += pnl_value  # 计算浮盈浮亏
        g.strategy_value_data[strategy_id] += current_value

    if g.portfolio_value_proportion[0]:
        record(小市值=round(copy_strategy_value[1] / g.strategy_starting_cash[1] * 100 - 100, 2))
    if g.portfolio_value_proportion[1]:
        record(ETF反弹=round(copy_strategy_value[2] / g.strategy_starting_cash[2] * 100 - 100, 2))
    if g.portfolio_value_proportion[2]:
        record(ETF轮动=round(copy_strategy_value[3] / g.strategy_starting_cash[3] * 100 - 100, 2))


# 制表展示每日收益
def print_summary(context):
    """
    打印当前投资组合的总资产和持仓详情

    参数:
        context: 包含投资组合信息的对象。
        get_current_data: 获取当前市场数据的函数。
    """
    # 获取总资产
    total_value = round(context.portfolio.total_value, 2)

    # 获取当前持仓
    current_stocks = context.portfolio.positions
    if not current_stocks:
        # 如果没有持仓，只显示总资产
        print(f"当前总资产: {total_value}")
        return

    # 创建表格
    table = PrettyTable(
        ["所属策略", "股票代码", "股票名称", "持仓数量", "持仓价格", "当前价格", "盈亏数额", "盈亏比例", "市值"])
    table.hrules = prettytable.ALL  # 显示所有水平线

    # 设置对齐方式
    table.align["所属策略"] = "l"
    table.align["股票代码"] = "l"
    table.align["股票名称"] = "l"
    for field in ["持仓数量", "持仓价格", "当前价格", "盈亏数额", "盈亏比例", "市值"]:
        table.align[field] = "r"

    # 遍历持仓股票
    total_market_value = 0  # 总市值（用于累加每只股票的市值）
    for stock in current_stocks:
        current_shares = current_stocks[stock].total_amount  # 持仓数量
        current_price = round(get_current_data()[stock].last_price, 3)  # 当前价格
        avg_cost = round(current_stocks[stock].avg_cost, 3)  # 持仓平均成本

        # 计算盈亏比例
        profit_ratio = (current_price - avg_cost) / avg_cost if avg_cost != 0 else 0
        profit_ratio_percent = f"{profit_ratio * 100:.2f}%"  # 转为百分比并保留两位小数
        # profit_ratio_percent += f" {'📈' if profit_ratio > 0 else '📉'}
        # 计算盈亏数额
        profit_amount = round((current_price - avg_cost) * current_shares, 2)

        # 计算市值
        market_value = round(current_shares * current_price, 2)
        total_market_value += market_value  # 累加总市值

        # 处理股票代码：移除后缀
        stock_code = stock.split(".")[0]  # 只保留股票代码部分

        # 添加到表格
        table.add_row([
            g.stock_strategy[stock],
            stock_code,
            get_stock_name(stock),
            current_shares,
            avg_cost,
            current_price,
            profit_amount,
            profit_ratio_percent,
            market_value
        ])
    # 汇总
    if g.portfolio_value_proportion[0]:
        table.add_row(["小市值", "", "", "", "", "", "", "", f"{g.strategy_value_data[1]:.2f}"])
    # if g.portfolio_value_proportion[0]:
    #     table.add_row(["白马", "", "", "", "", "", "", "", f"{g.strategy_value_data[2]:.2f}"])
    # if g.portfolio_value_proportion[0]:
    #     table.add_row(["ETF", "", "", "", "", "", "", "", f"{g.strategy_value_data[3]:.2f}"])
    table.add_row(["总市值", "", "", "", "", "", "", "", f"{total_market_value:.2f}"])
    table.add_row(["总资产", "", "", "", "", "", "", "", f"{total_value:.2f}"])

    # 打印表格
    print(f'当前总资产\n{table}')


""" ====================== 公共策略函数 ====================== """


# 开仓买入并记录策略持仓
def open_position(context, security, value, strategy_id):
    order = my_order_target_value(context, security, value)
    if order:
        g.strategy_holdings[strategy_id].append(security)
        g.stock_strategy[security] = strategy_id
    return order


# 闭仓卖出并清空策略持仓
def close_position(context, security):
    order = my_order_target_value(context, security, 0)
    if order:
        strategy_id = g.stock_strategy[security]
        # 持仓列表移除
        security in g.strategy_holdings[strategy_id] and g.strategy_holdings[strategy_id].remove(security)
        # 计算卖出的盈亏
        pnl_value = (order.price - order.avg_cost) * order.amount
        # 每日策略总价值更新盈亏
        g.strategy_value[strategy_id] += pnl_value
    return order


# 止盈止损
def sell_stocks(context):
    if not g.run_stoploss:
        return

    # 更新已经止损的票止损日到目前的时间
    no_buy_stocks = {}
    for k, v in g.no_buy_stocks.items():
        v += 1
        if v <= g.no_buy_after_day:
            no_buy_stocks[k] = v
    g.no_buy_stocks = no_buy_stocks

    # 计算移动止损
    current_data = get_current_data()
    if g.use_move_stoploss:
        for stock, position in context.portfolio.positions.items():
            if current_data[stock].paused:
                continue
            current_price = current_data[stock].last_price
            # 更新最高价
            if stock not in g.stop_loss_tracking:
                g.stop_loss_tracking[stock] = max(position.avg_cost, current_price)
            # 检查是否触发移动止损
            highest_price = g.stop_loss_tracking[stock]
            if current_price <= highest_price * (1 - g.stoploss_limit):
                close_position(context, stock)
                g.no_buy_stocks[stock] = 1
                print(f"移动止损卖出 {stock}, 亏损:{(1 - position.price / position.avg_cost):.2%}")

    for stock, pos in context.portfolio.positions.items():
        if current_data[stock].paused:
            continue
        # 盈利100%止盈
        if pos.price >= pos.avg_cost * 2:
            close_position(context, stock)
            g.no_buy_stocks[stock] = 1
            print(f"止盈卖出 {stock}, 收益率:{(pos.price / pos.avg_cost - 1):.2%}")
        # 非移动止损
        if not g.use_move_stoploss and pos.price <= pos.avg_cost * (1 - g.stoploss_limit):
            close_position(context, stock)
            g.no_buy_stocks[stock] = 1
            print(f"止损卖出 {stock}, 亏损:{(1 - pos.price / pos.avg_cost):.2%}")


# 检查昨日涨停股今日表现
def check_limit_up(context):
    # 获取当前持仓
    holdings = list(context.portfolio.positions.keys())
    g.yesterday_HL_list = []
    # 获取昨日涨停股
    if holdings:
        # 确保所有持仓股票代码都是字符串
        valid_holdings = [s for s in holdings if isinstance(s, str) and '.' in s]
        if valid_holdings:
            df = get_price(valid_holdings, end_date=context.previous_date,
                           frequency='daily', fields=['close', 'high_limit'],
                           count=1, panel=False)
            if not df.empty:
                g.yesterday_HL_list = list(df[df['close'] >= df['high_limit'] * 0.997].index)
                print(f"昨日涨停股: {[holdings[i] for i in g.yesterday_HL_list]}")
    # 检查涨停是否打开
    for i in g.yesterday_HL_list:
        stock = holdings[i]
        try:
            current_data = get_current_data()[stock]
            if current_data.last_price < current_data.high_limit * 0.99:  # 打开超过1%
                print(f"涨停打开卖出 {stock}")
                close_position(context, stock)
                # 记录不再购买
                g.no_buy_stocks[stock] = 1
        except Exception as e:
            log.error(f"处理股票{stock}时出错: {str(e)}")


# 封装实盘下单函数
def my_order_target_value(context, security, value):
    o = order_target_value(security, value)
    if o:
        security_name = get_stock_name(security)
        stock_show = f"{security} {security_name[:8]}: "
        stock_show = stock_show.ljust(20)
        if o.is_buy:
            if o.price * o.amount > 0:
                print(f"🚚🚚🚚🚚🚚 {stock_show}  "
                      f"买价{o.price:<7.2f}  "
                      f"买量{o.amount:<7}   "
                      f"价值{o.price * o.amount:.2f}")
                return o
        else:
            if o.price * o.amount > 0:
                print(f"🚛🚛🚛🚛🚛 {stock_show}  "
                      f"卖价{o.price:<7.2f}  "
                      f"成本{o.avg_cost:<7.2f}   "
                      f"卖量{o.amount:<7}   "
                      f"盈亏{(o.price - o.avg_cost) * o.amount:.2f}"
                      f"( {(o.price - o.avg_cost) / o.avg_cost * 100:.2f}% )")
                return o


""" ====================== 模块工具函数 ====================== """


# 获取股票名字
def get_stock_name(security):
    try:
        stock_info = get_security_info(security)
        return stock_info.display_name
    except Exception:
        return "未上市"


# 基础过滤
def filter_stocks(context, stock_list):
    """股票过滤"""
    current_data = get_current_data()
    filtered = []

    for stock in stock_list:
        # 停牌
        if current_data[stock].paused:
            continue
        # ST
        if current_data[stock].is_st:
            continue
        # 退市
        if '退' in current_data[stock].name:
            continue
        # 板块过滤 (排除创业板/科创板/北交所)
        if stock.startswith(('30', '68', '8', '4')):
            continue
        # 次新股过滤 (上市不足1年)
        ipo_date = get_security_info(stock).start_date
        if (context.current_dt.date() - ipo_date).days < 365:
            continue
        # 价格过滤 (非涨停跌停)
        last_price = current_data[stock].last_price
        if last_price >= current_data[stock].high_limit:
            continue  # 涨停
        if last_price <= current_data[stock].low_limit:
            continue  # 跌停
        # if last_price >= g.up_price:
        #     continue  # 过滤股价
        # 检测期内不再购买
        if g.check_after_no_buy:
            if stock in g.no_buy_stocks:
                print(f"{stock} 在 {g.no_buy_stocks[stock]} 日前列入不买清单, 不进行筛选")
                continue
        filtered.append(stock)
    return filtered


# v7 新增审计过滤
def filter_audit_opinion(context, stock_list):
    # 筛选审计意见 - 只看最近一期审计意见
    # 审计意见类型：1-无保留 2-无保留带解释 3-保留意见 4-拒绝/无法表示 5-否定意见 7-保留带解释
    final_list = []
    exception_audit_list = []

    for stock in stock_list:
        # 查询最近一期正式审计意见（财务报表审计，排除未经审计）
        q = query(finance.STK_AUDIT_OPINION.code, finance.STK_AUDIT_OPINION.pub_date,
                  finance.STK_AUDIT_OPINION.opinion_type_id).filter(
            finance.STK_AUDIT_OPINION.code == stock,
            finance.STK_AUDIT_OPINION.pub_date <= context.current_dt,
            finance.STK_AUDIT_OPINION.report_type == 0,  # 只看财务报表审计报告
            finance.STK_AUDIT_OPINION.opinion_type_id != 6,  # 排除未经审计
        ).order_by(finance.STK_AUDIT_OPINION.pub_date.desc()).limit(1)

        df = finance.run_query(q)

        if len(df) > 0:
            # 检查最近一期是否为不合格的审计意见类型
            # 不合格类型：保留意见(3)、拒绝/无法表示(4)、否定意见(5)、保留带解释(7)、持续经营重大不确定性(11)
            bad_opinion_types = [3, 4, 5, 7, 11]
            # 可接受类型：无保留(1)、无保留带解释(2)
            good_opinion_types = [1, 2]

            latest_opinion = df['opinion_type_id'].iloc[0]

            if latest_opinion in good_opinion_types:
                final_list.append(stock)
            elif latest_opinion in bad_opinion_types:
                exception_audit_list.append(stock)
            else:
                # 对于类型10(经审计但不确定具体类型)等未知类型，保守处理：保留股票
                final_list.append(stock)
        else:
            # 如果没有正式审计意见记录，保留该股票
            final_list.append(stock)

    return final_list


# 计算指数移动平均线
def EMA(series, N):
    """计算指数移动平均线（Exponential Moving Average）
    用于平滑价格波动，反映近期价格趋势，权重随时间递减

    参数:
        series: 价格序列（如收盘价）
        N: 计算周期

    返回:
        EMA序列
    """
    return pd.Series.ewm(series, span=N, min_periods=N - 1, adjust=False).mean()


# 计算MACD指标
def MACD(close, SHORT=12, LONG=26, M=9):
    """计算MACD指标（Moving Average Convergence Divergence）
    用于判断趋势强度和潜在反转点，由DIF、DEA、MACD柱组成

    参数:
        close: 收盘价序列
        SHORT: 短期EMA周期（默认12）
        LONG: 长期EMA周期（默认26）
        M: 信号周期（默认9）

    返回:
        DIF: 短期EMA与长期EMA的差值
        DEA: DIF的M期EMA
        MACD: (DIF-DEA)*2（放大波动）
    """
    DIF = EMA(close, SHORT) - EMA(close, LONG)
    DEA = EMA(DIF, M)
    MACD = (DIF - DEA) * 2
    return DIF, DEA, MACD


# 换手率计算
def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        # 计算平均换手率
        end_date = context.previous_date
        df_volume = get_price(stock, end_date=end_date, frequency='daily', fields=['volume'], count=20)
        df_cap = get_valuation(stock, end_date=end_date, fields=['circulating_cap'], count=1)
        circulating_cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
        return df_volume['turnover_ratio'].mean()
    else:
        # 计算实时换手率
        date_now = context.current_dt
        df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now, frequency='1m', fields=['volume'],
                           skip_paused=False, fq='pre', panel=True, fill_paused=False)
        volume = df_vol['volume'].sum()
        date_pre = context.previous_date
        df_circulating_cap = get_valuation(stock, end_date=date_pre, fields=['circulating_cap'], count=1)
        circulating_cap = df_circulating_cap['circulating_cap'].iloc[0] if not df_circulating_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        turnover_ratio = volume / (circulating_cap * 10000)
        return turnover_ratio


# 换手检测
def huanshou(context):
    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0:
            continue
        r = rt / avg
        action, icon = '', ''
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '🔥'
        if action:
            print(f"{action} {stock} {get_stock_name(stock)}  换手率:{rt:.2%}  均:{avg:.2%} 倍率:x{r:.1f} {icon}")
            close_position(context, stock)


# 成交量宽度防御检测
def check_defense_trigger(context):
    """改进后的防御条件检查"""

    # 计算宽度
    def get_market_breadth(ma_days):
        required_days = ma_days + 10
        end_date = context.current_dt.replace(hour=14, minute=49)

        # 获取行业分类数据
        sw_l1 = get_industries('sw_l1', date=context.current_dt.date())
        industry_stocks = {}
        for idx, row in sw_l1.iterrows():
            ind_stocks = get_industry_stocks(idx, date=end_date)
            industry_stocks[row['name']] = ind_stocks  # 存储行业对应的股票列表

        # 获取所有股票
        all_stocks = []
        for stocks in industry_stocks.values():
            all_stocks.extend(stocks)
        all_stocks = list(set(all_stocks))  # 去重

        # 获取价格和成交额数据
        data = get_bars(all_stocks, end_dt=end_date, count=required_days, unit='1d',
                        fields=['date', 'close', 'volume', 'money'], include_now=True, df=True)

        # 处理价格数据：用level_1作为索引（行号），level_0作为股票代码列
        price_reset = data.reset_index()
        price_data = price_reset.pivot(index='level_1', columns='level_0', values='close')  # 按要求的透视表写法

        # 计算移动平均和站上均线的股票占比
        ma = price_data.rolling(window=ma_days).mean()
        above_ma = price_data > ma

        # 核心逻辑：按透视表处理20日成交金额，计算平均值后再分组
        # 1. 重置索引并创建成交额透视表（行=行号，列=股票代码，值=成交额）
        money_reset = data.reset_index()
        money_pivot = money_reset.pivot(index='level_1', columns='level_0', values='money')  # 成交额透视表

        recent_20d_money_pivot = money_pivot.tail(20)  # 关键：直接从透视表取最近20天

        avg_money = recent_20d_money_pivot.mean().reset_index()  # 按列求平均
        avg_money.columns = ['code', 'avg_money']  # 重命名列：股票代码、平均成交额

        # 4. 按平均成交额排序并分为20组
        avg_money = avg_money.sort_values('avg_money', ascending=False)
        # 使用qcut进行分组，处理可能的重复值
        avg_money['money_group'] = pd.qcut(avg_money['avg_money'], 20, labels=[f'组{i + 1}' for i in range(20)],
                                           duplicates='drop')

        # 5. 创建成交额分组字典（组名: 股票列表）
        money_groups = {group: group_df['code'].tolist()
                        for group, group_df in avg_money.groupby('money_group')}

        # 6. 计算每个成交额组站上均线的股票比例
        group_scores = pd.DataFrame(index=price_data.index)
        for group, stocks in money_groups.items():
            valid_stocks = list(set(above_ma.columns) & set(stocks))
            if valid_stocks:
                group_scores[group] = 100 * above_ma[valid_stocks].sum(axis=1) / len(valid_stocks)

        # 7. 计算近3天各组平均站上均线比例
        recent_group_data = group_scores[-3:].mean()
        _sorted_ma_data = recent_group_data.sort_values(ascending=False)

        # 8. 处理涨跌幅数据和每日指标
        df = data.reset_index().rename(columns={'level_0': 'symbol', 'level_1': 'index'})
        df['pct_change'] = df.groupby(['symbol'])['close'].pct_change()

        trade_days = get_trade_days(end_date=context.current_dt, count=3)
        by_date = trade_days[0]
        df = df[df.date >= by_date]

        grouped = df.groupby('date')
        _result = pd.DataFrame({
            'up_ratio': grouped['pct_change'].apply(lambda x: (x > 0).mean()),
            'down_over': grouped['pct_change'].apply(lambda x: (x <= -0.0985).sum())
        }).reset_index()
        return _sorted_ma_data, _result

    # 计算趋势指标
    def calculate_trend_indicators(index_symbol='399101.XSHE'):
        """计算趋势指标: 过去3天内只要有一天处于高位，则视为高位，避免边界问题）"""
        # 参数设置
        high_lookback = 60  # 近期高点观察窗口
        high_proximity = 0.95  # 接近高点的阈值（95%）
        check_days = 2  # 检查过去1天的状态

        end_date = context.current_dt.replace(hour=14, minute=49)

        # 获取历史数据（需要包含足够天数，用于计算过去5天的指标）
        # 为了计算过去5天的指标，需要多获取high_lookback天数据（避免边界问题）
        total_days_needed = high_lookback + 10
        data = get_bars(index_symbol, end_dt=end_date,
                        count=total_days_needed,
                        unit='1d', fields=['date', 'close', 'high', 'avg', 'volume'], include_now=True, df=True)

        data['date'] = pd.to_datetime(data['date'])

        # 计算过去每天的is_high状态
        _past_is_high_list = []

        # 遍历过去2天
        for i in range(-check_days, 0):
            # 数据切片，每次60天，不包含最后一天
            valid_data = data.iloc[:i][-high_lookback:]
            current_day_price = valid_data['close'].iloc[-1]

            # 计算当天的接近高点状态
            day_max_high = valid_data['high'].max()
            day_close_to_high = current_day_price >= (day_max_high * high_proximity)

            # 当天的is_high
            day_is_high = day_close_to_high
            _past_is_high_list.append(day_is_high)

        # 当前天的指标（最后一天）
        current_data = data[-high_lookback:]
        current_price = current_data['close'].iloc[-1]
        max_high = current_data['high'].max()
        close_to_high = current_price >= (max_high * high_proximity)

        # 将当前天加入列表，
        _past_is_high_list.append(close_to_high)

        # 新的is_high只要有一天为True，则为True
        _is_high = any(_past_is_high_list)

        return _is_high, _past_is_high_list

    # 为方便回测直接用记录的历史路标对比
    cur_date_str = str(context.current_dt.date())
    if cur_date_str <= g.history_defense_date_list[-1]:
        if cur_date_str in g.history_defense_date_list:
            g.defense_signal = True
            print("组20防御: True, 处于历史触发范围内")
        else:
            g.defense_signal = False
            print("触发防御: False, 未处于历史触发范围内")
    # 超过时间则手动计算, 用于实盘
    else:
        if g.defense_signal:
            # 如果已经进入防御板块，只要看组20有没有在前三
            sorted_ma_data, result = get_market_breadth(20)
            up_ratio = result.iloc[-3:]['up_ratio'].mean()  # 涨跌比
            avg_score = sorted_ma_data['组1']  # 宽度
            # 退出版本1：
            defense_in_top = any([ind in sorted_ma_data.index[:3] for ind in g.industries])  # 逻辑防御板块在前3
            bank_exit_signal = not defense_in_top
            # 退出版本2：宽度和涨跌比修复
            # bank_exit_signal= up_ratio>=0.5 and avg_score >=55
            g.defense_signal = not bank_exit_signal
            log.info(f"组20防御: {g.defense_signal} "
                     f"组1宽度:{avg_score:.1f} "
                     f"涨跌比:{up_ratio:.2f} "
                     f"组20防御次数:{sum(g.cnt_bank_signal)} "
                     f"top宽度:{sorted_ma_data.index[:5].tolist()}")
        else:
            # 判断条件
            is_high, past_is_high_list = calculate_trend_indicators()
            if is_high:  # 高位或者缩量
                # 行业强度判断
                sorted_ma_data, result = get_market_breadth(20)
                defense_in_top = any([ind in sorted_ma_data.index[:2] for ind in g.industries])  # 防御板块在前二
                # 版本2改为判断剔除防御板块后的平均宽度
                avg_score = sorted_ma_data[[ind not in g.industries for ind in sorted_ma_data.index]].mean()
                above_average = avg_score < 60  # 平均宽度低于60

                # 版本三，涨跌比均值低于50%
                up_ratio = result.iloc[-3:]['up_ratio'].mean()
                above_ratio = up_ratio < 0.5

                # 组20择时综合判断
                is_bank_defense = defense_in_top and above_average and above_ratio

                g.defense_signal = is_bank_defense

                if is_bank_defense:
                    g.cnt_bank_signal.append(is_bank_defense)

                log.info(f"组20防御: {is_bank_defense} "
                         f"高位:{is_high}{past_is_high_list} "
                         f"组1宽度:{avg_score:.1f} "
                         f"涨跌比:{up_ratio:.2f} "
                         f"top宽度:{sorted_ma_data.index[:5].tolist()} ")
            else:
                g.defense_signal = False
                log.info(f"触发防御: {g.defense_signal} 高位:{is_high}{past_is_high_list}")

    # 检测到需要防御进行空仓, 只空仓小市值的票
    now_time = context.current_dt
    if g.defense_signal:
        for stock in g.strategy_holdings[1][:]:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'],
                                     skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            # 已涨停不清仓
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                close_position(context, stock)


""" ====================== 特殊函数 ====================== """


def after_code_changed(context):
    # g.limit_days = 2
    # g.check_after_no_buy = False
    pass
