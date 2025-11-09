# region imports
from AlgorithmImports import *
from alpha import *
from PortfolioConstructor import MLP_PortfolioConstructionModel
# endregion


class LiquidEquityAlgorithm(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2021, 1, 1) 
        self.set_cash(1_000_000)
        self.SetBenchmark(self.AddEquity("SPY").Symbol)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)
        self.settings.minimum_order_margin_portfolio_percentage = 0
        self.settings.rebalance_portfolio_on_security_changes = False
        self.settings.rebalance_portfolio_on_insight_changes = False
        self.day = -1
        self.set_warm_up(timedelta(30))

        self.universe_settings.asynchronous = True
        self.add_universe_selection(FundamentalUniverseSelectionModel(self.fundamental_filter_function))
        
        self.add_alpha(TSZscore_VwapReversion())
        self.add_alpha(TSZscore_DividendGrowth())
        self.add_alpha(Conditional_Reversion())
        self.add_alpha(MomentumQuantilesAlphaModel())

        self.set_portfolio_construction(MLP_PortfolioConstructionModel(algorithm=self, rebalance=timedelta(5)))
        
        self.add_risk_management(NullRiskManagementModel())

        self.set_execution(ImmediateExecutionModel())
        
    def fundamental_filter_function(self, fundamental: List[Fundamental]):
        filtered = [f for f in fundamental if f.symbol.value != "AMC" and f.has_fundamental_data and not np.isnan(f.dollar_volume)]
        sorted_by_dollar_volume = sorted(filtered, key=lambda f: f.dollar_volume, reverse=True)
        return [f.symbol for f in sorted_by_dollar_volume[0:500]]