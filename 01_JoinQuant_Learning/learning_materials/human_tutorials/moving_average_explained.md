# 移动平均线计算详解

## 🎯 问题：为什么 `hist_data['close'][-5:].mean()` 可以算出5日均线？

让我们逐步分解这个代码，彻底理解移动平均线的计算原理。

## 📊 数据结构理解

### 1. `hist_data` 是什么？
```python
# 假设我们获取了10天的历史数据
hist_data = get_price('000001.XSHE', count=10, frequency='daily', fields=['close'])
print(hist_data)
```

输出类似这样：
```
            close
2024-01-01  10.50
2024-01-02  10.80
2024-01-03  10.60
2024-01-04  11.20
2024-01-05  11.50
2024-01-06  11.30
2024-01-07  11.80
2024-01-08  12.00
2024-01-09  11.90
2024-01-10  12.20  ← 最新的数据
```

### 2. `hist_data['close']` 是什么？
```python
close_prices = hist_data['close']
print(close_prices)
print(type(close_prices))
```

输出：
```
2024-01-01    10.50
2024-01-02    10.80
2024-01-03    10.60
2024-01-04    11.20
2024-01-05    11.50
2024-01-06    11.30
2024-01-07    11.80
2024-01-08    12.00
2024-01-09    11.90
2024-01-10    12.20
Name: close, dtype: float64

<class 'pandas.core.series.Series'>
```

这是一个 **pandas Series**，包含了按时间排序的收盘价数据。

## 🔍 切片操作详解

### 3. `[-5:]` 是什么意思？

这是Python的**切片操作**，让我们详细理解：

```python
# 原始数据（索引从0开始）
close_prices = [10.50, 10.80, 10.60, 11.20, 11.50, 11.30, 11.80, 12.00, 11.90, 12.20]
#               索引: 0     1     2     3     4     5     6     7     8     9

# [-5:] 表示从倒数第5个元素开始，一直到最后
last_5_prices = close_prices[-5:]
print(last_5_prices)
# 输出: [11.30, 11.80, 12.00, 11.90, 12.20]
```

**负数索引解释**：
- `-1` 表示最后一个元素（最新价格）
- `-2` 表示倒数第二个元素
- `-5` 表示倒数第五个元素
- `[-5:]` 表示从倒数第五个开始到最后

### 4. 为什么要取最后5天？

移动平均线的定义：**某个时间点的N日移动平均线 = 该时间点往前N天的价格平均值**

```
日期        收盘价    5日均线计算
01-06      11.30     (10.80+10.60+11.20+11.50+11.30)/5 = 11.08
01-07      11.80     (10.60+11.20+11.50+11.30+11.80)/5 = 11.28  
01-08      12.00     (11.20+11.50+11.30+11.80+12.00)/5 = 11.56
01-09      11.90     (11.50+11.30+11.80+12.00+11.90)/5 = 11.70
01-10      12.20     (11.30+11.80+12.00+11.90+12.20)/5 = 11.84 ← 当前5日均线
```

所以，当前时间点的5日均线 = 最近5天的收盘价平均值

## 💡 `.mean()` 方法

### 5. `.mean()` 计算平均值

```python
last_5_prices = [11.30, 11.80, 12.00, 11.90, 12.20]
average = sum(last_5_prices) / len(last_5_prices)
print(average)  # 11.84

# pandas的mean()方法做的是同样的事情
import pandas as pd
series = pd.Series(last_5_prices)
print(series.mean())  # 11.84
```

## 🔬 完整代码分解

让我们用一个完整的例子来演示：

```python
# 步骤1：获取历史数据
hist_data = get_price('000001.XSHE', count=10, frequency='daily', fields=['close'])
print("历史数据：")
print(hist_data)

# 步骤2：提取收盘价列
close_prices = hist_data['close']
print("\n收盘价序列：")
print(close_prices)

# 步骤3：获取最后5天的数据
last_5_days = close_prices[-5:]
print("\n最后5天收盘价：")
print(last_5_days)
print("具体数值：", last_5_days.tolist())

# 步骤4：计算平均值
ma5 = last_5_days.mean()
print(f"\n5日均线：{ma5:.2f}")

# 验证计算
manual_calculation = sum(last_5_days) / len(last_5_days)
print(f"手动计算验证：{manual_calculation:.2f}")
```

## 📈 不同周期的移动平均线

```python
# 获取足够的历史数据
hist_data = get_price('000001.XSHE', count=30, frequency='daily', fields=['close'])
close_prices = hist_data['close']

# 计算不同周期的移动平均线
ma5 = close_prices[-5:].mean()    # 5日均线
ma10 = close_prices[-10:].mean()  # 10日均线
ma20 = close_prices[-20:].mean()  # 20日均线

print(f"5日均线：{ma5:.2f}")
print(f"10日均线：{ma10:.2f}")
print(f"20日均线：{ma20:.2f}")

# 一般规律：短期均线更接近当前价格，长期均线更平滑
current_price = close_prices.iloc[-1]
print(f"当前价格：{current_price:.2f}")
```

## 🔄 pandas的rolling()方法

虽然 `[-5:].mean()` 可以计算当前的5日均线，但如果要计算**每一天的5日均线**，更好的方法是使用pandas的 `rolling()` 方法：

```python
# 计算每一天的5日均线
hist_data = get_price('000001.XSHE', count=30, frequency='daily', fields=['close'])
close_prices = hist_data['close']

# 使用rolling方法计算移动平均线
ma5_series = close_prices.rolling(window=5).mean()
print("每天的5日均线：")
print(ma5_series.tail(10))  # 显示最后10天的5日均线

# 获取最新的5日均线（两种方法结果相同）
latest_ma5_method1 = close_prices[-5:].mean()          # 方法1
latest_ma5_method2 = ma5_series.iloc[-1]               # 方法2

print(f"\n方法1结果：{latest_ma5_method1:.2f}")
print(f"方法2结果：{latest_ma5_method2:.2f}")
print(f"结果是否相同：{abs(latest_ma5_method1 - latest_ma5_method2) < 0.001}")
```

## 🎯 实际应用示例

在聚宽策略中的典型用法：

```python
def handle_data(context, data):
    stock = '000001.XSHE'
    
    # 获取足够的历史数据
    hist_data = attribute_history(stock, 30, '1d', ['close'])
    
    # 计算移动平均线
    ma5 = hist_data['close'][-5:].mean()     # 当前5日均线
    ma20 = hist_data['close'][-20:].mean()   # 当前20日均线
    
    # 计算前一天的移动平均线（用于判断金叉死叉）
    ma5_prev = hist_data['close'][-6:-1].mean()   # 前一天的5日均线
    ma20_prev = hist_data['close'][-21:-1].mean() # 前一天的20日均线
    
    # 判断金叉（短期均线上穿长期均线）
    if ma5 > ma20 and ma5_prev <= ma20_prev:
        log.info(f"金叉信号！ma5={ma5:.2f}, ma20={ma20:.2f}")
        # 计算目标股数（100股的整数倍）
        target_shares = int(context.portfolio.total_value * 0.5 / current_price / 100) * 100
        if target_shares >= 100:
            order_target(stock, target_shares)  # 买入
    
    # 判断死叉（短期均线下穿长期均线）
    elif ma5 < ma20 and ma5_prev >= ma20_prev:
        log.info(f"死叉信号！ma5={ma5:.2f}, ma20={ma20:.2f}")
        order_target(stock, 0)    # 卖出
```

## 📚 总结

**`hist_data['close'][-5:].mean()` 能计算5日均线的原因：**

1. **`hist_data['close']`** - 获取按时间排序的收盘价序列
2. **`[-5:]`** - 取最后5个数据（最近5天）
3. **`.mean()`** - 计算这5个数据的平均值

这就是**移动平均线的定义**：某个时间点往前N天的价格平均值。

**关键理解点：**
- 数据是按时间排序的
- 负数索引从后往前数
- 移动平均线永远基于**历史数据**计算
- 最新的移动平均线使用**最近N天**的数据

这种计算方法简单直观，是量化交易中最常用的技术指标计算方式！
