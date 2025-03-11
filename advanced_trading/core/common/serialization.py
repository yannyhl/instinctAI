"""
Serialization Utilities

This module provides utilities for serializing and deserializing data in various formats.
"""

import json
import pickle
import base64
import gzip
import zlib
import hashlib
import logging
from typing import Any, Dict, List, Optional, Union, Callable, Type, TypeVar
from datetime import datetime, date, time
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SerializationError(Exception):
    """Exception raised for serialization errors."""
    pass


class DeserializationError(Exception):
    """Exception raised for deserialization errors."""
    pass


class SerializationFormat(str, Enum):
    """Supported serialization formats."""
    JSON = "json"
    PICKLE = "pickle"
    COMPRESSED_JSON = "compressed_json"
    COMPRESSED_PICKLE = "compressed_pickle"


class JSONEncoder(json.JSONEncoder):
    """
    Extended JSON encoder with support for additional types.
    
    This encoder adds support for:
    - datetime, date, and time objects
    - Enum values
    - Path objects
    - Sets
    - Objects with a to_dict method
    - Objects with a __dict__ attribute
    """
    
    def default(self, obj):
        # Handle datetime objects
        if isinstance(obj, datetime):
            return {"__datetime__": obj.isoformat()}
        
        # Handle date objects
        if isinstance(obj, date):
            return {"__date__": obj.isoformat()}
        
        # Handle time objects
        if isinstance(obj, time):
            return {"__time__": obj.isoformat()}
        
        # Handle Enum values
        if isinstance(obj, Enum):
            return {"__enum__": {"name": obj.__class__.__name__, "value": obj.value}}
        
        # Handle Path objects
        if isinstance(obj, Path):
            return {"__path__": str(obj)}
        
        # Handle sets
        if isinstance(obj, set):
            return {"__set__": list(obj)}
        
        # Handle objects with a to_dict method
        if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
            return {"__object__": {"class": obj.__class__.__name__, "data": obj.to_dict()}}
        
        # Handle objects with a __dict__ attribute
        if hasattr(obj, "__dict__"):
            return {"__object__": {"class": obj.__class__.__name__, "data": obj.__dict__}}
        
        # Let the base class handle it or raise an error
        return super().default(obj)


def json_object_hook(obj: Dict[str, Any]) -> Any:
    """
    JSON object hook for deserializing custom types.
    
    Args:
        obj: The JSON object to deserialize
        
    Returns:
        The deserialized object
    """
    # Handle datetime objects
    if "__datetime__" in obj:
        try:
            return datetime.fromisoformat(obj["__datetime__"])
        except ValueError as e:
            logger.warning(f"Failed to deserialize datetime: {e}")
            return obj
    
    # Handle date objects
    if "__date__" in obj:
        try:
            return date.fromisoformat(obj["__date__"])
        except ValueError as e:
            logger.warning(f"Failed to deserialize date: {e}")
            return obj
    
    # Handle time objects
    if "__time__" in obj:
        try:
            return time.fromisoformat(obj["__time__"])
        except ValueError as e:
            logger.warning(f"Failed to deserialize time: {e}")
            return obj
    
    # Handle Enum values
    if "__enum__" in obj:
        enum_data = obj["__enum__"]
        # Note: This requires the Enum class to be available in the current context
        # In practice, you would need to register Enum classes or use a more sophisticated approach
        return obj
    
    # Handle Path objects
    if "__path__" in obj:
        return Path(obj["__path__"])
    
    # Handle sets
    if "__set__" in obj:
        return set(obj["__set__"])
    
    # Handle objects
    if "__object__" in obj:
        # Note: This requires the class to be available in the current context
        # In practice, you would need to register classes or use a more sophisticated approach
        return obj
    
    return obj


def serialize_to_json(obj: Any, indent: Optional[int] = None, sort_keys: bool = False) -> str:
    """
    Serialize an object to a JSON string.
    
    Args:
        obj: The object to serialize
        indent: Number of spaces for indentation (None for compact representation)
        sort_keys: Whether to sort dictionary keys
        
    Returns:
        JSON string representation of the object
        
    Raises:
        SerializationError: If serialization fails
    """
    try:
        return json.dumps(obj, cls=JSONEncoder, indent=indent, sort_keys=sort_keys)
    except Exception as e:
        raise SerializationError(f"Failed to serialize to JSON: {e}") from e


def deserialize_from_json(json_str: str) -> Any:
    """
    Deserialize an object from a JSON string.
    
    Args:
        json_str: JSON string to deserialize
        
    Returns:
        The deserialized object
        
    Raises:
        DeserializationError: If deserialization fails
    """
    try:
        return json.loads(json_str, object_hook=json_object_hook)
    except Exception as e:
        raise DeserializationError(f"Failed to deserialize from JSON: {e}") from e


def serialize_to_pickle(obj: Any) -> bytes:
    """
    Serialize an object to a pickle byte string.
    
    Args:
        obj: The object to serialize
        
    Returns:
        Pickle byte string representation of the object
        
    Raises:
        SerializationError: If serialization fails
    """
    try:
        return pickle.dumps(obj)
    except Exception as e:
        raise SerializationError(f"Failed to serialize to pickle: {e}") from e


def deserialize_from_pickle(pickle_bytes: bytes) -> Any:
    """
    Deserialize an object from a pickle byte string.
    
    Args:
        pickle_bytes: Pickle byte string to deserialize
        
    Returns:
        The deserialized object
        
    Raises:
        DeserializationError: If deserialization fails
    """
    try:
        return pickle.loads(pickle_bytes)
    except Exception as e:
        raise DeserializationError(f"Failed to deserialize from pickle: {e}") from e


def compress_data(data: bytes, method: str = "gzip") -> bytes:
    """
    Compress binary data.
    
    Args:
        data: The data to compress
        method: Compression method ("gzip" or "zlib")
        
    Returns:
        Compressed data
        
    Raises:
        ValueError: If the compression method is not supported
    """
    if method == "gzip":
        return gzip.compress(data)
    elif method == "zlib":
        return zlib.compress(data)
    else:
        raise ValueError(f"Unsupported compression method: {method}")


def decompress_data(data: bytes, method: str = "gzip") -> bytes:
    """
    Decompress binary data.
    
    Args:
        data: The data to decompress
        method: Compression method ("gzip" or "zlib")
        
    Returns:
        Decompressed data
        
    Raises:
        ValueError: If the compression method is not supported
    """
    if method == "gzip":
        return gzip.decompress(data)
    elif method == "zlib":
        return zlib.decompress(data)
    else:
        raise ValueError(f"Unsupported compression method: {method}")


def serialize(obj: Any, format: SerializationFormat = SerializationFormat.JSON) -> Union[str, bytes]:
    """
    Serialize an object to the specified format.
    
    Args:
        obj: The object to serialize
        format: The serialization format
        
    Returns:
        Serialized representation of the object
        
    Raises:
        SerializationError: If serialization fails
        ValueError: If the format is not supported
    """
    if format == SerializationFormat.JSON:
        return serialize_to_json(obj)
    elif format == SerializationFormat.PICKLE:
        return serialize_to_pickle(obj)
    elif format == SerializationFormat.COMPRESSED_JSON:
        json_str = serialize_to_json(obj)
        return compress_data(json_str.encode("utf-8"))
    elif format == SerializationFormat.COMPRESSED_PICKLE:
        pickle_bytes = serialize_to_pickle(obj)
        return compress_data(pickle_bytes)
    else:
        raise ValueError(f"Unsupported serialization format: {format}")


def deserialize(data: Union[str, bytes], format: SerializationFormat = SerializationFormat.JSON) -> Any:
    """
    Deserialize an object from the specified format.
    
    Args:
        data: The serialized data
        format: The serialization format
        
    Returns:
        The deserialized object
        
    Raises:
        DeserializationError: If deserialization fails
        ValueError: If the format is not supported
    """
    if format == SerializationFormat.JSON:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return deserialize_from_json(data)
    elif format == SerializationFormat.PICKLE:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return deserialize_from_pickle(data)
    elif format == SerializationFormat.COMPRESSED_JSON:
        if isinstance(data, str):
            data = data.encode("utf-8")
        decompressed = decompress_data(data)
        return deserialize_from_json(decompressed.decode("utf-8"))
    elif format == SerializationFormat.COMPRESSED_PICKLE:
        if isinstance(data, str):
            data = data.encode("utf-8")
        decompressed = decompress_data(data)
        return deserialize_from_pickle(decompressed)
    else:
        raise ValueError(f"Unsupported serialization format: {format}")


def serialize_to_file(obj: Any, file_path: Union[str, Path], 
                     format: SerializationFormat = SerializationFormat.JSON) -> None:
    """
    Serialize an object to a file.
    
    Args:
        obj: The object to serialize
        file_path: Path to the output file
        format: The serialization format
        
    Raises:
        SerializationError: If serialization fails
        ValueError: If the format is not supported
        IOError: If file operations fail
    """
    file_path = Path(file_path)
    
    # Create directory if it doesn't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        data = serialize(obj, format)
        
        # Determine the mode based on the data type
        mode = "wb" if isinstance(data, bytes) else "w"
        
        with open(file_path, mode) as f:
            f.write(data)
    except Exception as e:
        raise SerializationError(f"Failed to serialize to file {file_path}: {e}") from e


def deserialize_from_file(file_path: Union[str, Path], 
                         format: SerializationFormat = SerializationFormat.JSON) -> Any:
    """
    Deserialize an object from a file.
    
    Args:
        file_path: Path to the input file
        format: The serialization format
        
    Returns:
        The deserialized object
        
    Raises:
        DeserializationError: If deserialization fails
        ValueError: If the format is not supported
        FileNotFoundError: If the file does not exist
        IOError: If file operations fail
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        # Determine the mode based on the format
        mode = "rb" if format in [SerializationFormat.PICKLE, 
                                 SerializationFormat.COMPRESSED_JSON, 
                                 SerializationFormat.COMPRESSED_PICKLE] else "r"
        
        with open(file_path, mode) as f:
            data = f.read()
        
        return deserialize(data, format)
    except Exception as e:
        raise DeserializationError(f"Failed to deserialize from file {file_path}: {e}") from e


def calculate_hash(data: Union[str, bytes], algorithm: str = "sha256") -> str:
    """
    Calculate a hash of the data.
    
    Args:
        data: The data to hash
        algorithm: The hash algorithm to use
        
    Returns:
        The hash as a hexadecimal string
        
    Raises:
        ValueError: If the algorithm is not supported
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    
    if algorithm == "md5":
        return hashlib.md5(data).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(data).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(data).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(data).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def serialize_to_base64(obj: Any, format: SerializationFormat = SerializationFormat.JSON) -> str:
    """
    Serialize an object to a base64-encoded string.
    
    Args:
        obj: The object to serialize
        format: The serialization format
        
    Returns:
        Base64-encoded string representation of the object
        
    Raises:
        SerializationError: If serialization fails
        ValueError: If the format is not supported
    """
    data = serialize(obj, format)
    
    if isinstance(data, str):
        data = data.encode("utf-8")
    
    return base64.b64encode(data).decode("utf-8")


def deserialize_from_base64(base64_str: str, format: SerializationFormat = SerializationFormat.JSON) -> Any:
    """
    Deserialize an object from a base64-encoded string.
    
    Args:
        base64_str: Base64-encoded string to deserialize
        format: The serialization format
        
    Returns:
        The deserialized object
        
    Raises:
        DeserializationError: If deserialization fails
        ValueError: If the format is not supported
    """
    try:
        data = base64.b64decode(base64_str)
        return deserialize(data, format)
    except Exception as e:
        raise DeserializationError(f"Failed to deserialize from base64: {e}") from e 