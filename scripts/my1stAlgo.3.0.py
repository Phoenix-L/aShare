# Version 3, Rewritten by 豆包

import backtrader as bt
import tushare as ts
import pandas as pd
from datetime import datetime

# -------------------------- 1. Tushare初始化 --------------------------
ts.set_token('18952b6d07542d6ad63ce79bb29b06647a9b16314fc0b984caa5d490')  # 替换成你的Token
pro = ts.pro_api()


# -------------------------- 2. 数据加载函数（核心修复） --------------------------
def get_stock_data(ts_code, start_date, end_date):
    """获取A股日线数据（含换手率）"""
    # 调用Tushare daily接口
    df = pro.daily(
        ts_code=ts_code,
        start_date=start_date.replace('-', ''),
        end_date=end_date.replace('-', '')
    )
    
    if df.empty:
        raise ValueError(f"未获取到{ts_code}的日线数据")
    
    # 核心修复1：先校验Tushare返回的字段是否包含turnover_rate
    if 'turnover_rate' not in df.columns:
        raise ValueError(f"Tushare返回的数据中没有turnover_rate字段，请检查接口/股票代码")
    
    # 核心修复2：重命名列（仅重命名需要的列，保留turnover_rate）
    rename_map = {
        'trade_date': 'datetime',
        'vol': 'volume'
        # 不修改turnover_rate，直接保留
    }
    df.rename(columns=rename_map, inplace=True)
    
    # 转换时间格式
    df['datetime'] = pd.to_datetime(df['datetime'], format='%Y%m%d')
    
    # 核心修复3：设置索引后，验证列（而非索引）是否存在
    df.set_index('datetime', inplace=True)
    if 'turnover_rate' not in df.columns:
        raise ValueError(f"设置索引后丢失turnover_rate字段")
    
    # 按日期排序
    df = df.sort_index()
    
    # 核心修复4：打印数据验证（列而非索引）
    print(f"\n数据验证：{ts_code}前5条数据（含换手率）")
    print(df[['close', 'turnover_rate']].head())
    
    # 额外：检查换手率是否为0（避免无意义数据）
    if df['turnover_rate'].max() == 0:
        print(f"警告：{ts_code}的换手率全为0，请检查数据时间段")
    
    return df

# -------------------------- 3. 自定义PandasData --------------------------
class PandasDataWithTurnover(bt.feeds.PandasData):
    """扩展Backtrader数据源，添加换手率字段"""
    lines = ("turnover_rate",)  # 声明换手率字段
    params = (("turnover_rate", -1),)  # 映射到df的turnover_rate列

# -------------------------- 4. 策略类 --------------------------
class MidFreqMA(bt.Strategy):
    params = (
        ('short_period', 5),
        ('long_period', 20),
        ('turnover_thresh', 1),  # 换手率阈值1%
    )

    def __init__(self):
        self.short_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.short_period)
        self.long_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.long_period)
        self.crossover = bt.indicators.CrossOver(self.short_ma, self.long_ma)
        self.log_enabled = True

    def log(self, txt):
        """打印日志（带时间戳）"""
        if self.log_enabled:
            dt = self.data.datetime.date(0)
            print(f'[{dt}] {txt}')

    def next(self):
        # 读取当日关键数据
        current_close = self.data.close[0]
        current_turnover = self.data.turnover_rate[0]
        short_ma_val = self.short_ma[0]
        long_ma_val = self.long_ma[0]
        crossover_val = self.crossover[0]
        
        # 每日日志（调试用）
        self.log(f'收盘价：{current_close:.2f} | MA5：{short_ma_val:.2f} | MA20：{long_ma_val:.2f} | 换手率：{current_turnover:.2f}% | 金叉信号：{crossover_val}')
        
        # 买入逻辑
        if not self.position:
            if crossover_val > 0 and current_turnover > self.p.turnover_thresh:
                cash = self.broker.getcash()
                buy_price = current_close
                max_shares = (cash // (buy_price * 100)) * 100
                if max_shares > 0:
                    self.buy(size=max_shares)
                    self.log(f'买入 {max_shares} 股 | 价格：{buy_price:.2f} | 剩余现金：{self.broker.getcash():.2f}')
        # 卖出逻辑
        else:
            if crossover_val < 0:
                self.close()
                self.log(f'卖出全部持仓 | 价格：{current_close:.2f} | 剩余现金：{self.broker.getcash():.2f}')

# -------------------------- 5. 自定义A股佣金计算器 --------------------------
class AStockCommission(bt.CommInfoBase):
    params = (
        ('commission', 0.0003),
        ('stamp_duty', 0.001),
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),
    )

    def _getcommission(self, size, price, pseudoexec):
        value = abs(size) * price
        comm = value * self.p.commission
        if size < 0:
            comm += value * self.p.stamp_duty
        return comm

# -------------------------- 6. 回测主流程 --------------------------
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)

    # 设置佣金+印花税
    comminfo = AStockCommission()
    cerebro.broker.addcommissioninfo(comminfo)
    
    # 设置滑点
    cerebro.broker.set_slippage_perc(0.001)

    # 加载数据
    stock_code = '600519.SH'
    start = '2023-01-01'
    end = '2024-12-31'
    
    try:
        df = get_stock_data(stock_code, start, end)
        data = PandasDataWithTurnover(dataname=df)
        cerebro.adddata(data)
    except Exception as e:
        print(f"数据加载失败：{e}")
        exit(1)

    # 添加策略和分析器
    cerebro.addstrategy(MidFreqMA)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, 
                        _name='sharpe',
                        timeframe=bt.TimeFrame.Days,
                        annualize=True,
                        riskfreerate=0.0)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')

    # 运行回测
    print(f'\n初始资金: {cerebro.broker.getcash():.2f} 元')
    results = cerebro.run()
    strat = results[0]
    
    # 打印结果
    final_cash = cerebro.broker.getcash()
    total_return = strat.analyzers.returns.get_analysis()["rtot"] * 100
    max_drawdown = strat.analyzers.drawdown.get_analysis()["max"]["drawdown"]
    
    print(f'最终资金: {final_cash:.2f} 元')
    print(f'总收益率: {total_return:.2f}%')
    print(f'最大回撤: {max_drawdown:.2f}%')
    
    # 夏普比率异常处理
    sharpe_data = strat.analyzers.sharpe.get_analysis()
    sharpe_ratio = sharpe_data.get("sharperatio", None)
    if sharpe_ratio is not None:
        print(f'夏普比率: {sharpe_ratio:.2f}')
    else:
        print(f'夏普比率: 无法计算（无交易/收益波动为0）')
    
    # 交易统计
    trade_analysis = strat.analyzers.trade_analyzer.get_analysis()
    print(f'\n交易统计：')
    if 'total' in trade_analysis and 'closed' in trade_analysis['total']:
        print(f'总成交次数：{trade_analysis["total"]["closed"]}')
    else:
        print(f'总成交次数：0（策略未触发交易）')

    # 绘制回测曲线
    cerebro.plot()