"""
Validation Utilities

Common validation functions for configuration and input parameters.
"""

from typing import Any, List, Tuple, Set, Optional, Union, TypeVar, Generic


def validate_numeric_range(value: Union[int, float], min_value: Optional[Union[int, float]] = None, 
                          max_value: Optional[Union[int, float]] = None, 
                          inclusive: bool = True) -> bool:
    """
    Validate that a numeric value is within a specified range.
    
    Args:
        value: The numeric value to validate
        min_value: Optional minimum value
        max_value: Optional maximum value
        inclusive: Whether the range bounds are inclusive
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(value, (int, float)):
        return False
        
    if min_value is not None:
        if inclusive:
            if value < min_value:
                return False
        else:
            if value <= min_value:
                return False
    
    if max_value is not None:
        if inclusive:
            if value > max_value:
                return False
        else:
            if value >= max_value:
                return False
    
    return True


def validate_string_choice(value: str, choices: Union[List[str], Set[str], Tuple[str, ...]]) -> bool:
    """
    Validate that a string value is one of the allowed choices.
    
    Args:
        value: The string value to validate
        choices: Allowed string values
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(value, str):
        return False
        
    return value in choices


def validate_list_length(value: List[Any], min_length: Optional[int] = None, 
                        max_length: Optional[int] = None) -> bool:
    """
    Validate that a list has a length within the specified range.
    
    Args:
        value: The list to validate
        min_length: Optional minimum length
        max_length: Optional maximum length
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(value, list):
        return False
        
    if min_length is not None and len(value) < min_length:
        return False
        
    if max_length is not None and len(value) > max_length:
        return False
        
    return True


def validate_type(value: Any, expected_type: Union[type, Tuple[type, ...]]) -> bool:
    """
    Validate that a value is of the expected type.
    
    Args:
        value: The value to validate
        expected_type: Expected type or tuple of types
        
    Returns:
        True if valid, False otherwise
    """
    return isinstance(value, expected_type)


def validate_url(value: str) -> bool:
    """
    Validate that a string is a valid URL.
    
    Args:
        value: The string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(value, str):
        return False
        
    # Very basic URL validation
    return (
        value.startswith(('http://', 'https://')) and 
        '.' in value and 
        ' ' not in value
    )


def validate_email(value: str) -> bool:
    """
    Validate that a string is a valid email address.
    
    Args:
        value: The string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(value, str):
        return False
        
    # Very basic email validation
    return '@' in value and '.' in value.split('@')[1] and ' ' not in value 