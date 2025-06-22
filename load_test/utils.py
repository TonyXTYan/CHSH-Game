"""
Utility functions for CHSH Game load testing.

Common helper functions, formatting, and logging setup.
"""

import sys
import asyncio
import time
import random
import string
import logging
from typing import Any
from datetime import datetime

# Use standard logging instead of loguru
logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO"):
    """
    Setup logging configuration for the load test.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )
    
    # Configure loguru to match the log level
    import loguru
    loguru.logger.remove()  # Remove default handler
    loguru.logger.add(
        sys.stderr,
        level=log_level.upper(),
        format='{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}'
    )
    
    # Add file logger for detailed debugging (if DEBUG level)
    if log_level == "DEBUG":
        file_handler = logging.FileHandler("load_test_debug.log")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.1f}s"


def format_bytes(bytes_value: float) -> str:
    """
    Format bytes to human-readable string.
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        Formatted byte string (e.g., "1.2 MB")
    """
    if bytes_value < 1024:
        return f"{bytes_value:.0f} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.1f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.1f} GB"


def format_rate(value: float, unit: str = "ops") -> str:
    """
    Format rate value with appropriate unit.
    
    Args:
        value: Rate value
        unit: Unit name (default: "ops")
        
    Returns:
        Formatted rate string
    """
    if value < 1000:
        return f"{value:.1f} {unit}/s"
    elif value < 1000000:
        return f"{value / 1000:.1f} K{unit}/s"
    else:
        return f"{value / 1000000:.1f} M{unit}/s"


def calculate_percentile(values: list, percentile: float) -> float:
    """
    Calculate percentile from a list of values.
    
    Args:
        values: List of numeric values
        percentile: Percentile to calculate (0-100)
        
    Returns:
        Percentile value
    """
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (percentile / 100)
    f = int(k)
    c = k - f
    
    if f == len(sorted_values) - 1:
        return sorted_values[f]
    else:
        return sorted_values[f] * (1 - c) + sorted_values[f + 1] * c


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is zero.
    
    Args:
        numerator: Numerator value
        denominator: Denominator value
        default: Default value if division by zero
        
    Returns:
        Division result or default
    """
    if denominator == 0:
        return default
    return numerator / denominator


def truncate_string(text: str, max_length: int = 50) -> str:
    """
    Truncate string to maximum length with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def validate_url(url: str) -> bool:
    """
    Validate URL format.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid
    """
    import re
    
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None


def get_current_timestamp() -> str:
    """
    Get current timestamp as string.
    
    Returns:
        Timestamp string in ISO format
    """
    from datetime import datetime
    return datetime.now().isoformat()


def chunks(lst: list, n: int):
    """
    Yield successive n-sized chunks from list.
    
    Args:
        lst: List to chunk
        n: Chunk size
        
    Yields:
        Chunks of the list
    """
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """
    Calculate exponential backoff delay.
    
    Args:
        attempt: Attempt number (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        
    Returns:
        Delay in seconds
    """
    import random
    
    delay = base_delay * (2 ** attempt)
    # Add jitter to prevent thundering herd
    jitter = random.uniform(0.1, 0.3) * delay
    return min(max_delay, delay + jitter)


def create_unique_name(prefix: str, existing_names: set, max_attempts: int = 100) -> str:
    """
    Create a unique name with given prefix.
    
    Args:
        prefix: Name prefix
        existing_names: Set of existing names to avoid
        max_attempts: Maximum attempts to find unique name
        
    Returns:
        Unique name
    """
    import random
    
    for attempt in range(max_attempts):
        suffix = random.randint(1000, 9999)
        name = f"{prefix}{suffix}"
        if name not in existing_names:
            return name
    
    # Fallback to timestamp-based name
    import time
    return f"{prefix}{int(time.time() * 1000) % 100000}"


def memory_usage_mb() -> float:
    """
    Get current memory usage in MB.
    
    Returns:
        Memory usage in MB
    """
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


def cpu_percent() -> float:
    """
    Get current CPU usage percentage.
    
    Returns:
        CPU usage percentage
    """
    try:
        import psutil
        return psutil.cpu_percent(interval=None)
    except ImportError:
        return 0.0


def check_dependencies():
    """
    Check if all required dependencies are installed.
    
    Raises:
        ImportError: If required dependencies are missing
    """
    required_packages = [
        'socketio',
        'rich',
        'loguru',
        'pydantic',
        'psutil',
        'faker',
        'numpy',
        'yaml'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'socketio':
                import socketio
            elif package == 'rich':
                import rich
            elif package == 'loguru':
                import loguru
            elif package == 'pydantic':
                import pydantic
            elif package == 'psutil':
                import psutil
            elif package == 'faker':
                import faker
            elif package == 'numpy':
                import numpy
            elif package == 'yaml':
                import yaml
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        raise ImportError(f"Missing required packages: {', '.join(missing_packages)}")


class ProgressTracker:
    """Simple progress tracking utility."""
    
    def __init__(self, total: int, description: str = "Progress"):
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = None
    
    def start(self):
        """Start progress tracking."""
        import time
        self.start_time = time.time()
        self.update(0)
    
    def update(self, current: int):
        """Update progress and display"""
        if current > self.total:
            current = self.total
        
        percentage = (current / self.total) * 100
        if self.start_time is not None:
            duration = time.time() - self.start_time
        else:
            duration = 0
        
        logger.info(f"{self.description}: {current}/{self.total} ({percentage:.1f}%)")
    
    def increment(self):
        """Increment progress by 1."""
        self.update(self.current + 1)
    
    def finish(self):
        """Mark progress as complete"""
        if self.start_time is not None:
            duration = time.time() - self.start_time
            if duration > 0:
                logger.info(f"{self.description}: {self.total}/{self.total} (100.0%) - Completed in {format_duration(duration)}")
            else:
                logger.info(f"{self.description}: {self.total}/{self.total} (100.0%) - Completed")
        else:
            logger.info(f"{self.description}: {self.total}/{self.total} (100.0%) - Completed")


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retries
        base_delay: Base delay between retries
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = exponential_backoff(attempt, base_delay)
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed")
                        raise last_exception
        
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = exponential_backoff(attempt, base_delay)
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay:.2f}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed")
                        raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator