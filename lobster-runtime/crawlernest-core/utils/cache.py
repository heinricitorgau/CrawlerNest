"""
Simple caching utilities.
"""

import time
from typing import Any, Optional


class SimpleCache:
    """Simple time-based cache implementation."""
    
    def __init__(self, ttl: int = 3600):
        """
        Initialize cache.
        
        Args:
            ttl: Time to live in seconds (default: 1 hour)
        """
        self.cache = {}
        self.timestamps = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if key not in self.cache:
            return None
        
        if time.time() - self.timestamps[key] > self.ttl:
            del self.cache[key]
            del self.timestamps[key]
            return None
        
        return self.cache[key]
    
    def set(self, key: str, value: Any):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def clear(self):
        """Clear all cached values."""
        self.cache.clear()
        self.timestamps.clear()
