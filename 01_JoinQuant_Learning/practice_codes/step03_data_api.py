# -*- coding: utf-8 -*-
"""
第二步：数据API学习
目标：掌握聚宽数据获取API的使用方法
"""

def initialize(context):
    """初始化函数"""
    g.stock = '000001.XSHE'  # 平安银行
    log.info("开始学习聚宽数据API")

def handle_data(context, data):
    """
    演示各种数据获取方法
    只在第一天演示，避免日志过多
    """
    # 只在回测第一天演示数据API
    if context.current_dt.date() != context.portfolio.start_date.date():
        return
    
    stock = g.stock
    log.info("=== 聚宽数据API演示 ===")
    
    # 1. 获取当前价格数据
    log.info("1. 当前价格数据:")
    current_data = data[stock]
    log.info("开盘价: %.2f" % current_data.open)
    log.info("最高价: %.2f" % current_data.high) 
    log.info("最低价: %.2f" % current_data.low)
    log.info("收盘价: %.2f" % current_data.close)
    log.info("成交量: %d" % current_data.volume)
    
    # 2. 获取历史价格数据
    log.info("\n2. 历史价格数据 (最近5天):")
    hist_data = get_price(stock, count=5, frequency='daily', fields=['close', 'volume'])
    log.info("最近5天收盘价:")
    for date, close in hist_data['close'].items():
        log.info("%s: %.2f" % (date.strftime('%Y-%m-%d'), close))
    
    # 3. 获取历史数据的另一种方法
    log.info("\n3. 使用attribute_history获取数据:")
    hist_attr = attribute_history(stock, 5, '1d', ['close', 'volume'])
    log.info("最近5天平均价格: %.2f" % hist_attr['close'].mean())
    log.info("最近5天最高价: %.2f" % hist_attr['close'].max())
    log.info("最近5天最低价: %.2f" % hist_attr['close'].min())
    
    # 4. 计算技术指标
    log.info("\n4. 技术指标计算:")
    closes = hist_attr['close']
    ma5 = closes.mean()  # 5日均线
    log.info("5日均线: %.2f" % ma5)
    log.info("当前价格相对5日均线: %.2f%%" % ((current_data.close / ma5 - 1) * 100))
    
    # 5. 获取财务数据
    log.info("\n5. 财务数据:")
    try:
        # 获取最新的财务数据
        fundamental = get_fundamentals(
            query(valuation.code, valuation.pe_ratio, valuation.pb_ratio)
            .filter(valuation.code == stock)
        )
        if not fundamental.empty:
            log.info("PE比率: %.2f" % fundamental.iloc[0]['pe_ratio'])
            log.info("PB比率: %.2f" % fundamental.iloc[0]['pb_ratio'])
    except Exception as e:
        log.info("获取财务数据失败: %s" % str(e))
    
    # 6. 获取股票基本信息
    log.info("\n6. 股票基本信息:")
    stock_info = get_security_info(stock)
    log.info("股票名称: %s" % stock_info.display_name)
    log.info("股票类型: %s" % stock_info.type)
    log.info("上市日期: %s" % stock_info.start_date)
    
    # 7. 获取行业信息
    log.info("\n7. 行业信息:")
    industry = get_industry(stock)
    log.info("所属行业: %s" % industry)
    
    # 8. 批量获取多只股票数据
    log.info("\n8. 批量获取数据:")
    stocks = ['000001.XSHE', '000002.XSHE', '600036.XSHG']
    batch_data = get_price(stocks, count=1, frequency='daily', fields=['close'])
    log.info("多只股票当前价格:")
    for stock_code in stocks:
        price = batch_data['close'][stock_code].iloc[-1]
        log.info("%s: %.2f" % (stock_code, price))

def after_trading_end(context):
    """收盘后运行"""
    if context.current_dt.date() == context.portfolio.start_date.date():
        log.info("=== 数据API演示完成 ===")
        log.info("请查看上面的日志输出，了解各种数据获取方法")

"""
核心API总结：

1. 实时数据获取：
   - data[stock].close  # 当前收盘价
   - data[stock].open   # 当前开盘价
   - data[stock].high   # 当前最高价
   - data[stock].low    # 当前最低价
   - data[stock].volume # 当前成交量

2. 历史数据获取：
   - get_price(stock, count, frequency, fields)
   - attribute_history(stock, count, unit, fields)

3. 财务数据：
   - get_fundamentals(query(...))

4. 股票信息：
   - get_security_info(stock)  # 基本信息
   - get_industry(stock)       # 行业信息

5. 技术指标：
   - 可以基于价格数据自己计算
   - 或使用talib库: talib.SMA(), talib.MACD()等

使用提示：
1. 将代码复制到聚宽平台运行
2. 查看"日志"标签页的输出
3. 尝试修改股票代码和参数
4. 实验不同的数据获取方法
"""
