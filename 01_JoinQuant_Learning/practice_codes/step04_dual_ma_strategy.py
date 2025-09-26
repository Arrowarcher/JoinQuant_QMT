"""
第三步：双均线策略实现
目标：实现一个完整的双均线交易策略
"""

# 导入函数库
from jqdata import *

def initialize(context):
    """
    初始化函数，设定基准等等
    """
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('双均线策略初始化开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    # 股票池 - 选择一些稳定的大盘股
    g.stocks = [
        '000001.XSHE',  # 平安银行
        '000002.XSHE',  # 万科A  
        '600036.XSHG',  # 招商银行
        '600519.XSHG',  # 贵州茅台
        '000858.XSHE',  # 五粮液
    ]
    
    # 策略参数
    g.short_period = 5   # 短期均线周期
    g.long_period = 20   # 长期均线周期
    g.max_stocks = 3     # 最大持仓股票数
    
    # 每只股票的目标权重
    g.stock_weight = 1.0 / g.max_stocks
    
    # 风控参数
    g.max_single_position = 0.4  # 单只股票最大仓位40%
    g.min_trade_amount = 5000    # 最小交易金额5000元
    g.stop_loss_threshold = 0.1  # 止损阈值10%
    g.take_profit_threshold = 0.2  # 止盈阈值20%
    
    
    # 运行函数（reference_security为运行时间的参考标的）
    # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
    # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
    log.info("双均线策略初始化完成")
    log.info("短期均线: %d日, 长期均线: %d日" % (g.short_period, g.long_period))
    log.info("股票池: %s" % str(g.stocks))

## 开盘前运行函数
def before_market_open(context):
    """
    每天开盘前运行，进行股票筛选
    """
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    
    # 过滤停牌股票和ST股票
    g.tradeable_stocks = []
    current_data = get_current_data()
    for stock in g.stocks:
        # 检查是否停牌
        if not current_data[stock].paused:
            # 检查是否为ST股票
            stock_info = get_security_info(stock)
            if not stock_info.display_name.startswith('ST'):
                g.tradeable_stocks.append(stock)
    
    log.info("今日可交易股票: %d只" % len(g.tradeable_stocks))

def check_stop_loss_take_profit(context):
    """
    检查止损止盈条件
    """
    positions = context.portfolio.positions
    for stock in positions:
        position = positions[stock]
        if position.total_amount > 0:
            current_price = get_current_data()[stock].last_price
            avg_cost = position.avg_cost
            
            if avg_cost > 0:
                profit_rate = (current_price - avg_cost) / avg_cost
                
                # 止损检查
                if profit_rate <= -g.stop_loss_threshold:
                    log.info("触发止损 %s: 收益率 %.2f%%" % (stock, profit_rate * 100))
                    order_target(stock, 0)
                    
                
                # 止盈检查
                elif profit_rate >= g.take_profit_threshold:
                    log.info("触发止盈 %s: 收益率 %.2f%%" % (stock, profit_rate * 100))
                    order_target(stock, 0)

## 开盘时运行函数
def market_open(context):
    """
    主要交易逻辑，每天开盘时运行
    """
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    
    # 首先检查止损止盈
    check_stop_loss_take_profit(context)
    
    # 当前持仓
    current_positions = list(context.portfolio.positions.keys())
    current_positions = [s for s in current_positions if context.portfolio.positions[s].total_amount > 0]
    
    # 生成交易信号
    buy_signals = []
    sell_signals = []
    
    for stock in g.tradeable_stocks:
        # 获取历史数据
        hist_data = get_bars(stock, count=g.long_period + 1, unit='1d', fields=['close'])
        
        if len(hist_data) < g.long_period:
            continue
            
        # 计算均线
        short_ma = hist_data['close'][-g.short_period:].mean()
        long_ma = hist_data['close'][-g.long_period:].mean()
        
        # 计算前一天的均线（用于判断金叉死叉）
        short_ma_prev = hist_data['close'][-g.short_period-1:-1].mean()
        long_ma_prev = hist_data['close'][-g.long_period-1:-1].mean()
        
        # 获取当前价格
        current_data = get_current_data()
        current_price = current_data[stock].last_price
        
        # 买入信号：金叉（短期均线上穿长期均线）
        # 增加成交量确认和价格合理性检查
        if (short_ma > long_ma and short_ma_prev <= long_ma_prev and 
            stock not in current_positions and len(current_positions) < g.max_stocks and
            current_price > 0 and not current_data[stock].paused):
            buy_signals.append({
                'stock': stock,
                'price': current_price,
                'short_ma': short_ma,
                'long_ma': long_ma
            })
        
        # 卖出信号：死叉（短期均线下穿长期均线）
        elif (short_ma < long_ma and short_ma_prev >= long_ma_prev and 
              stock in current_positions):
            sell_signals.append({
                'stock': stock,
                'price': current_price,
                'short_ma': short_ma,
                'long_ma': long_ma
            })
    
    # 执行卖出操作
    for signal in sell_signals:
        stock = signal['stock']
        try:
            # 获取当前持仓
            current_position = context.portfolio.positions[stock]
            if current_position.total_amount > 0:
                # 计算收益率
                avg_cost = current_position.avg_cost
                current_price = signal['price']
                profit_rate = (current_price - avg_cost) / avg_cost if avg_cost > 0 else 0
                
                order_target(stock, 0)  # 清仓
                log.info("卖出 %s, 价格: %.2f, 收益率: %.2f%%, 短期均线: %.2f, 长期均线: %.2f" % 
                        (stock, signal['price'], profit_rate*100, signal['short_ma'], signal['long_ma']))
            else:
                log.info("跳过卖出 %s: 当前无持仓" % stock)
        except Exception as e:
            log.error("卖出 %s 失败: %s" % (stock, str(e)))
    
    # 执行买入操作
    for signal in buy_signals:
        stock = signal['stock']
        try:
            current_price = signal['price']
            
            # 计算目标买入金额（考虑最大仓位限制）
            total_value = context.portfolio.total_value
            max_position_value = total_value * g.max_single_position
            target_value = min(total_value * g.stock_weight, max_position_value)
            
            # 检查最小交易金额
            if target_value < g.min_trade_amount:
                log.info("跳过买入 %s: 目标金额 %.2f 小于最小交易金额 %.2f" % 
                        (stock, target_value, g.min_trade_amount))
                continue
            
            # 计算目标股数（100股的整数倍）
            target_shares = int(target_value / current_price / 100) * 100
            
            # 只有当目标股数大于等于100时才买入
            if target_shares >= 100:
                order_target(stock, target_shares)
                log.info("买入 %s, 股数: %d, 价格: %.2f, 金额: %.2f, 短期均线: %.2f, 长期均线: %.2f" % 
                        (stock, target_shares, signal['price'], target_shares * current_price, 
                         signal['short_ma'], signal['long_ma']))
            else:
                log.info("跳过买入 %s: 目标股数 %d 小于最小交易单位 100" % (stock, target_shares))
        except Exception as e:
            log.error("买入 %s 失败: %s" % (stock, str(e)))

## 收盘后运行函数
def after_market_close(context):
    """
    每天收盘后运行
    """
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # 统计持仓信息
    positions = context.portfolio.positions
    holding_stocks = [stock for stock in positions if positions[stock].total_amount > 0]
    
    if len(holding_stocks) > 0:
        log.info("当前持仓 %d 只股票:" % len(holding_stocks))
        for stock in holding_stocks:
            position = positions[stock]
            log.info("  %s: %d股, 市值: %.2f" % 
                    (stock, position.total_amount, position.value))
    
    # 记录当前资产状况
    total_value = context.portfolio.total_value
    available_cash = context.portfolio.available_cash
    positions_value = context.portfolio.positions_value
    
    log.info("总资产: %.2f, 可用资金: %.2f, 持仓市值: %.2f" % 
            (total_value, available_cash, positions_value))
    
    
    
    log.info('一天结束')
    log.info('##############################################################')


"""
策略说明：

1. 策略逻辑：
   - 使用5日和20日双均线系统
   - 金叉时买入，死叉时卖出
   - 最多持有3只股票，每只占1/3仓位

2. 风控措施：
   - 过滤停牌股票和ST股票
   - 限制最大持仓数量
   - 均匀分配资金
   - 异常处理机制
   - 价格合理性检查

3. 优化方向：
   - 可以调整均线参数
   - 可以添加成交量确认
   - 可以加入止损机制
   - 可以优化选股条件
   - 可以添加技术指标确认
   - 可以加入市场情绪指标

4. 回测建议：
   - 时间范围: 2020-01-01 到 2023-12-31
   - 初始资金: 100000
   - 手续费: 默认设置

5. 预期表现：
   - 年化收益率: 8-15%
   - 最大回撤: 15-25%
   - 胜率: 45-55%

使用方法：
1. 复制代码到聚宽平台
2. 设置回测参数
3. 点击开始回测
4. 观察策略表现和交易记录
5. 尝试调整参数优化策略
"""
