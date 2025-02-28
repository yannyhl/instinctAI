# advanced_trading/strategies/volume_profile_strategy.py

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional, Union
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from pathlib import Path
import os

from ..models.volume_profile import VolumeProfile
from ..utils.indicators import add_technical_indicators

logger = logging.getLogger(__name__)

class VolumeProfileStrategy:
    """
    Strategy utilizing volume profile analysis to identify key levels and react
    to price movements around these levels, particularly during liquidation cascades.
    """
    
    def __init__(self, 
                lookback_periods: int = 30,
                num_volume_bins: int = 60,
                value_area_pct: float = 70.0,
                poc_threshold_pct: float = 0.5,
                key_level_threshold_pct: float = 0.2,
                liquidation_threshold: float = 2.0,
                position_size_pct: float = 0.2,
                profit_target_pct: float = 2.0,
                stop_loss_pct: float = 1.0,
                max_holding_periods: int = 48):
        """
        Initialize the volume profile strategy.
        
        Args:
            lookback_periods: Number of periods to use for volume profile analysis
            num_volume_bins: Number of bins for volume profile
            value_area_pct: Percentage of volume within value area
            poc_threshold_pct: Threshold for price proximity to POC (%)
            key_level_threshold_pct: Threshold for price proximity to key levels (%)
            liquidation_threshold: Threshold for detecting liquidation (std deviations)
            position_size_pct: Position size as percentage of capital
            profit_target_pct: Profit target percentage
            stop_loss_pct: Stop loss percentage
            max_holding_periods: Maximum holding periods before forced exit
        """
        self.lookback_periods = lookback_periods
        self.num_volume_bins = num_volume_bins
        self.value_area_pct = value_area_pct
        self.poc_threshold_pct = poc_threshold_pct / 100.0  # Convert to decimal
        self.key_level_threshold_pct = key_level_threshold_pct / 100.0
        self.liquidation_threshold = liquidation_threshold
        self.position_size_pct = position_size_pct
        self.profit_target_pct = profit_target_pct / 100.0
        self.stop_loss_pct = stop_loss_pct / 100.0
        self.max_holding_periods = max_holding_periods
        
        # Initialize volume profile analyzer
        self.volume_profile = VolumeProfile(
            num_bins=num_volume_bins,
            value_area_percentage=value_area_pct
        )
        
        # Strategy state
        self.active_positions = {}
        self.key_levels = {}
        self.last_analysis_time = {}
        
        logger.info(f"Initialized Volume Profile strategy with {lookback_periods} lookback periods")
    
    def detect_liquidation(self, data: pd.DataFrame, periods: int = 5) -> bool:
        """
        Detect potential liquidation cascades.
        
        Args:
            data: OHLCV DataFrame
            periods: Number of periods to check for liquidation
            
        Returns:
            True if liquidation detected, False otherwise
        """
        if len(data) < periods + 10:
            return False
        
        # Get recent data
        recent_data = data.tail(periods)
        
        # Check for rapid price decline
        price_change = recent_data['close'].pct_change().sum()
        
        # Check for increased volume
        avg_volume = data['volume'].iloc[-(periods+10):-periods].mean()
        recent_volume = recent_data['volume'].mean()
        volume_increase = recent_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Check for increased volatility
        avg_volatility = data['close'].pct_change().iloc[-(periods+10):-periods].std()
        recent_volatility = recent_data['close'].pct_change().std()
        volatility_increase = recent_volatility / avg_volatility if avg_volatility > 0 else 1.0
        
        # Define liquidation criteria
        is_liquidation = (
            price_change < -0.05 and  # At least 5% price drop
            volume_increase > 2.0 and  # Volume at least doubled
            volatility_increase > 1.5  # Volatility increased by at least 50%
        )
        
        if is_liquidation:
            logger.info(f"Potential liquidation detected: price change {price_change:.2%}, "
                      f"volume increase {volume_increase:.2f}x, "
                      f"volatility increase {volatility_increase:.2f}x")
        
        return is_liquidation
    
    def update_volume_profile(self, data: pd.DataFrame) -> Dict:
        """
        Update the volume profile analysis.
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            Dictionary of volume profile analysis results
        """
        # Use recent data for volume profile
        recent_data = data.tail(self.lookback_periods)
        
        # Run volume profile analysis
        analysis = self.volume_profile.analyze(recent_data)
        
        if analysis is None:
            logger.warning("Volume profile analysis failed")
            return {}
        
        # Get current price
        current_price = data['close'].iloc[-1]
        
        # Extract key levels
        poc = self.volume_profile.get_poc_level()
        value_area = self.volume_profile.value_area
        peak_levels = self.volume_profile.peak_levels
        
        # Calculate distance to POC
        poc_distance_pct = abs(current_price - poc) / current_price if poc else 1.0
        
        # Calculate distance to value area
        if value_area:
            val, vah = value_area
            in_value_area = val <= current_price <= vah
            value_area_distance_pct = 0.0 if in_value_area else min(
                abs(current_price - val) / current_price,
                abs(current_price - vah) / current_price
            )
        else:
            in_value_area = False
            value_area_distance_pct = 1.0
        
        # Check if price is near any key level
        near_key_level = False
        closest_level = None
        closest_distance_pct = 1.0
        
        # Check POC first
        if poc and poc_distance_pct <= self.poc_threshold_pct:
            near_key_level = True
            closest_level = poc
            closest_distance_pct = poc_distance_pct
        
        # Check peak levels
        if peak_levels is not None:
            for level in peak_levels:
                distance_pct = abs(current_price - level) / current_price
                if distance_pct <= self.key_level_threshold_pct and distance_pct < closest_distance_pct:
                    near_key_level = True
                    closest_level = level
                    closest_distance_pct = distance_pct
        
        # Store results
        results = {
            'poc': poc,
            'value_area': value_area,
            'peak_levels': peak_levels,
            'current_price': current_price,
            'poc_distance_pct': poc_distance_pct,
            'value_area_distance_pct': value_area_distance_pct,
            'in_value_area': in_value_area,
            'near_key_level': near_key_level,
            'closest_level': closest_level,
            'closest_distance_pct': closest_distance_pct
        }
        
        return results
    
    def generate_signal(self, data: pd.DataFrame, symbol: str) -> Tuple[int, Dict]:
        """
        Generate trading signal based on volume profile and market conditions.
        
        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol
            
        Returns:
            Tuple of (signal, metadata)
        """
        if len(data) < self.lookback_periods:
            logger.warning(f"Not enough data for {symbol}, need at least {self.lookback_periods} periods")
            return 0, {}
        
        # Add technical indicators
        df = add_technical_indicators(data.copy())
        
        # Update volume profile
        vp_results = self.update_volume_profile(df)
        
        if not vp_results:
            return 0, {}
        
        # Check for liquidation cascade
        is_liquidation = self.detect_liquidation(df)
        
        # Current price
        current_price = df['close'].iloc[-1]
        
        # Initialize signal
        signal = 0
        confidence = 0.0
        entry_level = None
        metadata = {}
        
        # Check if we're near a key level
        if vp_results['near_key_level']:
            closest_level = vp_results['closest_level']
            
            # Check price relative to key level
            if current_price < closest_level:
                # Price below key level (potential support)
                if is_liquidation:
                    # Liquidation at support: Strong buy signal
                    signal = 1
                    confidence = 0.8
                    entry_level = current_price
                    
                    logger.info(f"{symbol}: Liquidation cascade at support level {closest_level:.2f}")
                else:
                    # Regular support test: Moderate buy signal
                    signal = 1
                    confidence = 0.5
                    entry_level = current_price
                    
                    logger.info(f"{symbol}: Price testing support at {closest_level:.2f}")
            
            elif current_price > closest_level:
                # Price above key level (potential resistance)
                if is_liquidation:
                    # Liquidation at resistance: Ignore (not a typical pattern)
                    signal = 0
                    confidence = 0.0
                else:
                    # Regular resistance test: Moderate sell signal
                    signal = -1
                    confidence = 0.5
                    entry_level = current_price
                    
                    logger.info(f"{symbol}: Price testing resistance at {closest_level:.2f}")
        
        # Check value area
        elif vp_results['in_value_area']:
            # Inside value area, check position within value area
            val, vah = vp_results['value_area']
            position_in_va = (current_price - val) / (vah - val) if vah > val else 0.5
            
            if position_in_va < 0.3 and is_liquidation:
                # Near bottom of value area during liquidation: Moderate buy
                signal = 1
                confidence = 0.6
                entry_level = current_price
                
                logger.info(f"{symbol}: Liquidation near bottom of value area")
            
            elif position_in_va > 0.7 and not is_liquidation:
                # Near top of value area: Moderate sell
                signal = -1
                confidence = 0.4
                entry_level = current_price
                
                logger.info(f"{symbol}: Price near top of value area")
        
        # Create metadata for the signal
        metadata = {
            'signal': signal,
            'confidence': confidence,
            'entry_level': entry_level,
            'current_price': current_price,
            'is_liquidation': is_liquidation,
            'poc': vp_results['poc'],
            'value_area': vp_results['value_area'],
            'near_key_level': vp_results['near_key_level'],
            'closest_level': vp_results['closest_level'],
            'volume_profile': self.volume_profile
        }
        
        # Special case: check if we should exit an existing position
        if symbol in self.active_positions:
            position = self.active_positions[symbol]
            
            # Check stop loss
            if position['direction'] > 0:  # Long position
                stop_level = position['entry_price'] * (1 - self.stop_loss_pct)
                if current_price <= stop_level:
                    signal = 0  # Exit
                    metadata['exit_reason'] = 'stop_loss'
                    logger.info(f"{symbol}: Stop loss triggered for long position")
            
            elif position['direction'] < 0:  # Short position
                stop_level = position['entry_price'] * (1 + self.stop_loss_pct)
                if current_price >= stop_level:
                    signal = 0  # Exit
                    metadata['exit_reason'] = 'stop_loss'
                    logger.info(f"{symbol}: Stop loss triggered for short position")
            
            # Check profit target
            if position['direction'] > 0:  # Long position
                target_level = position['entry_price'] * (1 + self.profit_target_pct)
                if current_price >= target_level:
                    signal = 0  # Exit
                    metadata['exit_reason'] = 'profit_target'
                    logger.info(f"{symbol}: Profit target reached for long position")
            
            elif position['direction'] < 0:  # Short position
                target_level = position['entry_price'] * (1 - self.profit_target_pct)
                if current_price <= target_level:
                    signal = 0  # Exit
                    metadata['exit_reason'] = 'profit_target'
                    logger.info(f"{symbol}: Profit target reached for short position")
            
            # Check max holding time
            entry_time = position['entry_time']
            holding_periods = len(data) - data.index.get_loc(entry_time) if entry_time in data.index else self.max_holding_periods + 1
            
            if holding_periods >= self.max_holding_periods:
                signal = 0  # Exit
                metadata['exit_reason'] = 'max_holding_time'
                logger.info(f"{symbol}: Max holding time reached ({holding_periods} periods)")
        
        return signal, metadata
    
    def execute_trades(self, data_dict: Dict[str, pd.DataFrame], 
                      capital: float) -> List[Dict]:
        """
        Execute trades based on volume profile signals.
        
        Args:
            data_dict: Dictionary of OHLCV DataFrames
            capital: Available capital
            
        Returns:
            List of executed trades
        """
        executed_trades = []
        
        for symbol, data in data_dict.items():
            try:
                # Generate signal
                signal, metadata = self.generate_signal(data, symbol)
                
                # Current position
                current_position = self.active_positions.get(symbol, {}).get('direction', 0)
                
                # Skip if no position change
                if signal == current_position:
                    continue
                
                # Current price
                current_price = data['close'].iloc[-1]
                
                if signal == 0 and current_position != 0:
                    # Exit position
                    position = self.active_positions[symbol]
                    entry_price = position['entry_price']
                    entry_time = position['entry_time']
                    
                    # Calculate P&L
                    if current_position > 0:  # Long position
                        pnl_pct = (current_price / entry_price - 1) * 100
                    else:  # Short position
                        pnl_pct = (entry_price / current_price - 1) * 100
                    
                    # Calculate holding period
                    if entry_time in data.index:
                        holding_periods = len(data) - data.index.get_loc(entry_time)
                    else:
                        holding_periods = 0
                    
                    # Record trade
                    trade = {
                        'symbol': symbol,
                        'action': 'exit',
                        'direction': current_position,
                        'entry_price': entry_price,
                        'entry_time': entry_time,
                        'exit_price': current_price,
                        'exit_time': data.index[-1],
                        'pnl_pct': pnl_pct,
                        'holding_periods': holding_periods,
                        'exit_reason': metadata.get('exit_reason', 'signal_change')
                    }
                    
                    executed_trades.append(trade)
                    
                    # Remove from active positions
                    del self.active_positions[symbol]
                    
                    logger.info(f"Exited {symbol} position at {current_price:.2f}, "
                              f"P&L: {pnl_pct:.2f}%, holding periods: {holding_periods}")
                
                elif signal != 0 and current_position == 0:
                    # Enter new position
                    confidence = metadata.get('confidence', 0.5)
                    
                    # Calculate position size (scaled by confidence)
                    position_size = capital * self.position_size_pct * confidence
                    
                    # Record position
                    self.active_positions[symbol] = {
                        'direction': signal,
                        'entry_price': current_price,
                        'entry_time': data.index[-1],
                        'position_size': position_size,
                        'metadata': metadata
                    }
                    
                    # Record trade
                    trade = {
                        'symbol': symbol,
                        'action': 'entry',
                        'direction': signal,
                        'entry_price': current_price,
                        'entry_time': data.index[-1],
                        'position_size': position_size,
                        'confidence': confidence,
                        'key_level_proximity': metadata.get('closest_distance_pct', 1.0),
                        'is_liquidation': metadata.get('is_liquidation', False)
                    }
                    
                    executed_trades.append(trade)
                    
                    logger.info(f"Entered {symbol} {'long' if signal > 0 else 'short'} at {current_price:.2f}, "
                              f"size: {position_size:.2f}, confidence: {confidence:.2f}")
                
                elif signal != 0 and current_position != 0 and signal != current_position:
                    # Flip position
                    position = self.active_positions[symbol]
                    entry_price = position['entry_price']
                    entry_time = position['entry_time']
                    
                    # Calculate P&L for previous position
                    if current_position > 0:  # Long position
                        pnl_pct = (current_price / entry_price - 1) * 100
                    else:  # Short position
                        pnl_pct = (entry_price / current_price - 1) * 100
                    
                    # Calculate holding period
                    if entry_time in data.index:
                        holding_periods = len(data) - data.index.get_loc(entry_time)
                    else:
                        holding_periods = 0
                    
                    # Record exit trade
                    exit_trade = {
                        'symbol': symbol,
                        'action': 'exit_and_flip',
                        'direction': current_position,
                        'entry_price': entry_price,
                        'entry_time': entry_time,
                        'exit_price': current_price,
                        'exit_time': data.index[-1],
                        'pnl_pct': pnl_pct,
                        'holding_periods': holding_periods,
                        'exit_reason': 'signal_flip'
                    }
                    
                    executed_trades.append(exit_trade)
                    
                    # Calculate new position size
                    confidence = metadata.get('confidence', 0.5)
                    position_size = capital * self.position_size_pct * confidence
                    
                    # Record new position
                    self.active_positions[symbol] = {
                        'direction': signal,
                        'entry_price': current_price,
                        'entry_time': data.index[-1],
                        'position_size': position_size,
                        'metadata': metadata
                    }
                    
                    # Record entry trade
                    entry_trade = {
                        'symbol': symbol,
                        'action': 'entry_from_flip',
                        'direction': signal,
                        'entry_price': current_price,
                        'entry_time': data.index[-1],
                        'position_size': position_size,
                        'confidence': confidence,
                        'key_level_proximity': metadata.get('closest_distance_pct', 1.0),
                        'is_liquidation': metadata.get('is_liquidation', False)
                    }
                    
                    executed_trades.append(entry_trade)
                    
                    logger.info(f"Flipped {symbol} position from {current_position} to {signal} at {current_price:.2f}, "
                              f"P&L: {pnl_pct:.2f}%, holding periods: {holding_periods}")
            
            except Exception as e:
                logger.error(f"Error executing trades for {symbol}: {str(e)}", exc_info=True)
        
        return executed_trades
    
    def visualize_trades(self, symbol: str, data: pd.DataFrame, 
                       trades: List[Dict], save_dir: Optional[str] = None) -> plt.Figure:
        """
        Visualize trades with volume profile.
        
        Args:
            symbol: Trading symbol
            data: OHLCV DataFrame
            trades: List of executed trades
            save_dir: Directory to save visualization
            
        Returns:
            Matplotlib figure
        """
        # Create figure
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot price
        ax1.plot(data.index, data['close'], label='Close Price')
        
        # Create twin axes for volume
        ax3 = ax1.twinx()
        ax3.bar(data.index, data['volume'], alpha=0.3, color='gray', label='Volume')
        
        # Plot trades
        entry_times = []
        exit_times = []
        
        for trade in trades:
            if trade['symbol'] != symbol:
                continue
                
            if trade['action'] in ['entry', 'entry_from_flip']:
                marker = '^' if trade['direction'] > 0 else 'v'
                color = 'green' if trade['direction'] > 0 else 'red'
                
                ax1.scatter(trade['entry_time'], trade['entry_price'], marker=marker, 
                          color=color, s=100, label=f"Entry ({trade['direction']})")
                
                entry_times.append(trade['entry_time'])
            
            elif trade['action'] in ['exit', 'exit_and_flip']:
                marker = 'o'
                color = 'blue'
                
                ax1.scatter(trade['exit_time'], trade['exit_price'], marker=marker, 
                          color=color, s=100, label=f"Exit ({trade['pnl_pct']:.2f}%)")
                
                # Connect entry to exit with a line
                if 'entry_time' in trade and 'exit_time' in trade:
                    ax1.plot([trade['entry_time'], trade['exit_time']], 
                           [trade['entry_price'], trade['exit_price']], 
                           'k--', alpha=0.5)
                
                exit_times.append(trade['exit_time'])
        
        # Plot key levels if available
        if hasattr(self, 'volume_profile') and self.volume_profile.bins is not None:
            # Plot POC
            poc = self.volume_profile.get_poc_level()
            if poc:
                ax1.axhline(y=poc, color='purple', linestyle='-', 
                         label=f'POC: {poc:.2f}')
            
            # Plot Value Area
            if self.volume_profile.value_area:
                val, vah = self.volume_profile.value_area
                ax1.axhline(y=val, color='blue', linestyle='--', 
                         label=f'VAL: {val:.2f}')
                ax1.axhline(y=vah, color='blue', linestyle='--', 
                         label=f'VAH: {vah:.2f}')
                ax1.fill_between(data.index, val, vah, color='blue', alpha=0.1)
            
            # Plot peak levels
            if self.volume_profile.peak_levels is not None:
                for i, level in enumerate(self.volume_profile.peak_levels):
                    ax1.axhline(y=level, color='green', linestyle=':', alpha=0.5,
                             label=f'Peak {i+1}: {level:.2f}' if i < 3 else None)
        
        # Plot volume profile on the right side
        if hasattr(self, 'volume_profile') and self.volume_profile.bins is not None:
            # Get current axes position
            pos = ax1.get_position()
            
            # Create a new axes for volume profile on the right
            ax_vp = fig.add_axes([pos.x1, pos.y0, 0.1, pos.height])
            
            # Plot horizontal volume bars
            if self.volume_profile.bins is not None and self.volume_profile.volumes is not None:
                ax_vp.barh(self.volume_profile.bins, self.volume_profile.volumes, 
                          height=(self.volume_profile.bin_edges[1] - self.volume_profile.bin_edges[0]),
                          alpha=0.7, color='blue')
                
                ax_vp.set_ylim(ax1.get_ylim())
                ax_vp.set_xticks([])
                ax_vp.set_title('Volume Profile')
        
        # Plot liquidation indicators
        for i in range(len(data) - 5):
            window = data.iloc[i:i+5]
            is_liquidation = self.detect_liquidation(data.iloc[:i+5])
            
            if is_liquidation:
                ax1.axvspan(window.index[0], window.index[-1], color='red', alpha=0.2)
        
        # Set labels and title
        ax1.set_title(f'{symbol} - Volume Profile Strategy')
        ax1.set_ylabel('Price')
        ax3.set_ylabel('Volume')
        
        # Reduce legend duplicate entries
        handles, labels = ax1.get_legend_handles_labels()
        unique = [(h, l) for i, (h, l) in enumerate(zip(handles, labels)) 
                if l not in labels[:i]]
        ax1.legend(*zip(*unique), loc='upper left')
        
        # Plot P&L in second subplot
        pnl_data = []
        cumulative_pnl = 0
        
        for trade in trades:
            if trade['symbol'] != symbol or 'pnl_pct' not in trade:
                continue
            
            cumulative_pnl += trade['pnl_pct']
            pnl_data.append((trade['exit_time'], cumulative_pnl))
        
        if pnl_data:
            times, values = zip(*pnl_data)
            ax2.plot(times, values, 'b-', marker='o')
            ax2.set_ylabel('Cumulative P&L %')
            ax2.grid(True)
        
        plt.tight_layout()
        
        # Save figure if directory provided
        if save_dir:
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            
            save_path = os.path.join(save_dir, f"{symbol.replace('/', '_')}_vp_strategy.png")
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved visualization to {save_path}")
        
        return fig
    
    def analyze_performance(self, trades: List[Dict]) -> Dict:
        """
        Analyze strategy performance based on executed trades.
        
        Args:
            trades: List of executed trades
            
        Returns:
            Dictionary of performance metrics
        """
        if not trades:
            logger.warning("No trades available for performance analysis")
            return {}
        
        # Filter to only exit trades (with P&L)
        exit_trades = [t for t in trades if 'action' in t and 
                      t['action'] in ['exit', 'exit_and_flip'] and
                      'pnl_pct' in t]
        
        if not exit_trades:
            return {}
        
        # Calculate metrics
        pnl_values = [t['pnl_pct'] for t in exit_trades]
        win_trades = [t for t in exit_trades if t['pnl_pct'] > 0]
        loss_trades = [t for t in exit_trades if t['pnl_pct'] <= 0]
        
        total_trades = len(exit_trades)
        win_rate = len(win_trades) / total_trades if total_trades > 0 else 0
        
        avg_win = np.mean([t['pnl_pct'] for t in win_trades]) if win_trades else 0
        avg_loss = np.mean([t['pnl_pct'] for t in loss_trades]) if loss_trades else 0
        
        profit_factor = abs(sum(t['pnl_pct'] for t in win_trades) / 
                         sum(t['pnl_pct'] for t in loss_trades)) if loss_trades and sum(t['pnl_pct'] for t in loss_trades) != 0 else float('inf')
        
        avg_holding = np.mean([t.get('holding_periods', 0) for t in exit_trades])
        
        # Calculate metrics by trade type
        liquidation_trades = [t for t in exit_trades if t.get('is_liquidation', False)]
        key_level_trades = [t for t in exit_trades if t.get('key_level_proximity', 1.0) <= self.key_level_threshold_pct]
        
        liquidation_pnl = np.mean([t['pnl_pct'] for t in liquidation_trades]) if liquidation_trades else 0
        key_level_pnl = np.mean([t['pnl_pct'] for t in key_level_trades]) if key_level_trades else 0
        
        # Compile metrics
        metrics = {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_trade_pnl': np.mean(pnl_values),
            'total_pnl': sum(pnl_values),
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'avg_holding_periods': avg_holding,
            'liquidation_trades': len(liquidation_trades),
            'liquidation_pnl': liquidation_pnl,
            'key_level_trades': len(key_level_trades),
            'key_level_pnl': key_level_pnl,
            'best_trade': max(pnl_values) if pnl_values else 0,
            'worst_trade': min(pnl_values) if pnl_values else 0
        }
        
        logger.info(f"Performance metrics: Win rate: {win_rate:.2f}, "
                  f"Avg trade: {metrics['avg_trade_pnl']:.2f}%, "
                  f"Total PnL: {metrics['total_pnl']:.2f}%, "
                  f"Profit factor: {profit_factor:.2f}")
        
        return metrics