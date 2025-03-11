"""
API Version

This module provides version information for the API.
"""

# API version following semantic versioning (major.minor.patch)
API_VERSION = "1.0.0"

# API build information
API_BUILD = {
    "timestamp": "2023-07-01T00:00:00Z",
    "git_commit": "development",
    "build_number": "dev"
}

def get_version_info():
    """
    Get complete version information.
    
    Returns:
        Dictionary with version information.
    """
    return {
        "version": API_VERSION,
        "build": API_BUILD
    } 