# -*- coding: utf-8 -*-
"""
第一步：聚宽平台Hello World
目标：熟悉聚宽基本语法和框架结构
"""

# 初始化函数，设定基准等等
def initialize(context):
    """
    初始化函数，只在策略开始时运行一次
    context: 策略全局变量
    """
    # 设定沪深300作为基准
    g.benchmark = '000300.XSHG'
    
    # 设定股票池 - 选择几只知名股票
    g.stocks = [
        '000001.XSHE',  # 平安银行
        '000002.XSHE',  # 万科A
        '600036.XSHG',  # 招商银行
        '600519.XSHG',  # 贵州茅台
    ]
    
    # 打印日志
    log.info("策略初始化完成！股票池包含%d只股票" % len(g.stocks))
    log.info("股票池：%s" % str(g.stocks))

def before_trading_start(context):
    """
    每天开盘前运行
    context: 策略全局变量
    """
    # 获取当前日期
    current_date = context.current_dt.strftime('%Y-%m-%d')
    log.info("今天是：%s，准备开始交易" % current_date)

def handle_data(context, data):
    """
    主要的策略逻辑，每个交易周期运行一次
    context: 策略全局变量
    data: 当前时间的数据
    """
    # 获取当前价格
    for stock in g.stocks:
        current_price = data[stock].close
        log.info("%s 当前价格：%.2f" % (stock, current_price))
    
    # 简单的买入逻辑：如果没有持仓，就买入第一只股票
    stock = g.stocks[0]  # 平安银行
    
    # 检查是否已有持仓
    position = context.portfolio.positions[stock]
    
    if position.total_amount == 0:  # 没有持仓
        # 买入股票，投入25%的资金
        # 计算目标股数（100股的整数倍）
        target_shares = int(context.portfolio.total_value * 0.25 / current_price / 100) * 100
        if target_shares >= 100:
            order_target(stock, target_shares)
        log.info("买入 %s，目标仓位：25%%" % stock)
    else:
        log.info("%s 当前持仓：%d股" % (stock, position.total_amount))

def after_trading_end(context):
    """
    每天收盘后运行
    context: 策略全局变量
    """
    # 打印账户信息
    log.info("今日交易结束")
    log.info("账户总资产：%.2f" % context.portfolio.total_value)
    log.info("可用资金：%.2f" % context.portfolio.available_cash)
    
    # 打印持仓信息
    positions = context.portfolio.positions
    for stock in positions:
        if positions[stock].total_amount > 0:
            log.info("持仓 %s：%d股，市值：%.2f" % (
                stock, 
                positions[stock].total_amount,
                positions[stock].value
            ))

"""
使用说明：
1. 将代码复制到聚宽平台的策略编辑器中
2. 设置回测参数：
   - 开始时间：2023-01-01  
   - 结束时间：2023-12-31
   - 初始资金：100000
   - 基准：沪深300
3. 点击"开始回测"
4. 观察回测结果和日志输出

学习要点：
- initialize(): 策略初始化，只运行一次
- handle_data(): 核心交易逻辑，每个交易日运行
- before_trading_start(): 开盘前准备
- after_trading_end(): 收盘后总结
- order_target(): 按目标股数下单
- context.portfolio: 账户和持仓信息
- log.info(): 打印日志信息
"""
