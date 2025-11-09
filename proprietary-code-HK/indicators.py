#region imports
from AlgorithmImports import *
from collections import deque
import scipy as sp
import numpy as np
#endregion

def EWMA(value_history):
    output = value_history[0]
    for i in range(1, len(value_history)):
        output = 0.7 * value_history[i] + 0.3 * output
    return output
    
        
class CustomMomentumPercent(PythonIndicator):
    def __init__(self, name, period):
        self.name = name
        self.time = datetime.min
        self.value = 0
        self.momentum = MomentumPercent(period)

    def Update(self, input):
        self.momentum.update(IndicatorDataPoint(input.Symbol, input.EndTime, input.Close))
        self.time = input.EndTime
        self.value = self.momentum.Current.Value * input.Volume
        return self.momentum.IsReady


class Skewness(PythonIndicator):    # Doesn't work on 3th August 2020
    def __init__(self, name, period):
        self.name = name
        self.count = 0
        self.time = datetime.min
        self.value = 0
        self.queue = deque(maxlen=period)
        self.change_in_close = deque(maxlen=period)

    def Update(self, input):
        self.queue.appendleft(input.Close)
        if len(self.queue) > 1:
            self.change_in_close.appendleft(self.queue[0]/self.queue[1]-1)
        self.time = input.EndTime

        self.count = len(self.change_in_close)
        if self.count == self.queue.maxlen:
            self.value = sp.stats.skew(self.change_in_close, nan_policy="omit")
        
        return count == self.change_in_close.maxlen  


class VwapReversion(PythonIndicator):
    def __init__(self, name, symbol, algorithm):
        self.name = name
        self.time = datetime.min
        self.value = 0
        self.previous_value = 0
        self._vwap = algorithm.vwap(symbol)
        self.queue = deque(maxlen=30)
        

    def update(self, input):
        self._vwap.update(input)
        self.time = input.EndTime
        self.queue.appendleft(self._vwap.Current.Value / input.Close)

        count = len(self.queue)
        if count == self.queue.maxlen:
            z_array = sp.stats.zscore(self.queue)
            if np.isfinite(z_array[0]):
                self.previous_value = self.value
                self.value = 0.7 * z_array[0] + 0.3 * self.previous_value
                
        return count == self.queue.maxlen


    