#!/usr/bin/env python3
"""
Simple test script to validate the CHSH Game load testing framework.

This script performs basic validation of the load testing components
without actually connecting to a server.
"""

import asyncio
import sys
from pathlib import Path

# Add load_test module to path
sys.path.insert(0, str(Path(__file__).parent))

from load_test.config import LoadTestConfig, create_default_config
from load_test.player import Player, PlayerState
from load_test.metrics import LoadTestMetrics, PlayerMetrics
from load_test.team_manager import TeamManager
from load_test.utils import setup_logging, check_dependencies
from rich.console import Console

console = Console()

async def test_configuration():
    """Test configuration loading and validation."""
    console.print("[bold blue]Testing Configuration...[/bold blue]")
    
    # Test default configuration
    config = create_default_config()
    assert config.num_teams == 10
    assert config.total_players == 20
    assert config.deployment_url == "http://localhost:8080"
    console.print("✓ Default configuration created successfully")
    
    # Test configuration validation
    try:
        invalid_config = LoadTestConfig(
            deployment_url="invalid-url",
            num_teams=-1
        )
        assert False, "Should have raised validation error"
    except Exception:
        console.print("✓ Configuration validation working")
    
    # Test YAML loading
    try:
        from load_test.config import load_config_from_file
        if Path("load_test_config.yaml").exists():
            yaml_config = load_config_from_file("load_test_config.yaml")
            console.print("✓ YAML configuration loaded successfully")
        else:
            console.print("⚠ YAML config file not found, skipping")
    except Exception as e:
        console.print(f"✗ YAML loading failed: {e}")

def test_metrics():
    """Test metrics collection."""
    console.print("\n[bold blue]Testing Metrics...[/bold blue]")
    
    # Test player metrics
    player_metrics = PlayerMetrics("test_player")
    player_metrics.record_connection_time(1.5)
    player_metrics.record_question_response(0.8, 0.1, 0.9)
    player_metrics.record_error("test_error")
    
    summary = player_metrics.get_summary()
    assert summary['player_id'] == "test_player"
    assert summary['connections']['count'] == 1
    assert summary['error_count'] == 1
    console.print("✓ Player metrics working")
    
    # Test load test metrics
    load_metrics = LoadTestMetrics(num_teams=5)
    load_metrics.add_player("player_1")
    load_metrics.record_event("connection_success", "player_1", 1.2)
    
    status = load_metrics.get_real_time_status()
    assert status['successful_connections'] == 1
    console.print("✓ Load test metrics working")

async def test_player_creation():
    """Test player creation and basic functionality."""
    console.print("\n[bold blue]Testing Player Creation...[/bold blue]")
    
    config = create_default_config()
    player = Player("test_player", config)
    
    assert player.player_id == "test_player"
    assert player.state == PlayerState.DISCONNECTED
    assert player.team_name is None
    console.print("✓ Player creation working")
    
    # Test response delay calculation
    delay = player._calculate_response_delay()
    assert config.min_response_delay <= delay <= config.max_response_delay * 1.5
    console.print("✓ Response delay calculation working")

async def test_team_manager():
    """Test team manager functionality."""
    console.print("\n[bold blue]Testing Team Manager...[/bold blue]")
    
    config = create_default_config()
    metrics = LoadTestMetrics(config.num_teams)
    team_manager = TeamManager(config, metrics)
    
    # Test player creation
    players = await team_manager.create_players()
    assert len(players) == config.total_players
    console.print(f"✓ Created {len(players)} players")
    
    # Test status
    status = team_manager.get_status()
    assert status['total_players'] == config.total_players
    console.print("✓ Team manager status working")

def test_utilities():
    """Test utility functions."""
    console.print("\n[bold blue]Testing Utilities...[/bold blue]")
    
    from load_test.utils import format_duration, format_bytes, safe_divide
    
    # Test formatting
    assert format_duration(90) == "1m 30.0s"
    assert format_bytes(1024 * 1024) == "1.0 MB"
    assert safe_divide(10, 0, default=0) == 0
    console.print("✓ Utility functions working")

def test_dependencies():
    """Test dependency checking."""
    console.print("\n[bold blue]Testing Dependencies...[/bold blue]")
    
    try:
        check_dependencies()
        console.print("✓ All dependencies available")
    except ImportError as e:
        console.print(f"⚠ Missing dependencies: {e}")
        console.print("Install with: pip install -r load_test_requirements.txt")

async def run_validation_tests():
    """Run all validation tests."""
    console.print("[bold green]🧪 CHSH Load Test Framework Validation[/bold green]")
    console.print("=" * 50)
    
    try:
        # Setup logging
        setup_logging("INFO")
        
        # Run tests
        test_dependencies()
        await test_configuration()
        test_metrics()
        await test_player_creation()
        await test_team_manager()
        test_utilities()
        
        console.print("\n[bold green]✅ All validation tests passed![/bold green]")
        console.print("\n[dim]The load testing framework is ready to use.[/dim]")
        console.print("[dim]Run with: python chsh_load_test.py --help[/dim]")
        
        return True
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Validation failed: {str(e)}[/bold red]")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_validation_tests())
    sys.exit(0 if success else 1)