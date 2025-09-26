# -*- coding: utf-8 -*-
"""
基本面选股策略参考
AI可以参考这些策略实现，但实际使用时需要根据具体需求调整
"""

def fundamental_strategy_1_roe_pe():
    """
    策略1：ROE + PE 选股
    选股标准：ROE > 15%, PE < 30
    """
    # 构建查询条件
    q = query(
        valuation.code,
        valuation.pe_ratio,
        indicator.roe
    ).filter(
        valuation.pe_ratio > 0,
        valuation.pe_ratio < 30,
        indicator.roe > 15
    )
    
    # 获取财务数据
    df = get_fundamentals(q)
    return df['code'].tolist()

def fundamental_strategy_2_growth():
    """
    策略2：成长股选股
    选股标准：营收增长 > 20%, 净利润增长 > 15%
    """
    q = query(
        valuation.code,
        indicator.inc_revenue_year_on_year,
        indicator.inc_net_profit_year_on_year
    ).filter(
        indicator.inc_revenue_year_on_year > 20,
        indicator.inc_net_profit_year_on_year > 15
    )
    
    df = get_fundamentals(q)
    return df['code'].tolist()

def fundamental_strategy_3_value():
    """
    策略3：价值股选股
    选股标准：PB < 2, PE < 20, 股息率 > 3%
    """
    q = query(
        valuation.code,
        valuation.pb_ratio,
        valuation.pe_ratio,
        indicator.dividend_yield
    ).filter(
        valuation.pb_ratio < 2,
        valuation.pe_ratio < 20,
        indicator.dividend_yield > 3
    )
    
    df = get_fundamentals(q)
    return df['code'].tolist()

def fundamental_strategy_4_quality():
    """
    策略4：质量股选股
    选股标准：ROE > 20%, 负债率 < 50%, 毛利率 > 30%
    """
    q = query(
        valuation.code,
        indicator.roe,
        balance.total_liability,
        balance.total_assets,
        income.gross_profit_margin
    ).filter(
        indicator.roe > 20
    )
    
    df = get_fundamentals(q)
    if not df.empty:
        # 计算负债率
        df['debt_ratio'] = df['total_liability'] / df['total_assets']
        df = df[(df['debt_ratio'] < 0.5) & (df['gross_profit_margin'] > 30)]
    
    return df['code'].tolist()

def fundamental_strategy_5_industry_leader():
    """
    策略5：行业龙头选股
    选股标准：市值前20%, ROE > 10%
    """
    # 获取市值数据
    q = query(
        valuation.code,
        valuation.market_cap,
        indicator.roe
    ).filter(
        indicator.roe > 10
    )
    
    df = get_fundamentals(q)
    if not df.empty:
        # 按市值排序，取前20%
        df = df.sort_values('market_cap', ascending=False)
        top_20_percent = int(len(df) * 0.2)
        df = df.head(top_20_percent)
    
    return df['code'].tolist()

def comprehensive_fundamental_selection():
    """
    综合基本面选股
    结合多个策略，按权重评分
    """
    # 获取基础数据
    q = query(
        valuation.code,
        valuation.pe_ratio,
        valuation.pb_ratio,
        indicator.roe,
        indicator.inc_revenue_year_on_year,
        indicator.inc_net_profit_year_on_year,
        balance.total_liability,
        balance.total_assets
    )
    
    df = get_fundamentals(q)
    if df.empty:
        return []
    
    # 计算负债率
    df['debt_ratio'] = df['total_liability'] / df['total_assets']
    
    # 评分系统
    scores = []
    for _, row in df.iterrows():
        score = 0
        
        # ROE评分 (0-30分)
        if row['roe'] > 20:
            score += 30
        elif row['roe'] > 15:
            score += 20
        elif row['roe'] > 10:
            score += 10
        
        # PE评分 (0-20分)
        if 0 < row['pe_ratio'] < 15:
            score += 20
        elif 15 <= row['pe_ratio'] < 25:
            score += 15
        elif 25 <= row['pe_ratio'] < 35:
            score += 10
        
        # 营收增长评分 (0-20分)
        if row['inc_revenue_year_on_year'] > 30:
            score += 20
        elif row['inc_revenue_year_on_year'] > 20:
            score += 15
        elif row['inc_revenue_year_on_year'] > 10:
            score += 10
        
        # 负债率评分 (0-15分)
        if row['debt_ratio'] < 0.3:
            score += 15
        elif row['debt_ratio'] < 0.5:
            score += 10
        elif row['debt_ratio'] < 0.7:
            score += 5
        
        # PB评分 (0-15分)
        if 0 < row['pb_ratio'] < 2:
            score += 15
        elif 2 <= row['pb_ratio'] < 4:
            score += 10
        elif 4 <= row['pb_ratio'] < 6:
            score += 5
        
        scores.append((row['code'], score))
    
    # 按评分排序
    scores.sort(key=lambda x: x[1], reverse=True)
    
    # 返回前50只股票
    return [stock for stock, score in scores[:50]]

"""
使用说明：

1. 这些策略仅供参考，实际使用时需要：
   - 根据市场环境调整参数
   - 结合具体投资目标
   - 考虑风险承受能力

2. 可以组合使用多个策略：
   - 取交集：更严格筛选
   - 取并集：扩大选择范围
   - 加权评分：综合多个因子

3. 参数调优建议：
   - 根据历史回测结果调整阈值
   - 考虑行业差异
   - 结合宏观经济环境

4. 风险控制：
   - 设置最大选股数量
   - 考虑行业分散度
   - 定期评估和调整
"""
