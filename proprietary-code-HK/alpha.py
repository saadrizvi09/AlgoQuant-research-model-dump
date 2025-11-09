#region imports
from AlgorithmImports import *
from indicators import *
from collections import deque
import numpy as np
import scipy as sp
#endregion

class TSZscore_VwapReversion(AlphaModel):

    def __init__(self):
        self.period = 20
        self.securities_list = []
        self.day = -1
        self.historical_VwapReversion_by_symbol = {}


    def on_securities_changed(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        # Register each security in the universe
        for security in changes.added_securities:
            if security not in self.securities_list:
                self.historical_VwapReversion_by_symbol[security.symbol] = deque(maxlen=self.period)
                self.securities_list.append(security)

        for security in changes.removed_securities:
            if security in self.securities_list:
                self.securities_list.remove(security)


    def update(self, algorithm: QCAlgorithm, data: Slice) -> List[Insight]: 
        if data.quote_bars.count == 0:   # Only emit insights when there is quote data, not when a corporate action occurs (at midnight)
            return []
        if self.day == algorithm.time.day:  # Only emit insights once per day
            return []
        self.day = algorithm.time.day

        # Neutralize Vwap/Close of securities so it's mean 0, then append them to the list 
        temp_list = {}
        for security in self.securities_list:
            if security.Close != 0:
                temp_list[security.symbol] = algorithm.vwap(security.symbol).Current.Value/security.Close
            else: 
                temp_list[security.symbol] = 1
        temp_mean = sum(temp_list.values())/len(temp_list.values())

        for security in self.securities_list:
            self.historical_VwapReversion_by_symbol[security.symbol].appendleft(temp_list[security.symbol]-temp_mean)
        
        # Compute ts_zscore of current Vwap/Close
        zscore_by_symbol = {}
        for security in self.securities_list:
            zscore_by_symbol[security.symbol] = sp.stats.zscore(self.historical_VwapReversion_by_symbol[security.symbol])[0]
        
        # create insights to long / short the asset
        insights = []
        weights = {}
        for symbol, zscore in zscore_by_symbol.items():
            if not np.isnan(zscore):
                weight = zscore
            else:
                weight = 0
            weights[symbol] = weight


        # Make scale similar across alphas
        abs_weight = {key: abs(val) for key, val in weights.items()}
        weights_sum = sum(abs_weight.values())
        if weights_sum != 0:
            for symbol, weight in weights.items():
                weights[symbol] = weight/ weights_sum


        for symbol, weight in weights.items():
            if weight > 0:
                insights.append(Insight.price(symbol, Expiry.END_OF_DAY, InsightDirection.UP, weight=weight))
            elif weight < 0:
                insights.append(Insight.price(symbol, Expiry.END_OF_DAY, InsightDirection.DOWN, weight=weight))

        return insights


class TSZscore_DividendGrowth(AlphaModel):

    def __init__(self):
        self.period = 252
        self.day = -1
        self.securities_list = []
        self.dps = {}
        

    def on_securities_changed(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        # Register each security in the universe
        for security in changes.added_securities:
            if security not in self.securities_list:
                self.dps[security.symbol] = deque(maxlen=self.period)
                self.securities_list.append(security)

        for security in changes.removed_securities:
            if security in self.securities_list:
                self.securities_list.remove(security)

    def update(self, algorithm: QCAlgorithm, data: Slice) -> List[Insight]:
        if data.quote_bars.count == 0:   # Only emit insights when there is quote data, not when a corporate action occurs (at midnight)
            return []
        if self.day == algorithm.time.day:  # Only emit insights once per day
            return []
        self.day = algorithm.time.day
        
        # Append dividend to the list, compute ts_zscore of current dividend
        zscore_by_symbol = {}
        for security in self.securities_list:
            if not np.isnan(security.fundamentals.earning_reports.dividend_per_share.Value):
                self.dps[security.symbol].appendleft(security.fundamentals.earning_reports.dividend_per_share.Value)
                zscore_by_symbol[security.symbol] = sp.stats.zscore(self.dps[security.symbol])[0]

        
        # create insights to long / short the asset
        insights = []
        weights = {}
        for symbol, zscore in zscore_by_symbol.items():
            if not np.isnan(zscore):
                weight = zscore
            else:
                weight = 0
            weights[symbol] = weight
            
        # Make scale similar across alphas
        abs_weight = {key: abs(val) for key, val in weights.items()}
        weights_sum = sum(abs_weight.values())
        if weights_sum != 0:
            for symbol, weight in weights.items():
                weights[symbol] = weight/ weights_sum

        for symbol, weight in weights.items():
            if weight >= 0:
                insights.append(Insight.price(symbol, Expiry.END_OF_DAY, InsightDirection.UP, weight=weight))
            else:
                insights.append(Insight.price(symbol, Expiry.END_OF_DAY, InsightDirection.DOWN, weight=weight))

        
        return insights


class Conditional_Reversion(AlphaModel):

    def __init__(self):
        self.condition_period = 5
        self.period = 3
        self.securities_list = []
        self.day = -1
        self.historical_volume_by_symbol = {}
        self.historical_close_by_symbol = {}
        

    def on_securities_changed(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        # Register each security in the universe
        for security in changes.added_securities:
            if security not in self.securities_list:
                self.historical_volume_by_symbol[security.symbol] = deque(maxlen=self.condition_period)
                self.historical_close_by_symbol[security.symbol] = deque(maxlen=self.period)
                self.securities_list.append(security)

        for security in changes.removed_securities:
            if security in self.securities_list:
                self.securities_list.remove(security)


    def update(self, algorithm: QCAlgorithm, data: Slice) -> List[Insight]: 
        if data.quote_bars.count == 0:   # Only emit insights when there is quote data, not when a corporate action occurs (at midnight)
            return []
        if self.day == algorithm.time.day:  # Only emit insights once per month
            return []
        self.day = algorithm.time.day
        

        # Append volume and close to the list
        zscore_by_symbol = {}
        return_by_symbol = {}
        for security in self.securities_list:
            if (security.Close != 0 and security.Volume != 0):
                self.historical_close_by_symbol[security.symbol].appendleft(security.Close)
                self.historical_volume_by_symbol[security.symbol].appendleft(security.Volume)
                return_by_symbol[security.symbol] = (self.historical_close_by_symbol[security.symbol][0] - self.historical_close_by_symbol[security.symbol][-1])

        if return_by_symbol == {}:  # Don't emit insight if there's no valid data
            return []

        # Rank the 3 days return among securities to return value from 0 to 1
        sorted_return_by_symbol = sorted(return_by_symbol.items(), key=lambda x: x[1])
        return_rank_by_symbol = {}
        for item in sorted_return_by_symbol:   # item is a key-value pair. [0] is the security symbol and [1] is the return
            return_rank_by_symbol[item[0]] = (sorted_return_by_symbol.index(item))/ len(sorted_return_by_symbol)
        
        # Calculating the final weight
        weights = {}
        
        for security in self.securities_list:
            # If condition is met, assign weight
            if len(self.historical_volume_by_symbol[security.symbol]) != 0 and max(self.historical_volume_by_symbol[security.symbol]) == security.Volume:
                weight = -return_rank_by_symbol[security.symbol] # Change this sign and complete different behaviour if purely long. Investigate
            else:
                weight = 0 
            weights[security.symbol] = weight

        weights_mean = sum(weights.values())/len(weights.values())
        for symbol, weight in weights.items():
            weights[symbol] = weight - weights_mean

        # Make scale similar across alphas
        abs_weight = {key: abs(val) for key, val in weights.items()}
        weights_sum = sum(abs_weight.values())
        if weights_sum != 0:
            for symbol, weight in weights.items():
                weights[symbol] = weight/ weights_sum


        # Create insights to long / short the asset
        insights = []
        for symbol, weight in weights.items():
            if weight > 0:
                insights.append(Insight.price(symbol, Expiry.END_OF_DAY, InsightDirection.UP, weight=weight))
            elif weight < 0:
                insights.append(Insight.price(symbol, Expiry.END_OF_DAY, InsightDirection.DOWN, weight=weight))
        #Expiry.END_OF_DAY
        return insights


class MomentumQuantilesAlphaModel(AlphaModel):

    def __init__(self):
        self.quantiles = 10
        self.lookback_months = 6
        self.securities_list = []
        self.day = -1

    def on_securities_changed(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        # Create and register indicator for each security in the universe
        security_by_symbol = {}
        for security in changes.added_securities:

            # Create an indicator
            security_by_symbol[security.symbol] = security
            #security.indicator = CustomMomentumPercent("custom", self.lookback_months, self.securities_list)
            security.indicator = MomentumPercent(self.lookback_months)
            self._register_indicator(algorithm, security)
            self.securities_list.append(security)
        
        # Warm up the indicators of newly-added stocks
        if security_by_symbol:
            history = algorithm.history[TradeBar](list(security_by_symbol.keys()), (self.lookback_months+1) * 30, Resolution.DAILY, data_normalization_mode=DataNormalizationMode.SCALED_RAW)
            for trade_bars in history:
                for bar in trade_bars.values():
                    security_by_symbol[bar.symbol].consolidator.update(bar)

        # Stop updating consolidator when the security is removed from the universe
        for security in changes.removed_securities:
            if security in self.securities_list:
                algorithm.subscription_manager.remove_consolidator(security.symbol, security.consolidator)
                self.securities_list.remove(security)

    def update(self, algorithm: QCAlgorithm, data: Slice) -> List[Insight]:
        # Reset indicators when corporate actions occur
        for symbol in set(data.splits.keys() + data.dividends.keys()):
            security = algorithm.securities[symbol]
            if security in self.securities_list:
                security.indicator.reset()
                algorithm.subscription_manager.remove_consolidator(security.symbol, security.consolidator)
                self._register_indicator(algorithm, security)

                history = algorithm.history[TradeBar](security.symbol, (security.indicator.warm_up_period+1) * 30, Resolution.DAILY, data_normalization_mode=DataNormalizationMode.SCALED_RAW)
                for bar in history:
                    security.consolidator.update(bar)
        
        # Only emit insights when there is quote data, not when a corporate action occurs (at midnight)
        if data.quote_bars.count == 0:
            return []
        
        # Only emit insights once per day
        if self.day == algorithm.time.day:
            return []
        self.day = algorithm.time.day



        # Get the momentum of each asset in the universe
        momentum_by_symbol = {security.symbol : security.indicator.current.value 
            for security in self.securities_list if security.symbol in data.quote_bars and security.indicator.is_ready}
                
        # Determine how many assets to hold in the portfolio
        quantile_size = int(len(momentum_by_symbol)/self.quantiles)
        if quantile_size == 0:
            return []

        # Create insights to long the assets in the universe with the greatest momentum
        weight = 1 / (quantile_size+1)

        insights = []
        for symbol, _ in sorted(momentum_by_symbol.items(), key=lambda x: x[1], reverse=True)[:quantile_size]:
            insights.append(Insight.price(symbol, Expiry.END_OF_DAY, InsightDirection.UP, weight=weight))

        return insights

    

    def _register_indicator(self, algorithm, security):
        # Update the indicator with monthly bars
        security.consolidator = TradeBarConsolidator(Calendar.MONTHLY)
        algorithm.subscription_manager.add_consolidator(security.symbol, security.consolidator)
        algorithm.register_indicator(security.symbol, security.indicator, security.consolidator)
