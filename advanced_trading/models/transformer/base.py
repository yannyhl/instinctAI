"""
Base Transformer Components

This module implements the core components of transformer architectures adapted for financial time series.
It provides the building blocks for constructing specialized transformer models for time series forecasting
and classification tasks.

Components:
- TransformerConfig: Configuration class for transformer models
- PositionalEncoding: Time-specific positional encodings
- MultiHeadAttention: Self-attention mechanism with multiple heads
- TransformerBlock: Core transformer block with attention and feed-forward layers
- TransformerBase: Abstract base class for transformer models
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple, List, Dict, Any, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TransformerConfig:
    """Configuration class for transformer models.
    
    Attributes:
        input_features (int): Number of input features
        hidden_size (int): Dimension of transformer hidden layers
        num_layers (int): Number of transformer layers
        attention_heads (int): Number of attention heads
        dropout (float): Dropout rate
        forecast_horizon (int): Number of future steps to predict
        context_length (int): Length of historical context window
        learning_rate (float): Initial learning rate
        weight_decay (float): L2 regularization factor
        max_epochs (int): Maximum training epochs
        patience (int): Early stopping patience
        use_positional_encoding (bool): Whether to use positional encoding
        activation (str): Activation function ("relu", "gelu")
    """
    input_features: int
    hidden_size: int = 128
    num_layers: int = 4
    attention_heads: int = 4
    dropout: float = 0.1
    forecast_horizon: int = 5
    context_length: int = 60
    learning_rate: float = 1e-4
    weight_decay: float = 1e-6
    max_epochs: int = 100
    patience: int = 10
    use_positional_encoding: bool = True
    activation: str = "gelu"


class PositionalEncoding(nn.Module):
    """Positional encoding for time series data.
    
    Adds information about the relative or absolute position of the timestamps in the sequence.
    This is adapted specifically for time series data with options for periodic encodings.
    
    Args:
        d_model (int): Embedding dimension
        max_len (int): Maximum sequence length
        dropout (float): Dropout rate
        use_time_features (bool): If True, uses time-aware features (day, week, month)
    """
    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1, 
                 use_time_features: bool = False):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)
        self.use_time_features = use_time_features
        
        # Standard transformer positional encoding
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0).transpose(0, 1)
        
        self.register_buffer('pe', pe)
        
        # Additional time-based encoding if requested
        if use_time_features:
            self.time_feature_proj = nn.Linear(4, d_model)
    
    def forward(self, x: torch.Tensor, time_features: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            x: Tensor of shape [seq_len, batch_size, embedding_dim]
            time_features: Optional tensor containing temporal features [seq_len, batch_size, 4]
                           (hour of day, day of week, day of month, month of year)
        
        Returns:
            Tensor with positional encoding added
        """
        x = x + self.pe[:x.size(0), :]
        
        if self.use_time_features and time_features is not None:
            # Project time features to embedding dimension and add
            time_encoding = self.time_feature_proj(time_features)
            x = x + time_encoding
            
        return self.dropout(x)


class MultiHeadAttention(nn.Module):
    """Multi-headed attention mechanism.
    
    Allows the model to jointly attend to information from different representation subspaces.
    Adapted for financial time series with mask support for causal attention.
    
    Args:
        hidden_size (int): Size of hidden dimension
        num_heads (int): Number of attention heads
        dropout (float): Dropout probability
    """
    def __init__(self, hidden_size: int, num_heads: int, dropout: float = 0.1):
        super(MultiHeadAttention, self).__init__()
        
        assert hidden_size % num_heads == 0, "hidden_size must be divisible by num_heads"
        
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.head_dim = hidden_size // num_heads
        
        self.query = nn.Linear(hidden_size, hidden_size)
        self.key = nn.Linear(hidden_size, hidden_size)
        self.value = nn.Linear(hidden_size, hidden_size)
        
        self.proj = nn.Linear(hidden_size, hidden_size)
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, 
                mask: Optional[torch.Tensor] = None, 
                attn_weights_only: bool = False) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Args:
            query: Query tensor [seq_len, batch_size, hidden_size]
            key: Key tensor [seq_len, batch_size, hidden_size]
            value: Value tensor [seq_len, batch_size, hidden_size]
            mask: Optional mask tensor [seq_len, seq_len]
            attn_weights_only: If True, only return attention weights
            
        Returns:
            output: Attention output [seq_len, batch_size, hidden_size]
            attention: Attention weights [batch_size, num_heads, seq_len, seq_len]
        """
        seq_len, batch_size, _ = query.size()
        
        # Linear projections and reshape for multi-head attention
        q = self.query(query).view(seq_len, batch_size, self.num_heads, self.head_dim).permute(1, 2, 0, 3)
        k = self.key(key).view(seq_len, batch_size, self.num_heads, self.head_dim).permute(1, 2, 0, 3)
        v = self.value(value).view(seq_len, batch_size, self.num_heads, self.head_dim).permute(1, 2, 0, 3)
        
        # Compute attention scores
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        
        # Apply mask if provided
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        
        # Apply softmax and dropout
        attention_weights = F.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)
        
        if attn_weights_only:
            return attention_weights
            
        # Apply attention to values
        output = torch.matmul(attention_weights, v)
        
        # Reshape and concatenate heads
        output = output.permute(2, 0, 1, 3).contiguous().view(seq_len, batch_size, self.hidden_size)
        
        # Final linear projection
        output = self.proj(output)
        
        return output, attention_weights


class TransformerBlock(nn.Module):
    """Transformer block with self-attention and feed-forward layers.
    
    This implements a standard transformer block with adaptations for time series:
    1. Self-attention mechanism
    2. Position-wise feed-forward network
    3. Layer normalization and residual connections
    
    Args:
        hidden_size (int): Size of hidden dimension
        num_heads (int): Number of attention heads
        ff_dim (int): Dimension of feed-forward network
        dropout (float): Dropout probability
        activation (str): Activation function ("relu", "gelu")
    """
    def __init__(self, hidden_size: int, num_heads: int, ff_dim: int = None, 
                 dropout: float = 0.1, activation: str = "gelu"):
        super(TransformerBlock, self).__init__()
        
        if ff_dim is None:
            ff_dim = hidden_size * 4
            
        self.self_attention = MultiHeadAttention(hidden_size, num_heads, dropout)
        
        # Feed-forward network
        self.ff = nn.Sequential(
            nn.Linear(hidden_size, ff_dim),
            nn.GELU() if activation == "gelu" else nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(ff_dim, hidden_size),
            nn.Dropout(dropout)
        )
        
        # Layer normalization
        self.norm1 = nn.LayerNorm(hidden_size)
        self.norm2 = nn.LayerNorm(hidden_size)
        
        # Dropout
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Input tensor [seq_len, batch_size, hidden_size]
            mask: Optional attention mask [seq_len, seq_len]
            
        Returns:
            output: Transformer block output [seq_len, batch_size, hidden_size]
            attention_weights: Attention weights [batch_size, num_heads, seq_len, seq_len]
        """
        # Self-attention with residual connection and layer norm
        attn_output, attention_weights = self.self_attention(
            query=self.norm1(x),
            key=self.norm1(x),
            value=self.norm1(x),
            mask=mask
        )
        x = x + self.dropout(attn_output)
        
        # Feed-forward with residual connection and layer norm
        ff_output = self.ff(self.norm2(x))
        x = x + ff_output
        
        return x, attention_weights


class TransformerBase(nn.Module, ABC):
    """Abstract base class for all transformer models.
    
    This class defines the common interface and functionality for transformer-based models
    adapted to financial time series tasks.
    
    Args:
        config (TransformerConfig): Model configuration
    """
    def __init__(self, config: TransformerConfig):
        super(TransformerBase, self).__init__()
        self.config = config
        
    @abstractmethod
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None,
                time_features: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Forward pass.
        
        Args:
            x: Input tensor [seq_len, batch_size, input_features]
            mask: Optional attention mask [seq_len, seq_len]
            time_features: Optional temporal features [seq_len, batch_size, num_time_features]
            
        Returns:
            output: Model output
        """
        pass
    
    @abstractmethod
    def predict(self, x: Union[torch.Tensor, np.ndarray], 
                time_features: Optional[Union[torch.Tensor, np.ndarray]] = None) -> np.ndarray:
        """Generate predictions.
        
        Args:
            x: Input data
            time_features: Optional temporal features
            
        Returns:
            predictions: Model predictions
        """
        pass
    
    def get_attention_weights(self, x: torch.Tensor, 
                             time_features: Optional[torch.Tensor] = None) -> List[torch.Tensor]:
        """Extract attention weights for interpretability.
        
        Args:
            x: Input tensor
            time_features: Optional temporal features
            
        Returns:
            attention_weights: List of attention weight tensors from each layer
        """
        raise NotImplementedError("This method should be implemented by subclasses")
    
    def count_parameters(self) -> int:
        """Count the number of trainable parameters in the model.
        
        Returns:
            num_params: Number of trainable parameters
        """
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
    
    def save(self, path: str) -> None:
        """Save model weights and config.
        
        Args:
            path: Path to save the model
        """
        save_dict = {
            'model_state_dict': self.state_dict(),
            'config': self.config.__dict__
        }
        torch.save(save_dict, path)
        
    @classmethod
    def load(cls, path: str, map_location: Optional[str] = None) -> 'TransformerBase':
        """Load model weights and config.
        
        Args:
            path: Path to load the model from
            map_location: Optional device mapping
            
        Returns:
            model: Loaded model
        """
        save_dict = torch.load(path, map_location=map_location)
        config = TransformerConfig(**save_dict['config'])
        model = cls(config)
        model.load_state_dict(save_dict['model_state_dict'])
        return model 