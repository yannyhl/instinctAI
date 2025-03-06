"""
Emergency Protocols Module

This module provides emergency protocol functionality for the trading system.
Emergency protocols define how the system should respond to critical situations,
from minor warnings to system-wide emergency shutdowns.
"""

import time
import logging
import uuid
from enum import Enum
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field

# Initialize logger
logger = logging.getLogger(__name__)

class EmergencyLevel(Enum):
    """Emergency severity levels."""
    INFO = 0  # Informational, no action needed
    WARNING = 1  # Warning, caution advised
    ALERT = 2  # Alert, requires attention
    CRITICAL = 3  # Critical, immediate action required
    EMERGENCY = 4  # Emergency, system-wide impact

@dataclass
class EmergencyEvent:
    """Event generated when an emergency situation is detected."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    level: EmergencyLevel = EmergencyLevel.INFO
    source: str = "system"
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    affected_components: List[str] = field(default_factory=list)
    requires_acknowledgment: bool = False
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_time: Optional[float] = None
    resolved: bool = False
    resolved_time: Optional[float] = None
    actions_taken: List[str] = field(default_factory=list)

class EmergencyAction(ABC):
    """
    Base class for actions that can be taken in response to emergency events.
    
    Emergency actions define specific responses to emergency situations, such as
    pausing trading, sending notifications, or executing recovery procedures.
    """
    
    def __init__(self, name: str, description: Optional[str] = None):
        """
        Initialize the emergency action.
        
        Args:
            name: Name of the action
            description: Description of what the action does
        """
        self.id = f"{self.__class__.__name__}_{id(self)}"
        self.name = name
        self.description = description or f"Emergency action: {name}"
        self.enabled = True
        self.last_execution_time = None
        self.execution_count = 0
        self.execution_history: List[Dict[str, Any]] = []
        self.max_history_length = 100
    
    @abstractmethod
    def execute(self, event: EmergencyEvent) -> bool:
        """
        Execute this action in response to an emergency event.
        
        Args:
            event: The emergency event that triggered this action
            
        Returns:
            True if action executed successfully, False otherwise
        """
        pass
    
    def record_execution(self, event: EmergencyEvent, success: bool, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Record the execution of this action.
        
        Args:
            event: The emergency event that triggered this action
            success: Whether the execution was successful
            details: Additional details about the execution
        """
        execution_record = {
            "timestamp": time.time(),
            "event_id": event.id,
            "success": success,
            "details": details or {}
        }
        
        self.execution_history.append(execution_record)
        
        # Trim history if needed
        if len(self.execution_history) > self.max_history_length:
            self.execution_history.pop(0)
        
        # Update counters
        self.last_execution_time = execution_record["timestamp"]
        self.execution_count += 1
    
    def disable(self) -> None:
        """Disable this action."""
        self.enabled = False
        logger.info(f"Emergency action {self.name} ({self.id}) disabled")
    
    def enable(self) -> None:
        """Enable this action."""
        self.enabled = True
        logger.info(f"Emergency action {self.name} ({self.id}) enabled")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of this action.
        
        Returns:
            Status information dict
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "last_execution_time": self.last_execution_time,
            "execution_count": self.execution_count,
            "recent_executions": self.execution_history[-5:] if self.execution_history else []
        }


class EmergencyProtocol:
    """
    Defines a set of actions to be taken in response to specific types of emergency events.
    
    A protocol maps emergency event patterns to sets of actions, allowing the system
    to respond appropriately to different types of emergencies.
    """
    
    def __init__(self, name: str, description: Optional[str] = None):
        """
        Initialize the emergency protocol.
        
        Args:
            name: Name of the protocol
            description: Description of what the protocol handles
        """
        self.id = f"{self.__class__.__name__}_{id(self)}"
        self.name = name
        self.description = description or f"Emergency protocol: {name}"
        self.enabled = True
        self.actions: Dict[EmergencyLevel, List[EmergencyAction]] = {
            level: [] for level in EmergencyLevel
        }
        self.activation_count = 0
        self.last_activation_time = None
        self.activation_history: List[Dict[str, Any]] = []
        self.max_history_length = 100
    
    def add_action(self, action: EmergencyAction, level: EmergencyLevel) -> None:
        """
        Add an action to be executed for a specific emergency level.
        
        Args:
            action: The action to add
            level: The emergency level that will trigger this action
        """
        if action not in self.actions[level]:
            self.actions[level].append(action)
            logger.info(f"Added action {action.name} to protocol {self.name} for level {level.name}")
    
    def remove_action(self, action: EmergencyAction, level: EmergencyLevel) -> bool:
        """
        Remove an action from a specific emergency level.
        
        Args:
            action: The action to remove
            level: The emergency level to remove the action from
            
        Returns:
            True if the action was removed, False if it wasn't found
        """
        if action in self.actions[level]:
            self.actions[level].remove(action)
            logger.info(f"Removed action {action.name} from protocol {self.name} for level {level.name}")
            return True
        return False
    
    def handle_event(self, event: EmergencyEvent) -> List[Dict[str, Any]]:
        """
        Handle an emergency event by executing appropriate actions.
        
        Args:
            event: The emergency event to handle
            
        Returns:
            List of execution results for each action
        """
        if not self.enabled:
            logger.warning(f"Emergency protocol {self.name} is disabled, not handling event {event.id}")
            return []
        
        # Record the activation
        activation_record = {
            "timestamp": time.time(),
            "event_id": event.id,
            "level": event.level.name,
            "actions_executed": []
        }
        
        # Get actions for this level and all lower levels
        relevant_actions = []
        for level in EmergencyLevel:
            if level.value <= event.level.value:
                relevant_actions.extend(self.actions[level])
        
        # Execute each action
        results = []
        for action in relevant_actions:
            if not action.enabled:
                logger.warning(f"Action {action.name} is disabled, skipping for event {event.id}")
                continue
            
            try:
                success = action.execute(event)
                action.record_execution(event, success)
                
                result = {
                    "action_id": action.id,
                    "action_name": action.name,
                    "success": success,
                    "timestamp": time.time()
                }
                
                results.append(result)
                activation_record["actions_executed"].append(result)
                
                if success:
                    event.actions_taken.append(action.name)
                    logger.info(f"Successfully executed action {action.name} for event {event.id}")
                else:
                    logger.warning(f"Failed to execute action {action.name} for event {event.id}")
            except Exception as e:
                logger.error(f"Error executing action {action.name} for event {event.id}: {e}")
                result = {
                    "action_id": action.id,
                    "action_name": action.name,
                    "success": False,
                    "error": str(e),
                    "timestamp": time.time()
                }
                results.append(result)
                activation_record["actions_executed"].append(result)
        
        # Update activation tracking
        self.activation_count += 1
        self.last_activation_time = activation_record["timestamp"]
        self.activation_history.append(activation_record)
        
        # Trim history if needed
        if len(self.activation_history) > self.max_history_length:
            self.activation_history.pop(0)
        
        return results
    
    def disable(self) -> None:
        """Disable this protocol."""
        self.enabled = False
        logger.info(f"Emergency protocol {self.name} ({self.id}) disabled")
    
    def enable(self) -> None:
        """Enable this protocol."""
        self.enabled = True
        logger.info(f"Emergency protocol {self.name} ({self.id}) enabled")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of this protocol.
        
        Returns:
            Status information dict
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "action_count": sum(len(actions) for actions in self.actions.values()),
            "actions_by_level": {level.name: [a.name for a in actions] for level, actions in self.actions.items()},
            "activation_count": self.activation_count,
            "last_activation_time": self.last_activation_time,
            "recent_activations": self.activation_history[-5:] if self.activation_history else []
        }


class EmergencyHandler:
    """
    Central handler for emergency events and protocols.
    
    The emergency handler manages emergency protocols and routes events to the
    appropriate protocols for handling.
    """
    
    def __init__(self):
        """Initialize the emergency handler."""
        self.protocols: Dict[str, EmergencyProtocol] = {}
        self.events: Dict[str, EmergencyEvent] = {}
        self.active_events: Dict[str, EmergencyEvent] = {}
        self.event_listeners: Dict[EmergencyLevel, List[Callable[[EmergencyEvent], None]]] = {
            level: [] for level in EmergencyLevel
        }
        self.max_events_history = 1000
    
    def register_protocol(self, protocol: EmergencyProtocol) -> None:
        """
        Register an emergency protocol.
        
        Args:
            protocol: The protocol to register
        """
        self.protocols[protocol.id] = protocol
        logger.info(f"Registered emergency protocol: {protocol.name} ({protocol.id})")
    
    def unregister_protocol(self, protocol_id: str) -> bool:
        """
        Unregister an emergency protocol.
        
        Args:
            protocol_id: ID of the protocol to unregister
            
        Returns:
            True if protocol was found and removed, False otherwise
        """
        if protocol_id in self.protocols:
            protocol = self.protocols.pop(protocol_id)
            logger.info(f"Unregistered emergency protocol: {protocol.name} ({protocol.id})")
            return True
        return False
    
    def add_event_listener(self, level: EmergencyLevel, listener: Callable[[EmergencyEvent], None]) -> None:
        """
        Add a listener for events of a specific level.
        
        Args:
            level: Emergency level to listen for
            listener: Callback function to invoke when an event of this level occurs
        """
        if listener not in self.event_listeners[level]:
            self.event_listeners[level].append(listener)
    
    def remove_event_listener(self, level: EmergencyLevel, listener: Callable[[EmergencyEvent], None]) -> bool:
        """
        Remove an event listener.
        
        Args:
            level: Emergency level the listener is registered for
            listener: The listener to remove
            
        Returns:
            True if listener was found and removed, False otherwise
        """
        if listener in self.event_listeners[level]:
            self.event_listeners[level].remove(listener)
            return True
        return False
    
    def create_event(self, 
                    level: EmergencyLevel, 
                    source: str, 
                    description: str, 
                    details: Optional[Dict[str, Any]] = None,
                    affected_components: Optional[List[str]] = None,
                    requires_acknowledgment: bool = False) -> EmergencyEvent:
        """
        Create a new emergency event.
        
        Args:
            level: Severity level of the event
            source: Component that generated the event
            description: Human-readable description of the event
            details: Additional details about the event
            affected_components: Components affected by this event
            requires_acknowledgment: Whether the event requires explicit acknowledgment
            
        Returns:
            The created event
        """
        event = EmergencyEvent(
            level=level,
            source=source,
            description=description,
            details=details or {},
            affected_components=affected_components or [],
            requires_acknowledgment=requires_acknowledgment
        )
        
        # Store the event
        self.events[event.id] = event
        
        # If it's not resolved, add to active events
        if not event.resolved:
            self.active_events[event.id] = event
        
        # Trim events history if needed
        if len(self.events) > self.max_events_history:
            oldest_event_id = min(self.events.keys(), key=lambda k: self.events[k].timestamp)
            del self.events[oldest_event_id]
        
        # Log based on severity
        if level == EmergencyLevel.INFO:
            logger.info(f"Emergency event ({event.id}): {description}")
        elif level == EmergencyLevel.WARNING:
            logger.warning(f"Emergency event ({event.id}): {description}")
        elif level == EmergencyLevel.ALERT:
            logger.warning(f"ALERT: Emergency event ({event.id}): {description}")
        elif level == EmergencyLevel.CRITICAL:
            logger.error(f"CRITICAL: Emergency event ({event.id}): {description}")
        elif level == EmergencyLevel.EMERGENCY:
            logger.critical(f"EMERGENCY: Emergency event ({event.id}): {description}")
        
        return event
    
    def handle_event(self, event: EmergencyEvent) -> Dict[str, List[Dict[str, Any]]]:
        """
        Handle an emergency event by routing it to all protocols.
        
        Args:
            event: The event to handle
            
        Returns:
            Dict mapping protocol IDs to lists of action execution results
        """
        # Notify listeners
        for listener in self.event_listeners[event.level]:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Error in event listener for {event.id}: {e}")
        
        # Handle with protocols
        results = {}
        for protocol_id, protocol in self.protocols.items():
            if protocol.enabled:
                protocol_results = protocol.handle_event(event)
                results[protocol_id] = protocol_results
        
        return results
    
    def acknowledge_event(self, event_id: str, acknowledged_by: str) -> bool:
        """
        Acknowledge an emergency event.
        
        Args:
            event_id: ID of the event to acknowledge
            acknowledged_by: Identifier of the entity acknowledging the event
            
        Returns:
            True if event was found and acknowledged, False otherwise
        """
        if event_id in self.events:
            event = self.events[event_id]
            
            if event.requires_acknowledgment and not event.acknowledged:
                event.acknowledged = True
                event.acknowledged_by = acknowledged_by
                event.acknowledged_time = time.time()
                logger.info(f"Event {event_id} acknowledged by {acknowledged_by}")
                return True
        
        return False
    
    def resolve_event(self, event_id: str) -> bool:
        """
        Mark an emergency event as resolved.
        
        Args:
            event_id: ID of the event to resolve
            
        Returns:
            True if event was found and resolved, False otherwise
        """
        if event_id in self.events:
            event = self.events[event_id]
            
            if not event.resolved:
                event.resolved = True
                event.resolved_time = time.time()
                
                # Remove from active events
                if event_id in self.active_events:
                    del self.active_events[event_id]
                
                logger.info(f"Event {event_id} marked as resolved")
                return True
        
        return False
    
    def get_active_events(self, 
                         min_level: Optional[EmergencyLevel] = None, 
                         source: Optional[str] = None,
                         component: Optional[str] = None) -> List[EmergencyEvent]:
        """
        Get active (unresolved) emergency events, optionally filtered.
        
        Args:
            min_level: Minimum severity level to include
            source: Filter by source component
            component: Filter by affected component
            
        Returns:
            List of matching active emergency events
        """
        results = []
        
        for event_id, event in self.active_events.items():
            # Apply filters
            if min_level and event.level.value < min_level.value:
                continue
            
            if source and event.source != source:
                continue
            
            if component and component not in event.affected_components:
                continue
            
            results.append(event)
        
        # Sort by level (most severe first) and then by timestamp (newest first)
        results.sort(key=lambda e: (-e.level.value, -e.timestamp))
        
        return results
    
    def get_recent_events(self, 
                         count: int = 20, 
                         min_level: Optional[EmergencyLevel] = None,
                         include_resolved: bool = True) -> List[EmergencyEvent]:
        """
        Get recent emergency events, optionally filtered.
        
        Args:
            count: Maximum number of events to return
            min_level: Minimum severity level to include
            include_resolved: Whether to include resolved events
            
        Returns:
            List of matching emergency events, sorted by timestamp (newest first)
        """
        # Get all events that match filters
        filtered_events = []
        
        for event_id, event in self.events.items():
            # Apply filters
            if min_level and event.level.value < min_level.value:
                continue
            
            if not include_resolved and event.resolved:
                continue
            
            filtered_events.append(event)
        
        # Sort by timestamp (newest first)
        filtered_events.sort(key=lambda e: -e.timestamp)
        
        # Return up to count events
        return filtered_events[:count]
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the emergency handler.
        
        Returns:
            Status information dict
        """
        return {
            "total_protocols": len(self.protocols),
            "active_protocols": sum(1 for p in self.protocols.values() if p.enabled),
            "total_events": len(self.events),
            "active_events": len(self.active_events),
            "events_by_level": {
                level.name: sum(1 for e in self.events.values() if e.level == level)
                for level in EmergencyLevel
            },
            "active_events_by_level": {
                level.name: sum(1 for e in self.active_events.values() if e.level == level)
                for level in EmergencyLevel
            },
            "recent_events": [
                {
                    "id": e.id,
                    "level": e.level.name,
                    "source": e.source,
                    "description": e.description,
                    "timestamp": e.timestamp,
                    "resolved": e.resolved
                }
                for e in self.get_recent_events(count=5)
            ]
        } 