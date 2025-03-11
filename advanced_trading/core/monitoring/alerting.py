"""
Alerting System

This module provides alerting capabilities for the trading system, allowing
components to generate alerts that can be tracked, managed, and sent to
various notification channels.
"""

import os
import logging
import json
import uuid
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from collections import deque

from advanced_trading.core.observability.logging import setup_logger

logger = logging.getLogger('advanced_trading.core.monitoring.alerting')


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = 0
    WARNING = 1
    ERROR = 2
    CRITICAL = 3


class Alert:
    """
    Represents a system alert.
    
    Attributes:
        id: Unique identifier for the alert
        level: Severity level of the alert
        source: Component that generated the alert
        title: Short description of the alert
        message: Detailed alert message
        timestamp: When the alert was generated
        metadata: Additional information about the alert
        acknowledged: Whether the alert has been acknowledged
        resolved: Whether the alert has been resolved
        resolution_time: When the alert was resolved
        resolution_message: Message describing how the alert was resolved
    """
    
    def __init__(self, 
               level: AlertLevel,
               source: str,
               title: str,
               message: str,
               metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a new alert.
        
        Args:
            level: Severity level of the alert
            source: Component that generated the alert
            title: Short description of the alert
            message: Detailed alert message
            metadata: Additional information about the alert
        """
        self.id = str(uuid.uuid4())
        self.level = level
        self.source = source
        self.title = title
        self.message = message
        self.timestamp = datetime.now()
        self.metadata = metadata or {}
        self.acknowledged = False
        self.resolved = False
        self.resolution_time = None
        self.resolution_message = None
    
    def acknowledge(self) -> None:
        """Mark the alert as acknowledged."""
        self.acknowledged = True
    
    def resolve(self, message: Optional[str] = None) -> None:
        """
        Mark the alert as resolved.
        
        Args:
            message: Optional message describing how the alert was resolved
        """
        self.resolved = True
        self.resolution_time = datetime.now()
        self.resolution_message = message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the alert to a dictionary."""
        return {
            'id': self.id,
            'level': self.level.name,
            'level_value': self.level.value,
            'source': self.source,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'acknowledged': self.acknowledged,
            'resolved': self.resolved,
            'resolution_time': self.resolution_time.isoformat() if self.resolution_time else None,
            'resolution_message': self.resolution_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Alert':
        """Create an Alert from a dictionary."""
        alert = cls(
            level=AlertLevel[data['level']],
            source=data['source'],
            title=data['title'],
            message=data['message'],
            metadata=data.get('metadata', {})
        )
        alert.id = data['id']
        alert.timestamp = datetime.fromisoformat(data['timestamp'])
        alert.acknowledged = data.get('acknowledged', False)
        alert.resolved = data.get('resolved', False)
        
        if data.get('resolution_time'):
            alert.resolution_time = datetime.fromisoformat(data['resolution_time'])
        
        alert.resolution_message = data.get('resolution_message')
        
        return alert


class NotificationChannel:
    """Base class for alert notification channels."""
    
    def __init__(self, name: str):
        """Initialize the notification channel."""
        self.name = name
    
    def send_alert(self, alert: Alert) -> bool:
        """Send an alert through this channel."""
        raise NotImplementedError("Subclasses must implement send_alert")


class LoggingNotificationChannel(NotificationChannel):
    """Notification channel that logs alerts."""
    
    def __init__(self, name: str = "logging"):
        """Initialize the logging notification channel."""
        super().__init__(name)
    
    def send_alert(self, alert: Alert) -> bool:
        """Log the alert message."""
        if alert.level == AlertLevel.INFO:
            logger.info(f"ALERT: {alert.title} - {alert.message} (Source: {alert.source})")
        elif alert.level == AlertLevel.WARNING:
            logger.warning(f"ALERT: {alert.title} - {alert.message} (Source: {alert.source})")
        elif alert.level == AlertLevel.ERROR:
            logger.error(f"ALERT: {alert.title} - {alert.message} (Source: {alert.source})")
        elif alert.level == AlertLevel.CRITICAL:
            logger.critical(f"ALERT: {alert.title} - {alert.message} (Source: {alert.source})")
        
        return True


class AlertManager:
    """
    Manages system alerts, including tracking, storage, and notification.
    
    The AlertManager is responsible for:
    1. Receiving alerts from various system components
    2. Storing alerts in memory and optionally to disk
    3. Sending notifications through configured channels
    4. Providing query capabilities for active alerts
    5. Managing alert lifecycle (acknowledgment, resolution)
    """
    
    def __init__(self, 
               max_alerts_in_memory: int = 1000,
               alert_storage_path: Optional[str] = None,
               min_level_for_notification: AlertLevel = AlertLevel.WARNING):
        """
        Initialize the AlertManager.
        
        Args:
            max_alerts_in_memory: Maximum number of alerts to keep in memory
            alert_storage_path: Optional path to store alerts to disk
            min_level_for_notification: Minimum alert level to trigger notifications
        """
        self.alerts = deque(maxlen=max_alerts_in_memory)
        self.alert_storage_path = alert_storage_path
        self.min_level_for_notification = min_level_for_notification
        self.notification_channels: List[NotificationChannel] = []
        
        # Add default logging channel
        self.add_notification_channel(LoggingNotificationChannel())
        
        logger.info(f"AlertManager initialized with {max_alerts_in_memory} max alerts in memory")
        
        # Create alert storage directory if specified
        if alert_storage_path:
            os.makedirs(alert_storage_path, exist_ok=True)
            logger.info(f"Alert storage path set to {alert_storage_path}")
    
    def add_notification_channel(self, channel: NotificationChannel) -> None:
        """
        Add a notification channel to the manager.
        
        Args:
            channel: The notification channel to add
        """
        self.notification_channels.append(channel)
        logger.info(f"Added notification channel: {channel.name}")
    
    def add_alert(self, alert: Alert) -> str:
        """
        Add an alert to the system.
        
        Args:
            alert: The alert to add
            
        Returns:
            The ID of the alert
        """
        # Add to memory
        self.alerts.append(alert)
        
        # Store to disk if configured
        if self.alert_storage_path:
            self._store_alert(alert)
        
        # Send notifications if alert level meets threshold
        if alert.level.value >= self.min_level_for_notification.value:
            self._send_notifications(alert)
        
        return alert.id
    
    def create_alert(self, 
                   level: AlertLevel,
                   source: str,
                   title: str,
                   message: str,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create and add a new alert.
        
        Args:
            level: Severity level of the alert
            source: Component that generated the alert
            title: Short description of the alert
            message: Detailed alert message
            metadata: Additional information about the alert
            
        Returns:
            The ID of the new alert
        """
        alert = Alert(
            level=level,
            source=source,
            title=title,
            message=message,
            metadata=metadata
        )
        
        return self.add_alert(alert)
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Get an alert by ID.
        
        Args:
            alert_id: The ID of the alert to retrieve
            
        Returns:
            The alert, or None if not found
        """
        for alert in self.alerts:
            if alert.id == alert_id:
                return alert
        
        # If not in memory, try loading from disk
        if self.alert_storage_path:
            return self._load_alert(alert_id)
        
        return None
    
    def get_alerts(self, 
                 source: Optional[str] = None,
                 level: Optional[AlertLevel] = None,
                 since: Optional[datetime] = None,
                 resolved: Optional[bool] = None,
                 acknowledged: Optional[bool] = None,
                 limit: Optional[int] = None) -> List[Alert]:
        """
        Get alerts matching the specified criteria.
        
        Args:
            source: Filter by alert source
            level: Filter by alert level
            since: Filter by alerts after this time
            resolved: Filter by resolved status
            acknowledged: Filter by acknowledged status
            limit: Maximum number of alerts to return
            
        Returns:
            List of matching alerts
        """
        result = []
        
        for alert in self.alerts:
            # Apply filters
            if source and alert.source != source:
                continue
            if level and alert.level != level:
                continue
            if since and alert.timestamp < since:
                continue
            if resolved is not None and alert.resolved != resolved:
                continue
            if acknowledged is not None and alert.acknowledged != acknowledged:
                continue
            
            result.append(alert)
            
            # Check limit
            if limit and len(result) >= limit:
                break
        
        return result
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: ID of the alert to acknowledge
            
        Returns:
            True if the alert was acknowledged, False otherwise
        """
        alert = self.get_alert(alert_id)
        if not alert:
            return False
        
        alert.acknowledge()
        
        # Update on disk if configured
        if self.alert_storage_path:
            self._store_alert(alert)
        
        return True
    
    def resolve_alert(self, alert_id: str, message: Optional[str] = None) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: ID of the alert to resolve
            message: Optional resolution message
            
        Returns:
            True if the alert was resolved, False otherwise
        """
        alert = self.get_alert(alert_id)
        if not alert:
            return False
        
        alert.resolve(message)
        
        # Update on disk if configured
        if self.alert_storage_path:
            self._store_alert(alert)
        
        return True
    
    def _send_notifications(self, alert: Alert) -> None:
        """Send alert notifications through all configured channels."""
        for channel in self.notification_channels:
            try:
                channel.send_alert(alert)
            except Exception as e:
                logger.error(f"Failed to send alert through channel {channel.name}: {str(e)}")
    
    def _store_alert(self, alert: Alert) -> None:
        """Store an alert to disk."""
        if not self.alert_storage_path:
            return
        
        file_path = os.path.join(self.alert_storage_path, f"{alert.id}.json")
        
        try:
            with open(file_path, 'w') as f:
                json.dump(alert.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to store alert {alert.id} to disk: {str(e)}")
    
    def _load_alert(self, alert_id: str) -> Optional[Alert]:
        """Load an alert from disk."""
        if not self.alert_storage_path:
            return None
        
        file_path = os.path.join(self.alert_storage_path, f"{alert_id}.json")
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return Alert.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load alert {alert_id} from disk: {str(e)}")
            return None 