# -*- coding: utf-8 -*-
"""
技术面选股策略参考
AI可以参考这些策略实现，但实际使用时需要根据具体需求调整
"""

def technical_strategy_1_ma_cross():
    """
    策略1：均线金叉选股
    条件：5日均线上穿20日均线
    """
    selected_stocks = []
    
    # 获取所有A股
    all_stocks = list(get_all_securities(['stock']).index)
    
    for stock in all_stocks:
        try:
            # 获取历史数据
            hist = get_price(stock, count=30, frequency='daily', fields=['close'])
            if len(hist) < 30:
                continue
            
            # 计算均线
            ma5 = hist['close'].rolling(window=5).mean()
            ma20 = hist['close'].rolling(window=20).mean()
            
            # 检查金叉条件
            if (ma5[-1] > ma20[-1] and  # 当前5日均线在20日均线上方
                ma5[-2] <= ma20[-2]):  # 前一日5日均线在20日均线下方或相等
                selected_stocks.append(stock)
                
        except:
            continue
    
    return selected_stocks

def technical_strategy_2_breakout():
    """
    策略2：突破选股
    条件：价格突破20日最高价，成交量放大
    """
    selected_stocks = []
    
    all_stocks = list(get_all_securities(['stock']).index)
    
    for stock in all_stocks:
        try:
            # 获取历史数据
            hist = get_price(stock, count=30, frequency='daily', 
                           fields=['close', 'high', 'volume'])
            if len(hist) < 30:
                continue
            
            current_price = hist['close'][-1]
            high_20 = hist['high'][-20:].max()
            volume_avg = hist['volume'][-20:].mean()
            current_volume = hist['volume'][-1]
            
            # 突破条件
            if (current_price > high_20 and  # 价格突破20日最高
                current_volume > volume_avg * 1.5):  # 成交量放大1.5倍
                selected_stocks.append(stock)
                
        except:
            continue
    
    return selected_stocks

def technical_strategy_3_rsi_oversold():
    """
    策略3：RSI超卖反弹选股
    条件：RSI < 30，价格开始反弹
    """
    selected_stocks = []
    
    all_stocks = list(get_all_securities(['stock']).index)
    
    for stock in all_stocks:
        try:
            # 获取历史数据
            hist = get_price(stock, count=30, frequency='daily', fields=['close'])
            if len(hist) < 30:
                continue
            
            # 计算RSI
            rsi = calculate_rsi(hist['close'], 14)
            if len(rsi) < 2:
                continue
            
            current_rsi = rsi[-1]
            prev_rsi = rsi[-2]
            current_price = hist['close'][-1]
            prev_price = hist['close'][-2]
            
            # RSI超卖反弹条件
            if (current_rsi < 30 and  # RSI超卖
                current_rsi > prev_rsi and  # RSI开始上升
                current_price > prev_price):  # 价格开始上涨
                selected_stocks.append(stock)
                
        except:
            continue
    
    return selected_stocks

def technical_strategy_4_macd_golden_cross():
    """
    策略4：MACD金叉选股
    条件：MACD线上穿信号线
    """
    selected_stocks = []
    
    all_stocks = list(get_all_securities(['stock']).index)
    
    for stock in all_stocks:
        try:
            # 获取历史数据
            hist = get_price(stock, count=50, frequency='daily', fields=['close'])
            if len(hist) < 50:
                continue
            
            # 计算MACD
            macd_line, signal_line, histogram = calculate_macd(hist['close'])
            if len(macd_line) < 2:
                continue
            
            # MACD金叉条件
            if (macd_line[-1] > signal_line[-1] and  # 当前MACD线在信号线上方
                macd_line[-2] <= signal_line[-2]):  # 前一日MACD线在信号线下方或相等
                selected_stocks.append(stock)
                
        except:
            continue
    
    return selected_stocks

def technical_strategy_5_volume_surge():
    """
    策略5：成交量异动选股
    条件：成交量突然放大，价格配合上涨
    """
    selected_stocks = []
    
    all_stocks = list(get_all_securities(['stock']).index)
    
    for stock in all_stocks:
        try:
            # 获取历史数据
            hist = get_price(stock, count=20, frequency='daily', 
                           fields=['close', 'volume'])
            if len(hist) < 20:
                continue
            
            current_volume = hist['volume'][-1]
            volume_avg = hist['volume'][-20:].mean()
            current_price = hist['close'][-1]
            prev_price = hist['close'][-2]
            
            # 成交量异动条件
            if (current_volume > volume_avg * 2 and  # 成交量放大2倍
                current_price > prev_price):  # 价格上涨
                selected_stocks.append(stock)
                
        except:
            continue
    
    return selected_stocks

def comprehensive_technical_selection():
    """
    综合技术面选股
    结合多个技术指标，按权重评分
    """
    all_stocks = list(get_all_securities(['stock']).index)
    stock_scores = []
    
    for stock in all_stocks:
        try:
            # 获取历史数据
            hist = get_price(stock, count=50, frequency='daily', 
                           fields=['close', 'high', 'volume'])
            if len(hist) < 50:
                continue
            
            score = 0
            
            # 均线评分 (0-25分)
            ma5 = hist['close'].rolling(window=5).mean()
            ma20 = hist['close'].rolling(window=20).mean()
            if ma5[-1] > ma20[-1]:
                score += 25
            elif ma5[-1] > ma20[-1] * 0.98:  # 接近金叉
                score += 15
            
            # RSI评分 (0-20分)
            rsi = calculate_rsi(hist['close'], 14)
            if len(rsi) > 0:
                current_rsi = rsi[-1]
                if 30 < current_rsi < 70:  # 合理区间
                    score += 20
                elif current_rsi < 30:  # 超卖
                    score += 15
            
            # MACD评分 (0-20分)
            macd_line, signal_line, histogram = calculate_macd(hist['close'])
            if len(macd_line) > 0:
                if macd_line[-1] > signal_line[-1]:
                    score += 20
                elif histogram[-1] > 0:  # 柱状图为正
                    score += 10
            
            # 成交量评分 (0-20分)
            volume_avg = hist['volume'][-20:].mean()
            current_volume = hist['volume'][-1]
            if current_volume > volume_avg * 1.5:
                score += 20
            elif current_volume > volume_avg:
                score += 10
            
            # 价格动量评分 (0-15分)
            price_change = (hist['close'][-1] - hist['close'][-20]) / hist['close'][-20]
            if price_change > 0.1:  # 20日涨幅超过10%
                score += 15
            elif price_change > 0.05:  # 20日涨幅超过5%
                score += 10
            
            stock_scores.append((stock, score))
            
        except:
            continue
    
    # 按评分排序
    stock_scores.sort(key=lambda x: x[1], reverse=True)
    
    # 返回前30只股票
    return [stock for stock, score in stock_scores[:30]]

def calculate_rsi(prices, period=14):
    """
    计算RSI指标
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """
    计算MACD指标
    """
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram