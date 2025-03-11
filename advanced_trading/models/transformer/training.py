"""
Training Utilities for Transformer Models

This module provides utilities for training transformer models for financial time series,
including dataset preparation, batch generation, training loops, and evaluation metrics.

Key components:
- TransformerDataset: Dataset class for time series data with sliding windows
- TimeSeriesBatch: Container for batched time series data
- TransformerTrainer: Trainer class with training loop and early stopping
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
from typing import Optional, Tuple, List, Dict, Any, Union, Callable
import time
import logging
from tqdm.auto import tqdm
import matplotlib.pyplot as plt
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from advanced_trading.models.transformer.base import TransformerBase, TransformerConfig


class TransformerDataset(Dataset):
    """Dataset for transformer time series models with sliding windows.
    
    This dataset handles the creation of sliding windows for sequence-to-sequence
    or sequence-to-value prediction tasks. It supports different windowing strategies
    and can handle multivariate time series with optional time features.
    
    Args:
        data (np.ndarray): Time series data of shape [sequence_length, features]
        context_length (int): Length of historical context window
        forecast_horizon (int): Number of future steps to predict
        target_idx (int or List[int]): Index or indices of target variable(s)
        stride (int): Stride for sliding window (default: 1)
        time_features (np.ndarray, optional): Temporal features (e.g., hour, day, month)
        static_features (np.ndarray, optional): Static features that are constant for the sequence
        transform (callable, optional): Optional transform to apply to each sample
    """
    def __init__(
        self,
        data: np.ndarray,
        context_length: int,
        forecast_horizon: int,
        target_idx: Union[int, List[int]],
        stride: int = 1,
        time_features: Optional[np.ndarray] = None,
        static_features: Optional[np.ndarray] = None,
        transform: Optional[Callable] = None
    ):
        self.data = data
        self.context_length = context_length
        self.forecast_horizon = forecast_horizon
        self.window_size = context_length + forecast_horizon
        self.stride = stride
        self.time_features = time_features
        self.static_features = static_features
        self.transform = transform
        
        # Handle target index/indices
        if isinstance(target_idx, int):
            self.target_idx = [target_idx]
        else:
            self.target_idx = target_idx
            
        # Calculate number of windows
        self.num_windows = max(0, (len(data) - self.window_size) // stride + 1)
        
        if self.num_windows == 0:
            raise ValueError(
                f"Data length ({len(data)}) is too short for the requested "
                f"context_length ({context_length}) + forecast_horizon ({forecast_horizon})"
            )
    
    def __len__(self) -> int:
        """Get the number of samples in the dataset."""
        return self.num_windows
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """Get a sample from the dataset.
        
        Args:
            idx: Index of the sample
            
        Returns:
            Dict containing:
                - 'past_data': Historical context window [context_length, features]
                - 'future_data': Future window for target variables [forecast_horizon, num_targets]
                - 'time_features': Temporal features if provided [window_size, num_time_features]
                - 'static_features': Static features if provided [num_static_features]
        """
        start_idx = idx * self.stride
        end_idx = start_idx + self.window_size
        
        # Get data window
        window_data = self.data[start_idx:end_idx].copy()
        
        # Split into past and future
        past_data = window_data[:self.context_length]
        future_data = window_data[self.context_length:, self.target_idx]
        
        # Get time features if available
        time_features = None
        if self.time_features is not None:
            time_features = self.time_features[start_idx:end_idx].copy()
            time_features = torch.tensor(time_features, dtype=torch.float32)
        
        # Get static features if available
        static_data = None
        if self.static_features is not None:
            static_data = self.static_features.copy()
            static_data = torch.tensor(static_data, dtype=torch.float32)
        
        # Apply transform if provided
        if self.transform is not None:
            past_data, future_data = self.transform(past_data, future_data)
        
        # Convert to tensors
        past_data = torch.tensor(past_data, dtype=torch.float32)
        future_data = torch.tensor(future_data, dtype=torch.float32)
        
        return {
            'past_data': past_data,
            'future_data': future_data,
            'time_features': time_features,
            'static_features': static_data
        }


class TimeSeriesBatch:
    """Container for batched time series data.
    
    This class handles the conversion of batched time series data between different formats
    (e.g., sequence-first vs. batch-first) and provides easy access to different components
    of the batch.
    
    Args:
        batch (Dict[str, torch.Tensor]): Batch dictionary from DataLoader
        device (torch.device, optional): Device to move tensors to
    """
    def __init__(self, batch: Dict[str, torch.Tensor], device: Optional[torch.device] = None):
        self.device = device if device is not None else torch.device('cpu')
        
        # Extract and move data to device
        self.past_data = batch['past_data'].to(self.device)  # [batch_size, context_length, features]
        self.future_data = batch['future_data'].to(self.device)  # [batch_size, forecast_horizon, num_targets]
        
        # Optional data
        self.time_features = batch.get('time_features')
        if self.time_features is not None:
            self.time_features = self.time_features.to(self.device)
            
        self.static_features = batch.get('static_features')
        if self.static_features is not None:
            self.static_features = self.static_features.to(self.device)
        
        # Store dimensions
        self.batch_size = self.past_data.size(0)
        self.context_length = self.past_data.size(1)
        self.forecast_horizon = self.future_data.size(1)
        self.num_features = self.past_data.size(2)
        self.num_targets = self.future_data.size(2)
    
    def to_sequence_first(self) -> Tuple[torch.Tensor, torch.Tensor, Optional[torch.Tensor]]:
        """Convert batch data to sequence-first format for transformer input.
        
        Returns:
            past_data: Past data with shape [context_length, batch_size, features]
            future_data: Future data with shape [forecast_horizon, batch_size, num_targets]
            time_features: Optional time features with shape [window_size, batch_size, num_time_features]
        """
        # Transpose dimensions: [batch_size, seq_len, features] -> [seq_len, batch_size, features]
        past_data = self.past_data.transpose(0, 1)
        future_data = self.future_data.transpose(0, 1)
        
        time_features = None
        if self.time_features is not None:
            time_features = self.time_features.transpose(0, 1)
            
        return past_data, future_data, time_features
    
    def get_full_sequence(self) -> torch.Tensor:
        """Get the full sequence (past + future) for model input.
        
        This is useful for models that need the full sequence during training.
        
        Returns:
            full_sequence: Full sequence with shape [context_length + forecast_horizon, batch_size, features]
        """
        # For future time steps, we only have target variables, so we need to pad the other features
        if self.num_targets < self.num_features:
            # Create zero tensor for missing features in future time steps
            future_padding = torch.zeros(
                (self.batch_size, self.forecast_horizon, self.num_features - self.num_targets),
                device=self.device
            )
            # Combine target variables with padding
            future_data_padded = torch.cat([self.future_data, future_padding], dim=2)
        else:
            future_data_padded = self.future_data
            
        # Concatenate past and future
        full_sequence = torch.cat([self.past_data, future_data_padded], dim=1)
        
        # Convert to sequence-first
        return full_sequence.transpose(0, 1)


class TransformerTrainer:
    """Trainer for transformer time series models.
    
    This class handles the training of transformer models, including:
    - Training loop with early stopping
    - Learning rate scheduling
    - Gradient clipping
    - Validation metrics
    - Model checkpointing
    
    Args:
        model (TransformerBase): Transformer model to train
        optimizer (torch.optim.Optimizer, optional): Optimizer
        criterion (callable, optional): Loss function
        learning_rate (float, optional): Learning rate if optimizer not provided
        weight_decay (float, optional): Weight decay if optimizer not provided
        device (torch.device, optional): Device to use for training
        clip_gradient (float, optional): Gradient clipping threshold
        checkpoint_path (str, optional): Path to save model checkpoints
        patience (int, optional): Patience for early stopping
        scheduler_patience (int, optional): Patience for learning rate scheduler
        scheduler_factor (float, optional): Factor for learning rate scheduler
    """
    def __init__(
        self,
        model: TransformerBase,
        optimizer: Optional[torch.optim.Optimizer] = None,
        criterion: Optional[Callable] = None,
        learning_rate: float = 1e-4,
        weight_decay: float = 1e-6,
        device: Optional[torch.device] = None,
        clip_gradient: Optional[float] = 1.0,
        checkpoint_path: Optional[str] = None,
        patience: int = 10,
        scheduler_patience: int = 5,
        scheduler_factor: float = 0.5
    ):
        self.model = model
        self.device = device if device is not None else torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        
        # Set up optimizer
        if optimizer is None:
            self.optimizer = torch.optim.Adam(
                self.model.parameters(),
                lr=learning_rate,
                weight_decay=weight_decay
            )
        else:
            self.optimizer = optimizer
            
        # Set up criterion
        if criterion is None:
            self.criterion = nn.MSELoss()
        else:
            self.criterion = criterion
            
        # Set up scheduler
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=scheduler_factor,
            patience=scheduler_patience,
            verbose=True
        )
        
        # Training settings
        self.clip_gradient = clip_gradient
        self.checkpoint_path = checkpoint_path
        self.patience = patience
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # Training history
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'learning_rate': []
        }
    
    def train_epoch(self, train_loader: DataLoader) -> float:
        """Train for one epoch.
        
        Args:
            train_loader: DataLoader for training data
            
        Returns:
            avg_loss: Average loss for the epoch
        """
        self.model.train()
        total_loss = 0
        num_batches = len(train_loader)
        
        # Use tqdm for progress bar
        with tqdm(train_loader, desc="Training", leave=False) as pbar:
            for batch_data in pbar:
                # Create batch object
                batch = TimeSeriesBatch(batch_data, self.device)
                
                # Prepare data
                past_data, future_targets, time_features = batch.to_sequence_first()
                
                # Clear gradients
                self.optimizer.zero_grad()
                
                # Forward pass
                if isinstance(self.model.forward(past_data, time_features=time_features), dict):
                    # Model returns a dictionary (e.g., TemporalFusionTransformer)
                    output = self.model.forward(past_data, time_features=time_features)["predictions"]
                else:
                    # Model returns a tensor
                    output = self.model.forward(past_data, time_features=time_features)[-self.model.config.forecast_horizon:]
                
                # Calculate loss
                loss = self.criterion(output, future_targets)
                
                # Backward pass
                loss.backward()
                
                # Gradient clipping
                if self.clip_gradient is not None:
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.clip_gradient)
                
                # Update weights
                self.optimizer.step()
                
                # Update metrics
                batch_loss = loss.item()
                total_loss += batch_loss
                
                # Update progress bar
                pbar.set_postfix({"batch_loss": f"{batch_loss:.4f}"})
        
        # Calculate average loss
        avg_loss = total_loss / num_batches
        
        return avg_loss
    
    def validate(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate the model.
        
        Args:
            val_loader: DataLoader for validation data
            
        Returns:
            metrics: Dictionary of validation metrics
        """
        self.model.eval()
        total_loss = 0
        num_batches = len(val_loader)
        
        all_targets = []
        all_predictions = []
        
        with torch.no_grad():
            for batch_data in val_loader:
                # Create batch object
                batch = TimeSeriesBatch(batch_data, self.device)
                
                # Prepare data
                past_data, future_targets, time_features = batch.to_sequence_first()
                
                # Forward pass
                if isinstance(self.model.forward(past_data, time_features=time_features), dict):
                    # Model returns a dictionary (e.g., TemporalFusionTransformer)
                    output = self.model.forward(past_data, time_features=time_features)["predictions"]
                else:
                    # Model returns a tensor
                    output = self.model.forward(past_data, time_features=time_features)[-self.model.config.forecast_horizon:]
                
                # Calculate loss
                loss = self.criterion(output, future_targets)
                
                # Update metrics
                total_loss += loss.item()
                
                # Store predictions and targets for additional metrics
                all_predictions.append(output.cpu().numpy())
                all_targets.append(future_targets.cpu().numpy())
        
        # Calculate average loss
        avg_loss = total_loss / num_batches
        
        # Calculate additional metrics
        all_predictions = np.concatenate(all_predictions, axis=1)  # [forecast_horizon, total_samples, num_targets]
        all_targets = np.concatenate(all_targets, axis=1)  # [forecast_horizon, total_samples, num_targets]
        
        # Flatten time dimension for metrics
        flat_preds = all_predictions.reshape(-1, all_predictions.shape[-1])
        flat_targets = all_targets.reshape(-1, all_targets.shape[-1])
        
        # Calculate metrics
        metrics = {
            'val_loss': avg_loss,
            'mae': mean_absolute_error(flat_targets, flat_preds),
            'rmse': np.sqrt(mean_squared_error(flat_targets, flat_preds)),
            'r2': r2_score(flat_targets, flat_preds)
        }
        
        return metrics
    
    def fit(
        self,
        train_loader: DataLoader,
        val_loader: Optional[DataLoader] = None,
        epochs: int = 100,
        verbose: bool = True,
        callbacks: Optional[List[Callable]] = None
    ) -> Dict[str, List[float]]:
        """Train the model.
        
        Args:
            train_loader: DataLoader for training data
            val_loader: Optional DataLoader for validation data
            epochs: Number of epochs to train
            verbose: Whether to print progress
            callbacks: Optional list of callback functions
            
        Returns:
            history: Training history
        """
        # Initialize variables
        best_val_loss = float('inf')
        early_stop_counter = 0
        
        # Training loop
        for epoch in range(epochs):
            epoch_start_time = time.time()
            
            # Train for one epoch
            train_loss = self.train_epoch(train_loader)
            
            # Update history
            self.history['train_loss'].append(train_loss)
            self.history['learning_rate'].append(self.optimizer.param_groups[0]['lr'])
            
            # Validate if validation data is provided
            if val_loader is not None:
                val_metrics = self.validate(val_loader)
                val_loss = val_metrics['val_loss']
                self.history['val_loss'].append(val_loss)
                
                # Update learning rate scheduler
                self.scheduler.step(val_loss)
                
                # Check for early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    early_stop_counter = 0
                    
                    # Save checkpoint if path is provided
                    if self.checkpoint_path is not None:
                        self.model.save(self.checkpoint_path)
                else:
                    early_stop_counter += 1
            else:
                val_metrics = {}
                val_loss = None
            
            # Print epoch summary
            if verbose:
                epoch_time = time.time() - epoch_start_time
                metrics_str = f"Epoch {epoch+1}/{epochs} - {epoch_time:.2f}s - train_loss: {train_loss:.4f}"
                
                if val_loss is not None:
                    metrics_str += f" - val_loss: {val_loss:.4f}"
                    for metric_name, metric_value in val_metrics.items():
                        if metric_name != 'val_loss':
                            metrics_str += f" - {metric_name}: {metric_value:.4f}"
                
                print(metrics_str)
            
            # Execute callbacks
            if callbacks is not None:
                for callback in callbacks:
                    callback(self, epoch, self.history)
            
            # Check for early stopping
            if early_stop_counter >= self.patience:
                if verbose:
                    print(f"Early stopping triggered after {epoch+1} epochs")
                break
        
        # Load best model if checkpoint path is provided
        if self.checkpoint_path is not None and val_loader is not None:
            self.model = self.model.__class__.load(self.checkpoint_path, self.device)
        
        return self.history
    
    def predict(self, data_loader: DataLoader) -> np.ndarray:
        """Generate predictions for a dataset.
        
        Args:
            data_loader: DataLoader for prediction data
            
        Returns:
            predictions: Model predictions
        """
        self.model.eval()
        all_predictions = []
        
        with torch.no_grad():
            for batch_data in data_loader:
                # Create batch object
                batch = TimeSeriesBatch(batch_data, self.device)
                
                # Prepare data
                past_data, _, time_features = batch.to_sequence_first()
                
                # Forward pass
                if isinstance(self.model.forward(past_data, time_features=time_features), dict):
                    # Model returns a dictionary (e.g., TemporalFusionTransformer)
                    output = self.model.forward(past_data, time_features=time_features)["predictions"]
                else:
                    # Model returns a tensor
                    output = self.model.forward(past_data, time_features=time_features)[-self.model.config.forecast_horizon:]
                
                # Store predictions
                all_predictions.append(output.cpu().numpy())
        
        # Concatenate predictions
        predictions = np.concatenate(all_predictions, axis=1)  # [forecast_horizon, total_samples, num_targets]
        
        return predictions
    
    def evaluate(self, data_loader: DataLoader) -> Dict[str, float]:
        """Evaluate the model on a dataset.
        
        Args:
            data_loader: DataLoader for evaluation data
            
        Returns:
            metrics: Dictionary of evaluation metrics
        """
        self.model.eval()
        total_loss = 0
        num_batches = len(data_loader)
        
        all_targets = []
        all_predictions = []
        
        with torch.no_grad():
            for batch_data in data_loader:
                # Create batch object
                batch = TimeSeriesBatch(batch_data, self.device)
                
                # Prepare data
                past_data, future_targets, time_features = batch.to_sequence_first()
                
                # Forward pass
                if isinstance(self.model.forward(past_data, time_features=time_features), dict):
                    # Model returns a dictionary (e.g., TemporalFusionTransformer)
                    output = self.model.forward(past_data, time_features=time_features)["predictions"]
                else:
                    # Model returns a tensor
                    output = self.model.forward(past_data, time_features=time_features)[-self.model.config.forecast_horizon:]
                
                # Calculate loss
                loss = self.criterion(output, future_targets)
                
                # Update metrics
                total_loss += loss.item()
                
                # Store predictions and targets for additional metrics
                all_predictions.append(output.cpu().numpy())
                all_targets.append(future_targets.cpu().numpy())
        
        # Calculate average loss
        avg_loss = total_loss / num_batches
        
        # Calculate additional metrics
        all_predictions = np.concatenate(all_predictions, axis=1)  # [forecast_horizon, total_samples, num_targets]
        all_targets = np.concatenate(all_targets, axis=1)  # [forecast_horizon, total_samples, num_targets]
        
        # Calculate horizon-wise metrics
        horizon_metrics = {}
        for h in range(self.model.config.forecast_horizon):
            preds_h = all_predictions[h]  # [total_samples, num_targets]
            targets_h = all_targets[h]  # [total_samples, num_targets]
            
            horizon_metrics[f'horizon_{h+1}_mae'] = mean_absolute_error(targets_h, preds_h)
            horizon_metrics[f'horizon_{h+1}_rmse'] = np.sqrt(mean_squared_error(targets_h, preds_h))
            
            # Only calculate R² if there's variance in the targets
            target_var = np.var(targets_h)
            if target_var > 0:
                horizon_metrics[f'horizon_{h+1}_r2'] = r2_score(targets_h, preds_h)
            else:
                horizon_metrics[f'horizon_{h+1}_r2'] = np.nan
        
        # Flatten time dimension for overall metrics
        flat_preds = all_predictions.reshape(-1, all_predictions.shape[-1])
        flat_targets = all_targets.reshape(-1, all_targets.shape[-1])
        
        # Calculate overall metrics
        metrics = {
            'loss': avg_loss,
            'mae': mean_absolute_error(flat_targets, flat_preds),
            'rmse': np.sqrt(mean_squared_error(flat_targets, flat_preds)),
            'r2': r2_score(flat_targets, flat_preds)
        }
        
        # Combine metrics
        metrics.update(horizon_metrics)
        
        return metrics
    
    def plot_history(self, figsize: Tuple[int, int] = (10, 6)) -> None:
        """Plot training history.
        
        Args:
            figsize: Figure size
        """
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        # Plot loss
        axes[0].plot(self.history['train_loss'], label='Train Loss')
        if 'val_loss' in self.history and self.history['val_loss']:
            axes[0].plot(self.history['val_loss'], label='Validation Loss')
        axes[0].set_xlabel('Epoch')
        axes[0].set_ylabel('Loss')
        axes[0].set_title('Training and Validation Loss')
        axes[0].legend()
        axes[0].grid(True)
        
        # Plot learning rate
        axes[1].plot(self.history['learning_rate'])
        axes[1].set_xlabel('Epoch')
        axes[1].set_ylabel('Learning Rate')
        axes[1].set_title('Learning Rate')
        axes[1].grid(True)
        
        plt.tight_layout()
        plt.show()
    
    def plot_predictions(
        self,
        data_loader: DataLoader,
        num_samples: int = 5,
        sample_indices: Optional[List[int]] = None,
        figsize: Tuple[int, int] = (15, 10)
    ) -> None:
        """Plot model predictions against actual values.
        
        Args:
            data_loader: DataLoader for prediction data
            num_samples: Number of samples to plot
            sample_indices: Optional list of specific sample indices to plot
            figsize: Figure size
        """
        predictions = self.predict(data_loader)
        
        # Get targets
        all_targets = []
        for batch_data in data_loader:
            batch = TimeSeriesBatch(batch_data, torch.device('cpu'))
            _, future_targets, _ = batch.to_sequence_first()
            all_targets.append(future_targets.cpu().numpy())
        
        all_targets = np.concatenate(all_targets, axis=1)  # [forecast_horizon, total_samples, num_targets]
        
        # Determine samples to plot
        total_samples = all_targets.shape[1]
        num_targets = all_targets.shape[2]
        
        if sample_indices is None:
            if num_samples > total_samples:
                num_samples = total_samples
                
            sample_indices = np.random.choice(total_samples, num_samples, replace=False)
        else:
            num_samples = len(sample_indices)
        
        # Create figure
        fig, axes = plt.subplots(num_samples, num_targets, figsize=figsize, squeeze=False)
        
        # Plot each sample
        for i, sample_idx in enumerate(sample_indices):
            for j in range(num_targets):
                ax = axes[i, j]
                
                # Get target and prediction for this sample
                target = all_targets[:, sample_idx, j]
                pred = predictions[:, sample_idx, j]
                
                # Plot
                ax.plot(target, label='Actual', marker='o')
                ax.plot(pred, label='Prediction', marker='x')
                
                # Add labels and title
                ax.set_xlabel('Forecast Horizon')
                ax.set_ylabel('Value')
                ax.set_title(f'Sample {sample_idx}, Target {j}')
                ax.legend()
                ax.grid(True)
        
        plt.tight_layout()
        plt.show() 