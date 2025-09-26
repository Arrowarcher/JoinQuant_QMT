# -*- coding: utf-8 -*-
"""
移动平均线计算演示
目标：深入理解 hist_data['close'][-5:].mean() 的计算原理
"""

import pandas as pd
import numpy as np

def initialize(context):
    """
    初始化演示
    """
    g.stock = '000001.XSHE'
    log.info("=== 移动平均线计算演示 ===")

def handle_data(context, data):
    """
    演示移动平均线的计算过程
    """
    # 只在第一天演示
    if context.current_dt.date() != context.portfolio.start_date.date():
        return
    
    stock = g.stock
    
    # ===== 第一部分：理解数据结构 =====
    log.info("\n===== 第一部分：理解数据结构 =====")
    
    # 获取10天的历史数据
    hist_data = get_price(stock, count=10, frequency='daily', fields=['close'])
    log.info("获取到的历史数据形状: %s" % str(hist_data.shape))
    log.info("数据类型: %s" % type(hist_data))
    
    # 显示数据内容
    close_prices = hist_data['close']
    log.info("收盘价序列类型: %s" % type(close_prices))
    log.info("最近10天收盘价:")
    for i, (date, price) in enumerate(close_prices.items()):
        log.info("  第%d天 %s: %.2f" % (i+1, date.strftime('%Y-%m-%d'), price))
    
    # ===== 第二部分：切片操作演示 =====
    log.info("\n===== 第二部分：切片操作演示 =====")
    
    # 转换为列表便于理解索引
    price_list = close_prices.tolist()
    log.info("价格列表: %s" % [round(p, 2) for p in price_list])
    log.info("列表长度: %d" % len(price_list))
    
    # 演示不同的切片操作
    log.info("\n切片操作演示:")
    log.info("price_list[-1]    (最后1个):  %.2f" % price_list[-1])
    log.info("price_list[-2]    (倒数第2个): %.2f" % price_list[-2])
    log.info("price_list[-5]    (倒数第5个): %.2f" % price_list[-5])
    
    log.info("\nprice_list[-5:]   (最后5个):  %s" % [round(p, 2) for p in price_list[-5:]])
    log.info("price_list[-3:]   (最后3个):  %s" % [round(p, 2) for p in price_list[-3:]])
    log.info("price_list[-10:]  (最后10个): %s" % [round(p, 2) for p in price_list[-10:]])
    
    # ===== 第三部分：移动平均线计算 =====
    log.info("\n===== 第三部分：移动平均线计算 =====")
    
    # 方法1：使用pandas切片和mean()
    ma5_method1 = close_prices[-5:].mean()
    log.info("方法1 - close_prices[-5:].mean(): %.4f" % ma5_method1)
    
    # 方法2：手动计算验证
    last_5_prices = price_list[-5:]
    ma5_method2 = sum(last_5_prices) / len(last_5_prices)
    log.info("方法2 - 手动计算: (%.2f+%.2f+%.2f+%.2f+%.2f)/5 = %.4f" % 
            (last_5_prices[0], last_5_prices[1], last_5_prices[2], 
             last_5_prices[3], last_5_prices[4], ma5_method2))
    
    # 方法3：使用numpy
    ma5_method3 = np.mean(last_5_prices)
    log.info("方法3 - numpy.mean(): %.4f" % ma5_method3)
    
    # 验证三种方法结果是否相同
    log.info("三种方法结果是否相同: %s" % 
            (abs(ma5_method1 - ma5_method2) < 0.0001 and abs(ma5_method2 - ma5_method3) < 0.0001))
    
    # ===== 第四部分：不同周期移动平均线 =====
    log.info("\n===== 第四部分：不同周期移动平均线 =====")
    
    # 获取更多历史数据
    hist_data_30 = get_price(stock, count=30, frequency='daily', fields=['close'])
    close_prices_30 = hist_data_30['close']
    
    # 计算不同周期的移动平均线
    current_price = close_prices_30.iloc[-1]
    ma3 = close_prices_30[-3:].mean()
    ma5 = close_prices_30[-5:].mean()
    ma10 = close_prices_30[-10:].mean()
    ma20 = close_prices_30[-20:].mean()
    
    log.info("当前价格:   %.2f" % current_price)
    log.info("3日均线:    %.2f" % ma3)
    log.info("5日均线:    %.2f" % ma5)
    log.info("10日均线:   %.2f" % ma10)
    log.info("20日均线:   %.2f" % ma20)
    
    # 分析均线关系
    log.info("\n均线分析:")
    if ma5 > ma20:
        log.info("短期趋势: 向上 (5日线 > 20日线)")
    else:
        log.info("短期趋势: 向下 (5日线 < 20日线)")
    
    if current_price > ma5:
        log.info("价格位置: 强势 (价格 > 5日线)")
    else:
        log.info("价格位置: 弱势 (价格 < 5日线)")
    
    # ===== 第五部分：rolling方法对比 =====
    log.info("\n===== 第五部分：rolling方法对比 =====")
    
    # 使用rolling方法计算移动平均线序列
    ma5_rolling = close_prices_30.rolling(window=5).mean()
    
    # 比较两种方法的最新结果
    ma5_slice = close_prices_30[-5:].mean()      # 切片方法
    ma5_rolling_last = ma5_rolling.iloc[-1]      # rolling方法
    
    log.info("切片方法最新5日均线:   %.4f" % ma5_slice)
    log.info("rolling方法最新5日均线: %.4f" % ma5_rolling_last)
    log.info("两种方法结果相同: %s" % (abs(ma5_slice - ma5_rolling_last) < 0.0001))
    
    # 显示rolling方法的优势：可以计算历史每一天的均线
    log.info("\nrolling方法的优势 - 最近5天的5日均线:")
    for i, (date, ma_value) in enumerate(ma5_rolling.tail(5).items()):
        if not pd.isna(ma_value):
            log.info("  %s: %.2f" % (date.strftime('%Y-%m-%d'), ma_value))
    
    # ===== 第六部分：金叉死叉判断演示 =====
    log.info("\n===== 第六部分：金叉死叉判断演示 =====")
    
    # 计算当前和前一天的均线
    ma5_today = close_prices_30[-5:].mean()       # 今天的5日均线
    ma20_today = close_prices_30[-20:].mean()     # 今天的20日均线
    ma5_yesterday = close_prices_30[-6:-1].mean() # 昨天的5日均线
    ma20_yesterday = close_prices_30[-21:-1].mean() # 昨天的20日均线
    
    log.info("今天   - 5日均线: %.2f, 20日均线: %.2f" % (ma5_today, ma20_today))
    log.info("昨天   - 5日均线: %.2f, 20日均线: %.2f" % (ma5_yesterday, ma20_yesterday))
    
    # 判断金叉死叉
    if ma5_today > ma20_today and ma5_yesterday <= ma20_yesterday:
        log.info("信号: 金叉！(5日线上穿20日线)")
    elif ma5_today < ma20_today and ma5_yesterday >= ma20_yesterday:
        log.info("信号: 死叉！(5日线下穿20日线)")
    else:
        log.info("信号: 无变化")
    
    # ===== 第七部分：实际应用示例 =====
    log.info("\n===== 第七部分：实际应用示例 =====")
    
    # 模拟一个简单的均线策略
    def simple_ma_strategy(prices, short_period=5, long_period=20):
        """简单的双均线策略"""
        if len(prices) < long_period:
            return "HOLD", "数据不足"
        
        # 计算均线
        short_ma = prices[-short_period:].mean()
        long_ma = prices[-long_period:].mean()
        
        # 判断信号
        if short_ma > long_ma:
            return "BUY", f"短期均线({short_ma:.2f}) > 长期均线({long_ma:.2f})"
        elif short_ma < long_ma:
            return "SELL", f"短期均线({short_ma:.2f}) < 长期均线({long_ma:.2f})"
        else:
            return "HOLD", f"短期均线({short_ma:.2f}) = 长期均线({long_ma:.2f})"
    
    # 应用策略
    signal, reason = simple_ma_strategy(close_prices_30)
    log.info("策略信号: %s" % signal)
    log.info("信号原因: %s" % reason)
    
    log.info("\n=== 移动平均线演示完成 ===")

"""
核心总结：

1. hist_data['close'][-5:].mean() 的工作原理：
   - hist_data['close']: 获取收盘价序列
   - [-5:]: 取最后5个元素（最近5天）
   - .mean(): 计算平均值

2. 为什么这样计算是正确的：
   - 移动平均线定义：某时点往前N天的价格平均值
   - 数据按时间排序，最后的元素是最新数据
   - [-5:]正好取到最近5天的数据

3. 关键理解点：
   - 负数索引：-1是最后一个，-5是倒数第5个
   - 切片操作：[-5:]从倒数第5个到最后
   - pandas自动处理时间序列的顺序

4. 实际应用：
   - 计算当前均线：prices[-n:].mean()
   - 计算历史均线：prices.rolling(n).mean()
   - 比较均线判断趋势：ma_short vs ma_long

这种计算方法简洁高效，是量化交易中的标准做法！
"""
