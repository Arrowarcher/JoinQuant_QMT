# -*- coding: utf-8 -*-
"""
聚宽策略框架结构详解
目标：深入理解聚宽策略的基本结构和语法
"""

# ===== 1. 导入库 =====
# 聚宽平台已经预装了常用库，可以直接使用
import pandas as pd
import numpy as np
import talib  # 技术分析库
from datetime import datetime, timedelta

def initialize(context):
    """
    【策略框架核心函数1】初始化函数
    
    作用：策略启动时运行一次，用于设置策略参数
    参数：context - 策略全局变量容器
    运行时机：策略开始时执行一次
    """
    
    # ===== 全局变量设置 =====
    # 使用 g. 来设置全局变量，可以在其他函数中使用
    g.stocks = ['000001.XSHE', '000002.XSHE', '600036.XSHG']  # 股票池
    g.max_stocks = 3          # 最大持仓股票数
    g.rebalance_period = 20   # 调仓周期（天）
    g.last_rebalance = None   # 上次调仓日期
    
    # ===== 基准设置 =====
    set_benchmark('000300.XSHG')  # 设置基准为沪深300
    
    # ===== 手续费设置 =====
    set_order_cost(OrderCost(
        close_tax=0.001,      # 印花税
        open_commission=0.0003,  # 买入手续费
        close_commission=0.0003, # 卖出手续费
        min_commission=5      # 最低手续费
    ), type='stock')
    
    # ===== 股票池过滤 =====
    # 过滤掉ST股票、停牌股票等
    g.stock_filter = True
    
    # ===== 日志输出 =====
    log.info("=== 策略初始化完成 ===")
    log.info("股票池: %s" % g.stocks)
    log.info("最大持仓数: %d" % g.max_stocks)
    log.info("调仓周期: %d天" % g.rebalance_period)

def before_trading_start(context):
    """
    【策略框架核心函数2】开盘前函数
    
    作用：每个交易日开盘前运行，用于盘前准备工作
    参数：context - 策略全局变量容器  
    运行时机：每个交易日开盘前（9:30前）
    """
    
    # ===== 获取当前日期 =====
    current_date = context.current_dt.date()
    log.info("今日日期: %s" % current_date)
    
    # ===== 股票池过滤 =====
    if g.stock_filter:
        g.filtered_stocks = filter_stocks(g.stocks)
        log.info("过滤后可交易股票: %d只" % len(g.filtered_stocks))
    else:
        g.filtered_stocks = g.stocks
    
    # ===== 检查调仓时机 =====
    should_rebalance = check_rebalance_timing(context)
    if should_rebalance:
        log.info("今日需要调仓")
        g.need_rebalance = True
    else:
        g.need_rebalance = False

def handle_data(context, data):
    """
    【策略框架核心函数3】主策略函数
    
    作用：核心策略逻辑，每个bar运行一次
    参数：
        context - 策略全局变量容器
        data - 当前时间点的市场数据
    运行时机：每个交易周期（分钟/日）
    """
    
    # ===== 策略执行频率控制 =====
    # 只在需要调仓时执行策略
    if not g.need_rebalance:
        return
    
    log.info("=== 开始执行策略逻辑 ===")
    
    # ===== 1. 数据获取和处理 =====
    stock_data = prepare_stock_data(context, data)
    
    # ===== 2. 信号生成 =====
    signals = generate_trading_signals(stock_data)
    
    # ===== 3. 仓位管理 =====
    target_positions = calculate_target_positions(context, signals)
    
    # ===== 4. 执行交易 =====
    execute_trades(context, target_positions)
    
    # ===== 5. 更新状态 =====
    g.last_rebalance = context.current_dt.date()
    g.need_rebalance = False
    
    log.info("=== 策略执行完成 ===")

def after_trading_end(context):
    """
    【策略框架核心函数4】收盘后函数
    
    作用：每个交易日收盘后运行，用于日终处理
    参数：context - 策略全局变量容器
    运行时机：每个交易日收盘后（15:00后）
    """
    
    # ===== 账户信息统计 =====
    portfolio_summary = get_portfolio_summary(context)
    
    # ===== 持仓信息记录 =====
    positions_info = get_positions_info(context)
    
    # ===== 绩效分析 =====
    performance_analysis(context)
    
    # ===== 日志记录 =====
    log.info("=== 交易日结束 ===")
    log.info("总资产: %.2f" % portfolio_summary['total_value'])
    log.info("可用资金: %.2f" % portfolio_summary['available_cash'])
    log.info("持仓数量: %d" % portfolio_summary['positions_count'])
    log.info("当日收益率: %.2f%%" % portfolio_summary['daily_return'])

# ===== 辅助函数定义 =====

def filter_stocks(stock_list):
    """
    股票过滤函数
    过滤掉ST股票、停牌股票等不适合交易的股票
    """
    filtered = []
    current_data = get_current_data()
    
    for stock in stock_list:
        stock_info = current_data[stock]
        
        # 检查是否停牌
        if stock_info.paused:
            continue
            
        # 检查是否为ST股票
        if 'ST' in stock_info.name or '*ST' in stock_info.name:
            continue
            
        # 检查是否为新股（上市不足60天）
        if stock_info.start_date and (context.current_dt.date() - stock_info.start_date).days < 60:
            continue
            
        filtered.append(stock)
    
    return filtered

def check_rebalance_timing(context):
    """
    检查是否需要调仓
    """
    if g.last_rebalance is None:
        return True  # 首次运行需要调仓
    
    # 计算距离上次调仓的天数
    days_since_rebalance = (context.current_dt.date() - g.last_rebalance).days
    
    return days_since_rebalance >= g.rebalance_period

def prepare_stock_data(context, data):
    """
    准备股票数据用于分析
    """
    stock_data = {}
    
    for stock in g.filtered_stocks:
        try:
            # 获取历史数据
            hist_data = attribute_history(stock, 30, '1d', 
                                        ['close', 'high', 'low', 'volume'])
            
            # 获取当前价格
            current_price = data[stock].close
            
            # 计算技术指标
            ma5 = hist_data['close'].rolling(5).mean().iloc[-1]
            ma20 = hist_data['close'].rolling(20).mean().iloc[-1]
            
            # 使用talib计算RSI
            rsi = talib.RSI(hist_data['close'].values)[-1]
            
            stock_data[stock] = {
                'current_price': current_price,
                'ma5': ma5,
                'ma20': ma20,
                'rsi': rsi,
                'volume': data[stock].volume
            }
            
        except Exception as e:
            log.warning("获取 %s 数据失败: %s" % (stock, str(e)))
            continue
    
    return stock_data

def generate_trading_signals(stock_data):
    """
    生成交易信号
    """
    signals = {}
    
    for stock, data in stock_data.items():
        score = 0
        
        # 信号1：均线信号
        if data['ma5'] > data['ma20']:
            score += 1
        
        # 信号2：RSI信号
        if 30 < data['rsi'] < 70:  # RSI在合理区间
            score += 1
        
        # 信号3：价格位置
        if data['current_price'] > data['ma5']:
            score += 1
        
        # 根据得分确定信号强度
        if score >= 2:
            signals[stock] = 'BUY'
        elif score <= 1:
            signals[stock] = 'SELL'
        else:
            signals[stock] = 'HOLD'
    
    return signals

def calculate_target_positions(context, signals):
    """
    计算目标仓位
    """
    # 统计买入信号的股票
    buy_stocks = [stock for stock, signal in signals.items() if signal == 'BUY']
    
    # 限制最大持仓数
    buy_stocks = buy_stocks[:g.max_stocks]
    
    # 计算每只股票的目标权重
    if buy_stocks:
        weight_per_stock = 0.95 / len(buy_stocks)  # 保留5%现金
    else:
        weight_per_stock = 0
    
    # 构建目标仓位字典
    target_positions = {}
    for stock in g.stocks:
        if stock in buy_stocks:
            target_positions[stock] = weight_per_stock
        else:
            target_positions[stock] = 0
    
    return target_positions

def execute_trades(context, target_positions):
    """
    执行交易指令
    """
    for stock, target_weight in target_positions.items():
        try:
            # 使用order_target进行交易
            target_shares = int(context.portfolio.total_value * target_weight / current_price / 100) * 100
            if target_shares >= 100:
                order_target(stock, target_shares)
            
            if target_weight > 0:
                log.info("买入 %s，目标权重: %.1f%%" % (stock, target_weight * 100))
            else:
                current_position = context.portfolio.positions[stock]
                if current_position.total_amount > 0:
                    log.info("卖出 %s" % stock)
                    
        except Exception as e:
            log.error("交易 %s 失败: %s" % (stock, str(e)))

def get_portfolio_summary(context):
    """
    获取组合摘要信息
    """
    portfolio = context.portfolio
    
    return {
        'total_value': portfolio.total_value,
        'available_cash': portfolio.available_cash,
        'positions_count': len([s for s in portfolio.positions 
                               if portfolio.positions[s].total_amount > 0]),
        'daily_return': (portfolio.total_value / portfolio.previous_total_value - 1) * 100
    }

def get_positions_info(context):
    """
    获取持仓详细信息
    """
    positions = context.portfolio.positions
    positions_info = []
    
    for stock in positions:
        pos = positions[stock]
        if pos.total_amount > 0:
            positions_info.append({
                'stock': stock,
                'amount': pos.total_amount,
                'value': pos.value,
                'avg_cost': pos.avg_cost,
                'price': pos.price
            })
    
    return positions_info

def performance_analysis(context):
    """
    简单的绩效分析
    """
    portfolio = context.portfolio
    
    # 计算累计收益率
    total_return = (portfolio.total_value / portfolio.starting_cash - 1) * 100
    
    # 每月输出一次绩效
    if context.current_dt.day == 1:  # 每月1日
        log.info("=== 月度绩效报告 ===")
        log.info("累计收益率: %.2f%%" % total_return)
        log.info("当前总资产: %.2f" % portfolio.total_value)

"""
===== 聚宽策略框架总结 =====

1. 【核心函数结构】
   initialize(context)         - 初始化（运行1次）
   before_trading_start(context) - 开盘前（每日1次）
   handle_data(context, data)   - 主策略（每bar1次）  
   after_trading_end(context)   - 收盘后（每日1次）

2. 【重要对象】
   context - 策略上下文，包含账户、持仓等信息
   data - 当前时间点的市场数据
   g - 全局变量容器，用于存储策略参数

3. 【核心API】
   数据获取：get_price(), attribute_history(), get_fundamentals()
   交易指令：order(), order_target(), order_value()
   信息查询：get_current_data(), get_security_info()

4. 【最佳实践】
   - 在initialize中设置策略参数
   - 在before_trading_start中做盘前准备
   - 在handle_data中实现核心策略逻辑
   - 使用异常处理保证策略稳定性
   - 合理使用日志记录策略运行状态

5. 【调试技巧】
   - 使用log.info()输出关键信息
   - 分步骤验证策略逻辑
   - 先用少量股票测试
   - 关注回测结果中的交易记录
"""
