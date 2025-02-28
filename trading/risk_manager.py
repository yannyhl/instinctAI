import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Any
import logging
from datetime import datetime, timedelta
import json
import os

class RiskManager:
    """
    Manages risk for trading strategies by enforcing position sizing,
    stop-loss, take-profit, and exposure rules.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the risk manager with configuration.
        
        Args:
            config: Dictionary containing risk management parameters
        """
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = config
        
        # Default risk parameters
        self.max_position_size = config.get('max_position_size', 0.25)  # Max 25% of portfolio in one position
        self.max_portfolio_risk = config.get('max_portfolio_risk', 0.02)  # Max 2% portfolio risk per trade
        self.max_correlated_risk = config.get('max_correlated_risk', 0.05)  # Max 5% risk in correlated assets
        self.max_leverage = config.get('max_leverage', 3.0)  # Max 3x leverage
        self.max_drawdown = config.get('max_drawdown', 0.15)  # 15% max drawdown before reducing risk
        
        # Strategy-specific risk parameters
        self.default_stop_pct = config.get('default_stop_pct', 0.02)  # Default 2% stop loss
        self.trailing_stop_activation = config.get('trailing_stop_activation', 0.015)  # Activate at 1.5% profit
        self.take_profit_pct = config.get('take_profit_pct', 0.03)  # Take profit at 3%
        
        # Risk state tracking
        self.current_drawdown = 0.0
        self.peak_equity = None
        self.trades_history = []
        self.open_positions = {}
        self.daily_pnl = []
        self.current_exposure = 0.0
        
        # Correlation matrix for instruments (could be updated dynamically)
        self.correlation_matrix = {}
        
        # Risk reduction states
        self.risk_reduction_active = False
        self.recovery_mode = False
        
        # Logging for risk events
        self.risk_events = []
        
    def update_portfolio_state(self, equity: float, positions: Dict[str, Dict], 
                               timestamp: Optional[datetime] = None) -> None:
        """
        Update the portfolio state and track risk metrics.
        
        Args:
            equity: Current portfolio equity value
            positions: Dictionary of open positions with details
            timestamp: Current timestamp (defaults to now if not provided)
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Update peak equity and calculate drawdown
        if self.peak_equity is None or equity > self.peak_equity:
            self.peak_equity = equity
            
        if self.peak_equity > 0:
            self.current_drawdown = 1 - (equity / self.peak_equity)
        
        # Update open positions
        self.open_positions = positions
        
        # Calculate current exposure
        total_position_value = sum([p.get('value', 0) for p in positions.values()])
        self.current_exposure = total_position_value / equity if equity > 0 else 0
        
        # Check for risk reduction conditions
        self._check_risk_reduction_triggers(equity, timestamp)
        
        # Log the update
        self.logger.debug(f"Portfolio updated: Equity={equity:.2f}, Exposure={self.current_exposure:.2f}, "
                         f"Drawdown={self.current_drawdown:.2%}")
    
    def calculate_position_size(self, symbol: str, entry_price: float, stop_price: float, 
                               equity: float, market_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Calculate the appropriate position size for a new trade.
        
        Args:
            symbol: Trading symbol
            entry_price: Planned entry price
            stop_price: Planned stop-loss price
            equity: Current portfolio equity
            market_data: Optional recent market data for volatility calculation
            
        Returns:
            Dictionary with position size details
        """
        # Calculate base position size using risk per trade
        if entry_price <= 0 or stop_price <= 0 or equity <= 0:
            self.logger.warning(f"Invalid inputs for position sizing: entry={entry_price}, stop={stop_price}, equity={equity}")
            return {'size': 0, 'value': 0, 'risk_pct': 0, 'reason': 'Invalid inputs'}
            
        # Risk amount in account currency
        risk_pct = self.max_portfolio_risk
        
        # Apply risk scaling based on drawdown
        if self.risk_reduction_active:
            risk_pct = self._apply_risk_scaling(risk_pct)
            
        risk_amount = equity * risk_pct
        
        # Calculate risk per unit (absolute difference between entry and stop)
        risk_per_unit = abs(entry_price - stop_price)
        
        if risk_per_unit <= 0:
            self.logger.warning(f"Invalid risk per unit: {risk_per_unit}. Using default 1% of price.")
            risk_per_unit = entry_price * 0.01  # Default to 1% of price
            
        # Calculate position size in units
        position_units = risk_amount / risk_per_unit
        position_value = position_units * entry_price
        
        # Apply maximum position size constraint
        max_position_value = equity * self.max_position_size
        
        if position_value > max_position_value:
            self.logger.info(f"Position size reduced due to max position constraint: {position_value:.2f} -> {max_position_value:.2f}")
            position_value = max_position_value
            position_units = position_value / entry_price
            
        # Check correlated risk
        correlated_symbols = self._get_correlated_symbols(symbol)
        current_correlated_risk = self._calculate_correlated_risk(correlated_symbols, equity)
        
        # If adding this position would exceed correlated risk limit, reduce size
        if current_correlated_risk + risk_pct > self.max_correlated_risk:
            available_risk = max(0, self.max_correlated_risk - current_correlated_risk)
            if available_risk <= 0:
                self.logger.warning(f"Cannot take position in {symbol}: correlated risk limit exceeded")
                return {'size': 0, 'value': 0, 'risk_pct': 0, 'reason': 'Correlated risk limit exceeded'}
                
            # Recalculate with available risk
            risk_amount = equity * available_risk
            position_units = risk_amount / risk_per_unit
            position_value = position_units * entry_price
            
        # Check leverage constraints
        projected_exposure = self.current_exposure + (position_value / equity)
        
        if projected_exposure > self.max_leverage:
            excess_leverage = projected_exposure - self.max_leverage
            reduction_factor = max(0, 1 - (excess_leverage / (position_value / equity)))
            position_units *= reduction_factor
            position_value = position_units * entry_price
            
        # Calculate actual risk percentage based on final position size
        actual_risk_amount = position_units * risk_per_unit
        actual_risk_pct = actual_risk_amount / equity if equity > 0 else 0
            
        result = {
            'size': position_units,
            'value': position_value,
            'risk_pct': actual_risk_pct,
            'entry_price': entry_price,
            'stop_price': stop_price,
        }
        
        # Add volatility adjustment if market data is provided
        if market_data is not None and len(market_data) > 20:
            volatility_factor = self._calculate_volatility_factor(market_data)
            result['volatility_factor'] = volatility_factor
            
            # Adjust size based on volatility
            if volatility_factor < 1.0:
                position_units *= volatility_factor
                position_value = position_units * entry_price
                result['size'] = position_units
                result['value'] = position_value
                result['risk_pct'] = (position_units * risk_per_unit) / equity if equity > 0 else 0
                
        self.logger.info(f"Position size for {symbol}: {position_units:.4f} units (${position_value:.2f}), "
                         f"risk: {actual_risk_pct:.2%}")
        
        return result
    
    def calculate_stop_loss(self, symbol: str, entry_price: float, direction: str, 
                           market_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Calculate appropriate stop loss levels for a trade.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            direction: Trade direction ('long' or 'short')
            market_data: Optional market data for ATR-based calculations
            
        Returns:
            Dictionary with stop loss details
        """
        if direction not in ['long', 'short']:
            self.logger.warning(f"Invalid direction: {direction}. Using 'long' as default.")
            direction = 'long'
            
        # Default stop calculation based on fixed percentage
        default_stop_pct = self.default_stop_pct
        
        if direction == 'long':
            fixed_stop = entry_price * (1 - default_stop_pct)
        else:  # short
            fixed_stop = entry_price * (1 + default_stop_pct)
            
        result = {
            'fixed_stop': fixed_stop,
            'initial_stop': fixed_stop,
            'trailing_stop': None,
            'trailing_active': False,
            'stop_type': 'fixed'
        }
        
        # Calculate ATR-based stop if market data is provided
        if market_data is not None and len(market_data) >= 14:
            atr = self._calculate_atr(market_data, period=14)
            
            if direction == 'long':
                atr_stop = entry_price - (atr * 1.5)  # 1.5 ATR for stop distance
            else:  # short
                atr_stop = entry_price + (atr * 1.5)
                
            # Use the more conservative stop (higher for shorts, lower for longs)
            if direction == 'long' and atr_stop > fixed_stop:
                result['initial_stop'] = fixed_stop
            elif direction == 'long':
                result['initial_stop'] = atr_stop
                result['stop_type'] = 'atr'
            elif direction == 'short' and atr_stop < fixed_stop:
                result['initial_stop'] = fixed_stop
            else:
                result['initial_stop'] = atr_stop
                result['stop_type'] = 'atr'
                
            # Add ATR value for reference
            result['atr'] = atr
            
        # Calculate take profit levels
        take_profit_pct = self.take_profit_pct
        
        if direction == 'long':
            result['take_profit'] = entry_price * (1 + take_profit_pct)
        else:  # short
            result['take_profit'] = entry_price * (1 - take_profit_pct)
            
        # Calculate initial risk-reward ratio
        stop_distance = abs(entry_price - result['initial_stop'])
        tp_distance = abs(entry_price - result['take_profit'])
        
        if stop_distance > 0:
            result['risk_reward_ratio'] = tp_distance / stop_distance
        else:
            result['risk_reward_ratio'] = 0
            
        self.logger.info(f"Stop loss for {symbol} {direction}: initial={result['initial_stop']:.4f}, "
                         f"take-profit={result['take_profit']:.4f}, R:R={result['risk_reward_ratio']:.2f}")
        
        return result
    
    def update_stops(self, symbol: str, current_price: float, position_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update stop loss levels based on current price and position information.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            position_info: Dictionary with position details including current stops
            
        Returns:
            Updated position info with new stop levels
        """
        if 'direction' not in position_info or 'entry_price' not in position_info:
            self.logger.warning(f"Insufficient position info for {symbol} to update stops")
            return position_info
            
        direction = position_info['direction']
        entry_price = position_info['entry_price']
        initial_stop = position_info.get('initial_stop', None)
        current_stop = position_info.get('current_stop', initial_stop)
        trailing_active = position_info.get('trailing_active', False)
        trailing_stop = position_info.get('trailing_stop', None)
        
        if current_stop is None:
            self.logger.warning(f"No stop loss defined for {symbol}, calculating default")
            stop_info = self.calculate_stop_loss(symbol, entry_price, direction)
            current_stop = stop_info['initial_stop']
        
        updated_info = position_info.copy()
        
        # Check if price reached take profit
        take_profit = position_info.get('take_profit', None)
        if take_profit is not None:
            if (direction == 'long' and current_price >= take_profit) or \
               (direction == 'short' and current_price <= take_profit):
                updated_info['take_profit_triggered'] = True
                self.logger.info(f"Take profit triggered for {symbol} at {current_price:.4f}")
                
        # Trailing stop activation check
        activation_threshold = self.trailing_stop_activation
        
        if not trailing_active:
            if direction == 'long':
                profit_pct = (current_price / entry_price) - 1
                if profit_pct >= activation_threshold:
                    trailing_active = True
                    # Set trailing stop at breakeven or better
                    trailing_stop = max(entry_price, current_price * (1 - activation_threshold))
            else:  # short
                profit_pct = 1 - (current_price / entry_price)
                if profit_pct >= activation_threshold:
                    trailing_active = True
                    # Set trailing stop at breakeven or better
                    trailing_stop = min(entry_price, current_price * (1 + activation_threshold))
                    
            updated_info['trailing_active'] = trailing_active
            
        # Update trailing stop if active
        if trailing_active and trailing_stop is not None:
            if direction == 'long':
                updated_trailing = max(trailing_stop, current_price * (1 - activation_threshold))
                updated_info['trailing_stop'] = updated_trailing
                updated_info['current_stop'] = max(current_stop, updated_trailing)
            else:  # short
                updated_trailing = min(trailing_stop, current_price * (1 + activation_threshold))
                updated_info['trailing_stop'] = updated_trailing
                updated_info['current_stop'] = min(current_stop, updated_trailing)
                
        # Check if stop loss is triggered
        current_stop = updated_info.get('current_stop', current_stop)
        
        if current_stop is not None:
            if (direction == 'long' and current_price <= current_stop) or \
               (direction == 'short' and current_price >= current_stop):
                updated_info['stop_triggered'] = True
                updated_info['stop_price'] = current_stop
                self.logger.info(f"Stop loss triggered for {symbol} at {current_stop:.4f}")
                
        return updated_info
    
    def check_max_drawdown_breach(self, equity: float) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if maximum drawdown has been breached and return action to take.
        
        Args:
            equity: Current portfolio equity value
            
        Returns:
            Tuple of (breach_occurred, action_details)
        """
        if self.peak_equity is None or self.peak_equity <= 0:
            return False, {}
            
        drawdown = 1 - (equity / self.peak_equity)
        
        if drawdown >= self.max_drawdown and not self.risk_reduction_active:
            self.risk_reduction_active = True
            self.recovery_mode = True
            
            # Calculate risk scaling factor based on drawdown severity
            scaling_factor = max(0.25, 1 - (drawdown / self.max_drawdown))
            
            action = {
                'type': 'reduce_risk',
                'drawdown': drawdown,
                'scaling_factor': scaling_factor,
                'max_position_size': self.max_position_size * scaling_factor,
                'close_positions': self._get_underwater_positions()
            }
            
            self.logger.warning(f"Max drawdown breached: {drawdown:.2%} > {self.max_drawdown:.2%}. "
                               f"Activating risk reduction with scaling factor {scaling_factor:.2f}")
            
            # Log risk event
            self._log_risk_event('max_drawdown_breach', action)
            
            return True, action
            
        # Check for recovery
        if self.risk_reduction_active and drawdown < (self.max_drawdown * 0.7):
            self.risk_reduction_active = False
            self.recovery_mode = False
            
            action = {
                'type': 'restore_risk',
                'drawdown': drawdown,
                'message': 'Drawdown recovered, restoring normal risk parameters'
            }
            
            self.logger.info(f"Drawdown recovered to {drawdown:.2%}, restoring normal risk parameters")
            
            # Log risk event
            self._log_risk_event('drawdown_recovery', action)
            
            return True, action
            
        return False, {}
    
    def evaluate_trade_risks(self, trade_params: Dict[str, Any], 
                            market_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Evaluate risks for a potential trade and provide risk assessment.
        
        Args:
            trade_params: Dictionary with trade parameters
            market_data: Optional market data for analysis
            
        Returns:
            Risk assessment dictionary
        """
        required_fields = ['symbol', 'direction', 'entry_price', 'stop_price', 'equity']
        
        if not all(field in trade_params for field in required_fields):
            self.logger.warning(f"Missing required fields for trade risk evaluation")
            return {'approved': False, 'reason': 'Missing required trade parameters'}
            
        symbol = trade_params['symbol']
        direction = trade_params['direction']
        entry_price = trade_params['entry_price']
        stop_price = trade_params['stop_price']
        equity = trade_params['equity']
        
        # Calculate position size
        position_info = self.calculate_position_size(
            symbol, entry_price, stop_price, equity, market_data
        )
        
        # Check if position size is zero (risk limits reached)
        if position_info['size'] <= 0:
            return {
                'approved': False,
                'reason': position_info.get('reason', 'Position size calculation resulted in zero size'),
                'position_info': position_info
            }
            
        # Calculate risk-reward ratio
        stop_distance = abs(entry_price - stop_price)
        
        if 'take_profit' in trade_params:
            take_profit = trade_params['take_profit']
            tp_distance = abs(entry_price - take_profit)
            risk_reward = tp_distance / stop_distance if stop_distance > 0 else 0
        else:
            # Default take profit based on configuration
            take_profit_pct = self.take_profit_pct
            
            if direction == 'long':
                take_profit = entry_price * (1 + take_profit_pct)
            else:
                take_profit = entry_price * (1 - take_profit_pct)
                
            tp_distance = abs(entry_price - take_profit)
            risk_reward = tp_distance / stop_distance if stop_distance > 0 else 0
            
        # Risk assessment
        assessment = {
            'approved': True,
            'position_info': position_info,
            'risk_metrics': {
                'risk_reward_ratio': risk_reward,
                'risk_percent': position_info['risk_pct'],
                'position_size_percent': position_info['value'] / equity if equity > 0 else 0,
                'projected_exposure': self.current_exposure + (position_info['value'] / equity if equity > 0 else 0)
            }
        }
        
        # Check risk-reward ratio
        min_risk_reward = self.config.get('min_risk_reward', 1.5)
        
        if risk_reward < min_risk_reward:
            assessment['approved'] = False
            assessment['reason'] = f"Risk-reward ratio too low: {risk_reward:.2f} < {min_risk_reward:.2f}"
            
        # Check risk signals if market data provided
        if market_data is not None and len(market_data) > 30:
            risk_signals = self._analyze_market_risk(market_data, direction)
            assessment['risk_signals'] = risk_signals
            
            # If strong contrary signals exist, don't approve the trade
            if risk_signals.get('contrary_strength', 0) > 70:
                assessment['approved'] = False
                assessment['reason'] = f"Strong contrary risk signals: {risk_signals['contrary_signals']}"
            
        # Factor in the health of the current portfolio
        if self.risk_reduction_active:
            assessment['portfolio_status'] = 'risk_reduced'
            assessment['drawdown'] = self.current_drawdown
            
            # If in serious drawdown, more strict on new trades
            if self.current_drawdown > (self.max_drawdown * 0.9):
                assessment['approved'] = False
                assessment['reason'] = f"Portfolio in significant drawdown: {self.current_drawdown:.2%}"
                
        elif self.current_drawdown > (self.max_drawdown * 0.7):
            assessment['portfolio_status'] = 'caution'
            assessment['drawdown'] = self.current_drawdown
            
            # Require better risk-reward for trades during caution mode
            if risk_reward < min_risk_reward * 1.3:
                assessment['approved'] = False
                assessment['reason'] = f"Higher risk-reward needed during portfolio caution state"
        else:
            assessment['portfolio_status'] = 'normal'
            assessment['drawdown'] = self.current_drawdown
            
        return assessment
    
    def log_completed_trade(self, trade_info: Dict[str, Any]) -> None:
        """
        Log a completed trade for risk analysis purposes.
        
        Args:
            trade_info: Dictionary with completed trade information
        """
        required_fields = ['symbol', 'direction', 'entry_price', 'exit_price', 
                           'entry_time', 'exit_time', 'pnl', 'size']
        
        if not all(field in trade_info for field in required_fields):
            self.logger.warning(f"Missing required fields for trade logging")
            return
            
        # Add to trade history
        self.trades_history.append(trade_info)
        
        # Update daily PnL
        exit_date = trade_info['exit_time'].date()
        pnl = trade_info['pnl']
        
        # Find or create the daily PnL entry
        daily_entry = next((entry for entry in self.daily_pnl if entry['date'] == exit_date), None)
        
        if daily_entry:
            daily_entry['pnl'] += pnl
            daily_entry['trades'] += 1
        else:
            self.daily_pnl.append({
                'date': exit_date,
                'pnl': pnl,
                'trades': 1
            })
            
        # Log the completed trade
        self.logger.info(f"Completed trade logged: {trade_info['symbol']} {trade_info['direction']} "
                         f"PnL: {pnl:.2f}")
    
    def _calculate_atr(self, market_data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        if 'high' not in market_data.columns or 'low' not in market_data.columns or 'close' not in market_data.columns:
            return 0.0
            
        # Calculate True Range
        high = market_data['high']
        low = market_data['low']
        close = market_data['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        true_range = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
        atr = true_range.rolling(window=period).mean().iloc[-1]
        
        return atr if not np.isnan(atr) else 0.0
    
    def _calculate_volatility_factor(self, market_data: pd.DataFrame) -> float:
        """Calculate volatility adjustment factor for position sizing."""
        if 'close' not in market_data.columns or len(market_data) < 20:
            return 1.0
            
        # Calculate historical volatility (20-day)
        returns = market_data['close'].pct_change().dropna()
        
        if len(returns) < 10:
            return 1.0
            
        recent_vol = returns[-20:].std() * np.sqrt(252) if len(returns) >= 20 else returns.std() * np.sqrt(252)
        baseline_vol = self.config.get('baseline_volatility', 0.6)  # 60% annual vol as baseline
        
        if recent_vol <= 0:
            return 1.0
            
        vol_factor = baseline_vol / recent_vol
        
        # Limit the factor to reasonable bounds
        vol_factor = max(0.5, min(vol_factor, 1.5))
        
        return vol_factor
    
    def _apply_risk_scaling(self, base_risk: float) -> float:
        """Scale risk based on current drawdown and recovery status."""
        if not self.risk_reduction_active:
            return base_risk
            
        # Calculate scaling factor based on drawdown severity
        scaling_factor = max(0.25, 1 - (self.current_drawdown / self.max_drawdown))
        
        # Apply scaling factor to base risk
        scaled_risk = base_risk * scaling_factor
        
        # If in recovery mode, cap the maximum risk
        if self.recovery_mode:
            scaled_risk = min(scaled_risk, base_risk * 0.5)
            
        self.logger.debug(f"Risk scaled from {base_risk:.2%} to {scaled_risk:.2%} "
                         f"(factor: {scaling_factor:.2f}, recovery: {self.recovery_mode})")
        
        return scaled_risk
    
    def _get_correlated_symbols(self, symbol: str) -> List[str]:
        """Get list of symbols correlated with the given symbol."""
        # This is a simplified implementation that would typically use
        # a correlation matrix calculated from market data
        
        if not self.correlation_matrix:
            # Default correlations - in a real system, this would be dynamically updated
            self.correlation_matrix = {
                'BTC': ['ETH', 'SOL'],
                'ETH': ['BTC', 'SOL', 'AVAX'],
                'SOL': ['BTC', 'ETH', 'AVAX'],
                'AVAX': ['ETH', 'SOL'],
                'DOGE': ['SHIB'],
                'SHIB': ['DOGE']
            }
            
        # Extract symbol base name (remove suffixes like PERP, USDT, etc.)
        base_symbol = symbol.split('-')[0].split('/')[0]
        
        return self.correlation_matrix.get(base_symbol, [])
    
    def _calculate_correlated_risk(self, correlated_symbols: List[str], equity: float) -> float:
        """Calculate current risk exposure to correlated symbols."""
        if not correlated_symbols or not self.open_positions:
            return 0.0
            
        correlated_risk = 0.0
        
        for pos_symbol, pos_info in self.open_positions.items():
            base_pos_symbol = pos_symbol.split('-')[0].split('/')[0]
            
            if base_pos_symbol in correlated_symbols:
                # Add the risk from this correlated position
                if 'risk_pct' in pos_info:
                    correlated_risk += pos_info['risk_pct']
                elif 'value' in pos_info and 'entry_price' in pos_info and 'stop_price' in pos_info:
                    # Calculate risk if not explicitly provided
                    risk_amount = pos_info['value'] * abs(pos_info['entry_price'] - pos_info['stop_price']) / pos_info['entry_price']
                    correlated_risk += risk_amount / equity if equity > 0 else 0
                    
        return correlated_risk
    
    def _get_underwater_positions(self) -> List[Dict[str, Any]]:
        """Get list of positions that are significantly underwater."""
        underwater_positions = []
        
        for symbol, pos_info in self.open_positions.items():
            if 'unrealized_pnl_pct' in pos_info and pos_info['unrealized_pnl_pct'] < -0.1:
                # Position is down more than 10%
                underwater_positions.append({
                    'symbol': symbol,
                    'unrealized_pnl_pct': pos_info['unrealized_pnl_pct'],
                    'value': pos_info.get('value', 0),
                    'direction': pos_info.get('direction', 'unknown'),
                    'days_held': (datetime.now() - pos_info.get('entry_time', datetime.now())).days
                })
                
        return underwater_positions
    
    def _check_risk_reduction_triggers(self, equity: float, timestamp: datetime) -> None:
        """Check if risk reduction mode should be activated or deactivated."""
        # Activate risk reduction if drawdown exceeds threshold
        if self.current_drawdown > self.max_drawdown and not self.risk_reduction_active:
            self.risk_reduction_active = True
            self.logger.warning(f"Risk reduction activated: Drawdown {self.current_drawdown:.2%} > "
                               f"Max allowable {self.max_drawdown:.2%}")
            
            self.risk_events.append({
                'event': 'risk_reduction_activated',
                'timestamp': timestamp,
                'drawdown': self.current_drawdown,
                'equity': equity
            })
            
        # Check if we can deactivate risk reduction (recovery)
        elif self.risk_reduction_active and self.current_drawdown < (self.max_drawdown * 0.7):
            # If we've reduced drawdown substantially, we can exit risk reduction mode
            self.risk_reduction_active = False
            self.recovery_mode = False
            self.logger.info(f"Risk reduction deactivated: Drawdown recovered to {self.current_drawdown:.2%}")
            
            self.risk_events.append({
                'event': 'risk_reduction_deactivated',
                'timestamp': timestamp,
                'drawdown': self.current_drawdown,
                'equity': equity
            })
            
        # Check if we need to enter recovery mode (more severe risk reduction)
        elif self.risk_reduction_active and not self.recovery_mode and self.current_drawdown > (self.max_drawdown * 1.3):
            self.recovery_mode = True
            self.logger.warning(f"Recovery mode activated: Drawdown {self.current_drawdown:.2%}")
            
            self.risk_events.append({
                'event': 'recovery_mode_activated',
                'timestamp': timestamp,
                'drawdown': self.current_drawdown,
                'equity': equity
            })
    
    def _analyze_market_risk(self, market_data: pd.DataFrame, direction: str) -> Dict[str, Any]:
        """Analyze market data for risk signals that might affect the trade."""
        risk_signals = {
            'favorable_signals': [],
            'contrary_signals': [],
            'favorable_strength': 0,
            'contrary_strength': 0
        }
        
        # Not enough data for analysis
        if len(market_data) < 30 or 'close' not in market_data.columns:
            return risk_signals
            
        # Extract price data
        prices = market_data['close']
        
        # Calculate some indicators for risk assessment
        try:
            # Trend strength (using simple moving averages)
            sma20 = prices.rolling(window=20).mean()
            sma50 = prices.rolling(window=50).mean()
            
            trend_direction = 'up' if sma20.iloc[-1] > sma50.iloc[-1] else 'down'
            
            # Volatility (ATR relative to price)
            atr = self._calculate_atr(market_data)
            atr_pct = atr / prices.iloc[-1] if prices.iloc[-1] > 0 else 0
            
            # Recent momentum
            momentum_5d = (prices.iloc[-1] / prices.iloc[-6] - 1) if len(prices) >= 6 else 0
            
            # Recent volume trend (if available)
            volume_trend = None
            if 'volume' in market_data.columns:
                recent_vol = market_data['volume'].tail(5).mean()
                prev_vol = market_data['volume'].iloc[-10:-5].mean() if len(market_data) >= 10 else recent_vol
                volume_trend = 'increasing' if recent_vol > prev_vol * 1.2 else 'decreasing' if recent_vol < prev_vol * 0.8 else 'stable'
                
            # Check for signals favorable or contrary to the trade direction
            if direction == 'long':
                # Favorable signals for long trades
                if trend_direction == 'up':
                    risk_signals['favorable_signals'].append('Uptrend based on moving averages')
                    risk_signals['favorable_strength'] += 30
                    
                if momentum_5d > 0.03:  # Positive momentum
                    risk_signals['favorable_signals'].append(f'Strong positive momentum: {momentum_5d:.2%}')
                    risk_signals['favorable_strength'] += 20
                    
                if volume_trend == 'increasing' and momentum_5d > 0:
                    risk_signals['favorable_signals'].append('Increasing volume on positive price action')
                    risk_signals['favorable_strength'] += 15
                    
                # Contrary signals for long trades
                if trend_direction == 'down':
                    risk_signals['contrary_signals'].append('Downtrend based on moving averages')
                    risk_signals['contrary_strength'] += 30
                    
                if momentum_5d < -0.03:  # Negative momentum
                    risk_signals['contrary_signals'].append(f'Strong negative momentum: {momentum_5d:.2%}')
                    risk_signals['contrary_strength'] += 20
                    
                if volume_trend == 'increasing' and momentum_5d < 0:
                    risk_signals['contrary_signals'].append('Increasing volume on negative price action')
                    risk_signals['contrary_strength'] += 15
                    
            elif direction == 'short':
                # Favorable signals for short trades
                if trend_direction == 'down':
                    risk_signals['favorable_signals'].append('Downtrend based on moving averages')
                    risk_signals['favorable_strength'] += 30
                    
                if momentum_5d < -0.03:  # Negative momentum
                    risk_signals['favorable_signals'].append(f'Strong negative momentum: {momentum_5d:.2%}')
                    risk_signals['favorable_strength'] += 20
                    
                if volume_trend == 'increasing' and momentum_5d < 0:
                    risk_signals['favorable_signals'].append('Increasing volume on negative price action')
                    risk_signals['favorable_strength'] += 15
                    
                # Contrary signals for short trades
                if trend_direction == 'up':
                    risk_signals['contrary_signals'].append('Uptrend based on moving averages')
                    risk_signals['contrary_strength'] += 30
                    
                if momentum_5d > 0.03:  # Positive momentum
                    risk_signals['contrary_signals'].append(f'Strong positive momentum: {momentum_5d:.2%}')
                    risk_signals['contrary_strength'] += 20
                    
                if volume_trend == 'increasing' and momentum_5d > 0:
                    risk_signals['contrary_signals'].append('Increasing volume on positive price action')
                    risk_signals['contrary_strength'] += 15
            
            # Volatility considerations (applies to both directions)
            if atr_pct > 0.05:  # High volatility (5%+ daily range)
                risk_signals['contrary_signals'].append(f'High volatility environment: {atr_pct:.2%} ATR')
                risk_signals['contrary_strength'] += 10
                
        except Exception as e:
            self.logger.warning(f"Error in market risk analysis: {str(e)}")
            
        return risk_signals
    
    def get_risk_report(self) -> Dict[str, Any]:
        """Generate a comprehensive risk report for the current portfolio."""
        report = {
            'timestamp': datetime.now(),
            'current_state': {
                'drawdown': self.current_drawdown,
                'peak_equity': self.peak_equity,
                'exposure': self.current_exposure,
                'risk_reduction_active': self.risk_reduction_active,
                'recovery_mode': self.recovery_mode
            },
            'positions': {
                'total_count': len(self.open_positions),
                'total_value': sum([p.get('value', 0) for p in self.open_positions.values()]),
                'direction_exposure': self._calculate_directional_exposure(),
                'underwater_positions': self._get_underwater_positions()
            },
            'trading_stats': self._calculate_trading_stats(),
            'risk_events': self.risk_events[-10:] if len(self.risk_events) > 10 else self.risk_events
        }
        
        # Add risk alerts
        report['alerts'] = []
        
        if self.current_drawdown > self.max_drawdown:
            report['alerts'].append({
                'severity': 'high',
                'message': f'Maximum drawdown exceeded: {self.current_drawdown:.2%}',
                'recommended_action': 'Reduce position sizes and consider closing underwater positions'
            })
            
        if self.current_exposure > self.max_leverage * 0.9:
            report['alerts'].append({
                'severity': 'high',
                'message': f'Near maximum exposure: {self.current_exposure:.2f}x',
                'recommended_action': 'Avoid opening new positions and consider reducing exposure'
            })
            
        # Check for correlated positions
        correlated_groups = self._identify_correlated_position_groups()
        for group, details in correlated_groups.items():
            if details['total_risk'] > self.max_correlated_risk:
                report['alerts'].append({
                    'severity': 'medium',
                    'message': f'High correlated risk in {group}: {details["total_risk"]:.2%}',
                    'recommended_action': 'Consider reducing positions in correlated assets'
                })
                
        # Check win rate and profit trends
        trading_stats = report['trading_stats']
        if trading_stats.get('recent_win_rate', 1) < 0.3 and trading_stats.get('recent_trade_count', 0) >= 5:
            report['alerts'].append({
                'severity': 'medium',
                'message': f'Low recent win rate: {trading_stats["recent_win_rate"]:.2%} over last {trading_stats["recent_trade_count"]} trades',
                'recommended_action': 'Review recent trades and consider adjusting strategy parameters'
            })
            
        return report
    
    def _calculate_directional_exposure(self) -> Dict[str, float]:
        """Calculate exposure by direction (long/short)."""
        long_exposure = 0.0
        short_exposure = 0.0
        
        for pos_info in self.open_positions.values():
            if pos_info.get('direction') == 'long':
                long_exposure += pos_info.get('value', 0)
            elif pos_info.get('direction') == 'short':
                short_exposure += pos_info.get('value', 0)
                
        return {
            'long': long_exposure,
            'short': short_exposure,
            'net': long_exposure - short_exposure
        }
    
    def _identify_correlated_position_groups(self) -> Dict[str, Dict[str, Any]]:
        """Identify groups of correlated positions and their combined risk."""
        correlated_groups = {}
        
        # Define groups based on market segments or asset correlations
        # This is a simplified example - in a real system this would be more sophisticated
        groups = {
            'BTC Ecosystem': ['BTC', 'ETH', 'SOL'],
            'DeFi': ['AAVE', 'UNI', 'COMP', 'MKR'],
            'L1 Blockchains': ['ETH', 'SOL', 'AVAX', 'ATOM'],
            'Meme Coins': ['DOGE', 'SHIB', 'PEPE']
        }
        
        for group_name, symbols in groups.items():
            group_positions = []
            total_value = 0.0
            total_risk = 0.0
            
            for pos_symbol, pos_info in self.open_positions.items():
                base_symbol = pos_symbol.split('-')[0].split('/')[0]
                
                if base_symbol in symbols:
                    group_positions.append({
                        'symbol': pos_symbol,
                        'value': pos_info.get('value', 0),
                        'risk_pct': pos_info.get('risk_pct', 0)
                    })
                    
                    total_value += pos_info.get('value', 0)
                    total_risk += pos_info.get('risk_pct', 0)
                    
            if group_positions:
                correlated_groups[group_name] = {
                    'positions': group_positions,
                    'total_value': total_value,
                    'total_risk': total_risk
                }
                
        return correlated_groups
    
    def _calculate_trading_stats(self) -> Dict[str, Any]:
        """Calculate trading statistics based on completed trades."""
        stats = {
            'total_trades': len(self.trades_history),
            'profitable_trades': len([t for t in self.trades_history if t.get('pnl', 0) > 0]),
            'unprofitable_trades': len([t for t in self.trades_history if t.get('pnl', 0) <= 0])
        }
        
        if stats['total_trades'] > 0:
            stats['overall_win_rate'] = stats['profitable_trades'] / stats['total_trades']
            stats['total_pnl'] = sum([t.get('pnl', 0) for t in self.trades_history])
            
            # Calculate average profit and loss
            profits = [t.get('pnl', 0) for t in self.trades_history if t.get('pnl', 0) > 0]
            losses = [t.get('pnl', 0) for t in self.trades_history if t.get('pnl', 0) <= 0]
            
            stats['avg_profit'] = sum(profits) / len(profits) if profits else 0
            stats['avg_loss'] = sum(losses) / len(losses) if losses else 0
            stats['profit_factor'] = abs(sum(profits) / sum(losses)) if sum(losses) != 0 else float('inf')
            
            # Recent performance (last 10 trades)
            recent_trades = self.trades_history[-10:]
            stats['recent_trade_count'] = len(recent_trades)
            stats['recent_win_rate'] = len([t for t in recent_trades if t.get('pnl', 0) > 0]) / len(recent_trades) if recent_trades else 0
            stats['recent_pnl'] = sum([t.get('pnl', 0) for t in recent_trades])
            
            # Daily stats
            stats['daily_stats'] = self._calculate_daily_stats()
            
        return stats
    
    def _calculate_daily_stats(self) -> List[Dict[str, Any]]:
        """Calculate daily trading statistics."""
        if not self.daily_pnl:
            return []
            
        # Sort by date
        sorted_daily = sorted(self.daily_pnl, key=lambda x: x['date'])
        
        # Calculate cumulative metrics
        cumulative = 0
        result = []
        
        for day in sorted_daily:
            cumulative += day['pnl']
            result.append({
                'date': day['date'].strftime('%Y-%m-%d'),
                'daily_pnl': day['pnl'],
                'trade_count': day['trades'],
                'cumulative_pnl': cumulative
            })
            
        return result
    
    def save_risk_state(self, filepath: str = 'risk_manager_state.json') -> None:
        """Save the current risk manager state to a file."""
        state = {
            'current_drawdown': self.current_drawdown,
            'peak_equity': self.peak_equity,
            'risk_reduction_active': self.risk_reduction_active,
            'recovery_mode': self.recovery_mode,
            'risk_events': self.risk_events,
            'trades_count': len(self.trades_history),
            'saved_at': datetime.now().isoformat()
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(state, f, indent=4, default=str)
                
            self.logger.info(f"Risk manager state saved to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save risk manager state: {str(e)}")
            
    def load_risk_state(self, filepath: str = 'risk_manager_state.json') -> bool:
        """Load risk manager state from a file."""
        if not os.path.exists(filepath):
            self.logger.warning(f"Risk state file not found: {filepath}")
            return False
            
        try:
            with open(filepath, 'r') as f:
                state = json.load(f)
                
            self.current_drawdown = state.get('current_drawdown', 0)
            self.peak_equity = state.get('peak_equity')
            self.risk_reduction_active = state.get('risk_reduction_active', False)
            self.recovery_mode = state.get('recovery_mode', False)
            self.risk_events = state.get('risk_events', [])
            
            self.logger.info(f"Risk manager state loaded from {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load risk manager state: {str(e)}")
            return False