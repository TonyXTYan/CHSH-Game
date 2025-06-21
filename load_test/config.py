"""
Configuration management for CHSH Game load testing.

Provides validation, default values, and loading from files.
"""

import yaml
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator, computed_field
from pathlib import Path


class ResponsePatternType(Enum):
    """Response timing patterns for simulating different user behaviors."""
    RANDOM = "random"
    BURST = "burst"
    STEADY = "steady"
    HUMAN_LIKE = "human_like"


class ConnectionStrategy(Enum):
    """Strategies for establishing Socket.io connections."""
    GRADUAL = "gradual"    # Connect at specified rate
    BURST = "burst"        # Connect in batches
    IMMEDIATE = "immediate"  # All connections at once


class OutputFormat(Enum):
    """Output format options for test results."""
    CONSOLE = "console"
    JSON = "json"
    CSV = "csv"


class LoadTestConfig(BaseModel):
    """
    Configuration model for CHSH Game load testing.
    
    Uses Pydantic for validation and type checking.
    """
    
    # Server Configuration
    deployment_url: str = Field(
        default="http://localhost:8080",
        description="Target server URL for load testing"
    )
    
    # Load Parameters
    num_teams: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Number of teams to create (2 players each)"
    )
    
    # Connection Strategy
    connection_strategy: ConnectionStrategy = Field(
        default=ConnectionStrategy.GRADUAL,
        description="Strategy for establishing connections"
    )
    
    connections_per_second: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Connection rate for gradual strategy"
    )
    
    burst_size: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Batch size for burst connection strategy"
    )
    
    # Response Simulation
    response_pattern: ResponsePatternType = Field(
        default=ResponsePatternType.HUMAN_LIKE,
        description="Response timing pattern simulation"
    )
    
    min_response_delay: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description="Minimum response delay in seconds"
    )
    
    max_response_delay: float = Field(
        default=3.0,
        ge=1.0,
        le=10.0,
        description="Maximum response delay in seconds"
    )
    
    # Test Duration & Limits
    max_test_duration: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Maximum test duration in seconds"
    )
    
    max_rounds_per_team: int = Field(
        default=50,
        ge=5,
        le=200,
        description="Maximum rounds per team before stopping"
    )
    
    connection_timeout: float = Field(
        default=10.0,
        ge=5.0,
        le=60.0,
        description="Socket.io connection timeout in seconds"
    )
    
    answer_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Answer submission timeout in seconds"
    )
    
    # Output & Reporting
    output_format: OutputFormat = Field(
        default=OutputFormat.CONSOLE,
        description="Output format for test results"
    )
    
    save_results: bool = Field(
        default=True,
        description="Save detailed results to file"
    )
    
    results_dir: str = Field(
        default="./load_test_results",
        description="Directory to save results"
    )
    
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # Advanced Options
    enable_dashboard_simulation: bool = Field(
        default=True,
        description="Simulate dashboard game control"
    )
    
    simulate_disconnections: bool = Field(
        default=False,
        description="Randomly simulate player disconnections"
    )
    
    disconnection_rate: float = Field(
        default=0.05,
        ge=0.0,
        le=0.5,
        description="Probability of random disconnection per player"
    )
    
    @computed_field
    @property
    def total_players(self) -> int:
        """Calculate total number of players (2 per team)."""
        return self.num_teams * 2
    
    @validator('max_response_delay')
    def validate_response_delays(cls, v, values):
        """Ensure max_response_delay > min_response_delay."""
        if 'min_response_delay' in values and v <= values['min_response_delay']:
            raise ValueError('max_response_delay must be greater than min_response_delay')
        return v
    
    @validator('deployment_url')
    def validate_url(cls, v):
        """Validate URL format."""
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('deployment_url must start with http:// or https://')
        return v.rstrip('/')  # Remove trailing slash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.dict()
    
    def save_to_file(self, filepath: Path) -> None:
        """Save configuration to YAML file."""
        config_dict = self.to_dict()
        
        # Convert enums to their values for YAML serialization
        for key, value in config_dict.items():
            if hasattr(value, 'value'):
                config_dict[key] = value.value
        
        with open(filepath, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)


def load_config_from_file(filepath: str) -> LoadTestConfig:
    """
    Load configuration from YAML file.
    
    Args:
        filepath: Path to YAML configuration file
        
    Returns:
        LoadTestConfig instance
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If configuration is invalid
    """
    config_path = Path(filepath)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {filepath}")
    
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    # Convert string enum values back to enum instances
    if 'response_pattern' in config_data:
        config_data['response_pattern'] = ResponsePatternType(config_data['response_pattern'])
    
    if 'connection_strategy' in config_data:
        config_data['connection_strategy'] = ConnectionStrategy(config_data['connection_strategy'])
    
    if 'output_format' in config_data:
        config_data['output_format'] = OutputFormat(config_data['output_format'])
    
    return LoadTestConfig(**config_data)


def create_default_config() -> LoadTestConfig:
    """Create a default configuration for local testing."""
    return LoadTestConfig(
        deployment_url="http://localhost:8080",
        num_teams=10,  # Small scale for local testing
        connection_strategy=ConnectionStrategy.GRADUAL,
        connections_per_second=5,
        response_pattern=ResponsePatternType.HUMAN_LIKE,
        max_test_duration=120,  # 2 minutes for quick testing
        output_format=OutputFormat.CONSOLE
    )


def create_production_config(server_url: str, num_teams: int = 100) -> LoadTestConfig:
    """Create a production-ready configuration."""
    return LoadTestConfig(
        deployment_url=server_url,
        num_teams=num_teams,
        connection_strategy=ConnectionStrategy.GRADUAL,
        connections_per_second=10,
        response_pattern=ResponsePatternType.HUMAN_LIKE,
        max_test_duration=600,  # 10 minutes
        output_format=OutputFormat.JSON,
        save_results=True
    )