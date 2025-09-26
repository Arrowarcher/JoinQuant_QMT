# 聚宽API速查手册 - AI开发参考

## 📚 数据获取API

### 基础数据获取
```python
# 获取价格数据
get_price(code, count, frequency, fields)
get_price('000001.XSHE', count=20, frequency='daily', fields=['close'])

# 获取历史数据（另一种方式）
attribute_history(code, count, unit, fields)
attribute_history('000001.XSHE', 20, '1d', ['close', 'volume'])

# 获取财务数据
get_fundamentals(query)
get_fundamentals(query(valuation.pe_ratio).filter(valuation.code == '000001.XSHE'))
```

### 参数说明
- **frequency**: 'daily'(日), 'minute'(分钟), 'weekly'(周)
- **fields**: ['open', 'high', 'low', 'close', 'volume', 'money']

## 🔄 交易指令API

### 基本下单方式
```python
order(code, amount)                    # 按股数下单
order('000001.XSHE', 100)             # 买入100股
order('000001.XSHE', -100)            # 卖出100股

order_value(code, value)               # 按金额下单  
order_value('000001.XSHE', 10000)     # 买入1万元

order_target(code, amount)             # 调整到目标股数(推荐)
order_target('000001.XSHE', 1000)      # 调整到1000股
order_target('000001.XSHE', 0)         # 清仓

order_target_value(code, value)        # 调整到目标金额
order_target_value('000001.XSHE', 20000)  # 调整到2万元
```

### 限价单
```python
# 限价买入
order('000001.XSHE', 100, LimitOrderStyle(12.50))

# 市价单（默认）
order('000001.XSHE', 100, MarketOrderStyle())
```

## 📊 信息查询API

### 股票信息
```python
get_current_data()                     # 当前数据(停牌、涨跌停等)
get_security_info(code)                # 股票基本信息
get_industry(code)                     # 行业信息
get_all_securities(['stock'])          # 所有股票列表
get_index_stocks('000300.XSHG')       # 指数成分股(沪深300)
```

### 账户信息
```python
context.portfolio                      # 账户信息
  - total_value: 总资产
  - available_cash: 可用现金
  - positions_value: 持仓市值
  - starting_cash: 初始资金
  - previous_total_value: 前一日总资产

context.current_dt                     # 当前时间
g.变量名                               # 自定义全局变量
```

## 📈 技术指标计算

### 移动平均线
```python
ma5 = prices.rolling(5).mean()
ma20 = prices.rolling(20).mean()
```

### RSI指标
```python
import talib
rsi = talib.RSI(prices.values, timeperiod=14)
# RSI > 70: 超买, RSI < 30: 超卖
```

### MACD指标
```python
import talib
macd, signal, histogram = talib.MACD(prices.values)
# 金叉: macd > signal, 死叉: macd < signal
```

### 布林带
```python
import talib
upper, middle, lower = talib.BBANDS(prices.values, timeperiod=20, nbdevup=2, nbdevdn=2)
```

## 💰 财务指标

### 估值指标
```python
# PE比率
PE = 股价 / 每股收益
# PE < 15: 低估值, PE 15-25: 合理, PE > 25: 高估值

# PB比率
PB = 股价 / 每股净资产
# PB < 1: 破净, PB 1-3: 合理, PB > 3: 高估值
```

### 盈利能力指标
```python
# ROE (净资产收益率)
ROE = 净利润 / 股东权益 × 100%
# ROE > 15%: 优秀, ROE 10-15%: 良好, ROE < 10%: 一般

# ROA (总资产收益率)
ROA = 净利润 / 总资产 × 100%
# ROA > 5%: 优秀, ROA 3-5%: 良好, ROA < 3%: 一般
```

## 🧮 收益率计算

### 日收益率
```python
daily_return = (total_value / previous_total_value - 1) * 100
```

### 累计收益率
```python
total_return = (current_value / starting_cash - 1) * 100
annual_return = total_return * 365 / trading_days
```

## 🎯 常用策略模板

### 双均线策略
```python
def dual_ma_strategy(prices, short=5, long=20):
    ma_short = prices.rolling(short).mean()
    ma_long = prices.rolling(long).mean()
    
    # 金叉买入
    if ma_short.iloc[-1] > ma_long.iloc[-1] and ma_short.iloc[-2] <= ma_long.iloc[-2]:
        return "BUY"
    
    # 死叉卖出
    if ma_short.iloc[-1] < ma_long.iloc[-1] and ma_short.iloc[-2] >= ma_long.iloc[-2]:
        return "SELL"
        
    return "HOLD"
```

### RSI超买超卖策略
```python
def rsi_strategy(prices, period=14):
    rsi = talib.RSI(prices.values, timeperiod=period)
    
    if rsi[-1] < 30:        # 超卖买入
        return "BUY"
    elif rsi[-1] > 70:      # 超买卖出
        return "SELL"
    else:
        return "HOLD"
```

### 布林带突破策略
```python
def bollinger_strategy(prices, period=20):
    upper, middle, lower = talib.BBANDS(prices.values, timeperiod=period)
    current_price = prices.iloc[-1]
    
    if current_price > upper[-1]:      # 突破上轨
        return "SELL"  # 可能回调
    elif current_price < lower[-1]:    # 跌破下轨  
        return "BUY"   # 可能反弹
    else:
        return "HOLD"
```

## ⚠️ 注意事项

### 技术指标
- 结合多个指标确认信号
- 关注市场环境差异
- 参数调优适应不同股票
- 过滤假信号

### 财务指标
- 行业对比分析
- 关注趋势变化
- 数据质量验证
- 考虑周期影响