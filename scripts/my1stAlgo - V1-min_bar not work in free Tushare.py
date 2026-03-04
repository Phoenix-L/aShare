import backtrader as bt
import tushare as ts
import pandas as pd
from datetime import datetime

# 第一步：设置Tushare token（注册tushare后在个人中心获取）
ts.set_token('18952b6d07542d6ad63ce79bb29b06647a9b16314fc0b984caa5d490')
pro = ts.pro_api()

# 第二步：自定义数据加载函数（获取A股30分钟K线）
def get_stock_data(ts_code, start_date, end_date):
    # 获取30分钟K线（tushare免费版只能获取最近1年）
    df = pro.min_bar(ts_code=ts_code, start_date=start_date, end_date=end_date, freq='30min')
    # 整理数据格式，适配backtrader
    df.rename(columns={
        'trade_time': 'datetime',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'vol': 'volume'
    }, inplace=True)
    # 转换时间格式
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    # 补充换手率（日线级别，新手先简化）
    df_daily = pro.daily(ts_code=ts_code, start_date=start_date.replace('-', ''), end_date=end_date.replace('-', ''))
    df_daily['trade_date'] = pd.to_datetime(df_daily['trade_date'], format='%Y%m%d')
    df_daily.set_index('trade_date', inplace=True)
    df['turnover_rate'] = df.index.date.map(lambda x: df_daily.loc[x, 'turnover_rate'] if x in df_daily.index else 0)
    return df

# 第三步：自定义策略类（双均线+量能筛选）
class MidFreqMA(bt.Strategy):
    # 策略参数（可优化）
    params = (
        ('short_period', 5),   # 短期均线
        ('long_period', 20),   # 长期均线
        ('turnover_thresh', 5),# 换手率阈值（%）
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
        # 有持仓，且死叉 → 卖出
        elif self.position and self.crossover < 0:
            self.close()

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
    end = '2025-01-01'
    df = get_stock_data(stock_code, start, end)
    # 将数据导入backtrader
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    # 添加策略
    cerebro.addstrategy(MidFreqMA)
    # 添加分析指标（查看回测结果）
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')  # 夏普比率
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')    # 最大回撤
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')      # 收益率

    # 运行回测
    print(f'初始资金: {cerebro.broker.getcash():.2f} 元')
    results = cerebro.run()
    strat = results[0]
    # 打印回测结果
    print(f'最终资金: {cerebro.broker.getcash():.2f} 元')
    print(f'总收益率: {strat.analyzers.returns.get_analysis()["rtot"] * 100:.2f}%')
    print(f'夏普比率: {strat.analyzers.sharpe.get_analysis()["sharperatio"]:.2f}')
    print(f'最大回撤: {strat.analyzers.drawdown.get_analysis()["max"]["drawdown"]:.2f}%')
    # 绘制回测曲线（直观看到收益走势）
    cerebro.plot()
