# 克隆自聚宽文章：https://www.joinquant.com/post/61650
# 标题：整合两个表现不错的ETF策略形成多账户子策略
# 作者：聚看风景
# 增强版：添加通知功能

# ========= 通知配置 =========
NOTIFICATION_CONFIG = {
    'enabled': True,  # 是否启用通知功能
    'trading_notification': True,  # 是否发送交易通知
    'daily_summary': True,  # 是否发送每日摘要
    'notification_format': 'markdown',  # 通知格式: 'html', 'markdown', 'text'
    'email_config': {
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 587,
            'sender_email': '',
            'sender_password': '',
            'recipients':  []
        },
}

from jqdata import *
import pandas as pd
import numpy as np
import math
import talib
from jqfactor import *
from scipy.optimize import minimize
import statsmodels.api as sm
from scipy.linalg import solve
from prettytable import PrettyTable

# 导入通知库
try:
    from notification_lib import *
    NOTIFICATION_AVAILABLE = True
except ImportError:
    NOTIFICATION_AVAILABLE = False
    log.warning("通知库未找到，将跳过通知功能")

# ========= 初始化 =========
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 使用真实价格
    set_option('use_real_price', True)
    # 避免未来数据
    set_option("avoid_future_data", True)
    log.info('初始函数开始运行且全局只运行一次')
    log.set_level('order', 'error')
    
    # 设置交易成本
    set_order_cost(OrderCost(
        open_tax=0, 
        close_tax=0, 
        open_commission=0.0002, 
        close_commission=0.0002, 
        close_today_commission=0, 
        min_commission=1
    ), type='fund')
    
    # 设置滑点
    set_slippage(FixedSlippage(0.001))
    
    # 资金分配设置（全球选基0.9，动量轮动0.1）
    g.strategys = {}
    g.global_strategy_proportion = 0.9  # 全球选基策略资金比例
    g.momentum_strategy_proportion = 0.1  # 动量轮动策略资金比例
    
    # 创建子账户配置
    subportfolios = [
        SubPortfolioConfig(
            context.portfolio.starting_cash * g.global_strategy_proportion,
            'stock'
        ),
        SubPortfolioConfig(
            context.portfolio.starting_cash * g.momentum_strategy_proportion,
            'stock'
        )
    ]
    set_subportfolios(subportfolios)
    
    # 初始化策略
    g.strategys['全球选基策略'] = GlobalFundSelectionStrategy(context, 0, '全球选基策略')
    g.strategys['动量轮动策略'] = MomentumRotationStrategy(context, 1, '动量轮动策略')
    
    # 交易时间设置
    run_daily(strategy_trade, time="14:50", reference_security='000300.XSHG')
    run_daily(print_trade_info, time="14:51")
    run_daily(after_market_close, time="14:51")
    
    # 设置通知配置
    if NOTIFICATION_AVAILABLE and NOTIFICATION_CONFIG['enabled']:
        # 直接将整个配置存储到全局变量g中
        g.notification_config = NOTIFICATION_CONFIG
        
        log.info(f"ETF多账户子策略通知配置设置完成 - 格式: {NOTIFICATION_CONFIG['notification_format']}")
        log.info(f"邮件配置: {NOTIFICATION_CONFIG['email_config']['sender_email']}")
        log.info(f"收件人数量: {len(NOTIFICATION_CONFIG['email_config']['recipients'])}")
    
    # 初始化通知相关变量
    g.last_notification_date = None
    g.daily_trading_summary = {}


# ========= 交易调度 =========
def strategy_trade(context):
    """执行两个子策略的交易"""
    # 记录策略时间
    strategy_datetime = context.current_dt
    
    # 初始化当日交易摘要
    g.daily_trading_summary = {
        'date': strategy_datetime.strftime('%Y-%m-%d'),
        'global_strategy': {'trades': [], 'performance': 0},
        'momentum_strategy': {'trades': [], 'performance': 0}
    }
    
    # 执行子策略交易
    for strategy_name, strategy in g.strategys.items():
        log.info(f"=== 执行 {strategy_name} 交易 ===")
        strategy.my_trade(context)
        
        # 记录交易摘要
        subportfolio = context.subportfolios[strategy.subportfolio_index]
        if strategy_name == '全球选基策略':
            g.daily_trading_summary['global_strategy']['performance'] = (subportfolio.total_value / strategy.start_cash - 1) * 100 if strategy.start_cash != 0 else 0
        else:
            g.daily_trading_summary['momentum_strategy']['performance'] = (subportfolio.total_value / strategy.start_cash - 1) * 100 if strategy.start_cash != 0 else 0
    
    # 检查是否有实际交易，只在有交易时发送通知
    has_trades = (len(g.daily_trading_summary['global_strategy']['trades']) > 0 or 
                  len(g.daily_trading_summary['momentum_strategy']['trades']) > 0)
    
    config = getattr(g, 'notification_config', {})
    if NOTIFICATION_AVAILABLE and config.get('enabled', False) and config.get('trading_notification', False) and has_trades:
        send_etf_trading_notification(context, strategy_datetime)
    elif has_trades:
        log.info("有交易但通知功能未启用")
    else:
        log.info("今日无交易，跳过交易信号通知")

def print_trade_info(context):
    """打印交易信息"""
    orders = get_orders()
    for _order in orders.values():
        log.info('成交记录：' + str(_order))

def after_market_close(context):
    """收盘后处理"""
    for strategy in g.strategys.values():
        strategy.after_market_close(context)
    
    # 发送收盘后通知
    config = getattr(g, 'notification_config', {})
    if NOTIFICATION_AVAILABLE and config.get('enabled', False) and config.get('daily_summary', False):
        send_daily_summary_notification(context)


# ========= 基础策略类 =========
class BaseStrategy:
    def __init__(self, context, subportfolio_index, name, proportion):
        self.subportfolio_index = subportfolio_index
        self.name = name
        self.start_cash = context.portfolio.starting_cash * proportion
        self.portfolio_value_history = pd.DataFrame(columns=['date', 'total_value'])
    
    def my_trade(self, context):
        """交易逻辑，由子类实现"""
        pass
    
    def after_market_close(self, context):
        """收盘后处理，由子类实现或扩展"""
        sub = context.subportfolios[self.subportfolio_index]
        ret = (sub.total_value / self.start_cash - 1) * 100 if self.start_cash != 0 else 0
        record(**{self.name + '收益率': ret})
        self.print_holdings(context)
    
    def print_holdings(self, context):
        """打印持仓信息"""
        sub = context.subportfolios[self.subportfolio_index]
        pt = PrettyTable(["策略", "代码", "名称", "买入日", "买入价", "现价", "收益%", "数量", "市值"])
        
        if sub.long_positions:
            for stk in list(sub.long_positions):
                p = sub.long_positions[stk]
                pt.add_row([
                    self.name, p.security[:6], get_security_info(p.security).display_name,
                    p.init_time.date(), f"{p.avg_cost:.3f}", f"{p.price:.3f}",
                    f"{(p.price / p.avg_cost - 1) * 100:.2f}%", p.total_amount,
                    f"{p.value / 10000:.3f}万"
                ])
            log.info(f"\n{pt}")
        else:
            log.info(f"{self.name} 无持仓")


# ========= 全球选基策略 =========
# 全球选基策略使用的ETF池
g.etf_pool_global = [
    # 境外
    "513100.XSHG",  # 纳指ETF
    "513520.XSHG",  # 日经ETF
    "513030.XSHG",  # 德国ETF
    # 商品
    "518880.XSHG",  # 黄金ETF
    "159980.XSHE",  # 有色ETF
    "159985.XSHE",  # 豆粕ETF
    '501018.XSHG',  # 南方原油
    # 债券
    "511090.XSHG",  # 30年国债ETF
    # 国内
    "510300.XSHG",  # 沪深300ETF
    "159338.XSHE",  # 中证A500ETF
    "513130.XSHG",  # 恒生科技
    "159915.XSHE",  # 创业板ETF
    "588000.XSHG",  # 科创50ETF
]

class GlobalFundSelectionStrategy(BaseStrategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name, g.global_strategy_proportion)
        # 策略参数
        self.m_days = 25            # 默认动量参考天数
        self.auto_day = True        # 自动调整动量周期
        self.min_days = 20          # 最小lookback天数
        self.max_days = 60          # 最大lookback天数
    
    def get_rank(self, etf_pool):
        """基于年化收益和判定系数打分的动量因子轮动（固定天数版）"""
        data = pd.DataFrame(index=etf_pool, columns=["annualized_returns", "r2", "score"])
        current_data = get_current_data()
        
        for etf in etf_pool:
            # 获取历史数据
            df = attribute_history(etf, self.m_days, "1d", ["close", "high"])
            if df.empty or len(df) < self.m_days:
                data.loc[etf, "score"] = np.nan
                continue
                
            # 拼接最新价格
            prices = np.append(df["close"].values, current_data[etf].last_price)
            
            # 计算对数价格和时间序列
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))  # 线性加权，近期权重更高
            
            # 计算年化收益率
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1
            
            # 计算R²（拟合优度）
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0
            
            # 计算综合得分
            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]
            
            # 过滤近3日跌幅超过5%的ETF
            if len(prices) >= 4 and min(prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]) < 0.95:
                data.loc[etf, "score"] = 0
        
        # 按得分降序排列
        return data.sort_values(by="score", ascending=False)
    
    def get_rank2(self, etf_pool):
        """基于年化收益和判定系数打分的动量因子轮动（动态调整天数版）"""
        data = pd.DataFrame(index=etf_pool, columns=["annualized_returns", "r2", "score"])
        current_data = get_current_data()
        
        for etf in etf_pool:
            # 获取足够的历史数据
            df = attribute_history(etf, self.max_days + 10, "1d", ["close", "high", "low"])
            
            # 过滤历史数据不足的标的
            if (len(df) < (self.max_days + 10) or 
                df["low"].isna().sum() > self.max_days or 
                df["close"].isna().sum() > self.max_days or 
                df["high"].isna().sum() > self.max_days):
                data.loc[etf, "score"] = np.nan
                continue
            
            # 基于ATR动态调整lookback天数
            long_atr = talib.ATR(df["high"], df["low"], df["close"], timeperiod=self.max_days)
            short_atr = talib.ATR(df["high"], df["low"], df["close"], timeperiod=self.min_days)
            
            # 计算调整后的天数
            if long_atr[-1] == 0:
                lookback = self.m_days
            else:
                lookback = int(self.min_days + (self.max_days - self.min_days) * (1 - min(0.9, short_atr[-1]/long_atr[-1])))
            
            # 截取有效价格序列
            prices = np.append(df["close"].values, current_data[etf].last_price)
            prices = prices[-lookback:]
            log.info(f"{etf} 动态调整后周期: {lookback}天, 价格序列长度: {len(prices)}")
            
            # 计算对数价格和时间序列
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))  # 线性加权
            
            # 计算年化收益率
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1
            
            # 计算R²（拟合优度）
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0
            
            # 计算综合得分
            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]
            
            # 过滤近3日跌幅超过5%的ETF
            if len(prices) >= 4 and min(prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]) < 0.95:
                data.loc[etf, "score"] = 0
        
        # 按得分降序排列
        return data.sort_values(by="score", ascending=False)
    
    def my_trade(self, context):
        """全球选基策略的交易逻辑"""
        subportfolio = context.subportfolios[self.subportfolio_index]
        log.info(f"{self.name} 运行时间: {str(context.current_dt.time())}")
        
        # 根据参数选择评分方法
        if self.auto_day:
            rank_data = self.get_rank2(g.etf_pool_global)
        else:
            rank_data = self.get_rank(g.etf_pool_global)
        
        # 日志输出所有ETF的评分信息
        log.info("所有ETF评分信息:")
        for etf, row in rank_data.iterrows():
            if pd.isna(row['score']):
                log.info(f"{etf}: 数据不足或无效")
            else:
                log.info(f"{etf}: 年化收益={row['annualized_returns']:.4f}, R²={row['r2']:.4f}, 综合得分={row['score']:.4f}")
        
        # 筛选有效标的
        target_num = 1  # 选择排名第一的ETF
        valid_etfs = rank_data[(rank_data['score'] > 0) & (rank_data['score'] < 3) & (~rank_data['score'].isna())]
        target_list = valid_etfs.index.tolist()[:target_num]
        
        # 无有效标的时不交易
        if len(target_list) == 0:
            log.info(f"{self.name} 没有符合条件的ETF，今日不进行交易")
            return
        
        # 记录交易信息
        trades = []
        
        # 卖出不在目标列表中的持仓
        hold_list = list(subportfolio.positions)
        for etf in hold_list:
            if etf not in target_list:
                order_target_value(etf, 0, pindex=self.subportfolio_index)
                log.info(f"{self.name} 卖出 {etf}")
                trades.append({'action': '卖出', 'etf': etf, 'reason': '不在目标列表'})
            else:
                log.info(f"{self.name} 继续持有 {etf}")
        
        # 买入目标列表中的标的（若未持仓）
        current_hold = list(subportfolio.positions)
        if len(current_hold) < target_num:
            # 计算每个标的的配置资金
            invest_value = subportfolio.available_cash / (target_num - len(current_hold))
            for etf in target_list:
                if subportfolio.positions[etf].total_amount == 0:
                    order_target_value(etf, invest_value, pindex=self.subportfolio_index)
                    log.info(f"{self.name} 买入 {etf}")
                    trades.append({'action': '买入', 'etf': etf, 'amount': invest_value})
        
        # 记录交易摘要
        g.daily_trading_summary['global_strategy']['trades'] = trades


# ========= 动量轮动策略（优化版） =========
class MomentumRotationStrategy(BaseStrategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name, g.momentum_strategy_proportion)
        # 策略参数
        self.stock_num = 1
        self._lambda = 10
        self.w = 0.2
        self.m_days = 34   # 动量参考天数
        
        # 动量轮动策略使用的ETF池
        self.etf_pool = [
            # 商品
            '518880.XSHG',#黄金ETF
            '159985.XSHE',#豆粕ETF
            # 海外
            '513100.XSHG',#纳指ETF
            # 宽基
            '510300.XSHG',#沪深300ETF
            '159915.XSHE',#创业板
            # 窄基
            '159992.XSHE',#创新药ETF
            '515700.XSHG',#新能车ETF
            '510150.XSHG',#消费ETF
            '515790.XSHG',#光伏ETF
            '515880.XSHG',#通信ETF
            '512720.XSHG',#计算机ETF
            '512660.XSHG',#军工ETF
            '159740.XSHE',#恒生科技ETF
        ]
        
        # 记录上次交易日期，用于实现月度调仓
        self.last_trade_month = None
    
    def get_rank(self, etf_pool):
        """基于年化收益和判定系数打分的动量因子轮动"""
        score_list = []
        for etf in etf_pool:
            # 获取历史数据
            df = attribute_history(etf, self.m_days, '1d', ['close'])
            if df.empty or len(df) < self.m_days:
                score_list.append(np.nan)
                continue
                
            # 计算对数价格
            df['log'] = np.log(df['close'])
            y = df['log']
            x = np.arange(df['log'].size)
            
            # 计算斜率和截距
            slope, intercept = np.polyfit(x, y, 1)
            
            # 计算年化收益率
            annualized_returns = math.pow(math.exp(slope), 250) - 1
            
            # 计算R²
            r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
            
            # 计算综合得分
            score = annualized_returns * r_squared
            score_list.append(score)
            
        # 排序并过滤
        df = pd.DataFrame(index=etf_pool, data={'score': score_list})
        df = df.sort_values(by='score', ascending=False)
        df = df.dropna()
        rank_list = list(df.index)
        log.info(f"{self.name} 评分结果:\n{df}")
        
        # 过滤掉负收益的ETF
        filtered_rank_list = [etf for etf in rank_list if df.loc[etf, 'score'] > 0]
        return filtered_rank_list
    
    def epo(self, x, signal, lambda_, method='simple', w=None, anchor=None, normalize=True, endogenous=True):
        """优化函数"""
        n = x.shape[1]
        vcov = x.cov()
        corr = x.corr()
        I = np.eye(n)
        V = np.zeros((n, n))
        np.fill_diagonal(V, vcov.values.diagonal())
        std = np.sqrt(V)
        s = signal
        a = anchor

        shrunk_cor = ((1 - w) * I @ corr.values) + (w * I)
        cov_tilde = std @ shrunk_cor @ std
        inv_shrunk_cov = solve(cov_tilde, np.eye(n))

        if method == 'simple':
            epo = (1 / lambda_) * inv_shrunk_cov @ signal
        elif method == 'anchored':
            if endogenous:
                gamma = np.sqrt(a.T @ cov_tilde @ a) / np.sqrt(s.T @ inv_shrunk_cov @ cov_tilde @ inv_shrunk_cov @ s)
                epo = inv_shrunk_cov @ (((1 - w) * gamma * s) + ((w * I @ V @ a)))
            else:
                epo = inv_shrunk_cov @ (((1 - w) * (1 / lambda_) * s) + ((w * I @ V @ a)))

        if normalize:
            epo = [0 if val < 0 else val for val in epo]
            epo = epo / np.sum(epo) if np.sum(epo) > 0 else np.zeros_like(epo)

        return epo

    def run_optimization(self, stocks, end_date):
        """获取数据并调用优化函数，修复Panel警告"""
        if not stocks:
            return None
            
        try:
            # 获取1200天数据，添加panel=False参数避免使用Panel
            prices = get_price(stocks, count=1200, end_date=end_date, frequency='daily', fields=['close'], panel=False)
            # 重塑数据为宽表格式
            prices = prices.pivot(index='time', columns='code', values='close')
            returns = prices.pct_change().dropna()  # 计算收益率
            
            if returns.empty:
                return None
                
            # 计算权重
            d = np.diag(returns.cov())
            a = (1/d) / (1/d).sum() if np.sum(1/d) > 0 else np.ones(len(stocks))/len(stocks)
            
            weights = self.epo(
                x=returns, 
                signal=returns.mean(), 
                lambda_=self._lambda, 
                method='anchored', 
                w=self.w, 
                anchor=a
            )
            return weights
        except Exception as e:
            log.error(f"{self.name} 优化计算出错: {str(e)}")
            return None
    
    def my_trade(self, context):
        """动量轮动策略的交易逻辑（月度调仓）"""
        # 仅每月第一个交易日执行调仓
        current_month = context.current_dt.month
        if self.last_trade_month == current_month:
            return  # 本月已调仓，不再重复执行
        self.last_trade_month = current_month
        
        subportfolio = context.subportfolios[self.subportfolio_index]
        end_date = context.previous_date 
        
        # 记录交易信息
        trades = []
        
        # 获取排名前N的ETF
        target_list = self.get_rank(self.etf_pool)[:self.stock_num]
        
        # 卖出不在目标列表中的持仓
        hold_list = list(subportfolio.positions)
        for etf in hold_list:
            if etf not in target_list:
                order_target_value(etf, 0, pindex=self.subportfolio_index)
                log.info(f"{self.name} 卖出 {etf}")
                trades.append({'action': '卖出', 'etf': etf, 'reason': '不在目标列表'})
            else:
                log.info(f"{self.name} 继续持有 {etf}")
        
        # 买入目标ETF
        if target_list:
            weights = self.run_optimization(target_list, end_date)
            
            if weights is not None and np.sum(weights) > 0:
                total_value = subportfolio.total_value 
                index = 0
                for w in weights:
                    if index < len(target_list) and w > 0:
                        value = total_value * w 
                        order_target_value(target_list[index], value, pindex=self.subportfolio_index)
                        log.info(f"{self.name} 买入 {target_list[index]}，权重: {w:.4f}")
                        trades.append({'action': '买入', 'etf': target_list[index], 'weight': w, 'amount': value})
                    index += 1
            else:
                log.info(f"{self.name} 未计算出有效权重，不进行买入操作")
        else:
            log.info(f"{self.name} 没有符合条件的目标ETF，不进行买入操作")
        
        # 记录交易摘要
        g.daily_trading_summary['momentum_strategy']['trades'] = trades


# ========= 通知相关函数 =========

def send_etf_trading_notification(context, strategy_datetime):
    """
    发送ETF交易通知
    """
    if not NOTIFICATION_AVAILABLE:
        return
    
    # 准备通知内容
    strategy_time_info = f"策略时间: {strategy_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # 全球选基策略信息
    global_trades = g.daily_trading_summary['global_strategy']['trades']
    global_performance = g.daily_trading_summary['global_strategy']['performance']
    
    # 动量轮动策略信息
    momentum_trades = g.daily_trading_summary['momentum_strategy']['trades']
    momentum_performance = g.daily_trading_summary['momentum_strategy']['performance']
    
    # 构建Markdown格式的通知内容
    markdown_content = f"""# ETF多账户子策略 - 交易信号

## 📊 策略时间
{strategy_time_info}

## 🌍 全球选基策略 (90%资金)
- **收益率**: {global_performance:+.2f}%
- **交易记录**:
"""
    
    if global_trades:
        for trade in global_trades:
            # 获取ETF名称
            etf_info = get_security_info(trade['etf'])
            etf_name = etf_info.display_name if etf_info else trade['etf']
            markdown_content += f"- {trade['action']}: `{trade['etf']}` ({etf_name})"
            if 'amount' in trade:
                markdown_content += f" (金额: ¥{trade['amount']:,.0f})"
            markdown_content += "\n"
    else:
        markdown_content += "- 无交易\n"
    
    markdown_content += f"""
## ⚡ 动量轮动策略 (10%资金)
- **收益率**: {momentum_performance:+.2f}%
- **交易记录**:
"""
    
    if momentum_trades:
        for trade in momentum_trades:
            # 获取ETF名称
            etf_info = get_security_info(trade['etf'])
            etf_name = etf_info.display_name if etf_info else trade['etf']
            markdown_content += f"- {trade['action']}: `{trade['etf']}` ({etf_name})"
            if 'weight' in trade:
                markdown_content += f" (权重: {trade['weight']:.2%})"
            if 'amount' in trade:
                markdown_content += f" (金额: ¥{trade['amount']:,.0f})"
            markdown_content += "\n"
    else:
        markdown_content += "- 无交易\n"
    
    markdown_content += """
## ⚠️ 风险提示
> 投资有风险，入市需谨慎
"""
    
    # 发送通知
    send_message(markdown_content)  # 聚宽内置通知
    
    # 发送统一格式通知
    config = getattr(g, 'notification_config', {})
    send_unified_notification(
        content=markdown_content,
        subject="ETF多账户子策略 - 交易信号",
        title="ETF交易信号",
        format_type=config.get('notification_format', 'markdown'),
        context=context
    )
    
    log.info("ETF交易通知发送完成")

def send_daily_summary_notification(context):
    """
    发送每日收盘摘要通知
    """
    if not NOTIFICATION_AVAILABLE:
        return
    
    # 获取子账户信息
    global_sub = context.subportfolios[0]
    momentum_sub = context.subportfolios[1]
    
    # 计算总收益率
    total_value = global_sub.total_value + momentum_sub.total_value
    total_return = (total_value / context.portfolio.starting_cash - 1) * 100
    
    # 构建Markdown格式的摘要内容
    markdown_content = f"""# ETF多账户子策略 - 每日摘要

## 📅 日期
{context.current_dt.strftime('%Y年%m月%d日')}

## 📊 账户总览
- **总资产**: ¥{total_value:,.0f}
- **总收益率**: {total_return:+.2f}%

## 🌍 全球选基策略 (90%资金)
- **资产**: ¥{global_sub.total_value:,.0f}
- **收益率**: {g.daily_trading_summary['global_strategy']['performance']:+.2f}%
- **持仓数量**: {len(global_sub.long_positions)}只ETF

## ⚡ 动量轮动策略 (10%资金)
- **资产**: ¥{momentum_sub.total_value:,.0f}
- **收益率**: {g.daily_trading_summary['momentum_strategy']['performance']:+.2f}%
- **持仓数量**: {len(momentum_sub.long_positions)}只ETF

## 📈 持仓详情
"""
    
    # 添加持仓详情
    if global_sub.long_positions or momentum_sub.long_positions:
        markdown_content += "| 策略 | ETF代码 | ETF名称 | 买入日期 | 持仓数量 | 成本价 | 现价 | 总收益率 | 当日涨跌 | 市值 |\n"
        markdown_content += "|------|---------|---------|----------|----------|--------|------|----------|------------|------|\n"
        
        # 全球选基策略持仓
        for etf, position in global_sub.long_positions.items():
            etf_info = get_security_info(etf)
            current_price = get_current_data()[etf].last_price
            profit_pct = (current_price / position.avg_cost - 1) * 100 if position.avg_cost != 0 else 0
            
            # 获取当日涨跌幅
            try:
                current_data = get_current_data()[etf]
                if hasattr(current_data, 'day_open') and current_data.day_open and current_data.day_open != 0:
                    daily_return = (current_data.last_price / current_data.day_open - 1) * 100
                else:
                    daily_return = 0
            except:
                daily_return = 0
            
            markdown_content += f"| 全球选基 | {etf} | {etf_info.display_name} | {position.init_time.strftime('%m-%d')} | {position.total_amount} | ¥{position.avg_cost:.3f} | ¥{current_price:.3f} | {profit_pct:+.2f}% | {daily_return:+.2f}% | ¥{position.value:,.0f} |\n"
        
        # 动量轮动策略持仓
        for etf, position in momentum_sub.long_positions.items():
            etf_info = get_security_info(etf)
            current_price = get_current_data()[etf].last_price
            profit_pct = (current_price / position.avg_cost - 1) * 100 if position.avg_cost != 0 else 0
            
            # 获取当日涨跌幅
            try:
                current_data = get_current_data()[etf]
                if hasattr(current_data, 'day_open') and current_data.day_open and current_data.day_open != 0:
                    daily_return = (current_data.last_price / current_data.day_open - 1) * 100
                else:
                    daily_return = 0
            except:
                daily_return = 0
            
            markdown_content += f"| 动量轮动 | {etf} | {etf_info.display_name} | {position.init_time.strftime('%m-%d')} | {position.total_amount} | ¥{position.avg_cost:.3f} | ¥{current_price:.3f} | {profit_pct:+.2f}% | {daily_return:+.2f}% | ¥{position.value:,.0f} |\n"
    else:
        markdown_content += "当前无持仓\n"
    
    markdown_content += """
## ⚠️ 风险提示
> 本策略为量化投资策略，存在市场风险
> 
> 过往表现不代表未来收益
> 
> 投资有风险，入市需谨慎
"""
    
    # 发送通知
    send_message(markdown_content)  # 聚宽内置通知
    
    # 发送统一格式通知
    config = getattr(g, 'notification_config', {})
    send_unified_notification(
        content=markdown_content,
        subject="ETF多账户子策略 - 每日摘要",
        title="ETF每日摘要",
        format_type=config.get('notification_format', 'markdown'),
        context=context
    )
    
    log.info("每日摘要通知发送完成")
