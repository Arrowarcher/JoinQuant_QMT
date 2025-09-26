# -*- coding: utf-8 -*-
"""
聚宽API基础语法详解
目标：掌握聚宽平台的核心API和基本语法
"""

def initialize(context):
    """
    在这里演示各种API的基本用法
    """
    log.info("=== 聚宽API基础语法演示 ===")
    
    # 设置演示用的股票
    g.demo_stock = '000001.XSHE'  # 平安银行
    g.demo_stocks = ['000001.XSHE', '000002.XSHE', '600036.XSHG']

def handle_data(context, data):
    """
    API演示主函数
    """
    # 只在第一天演示，避免日志过多
    if context.current_dt.date() != context.portfolio.start_date.date():
        return
    
    log.info("开始API演示...")
    
    # ===== 1. 数据获取API =====
    demo_data_api(context, data)
    
    # ===== 2. 交易指令API =====
    demo_trading_api(context, data)
    
    # ===== 3. 信息查询API =====
    demo_query_api(context, data)
    
    # ===== 4. 技术分析API =====
    demo_technical_api(context, data)
    
    # ===== 5. 财务数据API =====
    demo_fundamental_api(context, data)

def demo_data_api(context, data):
    """
    演示数据获取API
    """
    log.info("\n===== 1. 数据获取API =====")
    
    stock = g.demo_stock
    
    # 【API 1】get_price() - 获取历史价格数据
    log.info("1.1 get_price() - 获取历史价格")
    
    # 获取最近10天的日线数据
    hist_data = get_price(stock, count=10, frequency='daily', 
                         fields=['open', 'high', 'low', 'close', 'volume'])
    log.info("数据形状: %s" % str(hist_data.shape))
    log.info("最新收盘价: %.2f" % hist_data['close'].iloc[-1])
    
    # 按时间范围获取数据
    start_date = '2024-01-01'
    end_date = '2024-01-10'
    range_data = get_price(stock, start_date=start_date, end_date=end_date, 
                          frequency='daily', fields=['close'])
    log.info("时间范围数据条数: %d" % len(range_data))
    
    # 【API 2】attribute_history() - 获取历史数据（另一种方式）
    log.info("\n1.2 attribute_history() - 历史数据")
    
    attr_data = attribute_history(stock, 5, '1d', ['close', 'volume'])
    log.info("最近5天平均价格: %.2f" % attr_data['close'].mean())
    log.info("最近5天成交量: %s" % attr_data['volume'].tolist())
    
    # 【API 3】批量获取多只股票数据
    log.info("\n1.3 批量获取数据")
    
    batch_data = get_price(g.demo_stocks, count=1, frequency='daily', fields=['close'])
    for stock_code in g.demo_stocks:
        price = batch_data['close'][stock_code].iloc[-1]
        log.info("%s 当前价格: %.2f" % (stock_code, price))

def demo_trading_api(context, data):
    """
    演示交易指令API
    """
    log.info("\n===== 2. 交易指令API =====")
    
    stock = g.demo_stock
    current_price = data[stock].close
    
    # 【API 1】order() - 按股数下单
    log.info("2.1 order() - 按股数下单")
    log.info("order('%s', 100)  # 买入100股" % stock)
    log.info("order('%s', -100) # 卖出100股" % stock)
    # order(stock, 100)  # 实际下单（演示中注释掉）
    
    # 【API 2】order_value() - 按金额下单
    log.info("\n2.2 order_value() - 按金额下单")
    log.info("order_value('%s', 10000)  # 买入10000元" % stock)
    log.info("order_value('%s', -5000)  # 卖出5000元" % stock)
    
    # 【API 3】order_target() - 按目标股数下单（推荐）
    log.info("\n2.3 order_target() - 按目标股数下单")
    log.info("order_target('%s', 1000)  # 调整到1000股" % stock)
    log.info("order_target('%s', 0)    # 清仓" % stock)
    
    # 【API 4】order_target_value() - 调整到目标金额
    log.info("\n2.4 order_target_value() - 目标金额")
    log.info("order_target_value('%s', 20000)  # 调整到20000元" % stock)
    
    # 【API 5】限价单
    log.info("\n2.5 限价单")
    limit_price = current_price * 0.98  # 低于当前价格2%
    log.info("order('%s', 100, LimitOrderStyle(%.2f))  # 限价买入" % (stock, limit_price))

def demo_query_api(context, data):
    """
    演示信息查询API
    """
    log.info("\n===== 3. 信息查询API =====")
    
    stock = g.demo_stock
    
    # 【API 1】get_current_data() - 获取当前数据
    log.info("3.1 get_current_data() - 当前数据")
    current_data = get_current_data()
    stock_data = current_data[stock]
    log.info("股票名称: %s" % stock_data.name)
    log.info("是否停牌: %s" % stock_data.paused)
    log.info("涨停价: %.2f" % stock_data.high_limit)
    log.info("跌停价: %.2f" % stock_data.low_limit)
    
    # 【API 2】get_security_info() - 股票基本信息
    log.info("\n3.2 get_security_info() - 基本信息")
    security_info = get_security_info(stock)
    log.info("股票全称: %s" % security_info.display_name)
    log.info("股票类型: %s" % security_info.type)
    log.info("上市日期: %s" % security_info.start_date)
    log.info("退市日期: %s" % security_info.end_date)
    
    # 【API 3】get_industry() - 行业信息
    log.info("\n3.3 get_industry() - 行业信息")
    try:
        industry_info = get_industry(stock)
        log.info("所属行业: %s" % industry_info)
    except:
        log.info("获取行业信息失败")
    
    # 【API 4】context.portfolio - 账户信息
    log.info("\n3.4 context.portfolio - 账户信息")
    portfolio = context.portfolio
    log.info("总资产: %.2f" % portfolio.total_value)
    log.info("可用现金: %.2f" % portfolio.available_cash)
    log.info("持仓市值: %.2f" % portfolio.positions_value)
    log.info("初始资金: %.2f" % portfolio.starting_cash)
    
    # 【API 5】持仓信息
    log.info("\n3.5 持仓信息")
    positions = portfolio.positions
    position = positions[stock]
    log.info("%s 持仓数量: %d" % (stock, position.total_amount))
    log.info("%s 持仓市值: %.2f" % (stock, position.value))
    log.info("%s 成本价: %.2f" % (stock, position.avg_cost))

def demo_technical_api(context, data):
    """
    演示技术分析API
    """
    log.info("\n===== 4. 技术分析API =====")
    
    stock = g.demo_stock
    
    # 获取历史数据用于技术分析
    hist_data = get_price(stock, count=30, frequency='daily', fields=['close', 'high', 'low'])
    closes = hist_data['close']
    highs = hist_data['high']
    lows = hist_data['low']
    
    # 【API 1】移动平均线
    log.info("4.1 移动平均线")
    ma5 = closes.rolling(5).mean().iloc[-1]
    ma20 = closes.rolling(20).mean().iloc[-1]
    log.info("5日均线: %.2f" % ma5)
    log.info("20日均线: %.2f" % ma20)
    
    # 【API 2】使用talib计算技术指标
    log.info("\n4.2 talib技术指标")
    
    # RSI相对强弱指标
    import talib
    rsi = talib.RSI(closes.values, timeperiod=14)[-1]
    log.info("RSI(14): %.2f" % rsi)
    
    # MACD指标
    macd, macdsignal, macdhist = talib.MACD(closes.values)
    log.info("MACD: %.4f" % macd[-1])
    log.info("MACD信号线: %.4f" % macdsignal[-1])
    log.info("MACD柱: %.4f" % macdhist[-1])
    
    # 布林带
    upper, middle, lower = talib.BBANDS(closes.values)
    log.info("布林带上轨: %.2f" % upper[-1])
    log.info("布林带中轨: %.2f" % middle[-1])
    log.info("布林带下轨: %.2f" % lower[-1])

def demo_fundamental_api(context, data):
    """
    演示财务数据API
    """
    log.info("\n===== 5. 财务数据API =====")
    
    stock = g.demo_stock
    
    # 【API 1】get_fundamentals() - 获取财务数据
    log.info("5.1 get_fundamentals() - 财务数据")
    
    try:
        # 获取估值数据
        valuation_data = get_fundamentals(
            query(valuation.code, valuation.pe_ratio, valuation.pb_ratio, 
                  valuation.market_cap).filter(valuation.code == stock)
        )
        
        if not valuation_data.empty:
            pe = valuation_data.iloc[0]['pe_ratio']
            pb = valuation_data.iloc[0]['pb_ratio']
            market_cap = valuation_data.iloc[0]['market_cap']
            
            log.info("PE比率: %.2f" % pe)
            log.info("PB比率: %.2f" % pb)
            log.info("总市值: %.2f亿元" % (market_cap / 100000000))
        
        # 获取盈利能力数据
        indicator_data = get_fundamentals(
            query(indicator.code, indicator.roe, indicator.roa, 
                  indicator.inc_revenue_year_on_year).filter(indicator.code == stock)
        )
        
        if not indicator_data.empty:
            roe = indicator_data.iloc[0]['roe']
            roa = indicator_data.iloc[0]['roa']
            revenue_growth = indicator_data.iloc[0]['inc_revenue_year_on_year']
            
            log.info("ROE净资产收益率: %.2f%%" % roe)
            log.info("ROA总资产收益率: %.2f%%" % roa)
            log.info("营收同比增长: %.2f%%" % revenue_growth)
            
    except Exception as e:
        log.warning("获取财务数据失败: %s" % str(e))
    
    # 【API 2】get_all_securities() - 获取股票列表
    log.info("\n5.2 get_all_securities() - 股票列表")
    
    # 获取所有A股
    all_stocks = get_all_securities(['stock'])
    log.info("A股总数: %d只" % len(all_stocks))
    
    # 获取沪深300成分股
    hs300_stocks = get_index_stocks('000300.XSHG')
    log.info("沪深300成分股: %d只" % len(hs300_stocks))
    log.info("前5只: %s" % hs300_stocks[:5])

def after_trading_end(context):
    """
    收盘后总结
    """
    if context.current_dt.date() == context.portfolio.start_date.date():
        log.info("\n===== API演示完成 =====")
        log.info("请查看上面的日志，学习各种API的使用方法")
        log.info("接下来可以在实际策略中使用这些API")

"""
===== 聚宽API基础演示完成 =====

本文件演示了聚宽平台的核心API使用方法：
1. 数据获取API - get_price(), attribute_history()
2. 交易指令API - order_target() 等
3. 信息查询API - get_current_data(), context.portfolio
4. 技术分析API - talib.RSI(), talib.MACD() 等  
5. 财务数据API - get_fundamentals()

📚 完整的API速查手册请查看:
learning_materials/joinquant_api_reference.md

该文档包含:
- 详细的API使用方法
- 技术指标原理解释
- 财务指标含义说明
- 常用策略模板
- 最佳实践建议
"""
