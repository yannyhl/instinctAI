#!/usr/bin/env python
"""
Data Quality Framework Example

This script demonstrates how to use the Data Quality Framework to validate, 
measure, and monitor data quality in the Instinct AI trading platform.
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt

# Import data quality components
from advanced_trading.data.quality import (
    # Validation
    validate_data_schema,
    validate_data_constraints,
    
    # Metrics
    create_quality_report,
    calculate_completeness,
    
    # Anomaly detection
    detect_zscore_anomalies,
    detect_isolation_forest_anomalies,
    
    # Lineage
    create_lineage_tracker,
    record_data_source,
    record_data_transformation,
    
    # Dashboard
    create_dashboard,
    add_report_to_dashboard,
    save_dashboard_history,
    
    # Integration
    create_data_quality_pipeline,
    create_strategy_quality_integration,
    create_risk_quality_integration
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_sample_data(rows=1000, include_anomalies=True, missing_pct=0.02):
    """Generate sample market data for demonstration purposes."""
    
    # Create dates
    end_date = datetime.now()
    start_date = end_date - timedelta(days=rows)
    dates = pd.date_range(start=start_date, end=end_date, periods=rows)
    
    # Create price series with realistic properties
    np.random.seed(42)  # For reproducibility
    returns = np.random.normal(0.0005, 0.015, rows)  # mean slightly positive, std 1.5%
    
    # Add some autocorrelation to returns
    for i in range(1, len(returns)):
        returns[i] = 0.1 * returns[i-1] + 0.9 * returns[i]
    
    # Convert returns to prices
    price = 100.0
    prices = [price]
    for ret in returns:
        price *= (1 + ret)
        prices.append(price)
    prices = prices[1:]  # Remove initial price
    
    # Create volume with price-volume correlation
    volume_base = np.random.lognormal(10, 1, rows)
    volume = volume_base * (1 + 0.3 * np.abs(returns))  # Higher volume on larger price moves
    
    # Introduce anomalies if requested
    if include_anomalies:
        # Price spikes
        spike_indices = np.random.choice(range(rows), size=5, replace=False)
        for idx in spike_indices:
            prices[idx] *= np.random.choice([0.8, 1.2])  # 20% jump up or down
        
        # Volume spikes
        volume_spike_indices = np.random.choice(range(rows), size=8, replace=False)
        for idx in volume_spike_indices:
            volume[idx] *= np.random.uniform(3, 5)  # 3-5x normal volume
    
    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'price': prices,
        'volume': volume.astype(int),
        'returns': returns
    })
    
    # Add derived columns
    df['volatility'] = df['returns'].rolling(20).std() * np.sqrt(252)  # Annualized volatility
    df['moving_avg_20'] = df['price'].rolling(20).mean()
    
    # Introduce missing values if requested
    if missing_pct > 0:
        mask = np.random.random(df.shape) < missing_pct
        df.mask(mask, inplace=True)
    
    return df

def demonstrate_validation():
    """Demonstrate data validation capabilities."""
    logger.info("=== Demonstrating Data Validation ===")
    
    # Generate sample data
    df = generate_sample_data(rows=500, include_anomalies=True, missing_pct=0.03)
    logger.info(f"Generated sample data with {len(df)} rows")
    
    # Define a schema for validation
    schema = {
        "price": {
            "type": "number",
            "required": True,
            "constraints": {
                "minimum": 0
            }
        },
        "volume": {
            "type": "integer",
            "required": True,
            "constraints": {
                "minimum": 0
            }
        },
        "date": {
            "type": "datetime",
            "required": True
        },
        "returns": {
            "type": "number",
            "required": False
        }
    }
    
    # Validate data against schema
    validation_result = validate_data_schema(df, schema)
    
    logger.info(f"Validation result: {'Valid' if validation_result.is_valid else 'Invalid'}")
    logger.info(f"Errors: {len(validation_result.errors)}, Warnings: {len(validation_result.warnings)}")
    
    # Define constraints for validation
    constraints = [
        {
            "type": "uniqueness",
            "columns": ["date"]
        },
        {
            "type": "relationship",
            "expression": "price >= 0"
        },
        {
            "type": "completeness",
            "columns": ["price", "volume"],
            "threshold": 0.95
        }
    ]
    
    # Validate data against constraints
    constraint_result = validate_data_constraints(df, constraints)
    
    logger.info(f"Constraint validation: {'Valid' if constraint_result.is_valid else 'Invalid'}")
    logger.info(f"Errors: {len(constraint_result.errors)}, Warnings: {len(constraint_result.warnings)}")
    
    # Print some sample errors if any
    if not validation_result.is_valid or not constraint_result.is_valid:
        for i, error in enumerate(validation_result.errors[:3]):
            logger.info(f"Validation Error {i+1}: {error.message}")
        
        for i, error in enumerate(constraint_result.errors[:3]):
            logger.info(f"Constraint Error {i+1}: {error.message}")
    
    return df

def demonstrate_metrics(df):
    """Demonstrate quality metrics capabilities."""
    logger.info("\n=== Demonstrating Quality Metrics ===")
    
    # Calculate individual metrics
    completeness = calculate_completeness(df, "price")
    logger.info(f"Price completeness: {completeness:.2%}")
    
    # Create a comprehensive quality report
    quality_report = create_quality_report(
        df, 
        "sample_market_data",
        metrics=["completeness", "uniqueness", "outlier_ratio", "freshness"],
        thresholds={
            "completeness": 0.95,
            "uniqueness": 0.95,
            "outlier_ratio": 0.05,
            "freshness": 0.9
        }
    )
    
    logger.info(f"Overall quality score: {quality_report.overall_score:.2f}/100")
    
    # Print metrics
    for metric in quality_report.metrics:
        threshold_info = f"(threshold: {metric.threshold:.2f})" if metric.threshold is not None else ""
        status = "✅" if metric.is_passing else "❌"
        logger.info(f"{metric.name}: {metric.value:.4f} {threshold_info} {status}")
    
    return quality_report

def demonstrate_anomaly_detection(df):
    """Demonstrate anomaly detection capabilities."""
    logger.info("\n=== Demonstrating Anomaly Detection ===")
    
    # Detect anomalies using Z-score method
    zscore_result = detect_zscore_anomalies(df, "returns", threshold=3.0)
    logger.info(f"Z-score anomalies: {zscore_result.anomaly_count} ({zscore_result.anomaly_percentage:.2%} of data)")
    
    # Detect anomalies using Isolation Forest
    iso_result = detect_isolation_forest_anomalies(
        df, 
        columns=["price", "volume", "returns"], 
        contamination=0.05
    )
    logger.info(f"Isolation Forest anomalies: {iso_result.anomaly_count} ({iso_result.anomaly_percentage:.2%} of data)")
    
    # Show some example anomalies
    if zscore_result.anomaly_count > 0:
        anomaly_indices = zscore_result.anomalies.index[:5]  # Show first 5 anomalies
        logger.info("Example Z-score anomalies:")
        for idx in anomaly_indices:
            logger.info(f"  Date: {df.loc[idx, 'date'].date()}, Returns: {df.loc[idx, 'returns']:.4f}")
    
    return zscore_result, iso_result

def demonstrate_lineage():
    """Demonstrate data lineage capabilities."""
    logger.info("\n=== Demonstrating Data Lineage ===")
    
    # Generate raw data
    raw_data = generate_sample_data(rows=200, include_anomalies=True, missing_pct=0.05)
    logger.info(f"Generated raw data with {len(raw_data)} rows")
    
    # Create lineage tracker
    lineage = create_lineage_tracker()
    
    # Record data source
    source_id = record_data_source(
        lineage,
        data=raw_data,
        name="sample_raw_data",
        description="Raw sample market data",
        source_type="synthetic",
        metadata={"generation_time": datetime.now().isoformat()}
    )
    logger.info(f"Recorded data source with ID: {source_id}")
    
    # Process data (clean missing values)
    cleaned_data = raw_data.copy()
    cleaned_data.fillna(method='ffill', inplace=True)
    
    # Record transformation
    transform_id = record_data_transformation(
        lineage,
        input_data=raw_data,
        output_data=cleaned_data,
        name="Clean missing values",
        description="Fill missing values using forward fill method",
        parameters={"method": "ffill"}
    )
    logger.info(f"Recorded data transformation with ID: {transform_id}")
    
    # Another transformation (calculate moving averages)
    augmented_data = cleaned_data.copy()
    augmented_data['ma_5'] = augmented_data['price'].rolling(5).mean()
    augmented_data['ma_10'] = augmented_data['price'].rolling(10).mean()
    
    # Record transformation
    transform_id2 = record_data_transformation(
        lineage,
        input_data=cleaned_data,
        output_data=augmented_data,
        name="Calculate moving averages",
        description="Add 5-day and 10-day moving averages",
        parameters={"windows": [5, 10]}
    )
    logger.info(f"Recorded another transformation with ID: {transform_id2}")
    
    # Get lineage for the final dataset
    dataset_lineage = lineage.get_dataset_lineage(transform_id2)
    logger.info(f"Retrieved lineage with {len(dataset_lineage.operations)} operations")
    
    # Print lineage details
    for op in dataset_lineage.operations:
        logger.info(f"Operation: {op.name} (Type: {op.operation_type.name})")
    
    return lineage, augmented_data

def demonstrate_dashboard(quality_report):
    """Demonstrate dashboard capabilities."""
    logger.info("\n=== Demonstrating Quality Dashboard ===")
    
    # Create dashboard
    dashboard = create_dashboard()
    logger.info("Created quality dashboard")
    
    # Add quality report
    add_report_to_dashboard(dashboard, quality_report)
    logger.info("Added quality report to dashboard")
    
    # Add more reports with different timestamps
    for days_ago in [7, 14, 21, 28]:
        # Generate data with different characteristics
        missing_pct = max(0.01, 0.05 - (days_ago / 100))  # Improve completeness over time
        df = generate_sample_data(rows=200, include_anomalies=True, missing_pct=missing_pct)
        
        # Create report
        report = create_quality_report(
            df, 
            "sample_market_data",
            metrics=["completeness", "uniqueness", "outlier_ratio", "freshness"],
            thresholds={
                "completeness": 0.95,
                "uniqueness": 0.95,
                "outlier_ratio": 0.05,
                "freshness": 0.9
            }
        )
        
        # Add to dashboard with historical timestamp
        timestamp = datetime.now() - timedelta(days=days_ago)
        add_report_to_dashboard(dashboard, report, timestamp)
    
    logger.info("Added historical reports to dashboard")
    
    # Save dashboard history to file
    history_file = "quality_history.csv"
    save_dashboard_history(dashboard, history_file)
    logger.info(f"Saved dashboard history to {history_file}")
    
    # Create visualizations
    try:
        # Create visualizations (in a real application, these would be displayed in a web UI)
        scorecard = dashboard.create_quality_scorecard()
        history_chart = dashboard.create_metric_history_chart("completeness", days=30)
        heatmap = dashboard.create_quality_heatmap()
        failing_chart = dashboard.create_failing_metrics_chart()
        
        logger.info("Created dashboard visualizations")
    except Exception as e:
        logger.error(f"Error creating visualizations: {e}")
    
    return dashboard

def demonstrate_integration():
    """Demonstrate integration capabilities."""
    logger.info("\n=== Demonstrating System Integration ===")
    
    # Create a data quality pipeline
    pipeline = create_data_quality_pipeline(
        name="market_data_pipeline",
        metrics=["completeness", "outlier_ratio", "data_freshness"],
        thresholds={"completeness": 0.95, "outlier_ratio": 0.05, "data_freshness": 0.9},
        anomaly_detection=True,
        track_lineage=True
    )
    logger.info("Created data quality pipeline")
    
    # Generate data
    df = generate_sample_data(rows=300, include_anomalies=True, missing_pct=0.04)
    
    # Process data through pipeline
    processed_data, quality_results = pipeline.process(
        data=df,
        dataset_name="market_data",
        on_validation_failure="warn",
        on_quality_failure="warn"
    )
    
    logger.info("Processed data through quality pipeline")
    logger.info(f"Quality results: Overall score = {quality_results['quality_report']['overall_score']:.2f}")
    logger.info(f"Passing metrics: {quality_results['quality_report']['passing_metrics']}")
    logger.info(f"Failing metrics: {quality_results['quality_report']['failing_metrics']}")
    
    # Create strategy quality integration
    strategy_quality = create_strategy_quality_integration(
        strategy_name="momentum_strategy",
        required_metrics=["completeness", "data_freshness"],
        metric_thresholds={"completeness": 0.98, "data_freshness": 0.95}
    )
    logger.info("Created strategy quality integration")
    
    # Validate strategy input data
    try:
        quality_results = strategy_quality.validate_input_data(
            df,
            raise_on_failure=False
        )
        logger.info(f"Strategy input validation: Score = {quality_results['overall_score']:.2f}")
    except ValueError as e:
        logger.error(f"Strategy validation error: {e}")
    
    # Create risk quality integration
    risk_quality = create_risk_quality_integration()
    logger.info("Created risk quality integration")
    
    # Validate risk data
    risk_results = risk_quality.validate_risk_data(
        df,
        data_type="market",
        raise_on_failure=False
    )
    logger.info(f"Risk data validation: Score = {risk_results['overall_score']:.2f}")
    
    # Calculate data quality risk factor
    risk_factor = risk_quality.calculate_data_quality_risk_factor()
    logger.info(f"Data quality risk factor: {risk_factor:.4f}")
    
    return pipeline, strategy_quality, risk_quality

def main():
    """Run the data quality examples."""
    logger.info("Starting Data Quality Framework example")
    
    # Demonstrate validation
    df = demonstrate_validation()
    
    # Demonstrate metrics
    quality_report = demonstrate_metrics(df)
    
    # Demonstrate anomaly detection
    zscore_result, iso_result = demonstrate_anomaly_detection(df)
    
    # Demonstrate lineage
    lineage, augmented_data = demonstrate_lineage()
    
    # Demonstrate dashboard
    dashboard = demonstrate_dashboard(quality_report)
    
    # Demonstrate integration
    pipeline, strategy_quality, risk_quality = demonstrate_integration()
    
    logger.info("\nData Quality Framework example completed successfully")

if __name__ == "__main__":
    main() 