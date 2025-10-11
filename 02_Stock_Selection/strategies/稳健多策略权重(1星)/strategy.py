# 克隆自聚宽文章：https://www.joinquant.com/post/57978
# 标题：优化了参数之后的稳健策略成绩, 年华55, 最大回撤5
# 作者：Cibo

# 作者：O_iX
# 修改优化：Cibo

# 导入函数库
from jqdata import *
from jqfactor import get_factor_values
import datetime
import math
import numpy as np
import pandas as pd
from scipy.optimize import minimize

"""--------------------------------- 初始化函数，设定基准等等 ------------------------------"""


def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    log.set_level("order", "error")  # 下单异常时才进行打印, 避免日志臃肿
    set_slippage(FixedSlippage(0.002), type="fund")  # 设置滑点
    set_slippage(FixedSlippage(0.02), type="stock")  # 设置滑点
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5,
        ),
        type="stock",
    )
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
    # 全局变量
    g.fill_stock = "511880.XSHG"
    g.strategys = {}
    # g.portfolio_value_proportion = [0.35, 0.2, 0.1, 0.25, 0.1]  # 标准版
    # g.portfolio_value_proportion = [0, 0.3, 0.1, 0.5, 0.1]  # 养老版
    g.portfolio_value_proportion = [0.3, 0.2, 0.1, 0.1, 0.3]  # 调整后的相对合理区间
    g.positions = {i: {} for i in range(len(g.portfolio_value_proportion))}  # 记录每个子策略的持仓股票

    # 策略变量
    g.jsg_signal = True

    # 子策略执行计划
    if g.portfolio_value_proportion[0] > 0:  # 搅屎棍策略
        run_weekly(jsg_adjust, 1, "11:00")
        run_daily(jsg_check, "14:50")
    if g.portfolio_value_proportion[1] > 0:  # 全天候策略
        run_monthly(all_day_adjust, 1, "11:01")
    if g.portfolio_value_proportion[2] > 0:
        run_monthly(simple_roa_adjust, 1, "11:02")  # 简单ROA策略
        run_daily(simple_roa_check, "14:52")
    if g.portfolio_value_proportion[3] > 0:
        run_weekly(weak_cyc_adjust, 1, "11:03")  # 弱周期价投策略
    if g.portfolio_value_proportion[4] > 0:
        run_daily(etf_rotation_adjust, "11:04")  # 核心资产轮动策略

    # # 子策略执行计划
    # if g.portfolio_value_proportion[0] > 0:  # 搅屎棍策略
    #     run_daily(jsg_adjust, "9:51")
    #     run_daily(jsg_check, "14:50")
    # if g.portfolio_value_proportion[1] > 0:  # 全天候策略
    #     run_daily(all_day_adjust, "9:52")
    # if g.portfolio_value_proportion[2] > 0:
    #     run_daily(simple_roa_adjust, "9:53")  # 简单ROA策略
    #     run_daily(simple_roa_check, "14:52")
    # if g.portfolio_value_proportion[3] > 0:
    #     run_daily(weak_cyc_adjust, "9:54")  # 弱周期价投策略
    # if g.portfolio_value_proportion[4] > 0:
    #     run_daily(etf_rotation_adjust, "9:55")
    #     run_daily(etf_rotation_adjust, "11:04")  # 核心资产轮动策略

    # 每日剩余资金购买货币ETF
    run_daily(end_trade, "14:59")
    # 每日打印持仓情况
    run_daily(print_holdings, "15:01")


def process_initialize(context):
    g.strategys["搅屎棍策略"] = JSG(context, index=0, name="搅屎棍策略")
    g.strategys["全天候策略"] = AllDay(context, index=1, name="全天候策略")
    g.strategys["简单ROA策略"] = SimpleROA(context, index=2, name="简单ROA策略")
    g.strategys["弱周期价投策略"] = WeakCyc(context, index=3, name="弱周期价投策略")
    g.strategys["核心资产轮动策略"] = EtfRotation(context, index=4, name="核心资产轮动策略")


"""--------------------------------- 任务调用函数 ------------------------------"""


# 尾盘处理
def end_trade(context):
    current_data = get_current_data()

    keys = [key for d in g.positions.values() if isinstance(d, dict) for key in d.keys()]
    for stock in context.portfolio.positions:
        if stock not in keys and stock != g.fill_stock and current_data[stock].last_price < current_data[
            stock].high_limit:
            if order_target_value(stock, 0):
                log.info(f"卖出{stock}因送股未记录在持仓中")

    # 买入货币ETF
    amount = int(context.portfolio.available_cash / current_data[g.fill_stock].last_price)
    if amount >= 100:
        order(g.fill_stock, amount)
        log.info(f"剩余买入 货币ETF: {amount}")


# 卖出货币ETF换现金
def get_cash(context, value):
    if g.fill_stock not in context.portfolio.positions:
        return
    current_data = get_current_data()
    amount = math.ceil(value / current_data[g.fill_stock].last_price / 100) * 100
    position = context.portfolio.positions[g.fill_stock].closeable_amount
    if amount >= 100:
        order(g.fill_stock, -min(amount, position))


def jsg_check(context):
    g.strategys["搅屎棍策略"].check()


def jsg_adjust(context):
    g.strategys["搅屎棍策略"].adjust()


def all_day_adjust(context):
    g.strategys["全天候策略"].adjust()


def simple_roa_adjust(context):
    g.strategys["简单ROA策略"].adjust()


def simple_roa_check(context):
    g.strategys["简单ROA策略"].check()


def weak_cyc_adjust(context):
    g.strategys["弱周期价投策略"].adjust()


def etf_rotation_adjust(context):
    g.strategys["核心资产轮动策略"].adjust()


def print_holdings(context):
    """打印当前持仓明细（股票代码、名称、成本价、盈亏、持仓金额）"""
    print(f"{'-' * 30} {str(context.current_dt)[:10]} 持仓信息 {'-' * 30}")
    # 获取当前持仓字典（代码: Position对象）
    positions = context.portfolio.positions
    if not positions:
        print("当前无持仓")
        return
    # 打印表头
    # 遍历所有持仓
    all_pnl_value = 0
    total_value = 0
    for stock in positions:
        position = positions[stock]
        # 获取股票名称
        stock_name = get_security_info(stock).display_name
        # 获取当前价格
        current_price = get_current_data()[stock].last_price

        # 计算关键指标
        cost_price = position.avg_cost  # 聚宽自动计算平均持仓成本
        current_value = position.total_amount * current_price  # 当前价值
        cost_value = position.total_amount * position.avg_cost  # 成本价值
        pnl_value = current_value - cost_value  # 当前盈亏金额
        pnl_ratio = ((current_price - cost_price) / cost_price * 100) if cost_price != 0 else 0  # 当前盈亏比例
        stock_show = f"{stock} {stock_name[:8]}: "
        stock_show = stock_show.ljust(20)
        if "ETF" in stock_show:
            stock_show += "  "
        current_show = f"{position.total_amount} * {round(current_price, 2)}"
        total_value += current_value
        # 格式化输出
        print(f"{stock_show}  "
              f"成本价{cost_price:<7.2f}  "
              f"当前价{current_price:<7.2f}  "
              f"价值{current_value:.2f}({current_show:^17})   "
              f"盈亏 {'📈' if pnl_value > 0 else '📉'} {pnl_ratio:.2f}%( {pnl_value:.2f} )")
        all_pnl_value += pnl_value
    print(f"  --------  {str(context.current_dt)[:10]} 合计: {total_value:.2f}  总盈亏:  {all_pnl_value:.2f}   --------  ")


"""--------------------------------- 策略基类 ------------------------------"""


class Strategy:

    def __init__(self, context, index, name):
        self.context = context
        self.index = index
        self.name = name
        self.stock_sum = 1
        self.hold_list = []
        self.min_volume = 2000
        self.pass_months = [1, 4]
        self.def_stocks = ["511260.XSHG", "518880.XSHG", "512800.XSHG"]  # 债券ETF、黄金ETF、银行ETF

    # 获取股票中文名称
    def get_stock_name(self, security):
        stock_info = get_security_info(security)
        return stock_info.display_name

    # 获取策略当前持仓市值
    def get_total_value(self):
        if not g.positions[self.index]:
            return 0
        return sum(
            self.context.portfolio.positions[key].price * value for key, value in g.positions[self.index].items())

    # 卖出非连板股票，并且返回成功卖出的股票列表
    def _check(self):
        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())
        stocks = []
        # 获取昨日涨停、前日涨停昨日跌停列表
        if self.hold_list != []:
            df = get_price(
                self.hold_list,
                end_date=self.context.previous_date,
                frequency="daily",
                fields=["close", "high_limit"],
                count=3,
                panel=False,
                fill_paused=False,
            )
            df = df[df["close"] == df["high_limit"]]  # 收盘价为涨停价
            for stock in df.code.drop_duplicates():
                if self.order_target_value_(stock, 0):  # 全部卖出
                    stocks.append(stock)
        return stocks

    # 调仓(等权购买target中按顺序排列固定数量的的标的)
    def _adjust(self, target):

        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())

        # 调仓卖出
        for stock in self.hold_list:
            if stock not in target:
                self.order_target_value_(stock, 0)

        # 调仓买入
        target = [stock for stock in target if stock not in self.hold_list]
        _sum = self.stock_sum - len(self.hold_list)
        self.buy(target[: min(len(target), _sum)])

    # 调仓2(targets为字典，key为股票代码，value为目标市值)
    def _adjust2(self, targets):

        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())
        current_data = get_current_data()
        portfolio = self.context.portfolio

        # 清仓被调出的
        for stock in self.hold_list:
            if stock not in targets:
                self.order_target_value_(stock, 0)

        # 先卖出
        for stock, target in targets.items():
            price = current_data[stock].last_price
            value = g.positions[self.index].get(stock, 0) * price
            if value - target > self.min_volume and value - target > price * 100:
                self.order_target_value_(stock, target)

        # 后买入
        for stock, target in targets.items():
            price = current_data[stock].last_price
            value = g.positions[self.index].get(stock, 0) * price
            if target - value > self.min_volume and target - value > price * 100:
                if target - value > portfolio.available_cash:
                    get_cash(self.context, target - value - portfolio.available_cash)
                if portfolio.available_cash > price * 100 and portfolio.available_cash > self.min_volume:
                    self.order_target_value_(stock, target)

    # 可用现金等比例买入
    def buy(self, target):

        count = len(target)
        portfolio = self.context.portfolio

        # target为空或者持仓数量已满，不进行操作
        if count == 0 or self.stock_sum <= len(self.hold_list):
            return

        # 目标市值
        target_value = portfolio.total_value * g.portfolio_value_proportion[self.index]

        # 当前市值
        position_value = self.get_total_value()

        # 可用现金:当前现金 + 货币ETF市值
        available_cash = portfolio.available_cash + (
            portfolio.positions[g.fill_stock].value if g.fill_stock in portfolio.positions else 0)

        # 买入股票的总市值
        value = max(0, min(target_value - position_value, available_cash))

        # 卖出部分货币ETF获取现金
        if value > portfolio.available_cash:
            get_cash(self.context, value - portfolio.available_cash)

        # 等价值买入每一个未买入的标的
        for security in target:
            self.order_target_value_(security, value / count)

    # 自定义下单(涨跌停不交易)
    def order_target_value_(self, security, value):
        current_data = get_current_data()
        security_name = self.get_stock_name(security)

        # 检查标的是否停牌、涨停、跌停
        if current_data[security].paused:
            print(f"{security} {security_name}: 今日停牌")
            return False
        if current_data[security].last_price == current_data[security].high_limit:
            print(f"{security} {security_name}: 当前涨停")
            return False
        if current_data[security].last_price == current_data[security].low_limit:
            print(f"{security} {security_name}: 当前跌停")
            return False

        price = current_data[security].last_price
        current_position = g.positions[self.index].get(security, 0)
        target_position = (int(value / price) // 100) * 100 if price != 0 else 0
        adjustment = target_position - current_position

        # 检查是否当天买入卖出
        closeable_amount = self.context.portfolio.positions[
            security].closeable_amount if security in self.context.portfolio.positions else 0
        if adjustment < 0 and closeable_amount == 0:
            print(f"{security} {security_name}: 当天买入不可卖出")
            return False

        if adjustment != 0:
            o = order(security, adjustment)
            if o:
                # 记录持仓成本, 更新持仓数量
                amount = o.amount if o.is_buy else -o.amount
                g.positions[self.index][security] = amount + current_position
                if target_position == 0:
                    g.positions[self.index].pop(security, None)
                self.hold_list = list(g.positions[self.index].keys())

                # 格式化股票名称显示（固定长度对齐）
                stock_show = f"{security} {security_name[:8]}: "
                stock_show = stock_show.ljust(20)
                if "ETF" in stock_show:
                    stock_show += "  "

                if o.is_buy:
                    print(f"🟠🟠🟠🟠{stock_show}  "
                          f"目标数量{target_position:<7}  "
                          f"买入价格{o.price:<7.2f}  "
                          f"买入数量{o.amount:<7}   "
                          f"价值{o.price * o.amount:.2f}")
                else:
                    print(f"{'🟣🟣🟣🟣' if value == 0 else '🟢🟢🟢🟢'}{stock_show}  "
                          f"卖出价格{o.price:<7.2f}  "
                          f"成本价格{o.avg_cost:<7.2f}   "
                          f"卖出数量{o.amount:<7}   "
                          f"盈亏{(o.price - o.avg_cost) * o.amount:.2f}"
                          f"( {(o.price - o.avg_cost) / o.avg_cost * 100:.2f}% )")

                return True
        return False

    # 基础过滤(过滤科创北交、ST、停牌、次新股)
    def filter_basic_stock(self, stock_list):

        current_data = get_current_data()
        return [
            stock
            for stock in stock_list
            if not current_data[stock].paused
               and not current_data[stock].is_st
               and "ST" not in current_data[stock].name
               and "*" not in current_data[stock].name
               and "退" not in current_data[stock].name
               and not (stock[0] == "4" or stock[0] == "8" or stock[:2] == "68")
               and not self.context.previous_date - get_security_info(stock).start_date < datetime.timedelta(375)
        ]

    # 过滤当前时间涨跌停的股票
    def filter_limitup_limitdown_stock(self, stock_list):
        current_data = get_current_data()
        return [
            stock
            for stock in stock_list
            if current_data[stock].last_price < current_data[stock].high_limit and current_data[stock].last_price >
               current_data[stock].low_limit
        ]

    # 过滤近几日涨停过的股票
    def filter_limitup_stock(self, stock_list, days):
        df = get_price(
            stock_list,
            end_date=self.context.previous_date,
            frequency="daily",
            fields=["close", "high_limit"],
            count=days,
            panel=False,
        )
        df = df[df["close"] == df["high_limit"]]
        filterd_stocks = df.code.drop_duplicates().tolist()
        return [stock for stock in stock_list if stock not in filterd_stocks]

    # 判断今天是在空仓月
    def is_empty_month(self):
        month = self.context.current_dt.month
        return month in self.pass_months


"""--------------------------------- 子策略 ------------------------------"""


# 搅屎棍策略
class JSG(Strategy):

    def __init__(self, context, index, name):
        super().__init__(context, index, name)

        self.stock_sum = 4
        # 判断买卖点的行业数量
        self.num = 1
        # 空仓的月份
        self.pass_months = [1, 4]

    def getStockIndustry(self, stocks):
        industry = get_industry(stocks)
        return pd.Series({stock: info["sw_l1"]["industry_name"] for stock, info in industry.items() if "sw_l1" in info})

    # 获取市场宽度
    def get_market_breadth(self):
        # 指定日期防止未来数据
        yesterday = self.context.previous_date
        # 获取初始列表
        stocks = get_index_stocks("000985.XSHG")
        count = 1
        h = get_price(
            stocks,
            end_date=yesterday,
            frequency="1d",
            fields=["close"],
            count=count + 20,
            panel=False,
        )
        h["date"] = pd.DatetimeIndex(h.time).date
        df_close = h.pivot(index="code", columns="date", values="close").dropna(axis=0)
        # 计算20日均线
        df_ma20 = df_close.rolling(window=20, axis=1).mean().iloc[:, -count:]
        # 计算偏离程度
        df_bias = df_close.iloc[:, -count:] > df_ma20
        df_bias["industry_name"] = self.getStockIndustry(stocks)
        # 计算行业偏离比例
        df_ratio = ((df_bias.groupby("industry_name").sum() * 100.0) / df_bias.groupby("industry_name").count()).round()
        # 获取偏离程度最高的行业
        top_values = df_ratio.loc[:, yesterday].nlargest(self.num)
        I = top_values.index.tolist()
        return I

    # 过滤股票
    def filter(self):
        stocks = get_index_stocks("399101.XSHE")
        stocks = self.filter_basic_stock(stocks)
        stocks = self.filter_limitup_stock(stocks, 5)  # 检查最近5日涨停
        stocks = (
            get_fundamentals(
                query(
                    valuation.code,
                )
                .filter(
                    valuation.code.in_(stocks),
                    indicator.adjusted_profit > 0,
                )
                .order_by(valuation.market_cap.asc())
            )
            .head(20)
            .code
        )
        stocks = self.filter_limitup_limitdown_stock(stocks)
        return stocks

    # 择时
    def select(self):
        I = self.get_market_breadth()
        industries = {"银行I", "煤炭I", "采掘I", "钢铁I"}
        if not industries.intersection(I) and not self.is_empty_month():
            return True
        return False

    # 调仓
    def adjust(self):
        if self.select():
            stocks = self.filter()[: self.stock_sum]
            self._adjust(stocks)
        else:
            total_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
            self._adjust2({stock: total_value / len(self.def_stocks) for stock in self.def_stocks})

    # 检查昨日涨停票
    def check(self):
        banner_stocks = self._check()
        if banner_stocks:
            target = [stock for stock in self.filter() if stock not in banner_stocks and stock not in self.hold_list][
                     : len(banner_stocks)]
            self.buy(target)


# 全天候ETF策略
class AllDay(Strategy):

    def __init__(self, context, index, name):
        super().__init__(context, index, name)

        # 最小交易额(限制手续费)
        self.min_volume = 2000
        # 全天候ETF组合参数
        self.etf_pool = [
            # "510880.XSHG",  # 红利
            "518880.XSHG",  # 黄金ETF
            "513100.XSHG",  # 纳指100
        ]
        # 标的仓位占比
        self.rates = [0.66, 0.34]

    # 调仓
    def adjust(self):
        total_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
        # 计算每个 ETF 的目标价值
        targets = {etf: total_value * rate for etf, rate in zip(self.etf_pool, self.rates)}
        self._adjust2(targets)


# 简单ROA策略
class SimpleROA(Strategy):
    def __init__(self, context, index, name):
        super().__init__(context, index, name)

        self.stock_sum = 1

    def filter(self):
        stocks = get_all_securities("stock", date=self.context.previous_date).index.tolist()
        stocks = self.filter_basic_stock(stocks)
        stocks = list(
            get_fundamentals(
                query(valuation.code, indicator.roa).filter(
                    valuation.code.in_(stocks),
                    valuation.pb_ratio > 0,
                    valuation.pb_ratio < 1,  # 破净股：PB<1
                    indicator.adjusted_profit > 0,  # 盈利：扣非净利润>0
                )
            )
            .sort_values(by="roa", ascending=False)  # 按ROA降序排序
            .head(10)  # 取ROA最高的10只
            .code
        )
        stocks = self.filter_limitup_limitdown_stock(stocks)
        return stocks

    # 调仓
    def adjust(self):
        self._adjust(self.filter()[: self.stock_sum])

    # 检查昨日涨停票
    def check(self):
        banner_stocks = self._check()
        if banner_stocks:
            target = [stock for stock in self.filter() if stock not in banner_stocks and stock not in self.hold_list][
                     : len(banner_stocks)]
            self.buy(target)


# 弱周期价投策略
class WeakCyc(Strategy):
    def __init__(self, context, index, name):
        super().__init__(context, index, name)

        self.bond_etf = "511260.XSHG"
        self.targets = {}
        # 最小交易额(限制手续费)
        self.min_volume = 10000
        # 行业比例（公用事业、交通运输）
        self.industry_ratio = [0.2, 0.2]
        # 个股比例(龙一龙二)
        self.stock_ratio = [1]
        self.total_value = 0

    # 分红过滤(近几年的分红总和满足股息率与股利支付率)
    def filter_dividend(self, stocks, year, div_yield, payout_rate):

        if not stocks:
            return []

        time1 = self.context.previous_date
        time0 = time1 - timedelta(days=(year + 0.1) * 365)
        f = finance.STK_XR_XD
        q = query(f.code, f.bonus_amount_rmb).filter(
            f.code.in_(stocks),
            f.a_registration_date >= time0,
            f.a_registration_date <= time1,
        )
        df = finance.run_query(q).fillna(0).set_index("code").groupby("code").sum()

        # 获取市值相关数据
        q = query(valuation.code, valuation.market_cap, valuation.pe_ratio).filter(valuation.code.in_(list(df.index)))
        cap = get_fundamentals(q, date=time1).set_index("code")

        # 计算股息率, 股利支付率
        df = pd.concat([df, cap], axis=1, sort=False)
        df["div_yield"] = df["bonus_amount_rmb"] / (df["market_cap"] * 10000) / year
        df["payout_rate"] = df["bonus_amount_rmb"] / ((df["market_cap"] * 10000) / df["pe_ratio"]) / year
        df = df.query("div_yield > @div_yield and payout_rate > @payout_rate")
        return list(df.index)

    # 利润过滤(近几年的营业收入、净利率、毛利率)
    def filter_profit(self, stocks, year, net_profit_margin, gross_profit_margin):

        if not stocks:
            return []

        df = get_history_fundamentals(
            stocks,
            fields=[income.operating_revenue, indicator.net_profit_margin, indicator.gross_profit_margin],
            watch_date=self.context.previous_date,
            count=4 * year,
            interval="1q",
            stat_by_year=False,
        )

        def agg_func(group):
            revenue = group["operating_revenue"].sum()
            return pd.Series(
                {
                    "operating_revenue": revenue,
                    "weighted_net_profit_margin": (group["operating_revenue"] * group[
                        "net_profit_margin"]).sum() / revenue,
                    "weighted_gross_profit_margin": (group["operating_revenue"] * group[
                        "gross_profit_margin"]).sum() / revenue,
                }
            )

        df = df.groupby("code").apply(agg_func).reset_index()
        df = df.query(
            "weighted_net_profit_margin > @net_profit_margin and weighted_gross_profit_margin > @gross_profit_margin")
        return list(df.code)

    # 获取净利润波动率(近几年的净利润标准差)
    def get_profit_vol(self, stocks, year):

        df = get_history_fundamentals(
            stocks,
            fields=[income.net_profit],
            watch_date=self.context.previous_date,
            count=4 * year,
            interval="1q",
            stat_by_year=False,
        )
        df["rolling_profit"] = df.groupby("code")["net_profit"].rolling(4).sum().reset_index(level=0, drop=True)
        df["growth_rate"] = df.groupby("code")["rolling_profit"].pct_change()
        return df.groupby("code")["growth_rate"].std().reset_index(name="volatility")

    # 801160: 公用事业I
    def select1(self):
        stocks = get_industry_stocks("801160")
        # 基本面过滤
        stocks = self.filter_basic_stock(stocks)
        df = get_fundamentals(
            query(valuation.code, valuation.pe_ratio).filter(
                valuation.code.in_(stocks),
                # 现金流
                cash_flow.net_operate_cash_flow > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 1.0,
                # 资产
                balance.total_liability / balance.total_assets < 0.8,
                # 市值
                valuation.market_cap > 200,
            )
        )

        stocks = self.filter_dividend(list(df.code), 3, 0.02, 0.4)
        stocks = self.filter_profit(stocks, 1, 20, 30)

        if not stocks:
            return

        # 业绩排序
        vol = self.get_profit_vol(stocks, 3)
        df = vol.merge(df[["code", "pe_ratio"]], on="code", how="left")
        df["score"] = 1 / df["pe_ratio"] * (1 - 2 * df["volatility"])
        df = df.sort_values(by="score", ascending=False).reset_index(drop=True)

        for i, ratio in enumerate(self.stock_ratio[: len(df)]):
            self.targets[df.code[i]] = self.total_value * ratio * self.industry_ratio[0]

    # 801170: 交通运输I
    def select2(self):
        stocks = get_industry_stocks("801170")
        # 基本面过滤
        stocks = self.filter_basic_stock(stocks)
        df = get_fundamentals(
            query(valuation.code, valuation.pe_ratio, indicator.roa).filter(
                valuation.code.in_(stocks),
                # 现金流
                cash_flow.net_operate_cash_flow > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 1.0,
                # 资产
                balance.total_liability / balance.total_assets < 0.6,
                # 市值
                valuation.market_cap > 200,
            )
        )
        stocks = self.filter_dividend(list(df.code), 3, 0.02, 0.3)
        stocks = self.filter_profit(stocks, 1, 20, 30)

        if not stocks:
            return

        # 业绩排序
        vol = self.get_profit_vol(stocks, 3)
        df = vol.merge(df[["code", "pe_ratio"]], on="code", how="left")
        df["score"] = 1 / df["pe_ratio"] * (1 - 2 * df["volatility"])
        df = df.sort_values(by="score", ascending=False).reset_index(drop=True)

        for i, ratio in enumerate(self.stock_ratio[: len(df)]):
            self.targets[df.code[i]] = self.total_value * ratio * self.industry_ratio[1]

    def adjust(self):
        self.targets = {}
        self.total_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
        self.select1()
        self.select2()
        self.targets[self.bond_etf] = self.total_value - sum(list(self.targets.values()))
        self._adjust2(self.targets)


# 核心资产轮动策略
class EtfRotation(Strategy):
    def __init__(self, context, index, name):
        super().__init__(context, index, name)

        self.stock_sum = 1
        self.etf_pool = [
            # 境外
            "513100.XSHG",  # 纳指ETF
            "513520.XSHG",  # 日经ETF
            "513030.XSHG",  # 德国ETF
            # 商品
            "518880.XSHG",  # 黄金ETF
            "159980.XSHE",  # 有色ETF
            "159985.XSHE",  # 豆粕ETF
            "501018.XSHG",  # 南方原油
            # 债券
            "511090.XSHG",  # 30年国债ETF
            # 国内
            "513130.XSHG",  # 恒生科技
            "510880.XSHG",  # 红利
        ]
        self.m_days = 25  # 动量参考天数

    def get_etf_rank(self):
        data = pd.DataFrame(index=self.etf_pool, columns=["annualized_returns", "r2", "score"])
        current_data = get_current_data()
        for etf in self.etf_pool:
            # 获取数据
            df = attribute_history(etf, self.m_days, "1d", ["close", "high"])
            prices = np.append(df["close"].values, current_data[etf].last_price)

            # 设置参数
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))

            # 计算年化收益率
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1

            # 计算R2
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0

            # 计算得分
            score = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]
            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]

            # 过滤近3日跌幅超过5%的ETF
            if min(prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4]) < 0.95:
                data.loc[etf, "score"] = 0

        # 过滤ETF，并按得分降序排列
        data = data.query("0 < score < 6").sort_values(by="score", ascending=False)

        return data.index.tolist()

    def adjust(self):
        target = self.get_etf_rank()
        self._adjust(target[: min(self.stock_sum, len(target))])
