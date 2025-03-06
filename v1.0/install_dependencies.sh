#!/bin/bash
# Installation script for advanced_trading dependencies

echo "Installing core dependencies for advanced_trading module..."

# Core data and scientific computing libraries
pip install numpy pandas matplotlib seaborn scikit-learn scipy statsmodels joblib pyyaml psutil tqdm

# Exchange API and data handling
pip install ccxt python-binance requests

# Technical analysis
pip install ta arch hmmlearn

# ML dependencies
pip install tensorflow sklearn

# Check for GPU and install GPU libraries if available
if python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))" | grep -q "PhysicalDevice"; then
    echo "GPU detected, installing GPU acceleration libraries..."
    pip install cupy
    # Conditionally install cuDF/cuML based on CUDA version
    CUDA_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | cut -d. -f1)
    if [ "$CUDA_VERSION" -ge "11" ]; then
        pip install cudf-cu11 cuml-cu11
    elif [ "$CUDA_VERSION" -ge "10" ]; then
        pip install cudf-cu10 cuml-cu10
    else
        echo "CUDA version too old for cuDF/cuML, using CPU only"
    fi
else
    echo "No GPU detected, skipping GPU acceleration libraries"
fi

# Environment setup
pip install python-dotenv

echo "Creating required directories..."
mkdir -p advanced_trading/data/cache
mkdir -p advanced_trading/models
mkdir -p advanced_trading/results
mkdir -p advanced_trading/logs

echo "Installation complete!" 