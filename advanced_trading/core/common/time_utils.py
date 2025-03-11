"""
Time Utilities

Common time-related utility functions.
"""

import time
from typing import Union, Optional
from datetime import datetime, timedelta, timezone


def format_time(dt: Union[datetime, float], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a datetime or timestamp as string.
    
    Args:
        dt: Datetime object or timestamp
        fmt: Format string
        
    Returns:
        Formatted datetime string
    """
    if isinstance(dt, (int, float)):
        dt = timestamp_to_datetime(dt)
    
    return dt.strftime(fmt)


def timestamp_to_datetime(timestamp: Union[int, float]) -> datetime:
    """
    Convert a UNIX timestamp to a datetime object.
    
    Args:
        timestamp: UNIX timestamp (seconds since epoch)
        
    Returns:
        Datetime object in UTC
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime) -> float:
    """
    Convert a datetime object to a UNIX timestamp.
    
    Args:
        dt: Datetime object
        
    Returns:
        UNIX timestamp (seconds since epoch)
    """
    # Ensure datetime is timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.timestamp()


def floor_dt_to_interval(dt: datetime, interval_minutes: int) -> datetime:
    """
    Floor a datetime to the nearest interval.
    
    Args:
        dt: Datetime object
        interval_minutes: Interval in minutes
        
    Returns:
        Floored datetime
    
    Example:
        If dt is 2023-01-01 14:37:00 and interval_minutes is 15,
        the result will be 2023-01-01 14:30:00.
    """
    minutes = dt.minute
    floored_minutes = (minutes // interval_minutes) * interval_minutes
    
    return dt.replace(minute=floored_minutes, second=0, microsecond=0)


def ceil_dt_to_interval(dt: datetime, interval_minutes: int) -> datetime:
    """
    Ceiling a datetime to the nearest interval.
    
    Args:
        dt: Datetime object
        interval_minutes: Interval in minutes
        
    Returns:
        Ceiled datetime
    
    Example:
        If dt is 2023-01-01 14:37:00 and interval_minutes is 15,
        the result will be 2023-01-01 14:45:00.
    """
    minutes = dt.minute
    floored_minutes = (minutes // interval_minutes) * interval_minutes
    
    if minutes > floored_minutes:
        floored_minutes += interval_minutes
    
    result = dt.replace(minute=floored_minutes, second=0, microsecond=0)
    
    # Handle overflow
    if floored_minutes >= 60:
        result = result.replace(minute=floored_minutes % 60)
        result = result + timedelta(hours=floored_minutes // 60)
    
    return result


def time_interval_to_seconds(interval: str) -> int:
    """
    Convert a time interval string to seconds.
    
    Args:
        interval: Time interval string (e.g., "1m", "5m", "1h", "1d")
        
    Returns:
        Seconds in the interval
        
    Raises:
        ValueError: If the interval string is invalid
    """
    if not interval:
        raise ValueError("Invalid interval: empty string")
    
    unit = interval[-1].lower()
    try:
        value = int(interval[:-1])
    except ValueError:
        raise ValueError(f"Invalid interval: {interval}")
    
    if value <= 0:
        raise ValueError(f"Invalid interval value: {value}")
    
    if unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    elif unit == 'w':
        return value * 604800
    else:
        raise ValueError(f"Invalid interval unit: {unit}")


def get_current_timestamp() -> float:
    """
    Get the current UNIX timestamp.
    
    Returns:
        Current UNIX timestamp (seconds since epoch)
    """
    return time.time()


def get_current_datetime() -> datetime:
    """
    Get the current datetime in UTC.
    
    Returns:
        Current UTC datetime
    """
    return datetime.now(timezone.utc) 