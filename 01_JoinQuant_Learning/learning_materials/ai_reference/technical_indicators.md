# 技术指标计算参考

## 📊 移动平均线 (MA)

### 计算公式
```
MA(n) = (P1 + P2 + ... + Pn) / n
```

### 聚宽实现
```python
# 简单移动平均线
ma5 = prices.rolling(5).mean()
ma20 = prices.rolling(20).mean()

# 指数移动平均线
ema12 = prices.ewm(span=12).mean()
ema26 = prices.ewm(span=26).mean()
```

### 应用场景
- **金叉**: MA5 > MA20 且 前一日 MA5 <= MA20
- **死叉**: MA5 < MA20 且 前一日 MA5 >= MA20

## 📈 RSI相对强弱指标

### 计算公式
```
RSI = 100 - 100/(1 + RS)
RS = 平均上涨幅度 / 平均下跌幅度
```

### 聚宽实现
```python
import talib
rsi = talib.RSI(prices.values, timeperiod=14)
```

### 判断标准
- RSI > 70: 超买区域
- RSI < 30: 超卖区域
- RSI 30-70: 正常区间

## 📊 MACD指标

### 计算公式
```
MACD = EMA12 - EMA26
Signal = MACD的9日EMA
Histogram = MACD - Signal
```

### 聚宽实现
```python
import talib
macd, signal, histogram = talib.MACD(prices.values)
```

### 交易信号
- **金叉**: MACD > Signal 且 前一日 MACD <= Signal
- **死叉**: MACD < Signal 且 前一日 MACD >= Signal

## 📊 布林带 (Bollinger Bands)

### 计算公式
```
上轨 = 20日均线 + 2倍标准差
中轨 = 20日均线
下轨 = 20日均线 - 2倍标准差
```

### 聚宽实现
```python
import talib
upper, middle, lower = talib.BBANDS(prices.values, timeperiod=20, nbdevup=2, nbdevdn=2)
```

### 应用策略
- 价格突破上轨: 可能回调
- 价格跌破下轨: 可能反弹
- 布林带收窄: 变盘在即

## 📊 KDJ指标

### 计算公式
```
K = (C - L9) / (H9 - L9) * 100
D = K的3日移动平均
J = 3K - 2D
```

### 聚宽实现
```python
import talib
k, d, j = talib.STOCH(high.values, low.values, close.values)
```

### 判断标准
- K > 80, D > 80: 超买
- K < 20, D < 20: 超卖
- K上穿D: 买入信号
- K下穿D: 卖出信号

## 📊 成交量指标

### 成交量移动平均
```python
volume_ma5 = volume.rolling(5).mean()
volume_ma20 = volume.rolling(20).mean()
```

### 量价关系
```python
# 放量上涨
if close > close.shift(1) and volume > volume_ma5 * 1.5:
    strong_uptrend = True

# 缩量下跌
if close < close.shift(1) and volume < volume_ma5 * 0.8:
    weak_downtrend = True
```

## 📊 综合指标应用

### 多指标确认
```python
def multi_indicator_signal(prices):
    # 计算多个指标
    ma5 = prices.rolling(5).mean()
    ma20 = prices.rolling(20).mean()
    rsi = talib.RSI(prices.values, timeperiod=14)
    macd, signal, _ = talib.MACD(prices.values)
    
    # 综合判断
    if (ma5.iloc[-1] > ma20.iloc[-1] and 
        rsi[-1] > 50 and 
        macd[-1] > signal[-1]):
        return "BUY"
    elif (ma5.iloc[-1] < ma20.iloc[-1] and 
          rsi[-1] < 50 and 
          macd[-1] < signal[-1]):
        return "SELL"
    else:
        return "HOLD"
```

## 📊 指标参数优化

### 常用参数组合
```python
# 短线参数
short_params = {
    'ma_short': 5,
    'ma_long': 10,
    'rsi_period': 14,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9
}

# 中线参数
medium_params = {
    'ma_short': 10,
    'ma_long': 20,
    'rsi_period': 14,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9
}

# 长线参数
long_params = {
    'ma_short': 20,
    'ma_long': 50,
    'rsi_period': 21,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9
}
```
