"""
Configuration settings for the Health Assistant application.
Supports multiple API keys with automatic rotation on rate limit.
"""

import os
import time
from pathlib import Path
from typing import List, Optional

# ============================================================================
# API KEY MANAGEMENT WITH ROTATION
# ============================================================================

class APIKeyManager:
    """
    Manages multiple Google API keys with automatic rotation on rate limit.
    Keys that hit rate limits are temporarily disabled.
    """
    
    def __init__(self):
        self.api_keys: List[str] = []
        self.current_index: int = 0
        self.rate_limited_keys: dict = {}  # key -> timestamp when it was rate limited
        self.rate_limit_cooldown: int = 60  # seconds to wait before retrying a rate-limited key
        self._load_keys()
    
    def _load_keys(self):
        """Load API keys from secrets.txt and environment variable."""
        keys = []
        
        # Load from secrets.txt (supports multiple keys, one per line)
        secrets_file = Path(__file__).parent / "secrets.txt"
        if secrets_file.exists():
            with open(secrets_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GOOGLE_API_KEY"):
                        # Handle both GOOGLE_API_KEY=xxx and GOOGLE_API_KEY_1=xxx formats
                        if "=" in line:
                            key = line.split("=", 1)[1].strip()
                            if key and key not in keys:
                                keys.append(key)
        
        # Also check environment variable
        env_key = os.environ.get("GOOGLE_API_KEY", "")
        if env_key and env_key not in keys:
            keys.append(env_key)
        
        self.api_keys = keys
        print(f"✅ Loaded {len(self.api_keys)} API key(s)")
    
    def get_current_key(self) -> Optional[str]:
        """Get the current active API key."""
        if not self.api_keys:
            return None
        return self.api_keys[self.current_index]
    
    def get_available_key(self) -> Optional[str]:
        """Get an available API key, skipping rate-limited ones."""
        if not self.api_keys:
            return None
        
        current_time = time.time()
        
        # Try each key starting from current index
        for i in range(len(self.api_keys)):
            index = (self.current_index + i) % len(self.api_keys)
            key = self.api_keys[index]
            
            # Check if key is rate limited
            if key in self.rate_limited_keys:
                limited_time = self.rate_limited_keys[key]
                if current_time - limited_time < self.rate_limit_cooldown:
                    continue  # Still in cooldown
                else:
                    # Cooldown expired, remove from rate limited
                    del self.rate_limited_keys[key]
            
            # Found an available key
            self.current_index = index
            return key
        
        # All keys are rate limited, return the one with oldest rate limit
        if self.rate_limited_keys:
            oldest_key = min(self.rate_limited_keys.keys(), 
                           key=lambda k: self.rate_limited_keys[k])
            # Wait for cooldown
            wait_time = self.rate_limit_cooldown - (current_time - self.rate_limited_keys[oldest_key])
            if wait_time > 0:
                print(f"⏳ All keys rate limited. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
            del self.rate_limited_keys[oldest_key]
            self.current_index = self.api_keys.index(oldest_key)
            return oldest_key
        
        return self.api_keys[self.current_index]
    
    def mark_rate_limited(self, key: str = None):
        """Mark a key as rate limited and switch to next available."""
        if key is None:
            key = self.get_current_key()
        
        if key:
            self.rate_limited_keys[key] = time.time()
            print(f"⚠️ API key ending in ...{key[-4:]} hit rate limit. Rotating...")
            
            # Try to get next available key
            next_key = self.get_available_key()
            if next_key:
                print(f"✅ Switched to API key ending in ...{next_key[-4:]}")
    
    def rotate_key(self):
        """Manually rotate to the next API key."""
        if len(self.api_keys) > 1:
            self.current_index = (self.current_index + 1) % len(self.api_keys)
            print(f"🔄 Rotated to API key ending in ...{self.api_keys[self.current_index][-4:]}")
    
    def get_key_count(self) -> int:
        """Get the total number of API keys."""
        return len(self.api_keys)
    
    def get_available_key_count(self) -> int:
        """Get the number of currently available (non-rate-limited) keys."""
        current_time = time.time()
        available = 0
        for key in self.api_keys:
            if key not in self.rate_limited_keys:
                available += 1
            elif current_time - self.rate_limited_keys[key] >= self.rate_limit_cooldown:
                available += 1
        return available


# Global API Key Manager instance
api_key_manager = APIKeyManager()

# For backward compatibility
GOOGLE_API_KEY = api_key_manager.get_current_key() or ""

# Model Configuration
MODEL_NAME = "gemini-2.5-flash"
MODEL_TEMPERATURE = 0

# Rate Limiting
API_DELAY = 3  # Delay between API calls in seconds

# Intent Keywords
FOOD_KEYWORDS = ["food analysis", "food", "analyze food", "ingredient", "nutrition"]
MEDICAL_KEYWORDS = ["health help", "medical", "health", "symptoms", "sick", "pain", "medicine"]

# Medical Commands (used to detect if user provided actual symptoms vs just command)
MEDICAL_COMMANDS = ["health help", "medical", "health", "medical help", "food analysis", "food"]

# Food Indicators (for classifying ambiguous input)
FOOD_INDICATORS = ["turmeric", "msg", "sugar", "cola", "ingredient", "eat", "food"]
