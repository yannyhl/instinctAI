FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY advanced_trading/requirements.txt /app/requirements.txt

# Install Python dependencies with special handling for blinker
RUN pip install --upgrade pip && \
    pip install --no-deps blinker==1.6.2 && \
    pip install -r requirements.txt && \
    # Install dashboard-specific dependencies
    pip install dash plotly PyJWT

# Copy application code
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/advanced_trading/logs /app/advanced_trading/data/cache

# Set environment variables
ENV PYTHONPATH="${PYTHONPATH}:/app"
ENV DASH_DEBUG="false"

# Expose the dashboard port
EXPOSE 8050

# Set up volumes for persistent data
VOLUME ["/app/advanced_trading/data", "/app/advanced_trading/logs"]

# Command to run the dashboard
ENTRYPOINT ["python", "advanced_trading/run_secured_dashboard.py", "--host=0.0.0.0", "--init-admin"] 