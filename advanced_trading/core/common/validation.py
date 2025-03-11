"""
Validation Framework

This module provides a comprehensive validation framework for the Instinct AI trading platform.
It includes a Validator class for complex validation scenarios and individual validation functions
for common use cases.
"""

import re
import ipaddress
from datetime import datetime
from typing import Any, Dict, List, Tuple, Set, Optional, Union, TypeVar, Generic, Callable
from enum import Enum

# Import basic validators
from .validators import (
    validate_numeric_range,
    validate_string_choice,
    validate_list_length,
    validate_type,
    validate_url,
    validate_email
)

T = TypeVar('T')


class ValidationError(Exception):
    """Exception raised for validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(self.message)


class ValidationResult:
    """Result of a validation operation."""
    
    def __init__(self, is_valid: bool, errors: Optional[List[ValidationError]] = None):
        self.is_valid = is_valid
        self.errors = errors or []
    
    def __bool__(self) -> bool:
        return self.is_valid
    
    def add_error(self, error: ValidationError) -> None:
        """Add an error to the validation result."""
        self.errors.append(error)
        self.is_valid = False
    
    def merge(self, other: 'ValidationResult') -> None:
        """Merge another validation result into this one."""
        if not other.is_valid:
            self.is_valid = False
            self.errors.extend(other.errors)


class Validator:
    """
    Validator class for complex validation scenarios.
    
    This class provides a fluent interface for building validation rules
    and applying them to values.
    
    Example:
        validator = Validator()
        result = validator.validate(
            value,
            validator.rules.type(int).range(1, 100)
        )
        
        if not result:
            for error in result.errors:
                print(error.message)
    """
    
    class Rules:
        """Container for validation rule builders."""
        
        def __init__(self, validator: 'Validator'):
            self._validator = validator
            self._rules = []
        
        def type(self, expected_type: Union[type, Tuple[type, ...]]) -> 'Validator.Rules':
            """Validate that a value is of the expected type."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_type(value, expected_type, field)
            )
            return self
        
        def range(self, min_value: Optional[Union[int, float]] = None, 
                 max_value: Optional[Union[int, float]] = None,
                 inclusive: bool = True) -> 'Validator.Rules':
            """Validate that a numeric value is within a specified range."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_range(
                    value, min_value, max_value, inclusive, field
                )
            )
            return self
        
        def choice(self, choices: Union[List[Any], Set[Any], Tuple[Any, ...]]) -> 'Validator.Rules':
            """Validate that a value is one of the allowed choices."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_choice(value, choices, field)
            )
            return self
        
        def length(self, min_length: Optional[int] = None, 
                  max_length: Optional[int] = None) -> 'Validator.Rules':
            """Validate that a sequence has a length within the specified range."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_length(
                    value, min_length, max_length, field
                )
            )
            return self
        
        def pattern(self, pattern: str) -> 'Validator.Rules':
            """Validate that a string matches a regular expression pattern."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_pattern(value, pattern, field)
            )
            return self
        
        def email(self) -> 'Validator.Rules':
            """Validate that a string is a valid email address."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_email(value, field)
            )
            return self
        
        def url(self) -> 'Validator.Rules':
            """Validate that a string is a valid URL."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_url(value, field)
            )
            return self
        
        def ip_address(self) -> 'Validator.Rules':
            """Validate that a string is a valid IP address."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_ip_address(value, field)
            )
            return self
        
        def date(self, format: str = "%Y-%m-%d") -> 'Validator.Rules':
            """Validate that a string is a valid date in the specified format."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_date(value, format, field)
            )
            return self
        
        def custom(self, func: Callable[[Any], bool], 
                  error_message: str = "Validation failed") -> 'Validator.Rules':
            """Add a custom validation function."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_custom(
                    value, func, error_message, field
                )
            )
            return self
        
        def required(self) -> 'Validator.Rules':
            """Validate that a value is not None."""
            self._rules.append(
                lambda value, field=None: self._validator._validate_required(value, field)
            )
            return self
        
        def apply(self, value: Any, field: Optional[str] = None) -> ValidationResult:
            """Apply all rules to a value."""
            result = ValidationResult(True)
            
            for rule in self._rules:
                rule_result = rule(value, field)
                result.merge(rule_result)
                
                if not result.is_valid and self._validator._fail_fast:
                    break
            
            return result
    
    def __init__(self, fail_fast: bool = False):
        """
        Initialize the validator.
        
        Args:
            fail_fast: Whether to stop validation after the first failure
        """
        self._fail_fast = fail_fast
        self.rules = self.Rules(self)
    
    def validate(self, value: Any, rules: Rules, field: Optional[str] = None) -> ValidationResult:
        """
        Validate a value against a set of rules.
        
        Args:
            value: The value to validate
            rules: The rules to apply
            field: Optional field name for error reporting
            
        Returns:
            A ValidationResult object
        """
        return rules.apply(value, field)
    
    def validate_dict(self, data: Dict[str, Any], 
                     schema: Dict[str, Rules]) -> ValidationResult:
        """
        Validate a dictionary against a schema.
        
        Args:
            data: The dictionary to validate
            schema: A dictionary mapping field names to validation rules
            
        Returns:
            A ValidationResult object
        """
        result = ValidationResult(True)
        
        for field, rules in schema.items():
            if field in data:
                field_result = self.validate(data[field], rules, field)
                result.merge(field_result)
                
                if not result.is_valid and self._fail_fast:
                    break
            else:
                # Check if the field is required
                is_required = any(
                    isinstance(rule, Callable) and rule.__name__ == '_validate_required'
                    for rule in rules._rules
                )
                
                if is_required:
                    result.add_error(ValidationError(f"Field '{field}' is required", field, None))
                    
                    if self._fail_fast:
                        break
        
        return result
    
    def _validate_type(self, value: Any, expected_type: Union[type, Tuple[type, ...]], 
                      field: Optional[str] = None) -> ValidationResult:
        """Validate that a value is of the expected type."""
        result = ValidationResult(True)
        
        if not isinstance(value, expected_type):
            type_name = (
                expected_type.__name__ if isinstance(expected_type, type)
                else ' or '.join(t.__name__ for t in expected_type)
            )
            
            result.add_error(ValidationError(
                f"Expected {type_name}, got {type(value).__name__}",
                field,
                value
            ))
        
        return result
    
    def _validate_range(self, value: Any, min_value: Optional[Union[int, float]],
                       max_value: Optional[Union[int, float]], inclusive: bool,
                       field: Optional[str] = None) -> ValidationResult:
        """Validate that a numeric value is within a specified range."""
        result = ValidationResult(True)
        
        if not isinstance(value, (int, float)):
            result.add_error(ValidationError(
                f"Expected numeric value, got {type(value).__name__}",
                field,
                value
            ))
            return result
        
        if min_value is not None and max_value is not None:
            if inclusive:
                if not (min_value <= value <= max_value):
                    result.add_error(ValidationError(
                        f"Value must be between {min_value} and {max_value} (inclusive)",
                        field,
                        value
                    ))
            else:
                if not (min_value < value < max_value):
                    result.add_error(ValidationError(
                        f"Value must be between {min_value} and {max_value} (exclusive)",
                        field,
                        value
                    ))
        elif min_value is not None:
            if inclusive:
                if value < min_value:
                    result.add_error(ValidationError(
                        f"Value must be at least {min_value}",
                        field,
                        value
                    ))
            else:
                if value <= min_value:
                    result.add_error(ValidationError(
                        f"Value must be greater than {min_value}",
                        field,
                        value
                    ))
        elif max_value is not None:
            if inclusive:
                if value > max_value:
                    result.add_error(ValidationError(
                        f"Value must be at most {max_value}",
                        field,
                        value
                    ))
            else:
                if value >= max_value:
                    result.add_error(ValidationError(
                        f"Value must be less than {max_value}",
                        field,
                        value
                    ))
        
        return result
    
    def _validate_choice(self, value: Any, choices: Union[List[Any], Set[Any], Tuple[Any, ...]],
                        field: Optional[str] = None) -> ValidationResult:
        """Validate that a value is one of the allowed choices."""
        result = ValidationResult(True)
        
        if value not in choices:
            choices_str = ', '.join(str(c) for c in choices)
            result.add_error(ValidationError(
                f"Value must be one of: {choices_str}",
                field,
                value
            ))
        
        return result
    
    def _validate_length(self, value: Any, min_length: Optional[int],
                        max_length: Optional[int], field: Optional[str] = None) -> ValidationResult:
        """Validate that a sequence has a length within the specified range."""
        result = ValidationResult(True)
        
        try:
            length = len(value)
        except (TypeError, AttributeError):
            result.add_error(ValidationError(
                f"Expected a sequence with a length, got {type(value).__name__}",
                field,
                value
            ))
            return result
        
        if min_length is not None and max_length is not None:
            if not (min_length <= length <= max_length):
                result.add_error(ValidationError(
                    f"Length must be between {min_length} and {max_length}",
                    field,
                    value
                ))
        elif min_length is not None:
            if length < min_length:
                result.add_error(ValidationError(
                    f"Length must be at least {min_length}",
                    field,
                    value
                ))
        elif max_length is not None:
            if length > max_length:
                result.add_error(ValidationError(
                    f"Length must be at most {max_length}",
                    field,
                    value
                ))
        
        return result
    
    def _validate_pattern(self, value: Any, pattern: str,
                         field: Optional[str] = None) -> ValidationResult:
        """Validate that a string matches a regular expression pattern."""
        result = ValidationResult(True)
        
        if not isinstance(value, str):
            result.add_error(ValidationError(
                f"Expected string, got {type(value).__name__}",
                field,
                value
            ))
            return result
        
        if not re.match(pattern, value):
            result.add_error(ValidationError(
                f"Value does not match pattern: {pattern}",
                field,
                value
            ))
        
        return result
    
    def _validate_email(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """Validate that a string is a valid email address."""
        result = ValidationResult(True)
        
        if not isinstance(value, str):
            result.add_error(ValidationError(
                f"Expected string, got {type(value).__name__}",
                field,
                value
            ))
            return result
        
        if not validate_email(value):
            result.add_error(ValidationError(
                "Invalid email address",
                field,
                value
            ))
        
        return result
    
    def _validate_url(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """Validate that a string is a valid URL."""
        result = ValidationResult(True)
        
        if not isinstance(value, str):
            result.add_error(ValidationError(
                f"Expected string, got {type(value).__name__}",
                field,
                value
            ))
            return result
        
        if not validate_url(value):
            result.add_error(ValidationError(
                "Invalid URL",
                field,
                value
            ))
        
        return result
    
    def _validate_ip_address(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """Validate that a string is a valid IP address."""
        result = ValidationResult(True)
        
        if not isinstance(value, str):
            result.add_error(ValidationError(
                f"Expected string, got {type(value).__name__}",
                field,
                value
            ))
            return result
        
        try:
            ipaddress.ip_address(value)
        except ValueError:
            result.add_error(ValidationError(
                "Invalid IP address",
                field,
                value
            ))
        
        return result
    
    def _validate_date(self, value: Any, format: str,
                      field: Optional[str] = None) -> ValidationResult:
        """Validate that a string is a valid date in the specified format."""
        result = ValidationResult(True)
        
        if not isinstance(value, str):
            result.add_error(ValidationError(
                f"Expected string, got {type(value).__name__}",
                field,
                value
            ))
            return result
        
        try:
            datetime.strptime(value, format)
        except ValueError:
            result.add_error(ValidationError(
                f"Invalid date format, expected {format}",
                field,
                value
            ))
        
        return result
    
    def _validate_custom(self, value: Any, func: Callable[[Any], bool],
                        error_message: str, field: Optional[str] = None) -> ValidationResult:
        """Apply a custom validation function."""
        result = ValidationResult(True)
        
        if not func(value):
            result.add_error(ValidationError(
                error_message,
                field,
                value
            ))
        
        return result
    
    def _validate_required(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """Validate that a value is not None."""
        result = ValidationResult(True)
        
        if value is None:
            result.add_error(ValidationError(
                "Value is required",
                field,
                value
            ))
        
        return result


# Create a singleton instance
validator = Validator()


def validate_ip_address(value: str) -> bool:
    """
    Validate that a string is a valid IP address.
    
    Args:
        value: The string to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        ipaddress.ip_address(value)
        return True
    except (ValueError, TypeError):
        return False


def validate_date(value: str, format: str = "%Y-%m-%d") -> bool:
    """
    Validate that a string is a valid date in the specified format.
    
    Args:
        value: The string to validate
        format: The expected date format
        
    Returns:
        True if valid, False otherwise
    """
    try:
        datetime.strptime(value, format)
        return True
    except (ValueError, TypeError):
        return False


def validate_dict_schema(data: Dict[str, Any], schema: Dict[str, Dict[str, Any]]) -> Tuple[bool, Dict[str, str]]:
    """
    Validate a dictionary against a schema.
    
    Args:
        data: The dictionary to validate
        schema: A dictionary mapping field names to validation rules
        
    Returns:
        A tuple of (is_valid, errors)
    """
    errors = {}
    
    for field, rules in schema.items():
        # Check if field is required
        required = rules.get('required', False)
        
        if field not in data:
            if required:
                errors[field] = "Field is required"
            continue
        
        value = data[field]
        
        # Check type
        if 'type' in rules:
            expected_type = rules['type']
            if not validate_type(value, expected_type):
                type_name = (
                    expected_type.__name__ if isinstance(expected_type, type)
                    else ' or '.join(t.__name__ for t in expected_type)
                )
                errors[field] = f"Expected {type_name}, got {type(value).__name__}"
                continue
        
        # Check range
        if 'min_value' in rules or 'max_value' in rules:
            min_value = rules.get('min_value')
            max_value = rules.get('max_value')
            inclusive = rules.get('inclusive', True)
            
            if not validate_numeric_range(value, min_value, max_value, inclusive):
                if min_value is not None and max_value is not None:
                    errors[field] = f"Value must be between {min_value} and {max_value}"
                elif min_value is not None:
                    errors[field] = f"Value must be at least {min_value}"
                else:
                    errors[field] = f"Value must be at most {max_value}"
                continue
        
        # Check choices
        if 'choices' in rules:
            choices = rules['choices']
            if not validate_string_choice(value, choices):
                choices_str = ', '.join(str(c) for c in choices)
                errors[field] = f"Value must be one of: {choices_str}"
                continue
        
        # Check length
        if 'min_length' in rules or 'max_length' in rules:
            min_length = rules.get('min_length')
            max_length = rules.get('max_length')
            
            if not validate_list_length(value, min_length, max_length):
                if min_length is not None and max_length is not None:
                    errors[field] = f"Length must be between {min_length} and {max_length}"
                elif min_length is not None:
                    errors[field] = f"Length must be at least {min_length}"
                else:
                    errors[field] = f"Length must be at most {max_length}"
                continue
        
        # Check pattern
        if 'pattern' in rules:
            pattern = rules['pattern']
            if not isinstance(value, str) or not re.match(pattern, value):
                errors[field] = f"Value does not match pattern: {pattern}"
                continue
        
        # Check email
        if rules.get('email', False):
            if not validate_email(value):
                errors[field] = "Invalid email address"
                continue
        
        # Check URL
        if rules.get('url', False):
            if not validate_url(value):
                errors[field] = "Invalid URL"
                continue
        
        # Check IP address
        if rules.get('ip_address', False):
            if not validate_ip_address(value):
                errors[field] = "Invalid IP address"
                continue
        
        # Check date
        if rules.get('date', False):
            format = rules.get('date_format', "%Y-%m-%d")
            if not validate_date(value, format):
                errors[field] = f"Invalid date format, expected {format}"
                continue
        
        # Custom validation
        if 'custom' in rules:
            custom_func = rules['custom']
            if not custom_func(value):
                errors[field] = rules.get('error_message', "Validation failed")
                continue
    
    return len(errors) == 0, errors 