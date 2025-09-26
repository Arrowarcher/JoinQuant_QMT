# 聚宽策略框架结构详解

## 🏗️ 策略框架总览

聚宽的策略就像一个有固定作息时间的交易员：

```
早上起床 → 开盘前准备 → 盘中交易 → 收盘后总结 → 睡觉
    ↓           ↓         ↓        ↓
initialize → before_trading_start → handle_data → after_trading_end
```

## 📋 核心函数详解

### 1. initialize(context) - 策略初始化
**就像交易员的入职培训**

```python
def initialize(context):
    # 设置策略参数（就像制定交易计划）
    g.stocks = ['000001.XSHE', '000002.XSHE']  # 我要交易哪些股票
    g.max_stocks = 3                           # 最多持有几只股票
    g.rebalance_days = 20                      # 多少天调整一次仓位
    
    # 设置基准（就像选择一个比较对象）
    set_benchmark('000300.XSHG')               # 和沪深300比较
    
    # 设置手续费（模拟真实交易成本）
    set_order_cost(OrderCost(
        close_tax=0.001,         # 印花税 0.1%
        open_commission=0.0003,  # 买入手续费 0.03%
        close_commission=0.0003, # 卖出手续费 0.03%
        min_commission=5         # 最低手续费 5元
    ), type='stock')
```

**关键点**：
- 只运行**一次**，在策略开始时
- 用来设置策略的**基本参数**
- 类似于写交易计划书

### 2. before_trading_start(context) - 开盘前准备
**就像交易员每天早上的准备工作**

```python
def before_trading_start(context):
    # 检查今天的市场情况
    current_date = context.current_dt.date()
    log.info("今天是: %s" % current_date)
    
    # 过滤股票池（去掉停牌、ST等不能交易的股票）
    g.tradeable_stocks = []
    for stock in g.stocks:
        if not get_current_data()[stock].paused:  # 没有停牌
            g.tradeable_stocks.append(stock)
    
    # 检查是否需要调仓
    if should_rebalance_today(context):
        g.need_rebalance = True
        log.info("今天需要调仓")
```

**关键点**：
- **每个交易日**运行一次
- 在**开盘前**（9:30之前）执行
- 用来做**盘前准备**工作

### 3. handle_data(context, data) - 核心策略逻辑
**就像交易员的核心工作时间**

```python
def handle_data(context, data):
    # 只在需要调仓时执行
    if not g.need_rebalance:
        return
    
    # 1. 获取数据
    for stock in g.tradeable_stocks:
        current_price = data[stock].close  # 当前价格
        
        # 获取历史数据计算指标
        hist_data = attribute_history(stock, 20, '1d', ['close'])
        ma5 = hist_data['close'][-5:].mean()   # 5日均线
        ma20 = hist_data['close'][-20:].mean() # 20日均线
        
        # 2. 判断买卖信号
        if ma5 > ma20:  # 金叉，买入信号
            # 计算目标股数（100股的整数倍）
            target_shares = int(context.portfolio.total_value * 0.3 / current_price / 100) * 100
            if target_shares >= 100:
                order_target(stock, target_shares)  # 买入，占总资产30%
            log.info("买入 %s" % stock)
        elif ma5 < ma20:  # 死叉，卖出信号
            order_target(stock, 0)    # 卖出，仓位清零
            log.info("卖出 %s" % stock)
```

**关键点**：
- 这是**策略的核心**，最重要的函数
- 根据设置的频率运行（可以是每分钟、每小时、每天）
- 包含**策略的所有逻辑**：数据获取、信号生成、下单交易

### 4. after_trading_end(context) - 收盘后总结
**就像交易员的每日总结**

```python
def after_trading_end(context):
    # 计算今天的表现
    portfolio = context.portfolio
    daily_return = (portfolio.total_value / portfolio.previous_total_value - 1) * 100
    
    # 统计持仓
    positions_count = len([s for s in portfolio.positions 
                          if portfolio.positions[s].total_amount > 0])
    
    # 记录日志
    log.info("=== 今日交易总结 ===")
    log.info("总资产: %.2f" % portfolio.total_value)
    log.info("今日收益率: %.2f%%" % daily_return)
    log.info("持仓数量: %d只" % positions_count)
```

**关键点**：
- **每个交易日**运行一次
- 在**收盘后**（15:00之后）执行
- 用来做**日终总结**和记录

## 🎯 重要对象详解

### context对象 - 策略上下文
就像交易员的工作台，包含所有需要的信息：

```python
# 账户信息
context.portfolio.total_value      # 总资产
context.portfolio.available_cash   # 可用现金
context.portfolio.positions        # 持仓信息

# 时间信息
context.current_dt                 # 当前时间
context.portfolio.start_date       # 策略开始日期

# 其他信息
context.universe                   # 股票池
```

### data对象 - 市场数据
就像实时行情屏，显示当前价格：

```python
# 获取单只股票数据
stock = '000001.XSHE'
data[stock].open      # 开盘价
data[stock].high      # 最高价
data[stock].low       # 最低价
data[stock].close     # 收盘价（当前价）
data[stock].volume    # 成交量
```

### g对象 - 全局变量
就像交易员的笔记本，记录重要信息：

```python
# 在initialize中设置
g.stocks = ['000001.XSHE', '000002.XSHE']
g.max_positions = 3
g.last_rebalance_date = None

# 在其他函数中使用
if len(g.stocks) > g.max_positions:
    # 做某些处理
```

## 📚 核心API速查

> 详细的API说明请查看：[joinquant_api_reference.md](../ai_reference/joinquant_api_reference.md)

## 💡 最佳实践

### 1. 策略结构建议
```python
def initialize(context):
    # 参数设置
    # 基准设置  
    # 手续费设置
    pass

def before_trading_start(context):
    # 股票过滤
    # 调仓时机判断
    pass

def handle_data(context, data):
    # 频率控制
    if not should_trade():
        return
    
    # 数据获取
    # 信号生成
    # 仓位计算
    # 执行交易
    pass

def after_trading_end(context):
    # 绩效统计
    # 日志记录
    pass
```

### 2. 常见错误避免
```python
# ❌ 错误：每次都重复计算
def handle_data(context, data):
    for stock in all_stocks:  # 太多股票，计算慢
        calculate_complex_indicator(stock)

# ✅ 正确：合理控制计算量
def handle_data(context, data):
    if not need_rebalance():  # 不需要时直接返回
        return
    
    for stock in filtered_stocks[:10]:  # 限制股票数量
        calculate_indicator(stock)
```

### 3. 调试技巧
```python
# 使用log.info()输出关键信息
log.info("当前股票池: %s" % g.stocks)
log.info("买入信号: %s, 价格: %.2f" % (stock, price))

# 分步验证策略逻辑
if ma5 > ma20:
    log.info("%s 金叉：ma5=%.2f, ma20=%.2f" % (stock, ma5, ma20))
    # 执行买入逻辑
```

## 🎓 学习建议

### 第一步：理解框架
1. 先理解4个核心函数的作用
2. 明白每个函数的运行时机
3. 搞清楚context、data、g的区别

### 第二步：熟悉API
1. 从简单的数据获取开始
2. 练习基本的交易指令
3. 学会查询股票信息

### 第三步：编写策略
1. 从简单的双均线策略开始
2. 逐步增加复杂度
3. 关注风险控制

### 第四步：优化改进
1. 分析回测结果
2. 优化参数设置
3. 改进策略逻辑

记住：**量化交易的本质是将交易逻辑程序化，聚宽框架帮你解决了技术问题，让你专注于策略本身！**
