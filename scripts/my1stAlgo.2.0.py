# Version 2, Removed min_bar which is not supported in Free Tushare
import os
os.environ["MPLBACKEND"] = "Agg"

import matplotlib
matplotlib.use("Agg")

import backtrader as bt
import tushare as ts
import pandas as pd
from datetime import datetime



# 第一步：设置Tushare token（注册tushare后在个人中心获取）
ts.set_token('18952b6d07542d6ad63ce79bb29b06647a9b16314fc0b984caa5d490')
pro = ts.pro_api()

# 第二步：自定义数据加载函数（获取A股日线数据代替30分钟K线）
def get_stock_data(ts_code, start_date, end_date):
    """
    改用日线数据（免费版稳定可用），避开分钟线接口问题
    """
    # 用Tushare免费版稳定的daily接口（无需高积分）
    df = pro.daily(
        ts_code=ts_code,
        start_date=start_date.replace('-', ''),  # 格式：YYYYMMDD
        end_date=end_date.replace('-', '')
    )
    
    if df.empty:
        raise ValueError(f"未获取到{ts_code}的日线数据，请检查代码/日期")
    
    # 整理格式适配Backtrader
    df.rename(columns={
        'trade_date': 'datetime',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'vol': 'volume',
        'turnover_rate': 'turnover_rate'  # 日线直接有换手率，无需额外获取
    }, inplace=True)
    
    # 转换时间格式
    df['datetime'] = pd.to_datetime(df['datetime'], format='%Y%m%d')
    df.set_index('datetime', inplace=True)
    
    # 按日期排序（确保时间递增）
    df = df.sort_index()
    
    return df

# 新增：自定义PandasData类，添加换手率字段
class PandasDataWithTurnover(bt.feeds.PandasData):
    """
    扩展Backtrader的PandasData，添加turnover_rate（换手率）字段
    """
    # 1. 声明要添加的字段（lines）
    lines = ("turnover_rate",)
    
    # 2. 映射字段到DataFrame的列（-1表示按列名匹配）
    params = (
        ("turnover_rate", -1),  # turnover_rate字段对应df中的turnover_rate列
    )
    
    

# 第三步：自定义策略类（双均线+量能筛选）
class MidFreqMA(bt.Strategy):
    # 策略参数（可优化）
    params = (
        ('short_period', 5),   # 短期均线
        ('long_period', 20),   # 长期均线
        ('turnover_thresh', 0),# 换手率阈值（%）
    )

    def __init__(self):
        # 计算均线
        self.short_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.short_period)
        self.long_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.long_period)
        # 金叉/死叉信号
        self.crossover = bt.indicators.CrossOver(self.short_ma, self.long_ma)

    def next(self):
        # 无持仓，且金叉+换手率达标 → 买入
        if not self.position and self.crossover > 0 and self.data.turnover_rate[0] > self.p.turnover_thresh:
            # 用全部资金买入（新手简化，实际需仓位管理）
            self.buy(size=self.broker.getcash() // (self.data.close[0] * 100) * 100)  # A股每手100股
            print(f'买入股票: {size:.2f} 手')
        # 有持仓，且死叉 → 卖出
        elif self.position and self.crossover < 0:
            self.close()
            print('买出股票')

# 第四步：回测主流程
if __name__ == '__main__':
    # 初始化回测引擎
    cerebro = bt.Cerebro()
    # 设置初始资金
    cerebro.broker.setcash(100000.0)
    # 设置手续费（A股实际费率）
    cerebro.broker.setcommission(commission=0.0013, stocklike=True)  # 简化版，合并佣金万3和印花税千1（卖出收，买入也收）
    # 设置滑点（模拟实际交易的价格偏差，中频策略设0.1%）
    cerebro.broker.set_slippage_perc(0.001)

    # 加载数据（示例：贵州茅台 600519.SH，时间2024-01-01至2025-01-01）
    stock_code = '600519.SH'
    start = '2024-01-01'
    end = '2026-01-01'
    df = get_stock_data(stock_code, start, end)
    # 将数据导入backtrader
    data = PandasDataWithTurnover(dataname=df)
    cerebro.adddata(data)

    # 添加策略
    cerebro.addstrategy(MidFreqMA)
    # 添加分析指标（查看回测结果）
    cerebro.addanalyzer(bt.analyzers.SharpeRatio_A, _name='sharpe')  # 夏普比率
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')    # 最大回撤
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')      # 收益率

    # 运行回测
    print(f'初始资金: {cerebro.broker.getcash():.2f} 元')
    results = cerebro.run()
    strat = results[0]
    # 打印回测结果
    print(f'最终资金: {cerebro.broker.getcash():.2f} 元')
    print(f'总收益率: {strat.analyzers.returns.get_analysis()["rtot"] * 100:.2f}%')

    sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio")
    if sharpe is not None:
        print(f'夏普比率: {sharpe:.2f}')
    else:
        print("夏普比率: 无法计算（可能无交易或收益为常数）")
    print(f'最大回撤: {strat.analyzers.drawdown.get_analysis()["max"]["drawdown"]:.2f}%')
    # 绘制回测曲线（直观看到收益走势）
    import matplotlib.pyplot as plt

    portfolio = strat.analyzers.returns.get_analysis()
    print(portfolio)

    #figs = cerebro.plot(
    #    style='candlestick',
    #    iplot=False,
    #    backend='Agg',
    #    volume=False
    #)
    #fig = figs[0][0]
    #fig.savefig("backtest_result.png")
    #print("图表已保存为 backtest_result.png")
