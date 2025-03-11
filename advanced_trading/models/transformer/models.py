"""
Transformer Models for Financial Time Series

This module implements specialized transformer models for financial time series forecasting
and classification tasks. Each model is optimized for different types of financial data and
prediction tasks.

Models:
- TimeSeriesTransformer: Vanilla transformer adapted for time series with causal masking
- TemporalFusionTransformer: Specialized model for multivariate time series with mixed variables
- Informer: Efficient transformer variant with reduced complexity for long sequences
- Autoformer: Self-attention based decomposition architecture for time series
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple, List, Dict, Any, Union

from advanced_trading.models.transformer.base import (
    TransformerConfig,
    TransformerBase,
    TransformerBlock,
    PositionalEncoding
)


class TimeSeriesTransformer(TransformerBase):
    """Transformer model adapted for time series forecasting.
    
    This model implements a vanilla transformer architecture with adaptations 
    specifically for financial time series, including:
    1. Causal masking to prevent lookahead bias
    2. Time-specific positional encoding
    3. Special handling of time features
    4. Flexible forecast generation
    
    Args:
        config (TransformerConfig): Model configuration
    """
    def __init__(self, config: TransformerConfig):
        super(TimeSeriesTransformer, self).__init__(config)
        
        # Input embedding layer
        self.input_embedding = nn.Linear(config.input_features, config.hidden_size)
        
        # Positional encoding
        if config.use_positional_encoding:
            self.positional_encoding = PositionalEncoding(
                config.hidden_size, 
                config.context_length + config.forecast_horizon,
                config.dropout,
                use_time_features=True
            )
        
        # Transformer layers
        self.layers = nn.ModuleList([
            TransformerBlock(
                config.hidden_size,
                config.attention_heads,
                ff_dim=config.hidden_size * 4,
                dropout=config.dropout,
                activation=config.activation
            )
            for _ in range(config.num_layers)
        ])
        
        # Output layer
        self.output_layer = nn.Linear(config.hidden_size, 1)  # Default to single-value prediction
        
        # Layer normalization
        self.norm = nn.LayerNorm(config.hidden_size)
        
        # Dropout
        self.dropout = nn.Dropout(config.dropout)
        
        # Initialize parameters
        self._init_parameters()
    
    def _init_parameters(self):
        """Initialize model parameters."""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)
    
    def _generate_square_subsequent_mask(self, sz: int) -> torch.Tensor:
        """Generate a causal mask for the sequence.
        
        Args:
            sz: Sequence length
            
        Returns:
            mask: Causal attention mask [sz, sz]
        """
        mask = (torch.triu(torch.ones(sz, sz)) == 1).transpose(0, 1)
        mask = mask.float().masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0))
        return mask
    
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None,
                time_features: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Forward pass.
        
        Args:
            x: Input tensor [seq_len, batch_size, input_features]
            mask: Optional attention mask [seq_len, seq_len]
            time_features: Optional temporal features [seq_len, batch_size, num_time_features]
            
        Returns:
            output: Model output [seq_len, batch_size, 1]
        """
        # Generate causal mask if not provided
        seq_len = x.size(0)
        if mask is None:
            mask = self._generate_square_subsequent_mask(seq_len).to(x.device)
        
        # Input embedding
        x = self.input_embedding(x)
        
        # Apply positional encoding if configured
        if self.config.use_positional_encoding:
            x = self.positional_encoding(x, time_features)
        else:
            x = self.dropout(x)
        
        # Apply transformer layers
        attentions = []
        for layer in self.layers:
            x, attention = layer(x, mask)
            attentions.append(attention)
        
        # Apply final normalization
        x = self.norm(x)
        
        # Output projection
        output = self.output_layer(x)
        
        return output
    
    def predict(self, x: Union[torch.Tensor, np.ndarray], 
                time_features: Optional[Union[torch.Tensor, np.ndarray]] = None) -> np.ndarray:
        """Generate predictions.
        
        Args:
            x: Input data [seq_len, batch_size, input_features] or [seq_len, input_features]
            time_features: Optional temporal features
            
        Returns:
            predictions: Model predictions [seq_len, batch_size, 1] or [seq_len, 1]
        """
        # Handle numpy input
        if isinstance(x, np.ndarray):
            # Add batch dimension if needed
            if x.ndim == 2:
                x = x[np.newaxis, :, :]
                x = np.transpose(x, (1, 0, 2))  # [seq_len, 1, features]
                single_batch = True
            else:
                x = np.transpose(x, (1, 0, 2))  # [seq_len, batch, features]
                single_batch = False
            
            x = torch.from_numpy(x).float()
            
            # Handle time features if provided
            if time_features is not None:
                if isinstance(time_features, np.ndarray):
                    if time_features.ndim == 2:
                        time_features = time_features[np.newaxis, :, :]
                        time_features = np.transpose(time_features, (1, 0, 2))
                    else:
                        time_features = np.transpose(time_features, (1, 0, 2))
                    
                    time_features = torch.from_numpy(time_features).float()
        
        # Set model to evaluation mode
        self.eval()
        
        # Generate predictions
        with torch.no_grad():
            predictions = self.forward(x, time_features=time_features)
            predictions = predictions.cpu().numpy()
        
        # Reshape output if needed
        if predictions.shape[1] == 1 and single_batch:
            predictions = predictions.squeeze(1)
        
        return predictions
    
    def get_attention_weights(self, x: torch.Tensor, 
                             time_features: Optional[torch.Tensor] = None) -> List[torch.Tensor]:
        """Extract attention weights for interpretability.
        
        Args:
            x: Input tensor [seq_len, batch_size, input_features]
            time_features: Optional temporal features
            
        Returns:
            attention_weights: List of attention weight tensors from each layer
        """
        # Set model to evaluation mode
        self.eval()
        
        # Generate causal mask
        seq_len = x.size(0)
        mask = self._generate_square_subsequent_mask(seq_len).to(x.device)
        
        # Input embedding
        x = self.input_embedding(x)
        
        # Apply positional encoding if configured
        if self.config.use_positional_encoding:
            x = self.positional_encoding(x, time_features)
        else:
            x = self.dropout(x)
        
        # Collect attention weights from each layer
        attention_weights = []
        for layer in self.layers:
            x, attention = layer(x, mask)
            attention_weights.append(attention)
        
        return attention_weights


class TemporalFusionTransformer(TransformerBase):
    """Temporal Fusion Transformer for multivariate time series forecasting.
    
    This model is specifically designed for multivariate time series with mixed variables
    (continuous and categorical). It leverages variable selection networks, gated residual
    networks, and temporal self-attention to model complex temporal patterns.
    
    Key features:
    1. Variable selection networks for input feature importance
    2. Separate processing for static, past, and future inputs
    3. Gated skip connections for temporal processing
    4. Interpretable attention weights for time steps and variables
    
    Args:
        config (TransformerConfig): Model configuration with additional attributes:
            - static_features (int): Number of static features (default: 0)
            - known_future_features (int): Number of known future features (default: 0)
            - categorical_features (List[int]): List of categorical feature indices (default: [])
            - embedding_dims (List[int]): Embedding dimensions for categorical features (default: [])
    """
    def __init__(self, config: TransformerConfig):
        super(TemporalFusionTransformer, self).__init__(config)
        
        # Extract additional configuration
        self.static_features = getattr(config, 'static_features', 0)
        self.known_future_features = getattr(config, 'known_future_features', 0)
        self.categorical_features = getattr(config, 'categorical_features', [])
        self.embedding_dims = getattr(config, 'embedding_dims', [])
        
        # Calculate feature dimensions
        self.num_features = config.input_features
        self.observed_features = self.num_features - self.static_features - self.known_future_features
        
        # Processing layers
        self._build_layers()
        
        # Initialize parameters
        self._init_parameters()
    
    def _build_layers(self):
        """Build the model layers."""
        # Static feature processing
        if self.static_features > 0:
            self.static_encoder = self._build_variable_selection_network(
                self.static_features, 
                self.config.hidden_size, 
                name="static"
            )
            self.static_enrichment = self._build_gated_residual_network(
                self.config.hidden_size, 
                self.config.hidden_size,
                name="static_enrichment"
            )
        
        # Input embeddings for observed and known features
        self.input_embeddings = nn.ModuleDict({
            "observed": self._build_variable_selection_network(
                self.observed_features,
                self.config.hidden_size,
                name="observed"
            ),
            "known": self._build_variable_selection_network(
                self.known_future_features,
                self.config.hidden_size,
                name="known"
            ) if self.known_future_features > 0 else None
        })
        
        # Positional encoding
        if self.config.use_positional_encoding:
            self.positional_encoding = PositionalEncoding(
                self.config.hidden_size,
                self.config.context_length + self.config.forecast_horizon,
                self.config.dropout,
                use_time_features=True
            )
        
        # LSTM layers for temporal processing
        self.lstm_encoder = nn.LSTM(
            self.config.hidden_size,
            self.config.hidden_size,
            batch_first=False,
            dropout=self.config.dropout if self.config.num_layers > 1 else 0
        )
        
        self.lstm_decoder = nn.LSTM(
            self.config.hidden_size,
            self.config.hidden_size,
            batch_first=False,
            dropout=self.config.dropout if self.config.num_layers > 1 else 0
        )
        
        # Attention layer for temporal fusion
        self.attention = nn.MultiheadAttention(
            self.config.hidden_size,
            self.config.attention_heads,
            dropout=self.config.dropout
        )
        
        # Gated skip connection for temporal processing
        self.post_attention_gate = self._build_gated_residual_network(
            self.config.hidden_size,
            self.config.hidden_size,
            name="post_attention"
        )
        
        self.pos_wise_ff = self._build_gated_residual_network(
            self.config.hidden_size,
            self.config.hidden_size,
            name="pos_wise_ff"
        )
        
        # Output layers
        self.pre_output_gate = self._build_gated_residual_network(
            self.config.hidden_size,
            self.config.hidden_size,
            name="pre_output"
        )
        
        self.output_layer = nn.Linear(self.config.hidden_size, 1)
    
    def _build_variable_selection_network(self, num_inputs: int, hidden_size: int, name: str) -> nn.Module:
        """Build a variable selection network.
        
        This network learns to attend to the most important variables for the task.
        
        Args:
            num_inputs: Number of input variables
            hidden_size: Hidden dimension size
            name: Module name for reference
            
        Returns:
            variable_selection_network: The VSN module
        """
        if num_inputs == 0:
            return None
            
        return nn.ModuleDict({
            "selection": nn.Sequential(
                nn.Linear(num_inputs, num_inputs),
                nn.LayerNorm(num_inputs),
                nn.ReLU(),
                nn.Linear(num_inputs, num_inputs),
                nn.Softmax(dim=-1)
            ),
            "processing": nn.ModuleList([
                nn.Sequential(
                    nn.Linear(1, hidden_size),
                    nn.LayerNorm(hidden_size),
                    nn.ReLU()
                )
                for _ in range(num_inputs)
            ])
        })
    
    def _build_gated_residual_network(self, input_size: int, hidden_size: int, 
                                     output_size: Optional[int] = None, name: str = "") -> nn.Module:
        """Build a gated residual network.
        
        This is a network with a gating layer and residual connection.
        
        Args:
            input_size: Input dimension
            hidden_size: Hidden dimension
            output_size: Output dimension (default: same as input_size)
            name: Module name for reference
            
        Returns:
            gated_residual_network: The GRN module
        """
        if output_size is None:
            output_size = input_size
            
        return nn.ModuleDict({
            "network": nn.Sequential(
                nn.Linear(input_size, hidden_size),
                nn.ELU(),
                nn.Linear(hidden_size, output_size)
            ),
            "gate": nn.Sequential(
                nn.Linear(input_size, output_size),
                nn.Sigmoid()
            ),
            "norm": nn.LayerNorm(output_size)
        })
    
    def _apply_gated_residual_network(self, module: nn.ModuleDict, x: torch.Tensor, 
                                     skip: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Apply a gated residual network to the input.
        
        Args:
            module: GRN module
            x: Input tensor
            skip: Optional skip connection tensor
            
        Returns:
            output: Processed tensor
        """
        network_output = module["network"](x)
        
        if skip is not None:
            network_output += skip
            
        gate = module["gate"](x)
        output = gate * network_output + (1 - gate) * x
        output = module["norm"](output)
        
        return output
    
    def _apply_variable_selection_network(self, module: nn.ModuleDict, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Apply a variable selection network to the input.
        
        Args:
            module: VSN module
            x: Input tensor [seq_len, batch_size, num_inputs]
            
        Returns:
            output: Selected and processed tensor [seq_len, batch_size, hidden_size]
            weights: Selection weights [seq_len, batch_size, num_inputs]
        """
        if module is None:
            return None, None
            
        # Calculate selection weights
        weights = module["selection"](x)  # [seq_len, batch_size, num_inputs]
        
        # Process each variable
        transformed_x = []
        num_inputs = x.size(-1)
        
        for i in range(num_inputs):
            # Extract the i-th variable and process it
            var = x[:, :, i:i+1]  # [seq_len, batch_size, 1]
            processed_var = module["processing"][i](var)  # [seq_len, batch_size, hidden_size]
            transformed_x.append(processed_var)
        
        # Stack processed variables
        transformed_x = torch.stack(transformed_x, dim=-2)  # [seq_len, batch_size, num_inputs, hidden_size]
        
        # Apply selection weights
        weights_expanded = weights.unsqueeze(-1)  # [seq_len, batch_size, num_inputs, 1]
        output = torch.sum(transformed_x * weights_expanded, dim=-2)  # [seq_len, batch_size, hidden_size]
        
        return output, weights
    
    def _init_parameters(self):
        """Initialize model parameters."""
        for name, p in self.named_parameters():
            if "bias" not in name and p.dim() > 1:
                nn.init.xavier_uniform_(p)
    
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None,
                time_features: Optional[torch.Tensor] = None) -> Dict[str, torch.Tensor]:
        """Forward pass for the Temporal Fusion Transformer.
        
        Args:
            x: Input tensor [seq_len, batch_size, input_features]
               - First static_features are static (same for all time steps)
               - Next observed_features are past observed
               - Last known_future_features are known future inputs
            mask: Optional attention mask [seq_len, seq_len]
            time_features: Optional temporal features [seq_len, batch_size, num_time_features]
            
        Returns:
            Dict containing:
                - predictions: Model output [forecast_horizon, batch_size, 1]
                - attention_weights: Attention weights for interpretability
                - static_weights: Static variable selection weights
                - observed_weights: Observed variable selection weights
                - known_weights: Known future variable selection weights
        """
        seq_len, batch_size, _ = x.size()
        context_length = self.config.context_length
        forecast_horizon = self.config.forecast_horizon
        
        # Split the input into static, past, and future components
        static_x = x[0, :, :self.static_features] if self.static_features > 0 else None
        observed_x = x[:context_length, :, self.static_features:self.static_features+self.observed_features]
        known_x = x[:, :, -self.known_future_features:] if self.known_future_features > 0 else None
        
        # Process static features
        static_embedding = None
        static_weights = None
        if static_x is not None:
            # Expand static for all time steps
            static_x = static_x.unsqueeze(0).expand(seq_len, -1, -1)
            static_embedding, static_weights = self._apply_variable_selection_network(
                self.static_encoder, static_x
            )
            static_embedding = static_embedding[0]  # Take the first time step as it's the same for all
        
        # Process observed and known features
        observed_embedding, observed_weights = self._apply_variable_selection_network(
            self.input_embeddings["observed"], observed_x
        )
        
        known_embedding = None
        known_weights = None
        if known_x is not None:
            known_embedding, known_weights = self._apply_variable_selection_network(
                self.input_embeddings["known"], known_x
            )
        
        # Combine embeddings
        input_embedding = observed_embedding
        if known_embedding is not None:
            # Replace with known future for forecast horizon
            input_embedding = torch.cat(
                [observed_embedding, known_embedding[context_length:]], dim=0
            )
        
        # Apply positional encoding if configured
        if self.config.use_positional_encoding:
            input_embedding = self.positional_encoding(input_embedding, time_features)
        
        # Process with encoder-decoder LSTM
        encoder_output, (h_n, c_n) = self.lstm_encoder(input_embedding[:context_length])
        decoder_output, _ = self.lstm_decoder(input_embedding[context_length:], (h_n, c_n))
        
        # Combine encoder and decoder outputs
        lstm_output = torch.cat([encoder_output, decoder_output], dim=0)
        
        # Apply static enrichment if available
        if static_embedding is not None:
            static_enrichment = self._apply_gated_residual_network(
                self.static_enrichment,
                static_embedding.unsqueeze(0).expand(seq_len, batch_size, -1)
            )
            lstm_output = lstm_output + static_enrichment
        
        # Apply temporal self-attention
        if mask is None:
            mask = torch.ones(seq_len, seq_len).to(x.device)
            # Mask future in encoder
            mask[:context_length, context_length:] = 0
            # Allow full attention in decoder
            mask = mask.bool()
        
        attn_output, attention_weights = self.attention(
            lstm_output, lstm_output, lstm_output,
            attn_mask=mask
        )
        
        # Post-attention processing
        output = self._apply_gated_residual_network(
            self.post_attention_gate,
            attn_output,
            lstm_output
        )
        
        # Position-wise feed-forward
        output = self._apply_gated_residual_network(
            self.pos_wise_ff,
            output
        )
        
        # Final processing for output
        output = self._apply_gated_residual_network(
            self.pre_output_gate,
            output
        )
        
        # Generate predictions (only for forecast horizon)
        predictions = self.output_layer(output[context_length:])
        
        return {
            "predictions": predictions,
            "attention_weights": attention_weights,
            "static_weights": static_weights,
            "observed_weights": observed_weights,
            "known_weights": known_weights
        }
    
    def predict(self, x: Union[torch.Tensor, np.ndarray], 
                time_features: Optional[Union[torch.Tensor, np.ndarray]] = None) -> np.ndarray:
        """Generate predictions.
        
        Args:
            x: Input data [seq_len, batch_size, input_features] or [seq_len, input_features]
            time_features: Optional temporal features
            
        Returns:
            predictions: Model predictions [forecast_horizon, batch_size, 1] or [forecast_horizon, 1]
        """
        # Handle numpy input
        single_batch = False
        if isinstance(x, np.ndarray):
            # Add batch dimension if needed
            if x.ndim == 2:
                x = x[np.newaxis, :, :]
                x = np.transpose(x, (1, 0, 2))  # [seq_len, 1, features]
                single_batch = True
            else:
                x = np.transpose(x, (1, 0, 2))  # [seq_len, batch, features]
            
            x = torch.from_numpy(x).float()
            
            # Handle time features if provided
            if time_features is not None:
                if isinstance(time_features, np.ndarray):
                    if time_features.ndim == 2:
                        time_features = time_features[np.newaxis, :, :]
                        time_features = np.transpose(time_features, (1, 0, 2))
                    else:
                        time_features = np.transpose(time_features, (1, 0, 2))
                    
                    time_features = torch.from_numpy(time_features).float()
        
        # Set model to evaluation mode
        self.eval()
        
        # Generate predictions
        with torch.no_grad():
            output = self.forward(x, time_features=time_features)
            predictions = output["predictions"].cpu().numpy()
        
        # Reshape output if needed
        if predictions.shape[1] == 1 and single_batch:
            predictions = predictions.squeeze(1)
        
        return predictions
    
    def get_attention_weights(self, x: torch.Tensor, 
                             time_features: Optional[torch.Tensor] = None) -> Dict[str, torch.Tensor]:
        """Extract attention weights and variable selection weights for interpretability.
        
        Args:
            x: Input tensor [seq_len, batch_size, input_features]
            time_features: Optional temporal features
            
        Returns:
            Dict containing attention weights and variable selection weights
        """
        # Set model to evaluation mode
        self.eval()
        
        # Forward pass to get all weights
        with torch.no_grad():
            output = self.forward(x, time_features=time_features)
        
        return {
            "attention_weights": output["attention_weights"],
            "static_weights": output["static_weights"],
            "observed_weights": output["observed_weights"],
            "known_weights": output["known_weights"]
        } 