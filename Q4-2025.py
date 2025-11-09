
from AlgorithmImports import *
import numpy as np
from collections import deque


class HKUSTIntradayMomentum(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2000, 1, 1)
        self.set_cash(100000)

       
        symbol_list = [ 'SPY','QQQ','GBTC']
        # Feed in historical data
        self.set_warm_up(timedelta(100))
        

        for symbol in symbol_list:
            ticker = self.add_equity(
                symbol, 
                Resolution.MINUTE,
                data_normalization_mode=DataNormalizationMode.TOTAL_RETURN
                )
            
            ticker.margin_model = PatternDayTradingMarginModel()
            ticker._vwap = self.vwap(ticker.symbol)
            ticker._roc = self.rocp(ticker.symbol, 1, Resolution.DAILY)
            ticker._vol = IndicatorExtensions.of(StandardDeviation(14), ticker._roc)
            ticker._deviation = AbsoluteDeviation('deviation', 63)
            ticker._previous_date = None
            ticker._open_price = None
            ticker._previous_close = None
            ticker._last_trade_date = None
            ticker._bars = deque(maxlen=2)
            self.consolidate(ticker.symbol, timedelta(minutes=30), self.consolidate_handler)




        self.schedule.on(
            self.date_rules.every_day(symbol_list[0]),
    
            self.time_rules.before_market_close(symbol_list[0], 1),
            self.end_of_day
        )

    def consolidate_handler(self, bar):

        symbol = bar.symbol
        security = self.securities[symbol]

        current_date = bar.end_time.date()

        security._bars.append(bar)

        if current_date != security._previous_date:
            security._previous_date = current_date
            security._open_price = bar.open
            security._previous_close = security._bars[-2].close if len(security._bars) == 2 else None

        security._deviation.update(bar)

        if not security._vol.is_ready or not security._previous_close or not security._deviation.ready:
            return

        upper_bound = (max(security._open_price, security._previous_close) * (1 + security._deviation.value))
        lower_bound = (min(security._open_price, security._previous_close) * (1 - security._deviation.value))

        vwap_price = security._vwap.current.value

        long_stop_price = np.max([vwap_price, upper_bound])
        short_stop_price = np.min([vwap_price, lower_bound])

        is_up_trend = bar.close > security._vwap.current.value
        is_down_trend = bar.close < security._vwap.current.value

        is_long = self.portfolio[symbol].is_long
        is_short = self.portfolio[symbol].is_short

        is_long_stopped_out = is_long and bar.close <= long_stop_price
        is_short_stopped_out = is_short and bar.close >= short_stop_price

        is_not_last_trade_date = security._last_trade_date != current_date

        vol_target = 0.02
        spy_vol = security._vol.current.value / 100
        leverage = np.min([2, vol_target / spy_vol]) * 1 / len(self.securities.keys())
        
        #make sure orders are sent after warmup period
        if self.is_warming_up:
            return
        if is_long_stopped_out or is_short_stopped_out:
            self.liquidate(symbol)

        if bar.close > upper_bound and not is_long and is_up_trend and is_not_last_trade_date:
            self.set_holdings(symbol, 1 * leverage)
            security._last_trade_date = current_date
        elif bar.close < lower_bound and not is_short and is_down_trend and is_not_last_trade_date:
            self.set_holdings(symbol, -1 * leverage)
            security._last_trade_date = current_date


    def end_of_day(self):
        self.liquidate()


class AbsoluteDeviation(PythonIndicator):

    def __init__(self, name, period):
        super().__init__()
        self.name = name
        self.period = period
        self.data = {}
        self.ready = False

        self.previous_data = None
        self.open_price = None

    def update(self, data: BaseData):
        current_data = data.end_time.date()

        if current_data != self.previous_data:
            self.previous_data = current_data
            self.open_price = data.open

        current_time = data.end_time.time()
        
        if current_time not in self.data:
            self.data[current_time] = deque(maxlen=self.period)

        self.data[current_time].append(
            np.abs(data.close / self.open_price - 1)
            )
        
        if len(self.data[current_time]) == self.period:
            self.ready = True
        
        self.value = np.mean(self.data[current_time])

        return len(self.data[current_time]) == self.period