# -*- coding: utf-8 -*-
"""
聚宽平台集成选股和通知系统
适用于聚宽平台的选股策略框架
"""

# 导入通知库
from notification_lib import *

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def initialize(context):
    """
    初始化聚宽选股策略框架
    """
    # 设置通知配置
    set_notification_config({
        'log_enabled': True,
        'email_enabled': False,
        'wechat_enabled': False
    })
    
    # 选股策略配置
    g.strategies = {
        'fundamental': True,      # 基本面选股
        'technical': True,        # 技术面选股
        'multi_factor': True      # 多因子选股
    }
    
    # 选股结果存储
    g.all_selected_stocks = {}
    g.final_recommendations = []
    
    # 设置运行频率
    run_monthly(integrated_stock_selection, monthday=1)
    
    log.info("聚宽选股策略框架初始化完成")
    log.info("启用的选股策略: %s" % [k for k, v in g.strategies.items() if v])

def integrated_stock_selection(context):
    """
    集成选股流程
    """
    log.info("=== 开始集成选股流程 ===")
    
    try:
        # 1. 执行各种选股策略
        all_results = {}
        
        if g.strategies.get('fundamental', False):
            log.info("执行基本面选股...")
            fundamental_stocks = run_fundamental_selection(context)
            all_results['fundamental'] = fundamental_stocks
            log.info("基本面选股完成: %d只" % len(fundamental_stocks))
        
        if g.strategies.get('technical', False):
            log.info("执行技术面选股...")
            technical_stocks = run_technical_selection(context)
            all_results['technical'] = technical_stocks
            log.info("技术面选股完成: %d只" % len(technical_stocks))
        
        if g.strategies.get('multi_factor', False):
            log.info("执行多因子选股...")
            multi_factor_stocks = run_multi_factor_selection(context)
            all_results['multi_factor'] = multi_factor_stocks
            log.info("多因子选股完成: %d只" % len(multi_factor_stocks))
        
        # 2. 综合选股结果
        final_stocks = integrate_selection_results(all_results)
        g.final_recommendations = final_stocks
        
        # 3. 生成综合报告
        report_data = generate_integrated_report(context, all_results, final_stocks)
        
        # 4. 发送选股通知
        send_stock_recommendation(final_stocks, "综合选股推荐")
        send_daily_report(report_data)
        
        # 5. 保存选股历史
        save_selection_history(context, all_results, final_stocks)
        
        log.info("=== 集成选股流程完成 ===")
        
    except Exception as e:
        log.error(f"集成选股流程出错: {e}")
        # 记录错误信息
        log.error(f"选股流程出错: {str(e)}")

def run_fundamental_selection(context):
    """
    执行基本面选股 - 请根据实际需求实现
    """
    try:
        # TODO: 在这里实现您的基本面选股逻辑
        # 参考 ai_reference/ 文件夹中的策略示例
        
        # 示例：获取所有A股
        all_stocks = list(get_all_securities(['stock']).index)
        
        # 示例：简单的市值筛选
        selected_stocks = []
        for stock in all_stocks[:100]:  # 只处理前100只作为示例
            try:
                # 获取基本信息
                stock_info = get_security_info(stock)
                if stock_info.display_name and len(stock_info.display_name) > 0:
                    selected_stocks.append(stock)
            except:
                continue
        
        # 获取股票详细信息
        stock_details = get_stock_details(selected_stocks[:20])  # 只取前20只
        
        log.info("基本面选股完成: %d只" % len(stock_details))
        return stock_details
        
    except Exception as e:
        log.error(f"基本面选股出错: {e}")
        return []

def run_technical_selection(context):
    """
    执行技术面选股 - 请根据实际需求实现
    """
    try:
        # TODO: 在这里实现您的技术面选股逻辑
        # 参考 ai_reference/ 文件夹中的策略示例
        
        # 示例：获取所有A股
        all_stocks = list(get_all_securities(['stock']).index)
        
        # 示例：简单的技术面筛选
        selected_stocks = []
        for stock in all_stocks[:100]:  # 只处理前100只作为示例
            try:
                # 获取历史数据
                hist = get_price(stock, count=20, frequency='daily', fields=['close'])
                if len(hist) >= 20:
                    # 简单的均线策略示例
                    ma5 = hist['close'][-5:].mean()
                    ma20 = hist['close'][-20:].mean()
                    current_price = hist['close'][-1]
                    
                    # 简单的技术条件
                    if current_price > ma5 and ma5 > ma20:
                        selected_stocks.append(stock)
            except:
                continue
        
        # 获取股票详细信息
        stock_details = get_stock_details(selected_stocks[:15])  # 只取前15只
        
        log.info("技术面选股完成: %d只" % len(stock_details))
        return stock_details
        
    except Exception as e:
        log.error(f"技术面选股出错: {e}")
        return []

def run_multi_factor_selection(context):
    """
    执行多因子选股 - 请根据实际需求实现
    """
    try:
        # TODO: 在这里实现您的多因子选股逻辑
        # 参考 ai_reference/ 文件夹中的策略示例
        
        # 示例：获取所有A股
        all_stocks = list(get_all_securities(['stock']).index)
        
        # 示例：简单的多因子评分
        stock_scores = []
        for stock in all_stocks[:100]:  # 只处理前100只作为示例
            try:
                # 获取基本信息
                stock_info = get_security_info(stock)
                if not stock_info.display_name:
                    continue
                
                # 简单的评分逻辑示例
                score = 50  # 基础分
                
                # 获取历史数据
                hist = get_price(stock, count=20, frequency='daily', fields=['close'])
                if len(hist) >= 20:
                    # 价格动量因子
                    price_change = (hist['close'][-1] - hist['close'][-20]) / hist['close'][-20]
                    if price_change > 0:
                        score += 20
                    
                    # 波动率因子
                    returns = hist['close'].pct_change().dropna()
                    volatility = returns.std()
                    if volatility < 0.05:  # 低波动
                        score += 10
                
                stock_scores.append((stock, score))
            except:
                continue
        
        # 按评分排序
        stock_scores.sort(key=lambda x: x[1], reverse=True)
        selected_stocks = [stock for stock, score in stock_scores[:10]]
        
        # 获取股票详细信息
        stock_details = get_stock_details(selected_stocks)
        
        log.info("多因子选股完成: %d只" % len(stock_details))
        return stock_details
        
    except Exception as e:
        log.error(f"多因子选股出错: {e}")
        return []

def get_stock_details(stocks):
    """
    获取股票详细信息
    """
    stock_details = []
    
    for stock in stocks:
        try:
            # 获取股票基本信息
            stock_info = get_security_info(stock)
            
            # 获取最新价格数据
            hist = get_price(stock, count=1, frequency='daily', 
                           fields=['close', 'high', 'low', 'volume'])
            
            if len(hist) > 0:
                current_price = hist['close'][-1]
                high_price = hist['high'][-1]
                low_price = hist['low'][-1]
                volume = hist['volume'][-1]
                
                # 计算涨跌幅（需要前一日数据）
                prev_hist = get_price(stock, count=2, frequency='daily', 
                                    fields=['close'])
                if len(prev_hist) >= 2:
                    prev_close = prev_hist['close'][-2]
                    change_pct = (current_price - prev_close) / prev_close * 100
                else:
                    change_pct = 0
                
                stock_details.append({
                    'code': stock,
                    'name': stock_info.display_name,
                    'price': current_price,
                    'high': high_price,
                    'low': low_price,
                    'volume': volume,
                    'change_pct': change_pct
                })
                
        except Exception as e:
            continue
    
    return stock_details

def integrate_selection_results(all_results):
    """
    综合选股结果
    """
    # 统计各策略选股结果
    strategy_counts = {}
    stock_votes = {}
    
    for strategy, stocks in all_results.items():
        strategy_counts[strategy] = len(stocks)
        
        for stock in stocks:
            stock_code = stock['code']
            if stock_code not in stock_votes:
                stock_votes[stock_code] = {
                    'stock': stock,
                    'votes': 0,
                    'strategies': []
                }
            
            stock_votes[stock_code]['votes'] += 1
            stock_votes[stock_code]['strategies'].append(strategy)
    
    # 按投票数排序
    sorted_stocks = sorted(stock_votes.values(), 
                         key=lambda x: x['votes'], reverse=True)
    
    # 选择前30只股票作为最终推荐
    final_stocks = []
    for item in sorted_stocks[:30]:
        stock = item['stock'].copy()
        stock['vote_count'] = item['votes']
        stock['strategies'] = ', '.join(item['strategies'])
        final_stocks.append(stock)
    
    log.info("综合选股结果:")
    log.info("各策略选股数量: %s" % strategy_counts)
    log.info("最终推荐股票: %d只" % len(final_stocks))
    
    return final_stocks

def generate_integrated_report(context, all_results, final_stocks):
    """
    生成综合选股报告
    """
    report_data = {
        'date': context.current_dt.strftime('%Y-%m-%d'),
        'total_recommendations': len(final_stocks),
        'strategy_results': {},
        'top_stocks': final_stocks[:10],  # 前10只股票
        'market_summary': get_market_summary()
    }
    
    # 各策略结果统计
    for strategy, stocks in all_results.items():
        report_data['strategy_results'][strategy] = {
            'count': len(stocks),
            'top_5': stocks[:5]
        }
    
    return report_data

def get_market_summary():
    """
    获取市场概况
    """
    try:
        # 获取主要指数数据
        indices = ['000001.SH', '399001.SZ', '399006.SZ']  # 上证、深证、创业板
        market_data = {}
        
        for index in indices:
            try:
                hist = get_price(index, count=1, frequency='daily', 
                               fields=['close'])
                if len(hist) > 0:
                    market_data[index] = {
                        'close': hist['close'][-1],
                        'change': 0  # 简化处理
                    }
            except:
                continue
        
        return market_data
        
    except Exception as e:
        return {}

def generate_selection_report(final_stocks, report_data):
    """
    生成选股报告（聚宽平台）
    """
    try:
        # 生成选股报告内容
        report_lines = ["=== 综合选股报告 ==="]
        report_lines.append("选股日期: %s" % report_data.get('date', ''))
        report_lines.append("推荐股票数量: %d只" % len(final_stocks))
        report_lines.append("")
        
        # 添加推荐股票列表
        report_lines.append("推荐股票列表:")
        for i, stock in enumerate(final_stocks[:20], 1):  # 只显示前20只
            report_lines.append("%d. %s (%s)" % (i, stock.get('name', ''), stock.get('code', '')))
            report_lines.append("   价格: ¥%.2f, 涨跌幅: %.2f%%" % 
                              (stock.get('price', 0), stock.get('change_pct', 0)))
            if 'vote_count' in stock:
                report_lines.append("   投票数: %d, 策略: %s" % 
                                  (stock.get('vote_count', 0), stock.get('strategies', '')))
            report_lines.append("")
        
        # 输出报告
        report = "\n".join(report_lines)
        log.info(report)
        
        # 保存报告到文件（聚宽平台支持）
        write_file('stock_selection_report.txt', report)
        
        log.info("选股报告生成完成")
        
    except Exception as e:
        log.error(f"生成选股报告失败: {e}")

def save_selection_history(context, all_results, final_stocks):
    """
    保存选股历史
    """
    try:
        history_entry = {
            'date': context.current_dt.strftime('%Y-%m-%d'),
            'all_results': all_results,
            'final_stocks': final_stocks,
            'timestamp': datetime.now().isoformat()
        }
        
        # 保存到全局变量
        if not hasattr(g, 'selection_history'):
            g.selection_history = []
        
        g.selection_history.append(history_entry)
        
        # 只保留最近30天的历史
        if len(g.selection_history) > 30:
            g.selection_history = g.selection_history[-30:]
        
        log.info("选股历史保存完成")
        
    except Exception as e:
        log.error(f"保存选股历史失败: {e}")

def handle_data(context, data):
    """
    每日运行，这里不做操作，专注于选股
    """
    pass

"""
使用说明：

1. 集成选股系统：
   - 结合基本面、技术面、多因子选股
   - 综合各策略结果，按投票数排序
   - 生成综合推荐报告

2. 通知系统：
   - 使用聚宽通知库发送选股推荐
   - 自动保存选股报告到文件
   - 支持日志输出

3. 选股流程：
   - 每月第一个交易日执行选股
   - 自动发送选股通知
   - 保存选股历史记录

4. 配置说明：
   - 可以启用/禁用不同选股策略
   - 可以调整选股参数
   - 可以修改通知配置

5. 优化建议：
   - 可以加入更多选股策略
   - 可以优化综合评分算法
   - 可以加入行业轮动因子
   - 可以结合宏观经济指标

使用方法：
1. 将notification_lib.py放在聚宽研究根目录
2. 复制integrated_stock_selector.py到聚宽平台运行
3. 查看选股推荐和通知
4. 根据效果调整选股参数
"""
