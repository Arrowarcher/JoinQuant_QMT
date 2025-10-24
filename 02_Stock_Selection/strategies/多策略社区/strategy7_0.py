# 克隆自聚宽文章：https://www.joinquant.com/post/52868
# 标题：多策略7.0（优化及增加注释版本）
# 作者：Ceng-Lucifffff

# 克隆自聚宽文章：https://www.joinquant.com/post/52465
# 标题：多策略7.0（重写框架，新增策略）
# 作者：O_iX

"""
多策略7.0 优化版本（详细注释版）

本代码实现了多个子策略的组合，主要包含以下逻辑：
1. 全局设置：设定回测/实盘基础选项、滑点、手续费、全局变量及定时调度。
2. 资金管理：利用货币ETF对现金进行管理，确保有足够资金调仓。
3. 基类 Strategy：封装公共方法，如数据准备、持仓市值计算、调仓及下单操作。
4. 各子策略：包括搅屎棍策略、全天候ETF策略、简单ROA策略、弱周期价投策略，每个策略继承自基类并实现自己的选股调仓逻辑。
5. 日志输出：在关键操作和每日收盘后输出详细日志，便于调试和复盘。

注意：请根据实际交易环境及聚宽平台的时间段要求，调整各调度函数的执行时间。
"""

from jqdata import *
from jqfactor import get_factor_values
import datetime
import math
from scipy.optimize import minimize

# ---------------------------
# 初始化函数及全局变量设置
# ---------------------------
def initialize(context):
    """
    初始化函数：在策略启动时最先运行一次
    - 设置基础选项（未来数据、真实价格）
    - 设置日志过滤级别，降低无用日志信息
    - 配置股票及ETF的固定滑点和手续费
    - 定义全局变量，包括现金管理工具、各子策略资金比例和持仓记录
    - 调度各子策略函数（每日、每周、每月），并在收盘后输出持仓数据的日志
    - 调用 process_initialize() 初始化各个子策略对象
    """
    # ---------------------
    # 设置数据相关选项，确保回测时不使用未来数据和真实价格
    # ---------------------
    set_option("avoid_future_data", True)  # 开启防未来数据模式，防止后续因数据时间错误引发误差
    set_option("use_real_price", True)       # 使用真实成交价格模拟交易
    log.info("初始函数开始运行，全局只运行一次。")
    log.set_level("order", "error")          # 设置订单相关日志，过滤掉低于 error 的日志以免干扰

    # ---------------------
    # 设置滑点及交易成本（手续费）
    # ---------------------
    # ETF 固定滑点设置：0.002 表示价格波动时略微偏离净值的情况
    set_slippage(FixedSlippage(0.002), type="fund")
    # 股票固定滑点设置：0.02 表示对股票交易的滑点设置
    set_slippage(FixedSlippage(0.02), type="stock")
    # 股票交易成本：设置税费和佣金
    set_order_cost(
        OrderCost(
            open_tax=0,             # 开仓不收印花税
            close_tax=0.001,        # 平仓时收取千分之一的印花税
            open_commission=0.0003,   # 开仓时收取万分之三的佣金
            close_commission=0.0003,  # 同上，平仓时的佣金
            close_today_commission=0, # 平今无额外手续费
            min_commission=5,         # 每笔交易最低收费5元
        ),
        type="stock",
    )
    # 货币ETF的手续费都设为0，方便用于资金管理
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0,
            close_commission=0,
            close_today_commission=0,
            min_commission=0,
        ),
        type="mmf",
    )

    # ---------------------
    # 全局变量初始化
    # ---------------------
    # 用于现金管理的货币ETF代码（资金闲置时自动买入，获得较低波动性）
    g.fill_stock = "511880.XSHG"  
    # 使用字典存储所有子策略对象，便于后续调用各策略的 prepare/adjust/check 等接口
    g.strategys = {}  
    # 各个子策略分配的资金比例，比例按组合总资金分配（总和要求为1）
    g.portfolio_value_proportion = [0.3, 0.3, 0.2, 0.2]
    # 全局持仓记录，各策略使用自己的下标记录持仓（子策略持仓信息存放在 g.positions 中）
    g.positions = {i: {} for i in range(len(g.portfolio_value_proportion))}

    # ---------------------
    # 子策略运行调度设置
    # ---------------------
    # 若策略资金比例大于0，则调度该子策略的运行
    # 搅屎棍策略：每日早上预处理、每周调整、每日尾盘检查
    if g.portfolio_value_proportion[0] > 0:
        run_daily(jsg_prepare, "9:05")      # 每日9:05运行 jsg_prepare() 收集数据准备工作
        run_weekly(jsg_adjust, 1, "9:31")     # 每周第一个交易日9:31根据预处理数据执行调仓
        run_daily(jsg_check, "14:50")         # 每日14:50检查昨日涨停股票风险
    # 全天候ETF策略：每月调仓一次
    if g.portfolio_value_proportion[1] > 0:
        run_monthly(all_day_adjust, 1, "9:32")
    # 简单ROA策略：每月调仓一次
    if g.portfolio_value_proportion[2] > 0:
        run_monthly(simple_roa_adjust, 1, "9:33")
    # 弱周期价投策略：每周调仓一次
    if g.portfolio_value_proportion[3] > 0:
        run_weekly(weak_cyc_adjust, 1, "9:34")
    # 每个交易日14:55运行 buy_fill_stock，用于利用剩余现金购买货币ETF
    run_daily(buy_fill_stock, "14:55")
    # 每日收盘后（15:00）调用 log_portfolio_holdings 输出持仓数据，用以监控和复盘
    run_daily(log_portfolio_holdings, "15:00")
    # 初始化所有子策略对象
    process_initialize(context)


def process_initialize(context):
    """
    初始化所有子策略对象，并存储在全局变量 g.strategys 中。
    每个子策略通过指定 index（对应资金比例和持仓存储下标）和自定义名称初始化。
    """
    g.strategys["搅屎棍策略"] = JSG_Strategy(context, index=0, name="搅屎棍策略")
    g.strategys["全天候策略"] = All_Day_Strategy(context, index=1, name="全天候策略")
    g.strategys["简单ROA策略"] = Simple_ROA_Strategy(context, index=2, name="简单ROA策略")
    g.strategys["弱周期价投策略"] = Weak_Cyc_Strategy(context, index=3, name="弱周期价投策略")


# ---------------------------
# 资金管理辅助函数
# ---------------------------
def buy_fill_stock(context):
    """
    利用剩余空闲资金购买货币ETF，
    保持一定比例的低风险、流动性较强的资产，便于补充现金。
    """
    current_data = get_current_data()
    # 计算可买入股数：剩余现金 / 当前ETF价格（注意结果为整数）
    amount = int(context.portfolio.available_cash / current_data[g.fill_stock].last_price)
    # 如果可买入股数大于等于100（交易单位为100股），则执行订单
    if amount >= 100:
        order(g.fill_stock, amount)
        log.info(f"买入货币ETF {g.fill_stock} 数量：{amount}")


def get_cash(context, value):
    """
    如果调仓时现金不足，则卖出部分货币ETF以补充所需资金。
    参数:
      value -- 需要补充的现金金额
    """
    if g.fill_stock not in context.portfolio.positions:
        return
    current_data = get_current_data()
    # 计算所需卖出股数，向上取整至100的倍数
    amount = math.ceil(value / current_data[g.fill_stock].last_price / 100) * 100
    # 获取该ETF当前可卖出的股数
    position = context.portfolio.positions[g.fill_stock].closeable_amount
    if amount >= 100:
        sell_amount = min(amount, position)
        order(g.fill_stock, -sell_amount)
        log.info(f"卖出货币ETF {g.fill_stock} 数量：{sell_amount}，换取现金")


def log_portfolio_holdings(context):
    """
    每日收盘后输出全局持仓数据日志：
     - 输出各个子策略当前持仓记录
     - 输出组合总资产数值
    该信息有助于后续分析策略的运行效果和仓位分布。
    """
    log.info("===== 每日收盘后持仓数据 =====")
    for strat_index, pos_dict in g.positions.items():
        log.info(f"策略 {strat_index} 持仓: {pos_dict}")
    log.info(f"总资产: {context.portfolio.total_value}")
    log.info("================================")


# ---------------------------
# 子策略调度接口函数
# ---------------------------
def jsg_prepare(context):
    """
    搅屎棍策略：数据准备阶段，在调仓前收集必要信息。
    """
    g.strategys["搅屎棍策略"].prepare()


def jsg_check(context):
    """
    搅屎棍策略：检查阶段，用于处理昨日涨停股票的风险控制，选择是否提前卖出。
    """
    g.strategys["搅屎棍策略"].check()


def jsg_adjust(context):
    """
    搅屎棍策略：调仓阶段，根据选股结果买入或卖出股票。
    """
    g.strategys["搅屎棍策略"].adjust()


def all_day_adjust(context):
    """
    全天候ETF策略：每月调仓一次，根据各ETF目标仓位调整持仓。
    """
    g.strategys["全天候策略"].adjust()


def simple_roa_adjust(context):
    """
    简单ROA策略：每月调仓一次，根据选股规则调整持仓。
    """
    g.strategys["简单ROA策略"].adjust()


def weak_cyc_adjust(context):
    """
    弱周期价投策略：每周调仓一次，调整股票和国债ETF组合持仓。
    """
    g.strategys["弱周期价投策略"].adjust()


# ---------------------------
# 策略基类：所有子策略的公共部分封装在这里
# ---------------------------
class Strategy:
    def __init__(self, context, index: int, name: str):
        """
        初始化策略基类
        参数:
          context - 聚宽提供的交易上下文对象，包含账户、时间和行情数据等
          index   - 一个整数，表示该策略在全局持仓 g.positions 中的位置
          name    - 策略名称，用于日志和调试输出
        """
        self.context = context
        self.index = index
        self.name = name
        # 默认策略计划管理的股票数目，子策略可以在构造中修改
        self.stock_sum = 1
        # 当前持仓列表，存放股票代码，便于后续查询
        self.hold_list = []
        # 记录昨日涨停股票列表（如若出现涨停但未继续涨停时可能需要风控处理）
        self.limit_up_list = []
        # 最小交易量设置（用于防止手续费过高的零散交易）
        self.min_volume = 2000

    def get_total_value(self) -> float:
        """
        计算当前策略持仓的市值总和
        遍历该策略持仓中所有股票，用当前价格乘以持仓数量求和
        """
        if not g.positions[self.index]:
            return 0.0
        return sum(self.context.portfolio.positions[sec].price * value 
                   for sec, value in g.positions[self.index].items())

    def _prepare(self):
        """
        数据准备阶段：
        1. 获取当前策略所持有的股票列表（hold_list）
        2. 获取昨日收盘价等于涨停价的股票，作为 limit_up_list，
           这些股票在当天可能会因涨停被保护而不适合调整仓位。
        """
        self.hold_list = list(g.positions[self.index].keys())
        if self.hold_list:
            df = get_price(
                self.hold_list,
                end_date=self.context.previous_date,
                frequency="daily",
                fields=["close", "high_limit"],
                count=1,
                panel=False,
                fill_paused=False,
            )
            # 过滤出收盘价等于涨停价的股票
            df = df[df["close"] == df["high_limit"]]
            self.limit_up_list = list(df.code)
        else:
            self.limit_up_list = []

    def _check(self):
        """
        检查昨日出现涨停的股票：如果这些股票在今天观察到状态发生变化，
        则调度下单卖出，保护账户资金不被被动锁死风险。
        """
        if self.limit_up_list:
            for stock in self.limit_up_list:
                self.order_target_value_(stock, 0)

    def _adjust(self, target: list):
        """
        等权调仓：目标为目标股票列表中各股票获得相似市值
        1. 卖出持仓中不再在目标列表内的股票（除非股价处于涨停保护中）
        2. 对未持有目标股票分配资金，等额买入
        参数:
          target -- 目标股票列表
        """
        portfolio = self.context.portfolio

        # 卖出：对所有当前持仓如果不在目标列表并且不在昨日涨停名单中则执行清仓操作
        for security in self.hold_list:
            if security not in target and security not in self.limit_up_list:
                self.order_target_value_(security, 0)

        # 确定需要买入的新标的，计算新买入目标数
        new_buys = set(target) - set(self.hold_list)
        count = len(new_buys)
        if count == 0 or self.stock_sum <= len(self.hold_list):
            return

        # 计算当前该策略资金份额中目标市值
        target_value = portfolio.total_value * g.portfolio_value_proportion[self.index]
        # 当前策略已有持仓市值
        position_value = self.get_total_value()
        # 剩余可用现金 = 现有现金 + 已持货币ETF资金（若有）
        available_cash = portfolio.available_cash
        if g.fill_stock in portfolio.positions:
            available_cash += portfolio.positions[g.fill_stock].value
        # 可用资金与目标市值差的较小值为需要买入的资金
        value = max(0, min(target_value - position_value, available_cash))

        # 如果现有现金不足，则卖出部分货币ETF来获取资金
        if value > portfolio.available_cash:
            get_cash(self.context, value - portfolio.available_cash)

        # 对所有未持有的新股票，等额分配资金进行买入操作
        for security in new_buys:
            self.order_target_value_(security, value / count)

    def _adjust2(self, targets: dict):
        """
        指定目标市值调仓：根据传入字典 targets 为每只股票确定目标市值，
        分两步完成：先卖出多余持仓，后买入不足部分
        参数:
          targets -- 字典格式，key是股票代码，value是目标市值
        """
        # 缓存当前行情数据，减少多次调用 API
        current_data = get_current_data()
        portfolio = self.context.portfolio

        # 卖出：清理所有当前持仓中不在目标列表的股票
        for stock in self.hold_list:
            if stock not in targets:
                self.order_target_value_(stock, 0)

        # 先卖出持仓中过剩部分
        for stock, target in targets.items():
            price = current_data[stock].last_price
            current_value = g.positions[self.index].get(stock, 0) * price
            if current_value - target > self.min_volume and current_value - target > price * 100:
                self.order_target_value_(stock, target)

        # 再买入不足部分
        for stock, target in targets.items():
            price = current_data[stock].last_price
            current_value = g.positions[self.index].get(stock, 0) * price
            if target - current_value > self.min_volume and target - current_value > price * 100:
                # 若资金不够，则先通过卖出ETF补充现金
                if target - current_value > portfolio.available_cash:
                    get_cash(self.context, target - current_value - portfolio.available_cash)
                if portfolio.available_cash > price * 100:
                    self.order_target_value_(stock, target)

    def order_target_value_(self, security: str, value: float) -> bool:
        """
        根据目标市值下单，封装了涨停、跌停、停牌等限制条件的判断，
        并对订单下单过程中的异常情况进行捕获，保证下单安全。
        参数:
          security -- 股票代码
          value    -- 目标市值
        返回:
          如果下单成功则返回 True，否则返回 False
        """
        # 使用当前行情数据，避免多次调用 API
        current_data = get_current_data()

        # 判断股票是否停牌，停牌则不能下单
        if current_data[security].paused:
            log.info(f"{security}: 今天停牌，无法交易。")
            return False
        # 判断股票是否涨停，涨停则通常不能成交
        if current_data[security].last_price == current_data[security].high_limit:
            log.info(f"{security}: 当前涨停，无法交易。")
            return False
        # 判断股票是否跌停，跌停同样不能下单
        if current_data[security].last_price == current_data[security].low_limit:
            log.info(f"{security}: 当前跌停，无法交易。")
            return False

        # 获取股票最新价格，用于计算目标持仓股数
        price = current_data[security].last_price
        # 获取当前策略中该股票持仓数量（如果没有则默认为 0）
        current_position = g.positions[self.index].get(security, 0)
        # 根据传入目标市值与当前股价，计算目标持仓数量，并向下取整到100的整数倍
        target_position = (int(value / price) // 100) * 100 if price != 0 else 0
        # 计算需要调整的股数差额
        adjustment = target_position - current_position

        if adjustment != 0:
            try:
                # 调用 order() 函数执行下单操作（正数买入，负数卖出）
                order_result = order(security, adjustment)
                if order_result:
                    # 下单成功后，更新全局持仓字典
                    g.positions[self.index][security] = target_position
                    # 如果目标持仓为 0，则清理该股票记录
                    if target_position == 0:
                        g.positions[self.index].pop(security, None)
                    # 更新当前持有列表
                    self.hold_list = list(g.positions[self.index].keys())
                    log.info(f"{self.name}: {security} 调仓成功，目标持仓：{target_position} 股。")
                    return True
                else:
                    log.info(f"{self.name}: {security} 下单失败。")
                    return False
            except Exception as e:
                # 捕获订单错误，并输出详细异常信息
                log.error(f"{self.name}: 下单 {security} 时出现异常: {e}")
                return False
        else:
            # 调整量为0，表示无需下单调整，则直接返回 False
            return False

    def filter_basic_stock(self, stock_list: list) -> list:
        """
        基础股票过滤函数：排除停牌、ST、含有特殊标识（如*和退）的股票，
        同时过滤科创板、北交所股票以及上市时间不足375天的次新股。
        参数:
          stock_list -- 待过滤的股票列表
        返回:
          过滤后的股票列表
        """
        current_data = get_current_data()
        filtered = []
        for stock in stock_list:
            # 获取股票详细信息，用于判断上市时间
            info = get_security_info(stock)
            # 判断股票是否满足各过滤条件
            if (not current_data[stock].paused and
                not current_data[stock].is_st and
                "ST" not in current_data[stock].name and
                "*" not in current_data[stock].name and
                "退" not in current_data[stock].name and
                # 判断股票代码是否为科创或北交代码（根据代码前缀判断）
                not (stock[0] == "4" or stock[0] == "8" or stock[:2] == "68" or stock[0] == "3") and
                # 上市时间需超过375天
                (self.context.previous_date - info.start_date) > datetime.timedelta(days=375)):
                filtered.append(stock)
        return filtered

    def filter_limitup_limitdown_stock(self, stock_list: list) -> list:
        """
        过滤当日处于涨停或跌停状态的股票（除非该股票已在当前持仓中）。
        参数:
          stock_list -- 待过滤的股票列表
        返回:
          过滤后的股票列表
        """
        current_data = get_current_data()
        return [
            stock for stock in stock_list
            if (stock in self.hold_list) or
               (current_data[stock].last_price < current_data[stock].high_limit and 
                current_data[stock].last_price > current_data[stock].low_limit)
        ]

    def is_empty_month(self) -> bool:
        """
        判断当前月份是否为“空仓月”，在空仓月内策略不建仓风险降低。
        该信息通过子策略中的 pass_months 属性进行设置。
        返回:
          True 表示当前月份为空仓月，False 表示可以持仓操作。
        """
        month = self.context.current_dt.month
        return month in self.pass_months  # pass_months 由子策略在构造中设定


# ---------------------------
# 子策略1：搅屎棍策略
# ---------------------------
class JSG_Strategy(Strategy):
    def __init__(self, context, index: int, name: str):
        """
        搅屎棍策略：通过行业宽度及基本面条件选股，旨在捕捉市场拐点。
        参数:
          context - 聚宽交易上下文对象
          index   - 策略在全局持仓记录中的下标
          name    - 策略名称
        """
        super().__init__(context, index, name)
        # 设定最大持仓股票数量为6只
        self.stock_sum = 6
        # 行业宽度检测时选择的目标行业个数（目前取1）
        self.num = 1
        # 指定空仓的月份，例如1月和4月不进行持仓操作
        self.pass_months = [1, 4]

    def getStockIndustry(self, stocks: list) -> "pd.Series":
        """
        获取传入股票列表中每只股票所属的一级行业（申万一级行业）
        参数:
          stocks -- 股票代码列表
        返回:
          Pandas Series，其中索引为股票代码，值为对应的行业名称
        """
        industry = get_industry(stocks)
        return pd.Series({stock: info["sw_l1"]["industry_name"] 
                          for stock, info in industry.items() if "sw_l1" in info})

    def get_market_breadth(self) -> list:
        """
        通过比较股票当前价格与20日均线，计算市场宽度
        1. 获取标的：使用000985.XSHG指数成分股
        2. 获取过去(count+20)天收盘价及计算20日均线
        3. 判断最新收盘价是否高于20日均线，反映市场走势
        4. 按照行业分组计算偏离比例，挑选出偏离程度最高的行业
        参数:
          无参数
        返回:
          行业列表，代表市场宽度指标中符合条件的行业（取前 num 个）
        """
        yesterday = self.context.previous_date
        stocks = get_index_stocks("000985.XSHG")
        count = 1  # 只取最新一天数据判断
        # 获取过去 count+20 天的收盘价数据
        h = get_price(
            stocks,
            end_date=yesterday,
            frequency="1d",
            fields=["close"],
            count=count + 20,
            panel=False,
        )
        # 将时间戳转换为日期格式
        h["date"] = pd.DatetimeIndex(h.time).date
        # 通过 pivot_table 获取按股票代码为行、日期为列的收盘价数据
        df_close = h.pivot(index="code", columns="date", values="close").dropna(axis=0)
        # 计算20日均线（窗口大小为20）
        df_ma20 = df_close.rolling(window=20, axis=1).mean().iloc[:, -count:]
        # 判断最新收盘价是否高于20日均线（True/False）
        df_bias = df_close.iloc[:, -count:] > df_ma20
        # 增加行业信息列，方便后续按行业分组统计
        df_bias["industry_name"] = self.getStockIndustry(stocks)
        # 按行业分组：统计每个行业中True的比例，并乘以100计算百分比
        df_ratio = ((df_bias.groupby("industry_name").sum() * 100.0) / df_bias.groupby("industry_name").count()).round()
        # 选取昨天时点内偏离程度最高的若干行业
        top_values = df_ratio.loc[:, yesterday].nlargest(self.num)
        I = top_values.index.tolist()
        return I

    def filter(self) -> list:
        """
        选股过滤逻辑：
        1. 以中小板（399101.XSHE）的股票为样本
        2. 使用基础过滤条件：过滤停牌、ST、特殊股票等
        3. 根据基本面指标（如ROA）和市值排序，取前20只股票
        4. 进一步过滤涨跌停股票，返回最终股票列表（不超过 self.stock_sum 只）
        返回:
          最终股票代码列表
        """
        stocks = get_index_stocks("399101.XSHE")
        stocks = self.filter_basic_stock(stocks)
        # 利用 get_fundamentals 获取基本面数据，根据市值升序排列后取前20只股票
        stocks = (
            get_fundamentals(
                query(valuation.code)
                .filter(
                    valuation.code.in_(stocks),
                    indicator.roa,          # 这里允许用默认的ROA过滤条件
                )
                .order_by(valuation.market_cap.asc())
            )
            .head(20)
            .code
        )
        stocks = self.filter_limitup_limitdown_stock(stocks)
        return stocks[: min(len(stocks), self.stock_sum)]

    def select(self) -> list:
        """
        择时指标选股：
        1. 先获取市场宽度行业列表（I）
        2. 如果市场宽度指标中不包含指定行业（例如银行、煤炭、采掘、钢铁）且非空仓月，则执行选股逻辑
        3. 否则返回空列表，表示当下不适合买入该策略股票
        返回:
          股票代码列表（满足条件的目标股票）
        """
        I = self.get_market_breadth()
        industries = {"银行I", "煤炭I", "采掘I", "钢铁I"}
        if not industries.intersection(I) and not self.is_empty_month():
            return self.filter()
        return []

    def prepare(self):
        """
        搅屎棍策略的数据准备接口，主要包括更新持仓列表和判断昨日涨停股票
        """
        self._prepare()

    def adjust(self):
        """
        调仓接口，根据择时逻辑执行买入卖出操作
        1. 调用 select() 获取符合条件的股票列表
        2. 调用 _adjust() 进行等权调仓操作（买入新股票并卖出不在目标内的股票）
        """
        target = self.select()
        self._adjust(target)

    def check(self):
        """
        检查昨日涨停股票的风险，必要时提前清仓以保护资金
        """
        self._check()


# ---------------------------
# 子策略2：全天候ETF策略
# ---------------------------
class All_Day_Strategy(Strategy):
    def __init__(self, context, index: int, name: str):
        """
        全天候ETF策略：通过持有多只ETF构建全天候组合，
        该策略主要用于分散风险并捕捉不同资产类别的收益机会。
        参数:
          context, index, name -- 同基类
        """
        super().__init__(context, index, name)
        self.min_volume = 2000
        # 定义ETF池，每只ETF代表不同的资产类别
        self.etf_pool = [
            "511260.XSHG",  # 十年国债ETF
            "518880.XSHG",  # 黄金ETF
            "513100.XSHG",  # 纳指100ETF
            "159980.XSHE",  # 有色ETF
            "162411.XSHE",  # 华宝油气LOF
            "159985.XSHE",  # 豆粕ETF
        ]
        # 定义各ETF在组合中的目标仓位比例（比例之和必须为1）
        self.rates = [0.45, 0.2, 0.1, 0.1, 0.05, 0.1]

    def adjust(self):
        """
        全天候ETF策略调仓接口：
        1. 计算该策略所管理的资金总额
        2. 根据预设的仓位比例计算每个ETF的目标市值
        3. 使用 _adjust2() 函数分步完成卖出和买入操作
        """
        self._prepare()  # 虽然ETF策略通常不需要做持仓涨停检查，但统一调用
        total_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
        # 构造目标市值字典，key为ETF代码，value为该ETF的目标市值
        targets = {etf: total_value * rate for etf, rate in zip(self.etf_pool, self.rates)}
        self._adjust2(targets)


# ---------------------------
# 子策略3：简单ROA策略
# ---------------------------
class Simple_ROA_Strategy(Strategy):
    def __init__(self, context, index: int, name: str):
        """
        简单ROA策略：通过选择ROA表现优异且市净率合理的股票构建仓位，
        旨在捕捉财务盈利能力突出的股票的投资机会。
        参数:
          context, index, name -- 同基类
        """
        super().__init__(context, index, name)
        self.stock_sum = 1  # 该策略只挑选1只优质标的

    def filter(self) -> list:
        """
        选股逻辑：
        1. 从所有股票中获取股票代码列表
        2. 过滤基础条件，保留市净率在合理范围内且有正利润的股票
        3. 按ROA从高到低排序后取前20只
        4. 进一步过滤涨跌停状态，返回最终目标股票列表
        返回:
          最终股票代码列表（不超过 self.stock_sum 只）
        """
        stocks = list(get_all_securities("stock", date=self.context.previous_date).index)
        stocks = self.filter_basic_stock(stocks)
        stocks_df = get_fundamentals(
            query(valuation.code, indicator.roa)
            .filter(
                valuation.code.in_(stocks),
                valuation.pb_ratio > 0,
                valuation.pb_ratio < 1,
                indicator.adjusted_profit > 0,
            )
        )
        # 按ROA降序排序，并取前20只股票
        stocks_df = stocks_df.sort_values(by="roa", ascending=False).head(20)
        stocks = list(stocks_df.code)
        stocks = self.filter_limitup_limitdown_stock(stocks)
        return stocks[: self.stock_sum] if stocks else []

    def adjust(self):
        """
        调仓：调用 _prepare() 获取持仓和风险信息，然后使用 filter() 筛选目标股票，
        最后使用 _adjust() 实施等权买卖操作。
        """
        self._prepare()
        target = self.filter()
        self._adjust(target)


# ---------------------------
# 子策略4：弱周期价投策略
# ---------------------------
class Weak_Cyc_Strategy(Strategy):
    def __init__(self, context, index: int, name: str):
        """
        弱周期价投策略：通过针对特定行业（如钢铁、采掘等）筛选基本面较好的股票，
        同时加入国债ETF进行防守性配置，以达到稳健盈利。
        参数:
          context, index, name -- 同基类
        """
        super().__init__(context, index, name)
        self.stock_sum = 4  # 策略计划挑选4只股票
        self.bond_etf = "511260.XSHG"  # 作为保守品种，加入国债ETF
        self.min_volume = 2000  # 规定最小交易额

    def select(self) -> list:
        """
        选股逻辑：
        1. 选取特定行业股票（例如行业代码"HY010"）
        2. 经过基础过滤和进一步的基本面筛选（市值、PE、ROA、毛利率过滤），
           从而获得优质股票
        返回:
          股票代码列表
        """
        yesterday = self.context.previous_date
        stocks = get_industry_stocks("HY010", date=yesterday)
        stocks = self.filter_basic_stock(stocks)
        stocks_df = get_fundamentals(
            query(valuation.code)
            .filter(
                valuation.code.in_(stocks),
                valuation.market_cap > 500,  # 总市值大于500亿
                valuation.pe_ratio < 20,       # 市盈率小于20
                indicator.roa > 0,             # ROA大于0
                indicator.gross_profit_margin > 30,  # 销售毛利率大于30%
            )
            .order_by(valuation.market_cap.desc())  # 按市值从大到小排序
        )
        return list(stocks_df.code)[: self.stock_sum]

    def adjust(self):
        """
        调仓逻辑：
        1. 调用 select() 获取股票选股结果（最多 self.stock_sum 只）
        2. 将国债ETF加入候选名单，用于防守性配置
        3. 计算各个标的的仓位比例，并通过 _adjust2() 实施调仓
        """
        self._prepare()
        stocks = self.select()[: self.stock_sum]
        stocks.append(self.bond_etf)
        # 计算所有标的的仓位比例（简单等权分配，债券ETF比例为剩余部分）
        rates = [round(1 / (self.stock_sum + 2), 3)] * (len(stocks) - 1)
        rates.append(round(1 - sum(rates), 3))
        total_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
        # 构造目标市值字典：每只股票对应应占用的市值
        targets = {stock: total_value * rate for stock, rate in zip(stocks, rates)}
        self._adjust2(targets)


# 代码结束