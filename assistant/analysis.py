import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import json
import os
from datetime import datetime
import matplotlib.pyplot as plt
from scipy import stats
import warnings


class BacktestAnalyzer:
    """Analyze backtest results and provide insights."""
    
    def __init__(self, 
                 equity_curve: pd.Series, 
                 trades: List[Dict], 
                 market_data: pd.DataFrame,
                 strategy_params: Dict[str, Any],
                 benchmark: Optional[pd.Series] = None):
        """
        Initialize with backtest results.
        
        Args:
            equity_curve: Time series of portfolio value
            trades: List of completed trades with entry/exit details
            market_data: Market data used in the backtest (OHLCV)
            strategy_params: Parameters used for the strategy
            benchmark: Optional benchmark series for comparison
        """
        self.equity_curve = equity_curve
        self.trades = trades
        self.market_data = market_data
        self.strategy_params = strategy_params
        self.benchmark = benchmark
        self.returns = self.equity_curve.pct_change().dropna()
        self.insights = {}
        
        # Initialize with warning suppression for some statistical calculations
        warnings.filterwarnings('ignore', category=RuntimeWarning)
        
    def run_full_analysis(self) -> Dict[str, Any]:
        """Run comprehensive analysis and return all insights."""
        self.analyze_overall_performance()
        self.analyze_market_conditions()
        self.analyze_trade_patterns()
        self.analyze_risk_exposure()
        self.analyze_parameter_sensitivity()
        
        if self.benchmark is not None:
            self.analyze_benchmark_comparison()
            
        return self.insights
    
    def analyze_overall_performance(self) -> Dict[str, Any]:
        """Analyze overall performance metrics and identify strengths/weaknesses."""
        perf_insights = {}
        
        # Check if we have enough data for meaningful analysis
        if len(self.returns) < 10 or not self.trades:
            perf_insights['warning'] = "Insufficient data for comprehensive analysis"
            self.insights['performance'] = perf_insights
            return perf_insights
        
        # Calculate key metrics
        total_return = (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0]) - 1
        annual_return = ((1 + total_return) ** (252 / len(self.returns))) - 1
        volatility = self.returns.std() * np.sqrt(252)
        sharpe = annual_return / volatility if volatility > 0 else 0
        
        # Running maximum and drawdown
        running_max = self.equity_curve.cummax()
        drawdown = (self.equity_curve / running_max - 1)
        max_drawdown = drawdown.min()
        
        # Win rate and profit factor
        win_trades = [t for t in self.trades if t.get('pnl', 0) > 0]
        lose_trades = [t for t in self.trades if t.get('pnl', 0) <= 0]
        win_rate = len(win_trades) / len(self.trades) if self.trades else 0
        
        total_profit = sum(t.get('pnl', 0) for t in win_trades)
        total_loss = abs(sum(t.get('pnl', 0) for t in lose_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Store metrics
        perf_insights['metrics'] = {
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'trade_count': len(self.trades)
        }
        
        # Analyze performance and provide insights
        strengths = []
        weaknesses = []
        
        # Check return and risk metrics
        if annual_return > 0.20:  # 20% annual return
            strengths.append("Strong annual returns above 20%")
        elif annual_return < 0:
            weaknesses.append("Strategy is losing money")
        
        if sharpe > 1.5:
            strengths.append("Good risk-adjusted returns with Sharpe > 1.5")
        elif sharpe < 0.5:
            weaknesses.append("Poor risk-adjusted returns with Sharpe < 0.5")
            
        if max_drawdown > -0.10:  # Less than 10% drawdown
            strengths.append("Controlled drawdowns under 10%")
        elif max_drawdown < -0.25:  # More than 25% drawdown
            weaknesses.append(f"Severe drawdowns of {max_drawdown:.1%}")
            
        if win_rate > 0.60:
            strengths.append(f"Strong win rate of {win_rate:.1%}")
        elif win_rate < 0.40:
            weaknesses.append(f"Low win rate of {win_rate:.1%}")
            
        if profit_factor > 2.0:
            strengths.append(f"Excellent profit factor of {profit_factor:.2f}")
        elif profit_factor < 1.2:
            weaknesses.append(f"Marginal profit factor of {profit_factor:.2f}")
            
        # Check consistency
        monthly_returns = self.returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
        positive_months = (monthly_returns > 0).mean()
        
        if positive_months > 0.65:
            strengths.append(f"Consistent with {positive_months:.1%} profitable months")
        elif positive_months < 0.50:
            weaknesses.append(f"Inconsistent with only {positive_months:.1%} profitable months")
            
        # Check for return clustering
        returns_autocorr = self.returns.autocorr(lag=1)
        if abs(returns_autocorr) > 0.2:
            if returns_autocorr > 0:
                insights = "Returns show momentum patterns (positive autocorrelation)"
            else:
                insights = "Returns show mean-reversion patterns (negative autocorrelation)"
            strengths.append(insights)
            
        perf_insights['strengths'] = strengths
        perf_insights['weaknesses'] = weaknesses
        
        # Summary
        perf_insights['summary'] = self._generate_performance_summary(
            perf_insights['metrics'], strengths, weaknesses
        )
        
        self.insights['performance'] = perf_insights
        return perf_insights
        
    def analyze_market_conditions(self) -> Dict[str, Any]:
        """Analyze how the strategy performs under different market conditions."""
        market_insights = {}
        
        if 'close' not in self.market_data.columns or len(self.market_data) < 20:
            market_insights['warning'] = "Insufficient market data for condition analysis"
            self.insights['market_conditions'] = market_insights
            return market_insights
            
        # Calculate market trends
        self.market_data['returns'] = self.market_data['close'].pct_change()
        self.market_data['volatility'] = self.market_data['returns'].rolling(20).std()
        
        # Define market conditions
        # 1. Trending up: 20-day return > 5%
        # 2. Trending down: 20-day return < -5%
        # 3. High volatility: Rolling 20-day volatility > 2x average volatility
        # 4. Low volatility: Rolling 20-day volatility < 0.5x average volatility
        
        avg_vol = self.market_data['volatility'].mean()
        self.market_data['up_trend'] = self.market_data['close'].pct_change(20) > 0.05
        self.market_data['down_trend'] = self.market_data['close'].pct_change(20) < -0.05
        self.market_data['high_vol'] = self.market_data['volatility'] > (2 * avg_vol)
        self.market_data['low_vol'] = self.market_data['volatility'] < (0.5 * avg_vol)
        
        # Analyze trades under different conditions
        condition_performance = {}
        
        for condition in ['up_trend', 'down_trend', 'high_vol', 'low_vol']:
            trades_in_condition = []
            
            for trade in self.trades:
                if 'entry_time' not in trade or 'exit_time' not in trade:
                    continue
                    
                # Check if trade was active during this condition
                trade_periods = self.market_data.loc[trade['entry_time']:trade['exit_time']]
                if len(trade_periods) == 0:
                    continue
                
                if trade_periods[condition].any():
                    trades_in_condition.append(trade)
            
            # Calculate performance metrics for trades in this condition
            if trades_in_condition:
                win_trades = [t for t in trades_in_condition if t.get('pnl', 0) > 0]
                win_rate = len(win_trades) / len(trades_in_condition)
                avg_pnl = np.mean([t.get('pnl', 0) for t in trades_in_condition])
                
                condition_performance[condition] = {
                    'trade_count': len(trades_in_condition),
                    'win_rate': win_rate,
                    'avg_pnl': avg_pnl
                }
                
        market_insights['condition_performance'] = condition_performance
        
        # Identify strengths and weaknesses by market condition
        strengths = []
        weaknesses = []
        
        # Compare performance across conditions
        if 'up_trend' in condition_performance and 'down_trend' in condition_performance:
            up_perf = condition_performance['up_trend']
            down_perf = condition_performance['down_trend']
            
            if up_perf['win_rate'] > down_perf['win_rate'] + 0.1:
                strengths.append("Strategy performs significantly better in uptrends")
            elif down_perf['win_rate'] > up_perf['win_rate'] + 0.1:
                strengths.append("Strategy performs significantly better in downtrends")
            else:
                strengths.append("Strategy performs consistently in both up and down trends")
                
        if 'high_vol' in condition_performance and 'low_vol' in condition_performance:
            high_vol_perf = condition_performance['high_vol']
            low_vol_perf = condition_performance['low_vol']
            
            if high_vol_perf['win_rate'] > low_vol_perf['win_rate'] + 0.1:
                strengths.append("Strategy excels in high volatility environments")
            elif low_vol_perf['win_rate'] > high_vol_perf['win_rate'] + 0.1:
                strengths.append("Strategy excels in low volatility environments")
                
        # Identify any particularly weak conditions
        for condition, perf in condition_performance.items():
            if perf['win_rate'] < 0.4:
                condition_name = condition.replace('_', ' ')
                weaknesses.append(f"Poor performance during {condition_name} conditions")
            if perf['avg_pnl'] < 0:
                condition_name = condition.replace('_', ' ')
                weaknesses.append(f"Negative average returns during {condition_name} conditions")
                
        market_insights['strengths'] = strengths
        market_insights['weaknesses'] = weaknesses
        
        # Generate recommendations based on market condition analysis
        recommendations = []
        
        # If strategy performs well in specific conditions, suggest focusing on those
        best_condition = None
        best_win_rate = 0
        
        for condition, perf in condition_performance.items():
            if perf['win_rate'] > best_win_rate:
                best_win_rate = perf['win_rate']
                best_condition = condition
                
        if best_condition:
            condition_name = best_condition.replace('_', ' ')
            recommendations.append(f"Consider focusing on {condition_name} conditions where win rate is {best_win_rate:.1%}")
            
        # If strategy has significant weaknesses in certain conditions, suggest avoiding them
        worst_condition = None
        worst_win_rate = 1.0
        
        for condition, perf in condition_performance.items():
            if perf['win_rate'] < worst_win_rate:
                worst_win_rate = perf['win_rate']
                worst_condition = condition
                
        if worst_condition and worst_win_rate < 0.4:
            condition_name = worst_condition.replace('_', ' ')
            recommendations.append(f"Consider avoiding trades during {condition_name} conditions where win rate is only {worst_win_rate:.1%}")
            
        market_insights['recommendations'] = recommendations
        self.insights['market_conditions'] = market_insights
        return market_insights
    
    def analyze_trade_patterns(self) -> Dict[str, Any]:
        """Analyze trade patterns to identify strengths and weaknesses."""
        trade_insights = {}
        
        if not self.trades or len(self.trades) < 5:
            trade_insights['warning'] = "Insufficient trade data for pattern analysis"
            self.insights['trade_patterns'] = trade_insights
            return trade_insights
            
        # Extract trade data
        trade_data = []
        for trade in self.trades:
            if not all(k in trade for k in ['entry_time', 'exit_time', 'pnl', 'direction']):
                continue
                
            duration = (trade['exit_time'] - trade['entry_time']).total_seconds() / 3600  # hours
            
            trade_data.append({
                'pnl': trade.get('pnl', 0),
                'direction': trade.get('direction', 'unknown'),
                'duration': duration,
                'entry_time': trade['entry_time'],
                'exit_time': trade['exit_time'],
                'win': trade.get('pnl', 0) > 0
            })
            
        if not trade_data:
            trade_insights['warning'] = "No valid trade data for pattern analysis"
            self.insights['trade_patterns'] = trade_insights
            return trade_insights
            
        # Convert to DataFrame for easier analysis
        trades_df = pd.DataFrame(trade_data)
        
        # Analyze by direction
        direction_performance = {}
        for direction in trades_df['direction'].unique():
            direction_trades = trades_df[trades_df['direction'] == direction]
            
            direction_performance[direction] = {
                'count': len(direction_trades),
                'win_rate': direction_trades['win'].mean(),
                'avg_pnl': direction_trades['pnl'].mean(),
                'avg_duration': direction_trades['duration'].mean()
            }
            
        trade_insights['direction_performance'] = direction_performance
        
        # Analyze by duration
        trades_df['duration_bucket'] = pd.cut(
            trades_df['duration'], 
            bins=[0, 4, 24, 72, float('inf')],
            labels=['<4h', '4-24h', '1-3d', '>3d']
        )
        
        duration_performance = {}
        for duration in trades_df['duration_bucket'].unique():
            if pd.isna(duration):
                continue
                
            duration_trades = trades_df[trades_df['duration_bucket'] == duration]
            
            duration_performance[str(duration)] = {
                'count': len(duration_trades),
                'win_rate': duration_trades['win'].mean(),
                'avg_pnl': duration_trades['pnl'].mean()
            }
            
        trade_insights['duration_performance'] = duration_performance
        
        # Analyze time of day patterns
        trades_df['hour'] = trades_df['entry_time'].dt.hour
        trades_df['day_of_week'] = trades_df['entry_time'].dt.day_name()
        
        hour_performance = {}
        for hour_group in [('00-06', 0, 6), ('06-12', 6, 12), ('12-18', 12, 18), ('18-24', 18, 24)]:
            label, start, end = hour_group
            hour_trades = trades_df[(trades_df['hour'] >= start) & (trades_df['hour'] < end)]
            
            if len(hour_trades) > 0:
                hour_performance[label] = {
                    'count': len(hour_trades),
                    'win_rate': hour_trades['win'].mean(),
                    'avg_pnl': hour_trades['pnl'].mean()
                }
                
        trade_insights['hour_performance'] = hour_performance
        
        # Analyze day of week patterns
        day_performance = {}
        for day in trades_df['day_of_week'].unique():
            day_trades = trades_df[trades_df['day_of_week'] == day]
            
            day_performance[day] = {
                'count': len(day_trades),
                'win_rate': day_trades['win'].mean(),
                'avg_pnl': day_trades['pnl'].mean()
            }
            
        trade_insights['day_performance'] = day_performance
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        
        # Direction analysis
        if len(direction_performance) > 1:
            best_dir = max(direction_performance.items(), key=lambda x: x[1]['win_rate'])
            worst_dir = min(direction_performance.items(), key=lambda x: x[1]['win_rate'])
            
            if best_dir[1]['win_rate'] > 0.6 and best_dir[1]['count'] >= 5:
                strengths.append(f"Strong performance in {best_dir[0]} trades with {best_dir[1]['win_rate']:.1%} win rate")
                
            if worst_dir[1]['win_rate'] < 0.4 and worst_dir[1]['count'] >= 5:
                weaknesses.append(f"Poor performance in {worst_dir[0]} trades with only {worst_dir[1]['win_rate']:.1%} win rate")
                
        # Duration analysis
        if duration_performance:
            best_dur = max(duration_performance.items(), key=lambda x: x[1]['win_rate'])
            worst_dur = min(duration_performance.items(), key=lambda x: x[1]['win_rate'])
            
            if best_dur[1]['win_rate'] > 0.6 and best_dur[1]['count'] >= 5:
                strengths.append(f"Strong performance in {best_dur[0]} duration trades with {best_dur[1]['win_rate']:.1%} win rate")
                
            if worst_dur[1]['win_rate'] < 0.4 and worst_dur[1]['count'] >= 5:
                weaknesses.append(f"Poor performance in {worst_dur[0]} duration trades with only {worst_dur[1]['win_rate']:.1%} win rate")
                
        # Time analysis
        if hour_performance:
            best_hour = max(hour_performance.items(), key=lambda x: x[1]['win_rate'])
            worst_hour = min(hour_performance.items(), key=lambda x: x[1]['win_rate'])
            
            if best_hour[1]['win_rate'] > 0.6 and best_hour[1]['count'] >= 5:
                strengths.append(f"Strong performance during {best_hour[0]} hours with {best_hour[1]['win_rate']:.1%} win rate")
                
            if worst_hour[1]['win_rate'] < 0.4 and worst_hour[1]['count'] >= 5:
                weaknesses.append(f"Poor performance during {worst_hour[0]} hours with only {worst_hour[1]['win_rate']:.1%} win rate")
                
        # Day analysis
        if day_performance:
            best_day = max(day_performance.items(), key=lambda x: x[1]['win_rate'])
            worst_day = min(day_performance.items(), key=lambda x: x[1]['win_rate'])
            
            if best_day[1]['win_rate'] > 0.6 and best_day[1]['count'] >= 3:
                strengths.append(f"Strong performance on {best_day[0]} with {best_day[1]['win_rate']:.1%} win rate")
                
            if worst_day[1]['win_rate'] < 0.4 and worst_day[1]['count'] >= 3:
                weaknesses.append(f"Poor performance on {worst_day[0]} with only {worst_day[1]['win_rate']:.1%} win rate")
                
        trade_insights['strengths'] = strengths
        trade_insights['weaknesses'] = weaknesses
        
        # Generate recommendations
        recommendations = []
        
        if strengths:
            for strength in strengths:
                if "direction" in strength:
                    recommendations.append(f"Consider focusing on {best_dir[0]} directional trades")
                if "duration" in strength:
                    recommendations.append(f"Optimize for {best_dur[0]} duration trades where performance is strongest")
                if "hours" in strength:
                    recommendations.append(f"Consider trading primarily during {best_hour[0]} hours")
                if "on" in strength and "day" in strength:
                    recommendations.append(f"Consider trading more actively on {best_day[0]}")
                    
        if weaknesses:
            for weakness in weaknesses:
                if "direction" in weakness:
                    recommendations.append(f"Avoid or refine {worst_dir[0]} directional trades")
                if "duration" in weakness:
                    recommendations.append(f"Reconsider {worst_dur[0]} duration trades or improve exit timing")
                if "hours" in weakness:
                    recommendations.append(f"Consider avoiding trades during {worst_hour[0]} hours")
                if "on" in weakness and "day" in weakness:
                    recommendations.append(f"Consider avoiding trades on {worst_day[0]}")
                    
        trade_insights['recommendations'] = list(set(recommendations))  # Remove duplicates
        
        self.insights['trade_patterns'] = trade_insights
        return trade_insights
    
    def analyze_risk_exposure(self) -> Dict[str, Any]:
        """Analyze risk exposure and risk-adjusted returns."""
        risk_insights = {}
        
        if len(self.returns) < 20:
            risk_insights['warning'] = "Insufficient data for comprehensive risk analysis"
            self.insights['risk_exposure'] = risk_insights
            return risk_insights
            
        # Calculate risk metrics
        volatility = self.returns.std() * np.sqrt(252)
        downside_returns = self.returns[self.returns < 0]
        downside_deviation = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        
        # Running maximum and drawdown
        running_max = self.equity_curve.cummax()
        drawdown = (self.equity_curve / running_max - 1)
        max_drawdown = drawdown.min()
        
        # Average drawdown and recovery time
        drawdown_series = drawdown[drawdown < -0.01]  # Only count drawdowns > 1%
        avg_drawdown = drawdown_series.mean() if len(drawdown_series) > 0 else 0
        
        # Calculate drawdown periods
        drawdown_periods = []
        in_drawdown = False
        start_idx = None
        
        for i, value in enumerate(drawdown):
            if not in_drawdown and value < -0.01:
                # Start of drawdown
                in_drawdown = True
                start_idx = i
            elif in_drawdown and value >= 0:
                # End of drawdown
                in_drawdown = False
                if start_idx is not None:
                    drawdown_periods.append({
                        'start': self.equity_curve.index[start_idx],
                        'end': self.equity_curve.index[i],
                        'depth': drawdown.iloc[start_idx:i].min(),
                        'duration': (self.equity_curve.index[i] - self.equity_curve.index[start_idx]).days
                    })
                    start_idx = None
                    
        # If still in drawdown at the end
        if in_drawdown and start_idx is not None:
            drawdown_periods.append({
                'start': self.equity_curve.index[start_idx],
                'end': self.equity_curve.index[-1],
                'depth': drawdown.iloc[start_idx:].min(),
                'duration': (self.equity_curve.index[-1] - self.equity_curve.index[start_idx]).days
            })
            
        # Calculate average recovery time
        if drawdown_periods:
            avg_recovery_days = np.mean([period['duration'] for period in drawdown_periods])
        else:
            avg_recovery_days = 0
            
        # Calculate trade-level risk metrics
        if self.trades and len(self.trades) >= 5:
            pnls = [t.get('pnl', 0) for t in self.trades]
            pnl_std = np.std(pnls)
            max_loss = min(pnls) if pnls else 0
            
            win_trades = [p for p in pnls if p > 0]
            lose_trades = [p for p in pnls if p < 0]
            
            avg_win = np.mean(win_trades) if win_trades else 0
            avg_loss = np.mean(lose_trades) if lose_trades else 0
            
            if avg_loss != 0:
                win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
            else:
                win_loss_ratio = float('inf') if avg_win > 0 else 0
        else:
            pnl_std = 0
            max_loss = 0
            win_loss_ratio = 0
            
        risk_metrics = {
            'volatility': volatility,
            'downside_deviation': downside_deviation,
            'max_drawdown': max_drawdown,
            'avg_drawdown': avg_drawdown,
            'avg_recovery_days': avg_recovery_days,
            'win_loss_ratio': win_loss_ratio,
            'max_trade_loss': max_loss
        }
        
        risk_insights['metrics'] = risk_metrics
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        
        # Risk ratio analysis
        annual_return = ((1 + (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0] - 1)) ** (252 / len(self.returns))) - 1
        
        sharpe = annual_return / volatility if volatility > 0 else 0
        sortino = annual_return / downside_deviation if downside_deviation > 0 else float('inf')
        calmar = annual_return / abs(max_drawdown) if max_drawdown < 0 else float('inf')
        
        risk_metrics.update({
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar
        })
        
        # Assess risk metrics
        if sharpe > 1.5:
            strengths.append(f"Strong Sharpe ratio of {sharpe:.2f}")
        elif sharpe < 0.5:
            weaknesses.append(f"Poor Sharpe ratio of {sharpe:.2f}")
            
        if sortino > 2.0:
            strengths.append(f"Excellent Sortino ratio of {sortino:.2f}")
        elif sortino < 0.75:
            weaknesses.append(f"Weak Sortino ratio of {sortino:.2f}")
            
        if calmar > 1.0:
            strengths.append(f"Strong Calmar ratio of {calmar:.2f}")
        elif calmar < 0.5:
            weaknesses.append(f"Poor Calmar ratio of {calmar:.2f}")
            
        if win_loss_ratio > 2.0:
            strengths.append(f"Excellent win/loss ratio of {win_loss_ratio:.2f}")
        elif win_loss_ratio < 1.0:
            weaknesses.append(f"Poor win/loss ratio of {win_loss_ratio:.2f}")
            
        if max_drawdown > -0.15:
            strengths.append(f"Contained maximum drawdown of {max_drawdown:.1%}")
        elif max_drawdown < -0.25:
            weaknesses.append(f"Severe maximum drawdown of {max_drawdown:.1%}")
            
        if avg_recovery_days < 30:
            strengths.append(f"Quick average drawdown recovery of {avg_recovery_days:.0f} days")
        elif avg_recovery_days > 90:
            weaknesses.append(f"Slow average drawdown recovery of {avg_recovery_days:.0f} days")
            
        risk_insights['strengths'] = strengths
        risk_insights['weaknesses'] = weaknesses
        
        # Recommendations
        recommendations = []
        
        if max_drawdown < -0.20:
            recommendations.append("Consider implementing stricter stop-loss rules to limit drawdowns")
            
        if win_loss_ratio < 1.5:
            recommendations.append("Improve win/loss ratio by letting profits run longer or cutting losses sooner")
            
        if avg_recovery_days > 60:
            recommendations.append("Optimize recovery time by adjusting position sizing after drawdowns")
            
        if volatility > 0.3:  # Very high volatility
            recommendations.append("Reduce overall volatility through more diversified positions or reduced leverage")
            
        risk_insights['recommendations'] = recommendations
        
        self.insights['risk_exposure'] = risk_insights
        return risk_insights
    
    def analyze_parameter_sensitivity(self) -> Dict[str, Any]:
        """Analyze the sensitivity of strategy to its parameters."""
        sensitivity_insights = {}
        
        # This is a placeholder for actual parameter sensitivity analysis
        # In a real implementation, we would run variations of the strategy
        # with different parameters and analyze the impact on performance
        
        sensitivity_insights['note'] = "Parameter sensitivity analysis requires running multiple backtests with varied parameters"
        sensitivity_insights['parameters'] = self.strategy_params
        
        # Suggestions for optimization
        suggestions = [
            "Consider optimizing entry/exit timing parameters",
            "Test variations of risk management parameters",
            "Evaluate different technical indicator settings"
        ]
        sensitivity_insights['suggestions'] = suggestions
        
        self.insights['parameter_sensitivity'] = sensitivity_insights
        return sensitivity_insights
    
    def analyze_benchmark_comparison(self) -> Dict[str, Any]:
        """Compare strategy performance against benchmark."""
        benchmark_insights = {}
        
        if self.benchmark is None or len(self.benchmark) < len(self.equity_curve) * 0.7:
            benchmark_insights['warning'] = "Insufficient benchmark data for comparison"
            self.insights['benchmark_comparison'] = benchmark_insights
            return benchmark_insights
            
        # Align benchmark with equity curve
        benchmark = self.benchmark.reindex(self.equity_curve.index, method='ffill')
        benchmark = benchmark.dropna()
        
        if len(benchmark) < 20:
            benchmark_insights['warning'] = "Insufficient aligned benchmark data for comparison"
            self.insights['benchmark_comparison'] = benchmark_insights
            return benchmark_insights
            
        # Normalize benchmark and equity curve to same starting point
        norm_equity = self.equity_curve / self.equity_curve.iloc[0]
        norm_benchmark = benchmark / benchmark.iloc[0]
        
        # Calculate relative performance
        outperformance = norm_equity.iloc[-1] / norm_benchmark.iloc[-1] - 1
        
        # Calculate benchmark returns
        benchmark_returns = benchmark.pct_change().dropna()
        
        # Calculate beta and alpha
        cov = np.cov(self.returns, benchmark_returns)[0, 1]
        benchmark_var = benchmark_returns.var()
        beta = cov / benchmark_var if benchmark_var > 0 else 0
        
        # Calculate alpha (annualized)
        strategy_annual_return = ((1 + (norm_equity.iloc[-1] - 1)) ** (252 / len(self.returns))) - 1
        benchmark_annual_return = ((1 + (norm_benchmark.iloc[-1] - 1)) ** (252 / len(benchmark_returns))) - 1
        
        alpha = strategy_annual_return - (0 + beta * benchmark_annual_return)  # Assuming 0% risk-free rate
        
        # Tracking error
        tracking_error = (self.returns - benchmark_returns).std() * np.sqrt(252)
        
        # Information ratio
        information_ratio = (strategy_annual_return - benchmark_annual_return) / tracking_error if tracking_error > 0 else 0
        
        # Up/down capture ratios
        up_months = benchmark_returns > 0
        down_months = benchmark_returns < 0
        
        if up_months.any():
            up_capture = (self.returns[up_months].mean() / benchmark_returns[up_months].mean()) * 100
        else:
            up_capture = 0
            
        if down_months.any():
            down_capture = (self.returns[down_months].mean() / benchmark_returns[down_months].mean()) * 100
        else:
            down_capture = 0
            
        benchmark_metrics = {
            'outperformance': outperformance,
            'alpha': alpha,
            'beta': beta,
            'information_ratio': information_ratio,
            'tracking_error': tracking_error,
            'up_capture': up_capture,
            'down_capture': down_capture
        }
        
        benchmark_insights['metrics'] = benchmark_metrics
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        
        if outperformance > 0.10:  # Outperforms by 10%+
            strengths.append(f"Outperforms benchmark by {outperformance:.1%}")
        elif outperformance < 0:
            weaknesses.append(f"Underperforms benchmark by {-outperformance:.1%}")
            
        if alpha > 0.05:  # 5%+ alpha
            strengths.append(f"Strong alpha generation of {alpha:.1%}")
        elif alpha < 0:
            weaknesses.append(f"Negative alpha of {alpha:.1%}")
            
        if beta < 0.8 and outperformance > 0:
            strengths.append(f"Achieves outperformance with reduced market exposure (beta: {beta:.2f})")
            
        if information_ratio > 0.5:
            strengths.append(f"Solid information ratio of {information_ratio:.2f}")
        elif information_ratio < 0:
            weaknesses.append(f"Negative information ratio of {information_ratio:.2f}")
            
        if up_capture > 80 and down_capture < 50:
            strengths.append(f"Excellent up/down capture ratio ({up_capture:.0f}% up, {down_capture:.0f}% down)")
        elif down_capture > up_capture:
            weaknesses.append(f"Poor up/down capture ratio ({up_capture:.0f}% up, {down_capture:.0f}% down)")
            
        benchmark_insights['strengths'] = strengths
        benchmark_insights['weaknesses'] = weaknesses
        
        # Recommendations
        recommendations = []
        
        if beta > 1.2:
            recommendations.append("Consider reducing market exposure to improve risk-adjusted returns")
            
        if outperformance < 0 and beta > 0.8:
            recommendations.append("Strategy doesn't justify its risk level; consider fundamental revisions")
            
        if down_capture > 70:
            recommendations.append("Improve downside protection during market downturns")
            
        if up_capture < 60:
            recommendations.append("Enhance ability to participate in market uptrends")
            
        benchmark_insights['recommendations'] = recommendations
        
        self.insights['benchmark_comparison'] = benchmark_insights
        return benchmark_insights
    
    def _generate_performance_summary(self, metrics: Dict, strengths: List[str], weaknesses: List[str]) -> str:
        """Generate a human-readable summary of performance."""
        summary = "Strategy Performance Summary:\n\n"
        
        # Overview section
        summary += f"Total Return: {metrics['total_return']:.2%}\n"
        summary += f"Annualized Return: {metrics['annual_return']:.2%}\n"
        summary += f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}\n"
        summary += f"Maximum Drawdown: {metrics['max_drawdown']:.2%}\n"
        summary += f"Win Rate: {metrics['win_rate']:.2%}\n"
        summary += f"Profit Factor: {metrics['profit_factor']:.2f}\n\n"
        
        # Strengths
        if strengths:
            summary += "Strengths:\n"
            for strength in strengths:
                summary += f"- {strength}\n"
            summary += "\n"
            
        # Weaknesses
        if weaknesses:
            summary += "Weaknesses:\n"
            for weakness in weaknesses:
                summary += f"- {weakness}\n"
            summary += "\n"
            
        # Overall assessment
        if metrics['annual_return'] > 0 and metrics['sharpe_ratio'] > 1:
            summary += "OVERALL: The strategy shows positive results with acceptable risk-adjusted returns."
        elif metrics['annual_return'] > 0 and metrics['sharpe_ratio'] <= 1:
            summary += "OVERALL: The strategy is profitable but has room for improvement in risk management."
        elif metrics['annual_return'] <= 0:
            summary += "OVERALL: The strategy is not profitable in its current form and needs significant revision."
            
        return summary
    
    def generate_ai_summary(self) -> str:
        """Generate a comprehensive AI-powered summary of all insights."""
        if not self.insights:
            self.run_full_analysis()
            
        summary = "# AI-Powered Strategy Analysis\n\n"
        
        # Performance section
        if 'performance' in self.insights:
            perf = self.insights['performance']
            summary += "## Performance Overview\n\n"
            if 'summary' in perf:
                summary += perf['summary'] + "\n\n"
                
        # Market conditions section
        if 'market_conditions' in self.insights:
            market = self.insights['market_conditions']
            summary += "## Market Condition Analysis\n\n"
            
            if 'condition_performance' in market:
                summary += "The strategy performs differently under various market conditions:\n\n"
                
                for condition, perf in market['condition_performance'].items():
                    condition_name = condition.replace('_', ' ').title()
                    summary += f"- {condition_name}: {perf['win_rate']:.1%} win rate over {perf['trade_count']} trades\n"
                    
            if 'strengths' in market and market['strengths']:
                summary += "\nStrengths in market conditions:\n"
                for strength in market['strengths']:
                    summary += f"- {strength}\n"
                    
            if 'weaknesses' in market and market['weaknesses']:
                summary += "\nWeaknesses in market conditions:\n"
                for weakness in market['weaknesses']:
                    summary += f"- {weakness}\n"
                    
            if 'recommendations' in market and market['recommendations']:
                summary += "\nRecommendations for market conditions:\n"
                for rec in market['recommendations']:
                    summary += f"- {rec}\n"
                
            summary += "\n"
            
        # Trade patterns section
        if 'trade_patterns' in self.insights:
            patterns = self.insights['trade_patterns']
            summary += "## Trade Pattern Analysis\n\n"
            
            if 'direction_performance' in patterns:
                summary += "Performance by trade direction:\n\n"
                for direction, perf in patterns['direction_performance'].items():
                    summary += f"- {direction.title()}: {perf['win_rate']:.1%} win rate, avg PnL: {perf['avg_pnl']:.4f}\n"
                    
            if 'duration_performance' in patterns:
                summary += "\nPerformance by trade duration:\n\n"
                for duration, perf in patterns['duration_performance'].items():
                    summary += f"- {duration}: {perf['win_rate']:.1%} win rate, avg PnL: {perf['avg_pnl']:.4f}\n"
                    
            if 'strengths' in patterns and patterns['strengths']:
                summary += "\nTrade pattern strengths:\n"
                for strength in patterns['strengths']:
                    summary += f"- {strength}\n"
                    
            if 'weaknesses' in patterns and patterns['weaknesses']:
                summary += "\nTrade pattern weaknesses:\n"
                for weakness in patterns['weaknesses']:
                    summary += f"- {weakness}\n"
                    
            if 'recommendations' in patterns and patterns['recommendations']:
                summary += "\nTrade pattern recommendations:\n"
                for rec in patterns['recommendations']:
                    summary += f"- {rec}\n"
                
            summary += "\n"
            
        # Risk section
        if 'risk_exposure' in self.insights:
            risk = self.insights['risk_exposure']
            summary += "## Risk Analysis\n\n"
            
            if 'metrics' in risk:
                metrics = risk['metrics']
                summary += f"Risk Metrics:\n"
                summary += f"- Volatility: {metrics['volatility']:.2%}\n"
                summary += f"- Max Drawdown: {metrics['max_drawdown']:.2%}\n"
                summary += f"- Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}\n"
                summary += f"- Sortino Ratio: {metrics.get('sortino_ratio', 0):.2f}\n"
                summary += f"- Win/Loss Ratio: {metrics.get('win_loss_ratio', 0):.2f}\n"
                
            if 'strengths' in risk and risk['strengths']:
                summary += "\nRisk strengths:\n"
                for strength in risk['strengths']:
                    summary += f"- {strength}\n"
                    
            if 'weaknesses' in risk and risk['weaknesses']:
                summary += "\nRisk weaknesses:\n"
                for weakness in risk['weaknesses']:
                    summary += f"- {weakness}\n"
                    
            if 'recommendations' in risk and risk['recommendations']:
                summary += "\nRisk management recommendations:\n"
                for rec in risk['recommendations']:
                    summary += f"- {rec}\n"
                
            summary += "\n"
            
        # Benchmark comparison
        if 'benchmark_comparison' in self.insights:
            bench = self.insights['benchmark_comparison']
            summary += "## Benchmark Comparison\n\n"
            
            if 'metrics' in bench:
                metrics = bench['metrics']
                summary += f"Benchmark Metrics:\n"
                summary += f"- Outperformance: {metrics['outperformance']:.2%}\n"
                summary += f"- Alpha: {metrics['alpha']:.2%}\n"
                summary += f"- Beta: {metrics['beta']:.2f}\n"
                summary += f"- Information Ratio: {metrics['information_ratio']:.2f}\n"
                
            if 'strengths' in bench and bench['strengths']:
                summary += "\nBenchmark comparison strengths:\n"
                for strength in bench['strengths']:
                    summary += f"- {strength}\n"
                    
            if 'weaknesses' in bench and bench['weaknesses']:
                summary += "\nBenchmark comparison weaknesses:\n"
                for weakness in bench['weaknesses']:
                    summary += f"- {weakness}\n"
                    
            if 'recommendations' in bench and bench['recommendations']:
                summary += "\nBenchmark-based recommendations:\n"
                for rec in bench['recommendations']:
                    summary += f"- {rec}\n"
                
            summary += "\n"
            
        # Final recommendations section
        summary += "## Key Recommendations\n\n"
        
        all_recommendations = []
        
        # Collect all recommendations from different sections
        for section in ['market_conditions', 'trade_patterns', 'risk_exposure', 'benchmark_comparison']:
            if section in self.insights and 'recommendations' in self.insights[section]:
                all_recommendations.extend(self.insights[section]['recommendations'])
                
        # Remove duplicates and sort by importance
        all_recommendations = list(set(all_recommendations))
        
        for i, rec in enumerate(all_recommendations, 1):
            summary += f"{i}. {rec}\n"
            
        return summary
        
    def save_analysis(self, output_dir: str = 'results', filename: str = None) -> str:
        """
        Save the analysis results to a file.
        
        Args:
            output_dir: Directory to save the analysis
            filename: Optional filename (default: auto-generated based on timestamp)
            
        Returns:
            Path to the saved file
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"strategy_analysis_{timestamp}.json"
            
        # Run full analysis if not already done
        if not self.insights:
            self.run_full_analysis()
            
        # Create a serializable version of the insights
        serializable_insights = {}
        for section, data in self.insights.items():
            serializable_insights[section] = {}
            for key, value in data.items():
                # Convert numpy and pandas objects to Python native types
                if isinstance(value, dict):
                    serializable_insights[section][key] = {
                        k: float(v) if isinstance(v, (np.float32, np.float64)) else v 
                        for k, v in value.items()
                    }
                else:
                    serializable_insights[section][key] = value
                    
        # Save to file
        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'w') as f:
            json.dump(serializable_insights, f, indent=4)
            
        # Also save the summary
        summary_path = os.path.join(output_dir, filename.replace('.json', '_summary.md'))
        with open(summary_path, 'w') as f:
            f.write(self.generate_ai_summary())
            
        return file_path