#!/usr/bin/env python3
"""
CHSH Game Load Testing Script

A comprehensive load testing tool for the CHSH Game server that creates N teams
with 2N players and simulates realistic game interactions via Socket.io.

Usage:
    python chsh_load_test.py --url http://localhost:8080 --teams 100
    python chsh_load_test.py --config config.yaml
"""

import asyncio
import sys
import signal
import logging
from typing import Optional
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

from load_test.config import LoadTestConfig, load_config_from_file, ResponsePatternType, ConnectionStrategy, OutputFormat
from load_test.orchestrator import CHSHLoadTester
from load_test.utils import setup_logging

console = Console()

@click.command()
@click.option('--url', default='http://localhost:8080', help='Server deployment URL')
@click.option('--teams', default=100, type=int, help='Number of teams to create (default: 100)')
@click.option('--pattern', default='human_like', 
              type=click.Choice(['random', 'burst', 'steady', 'human_like']),
              help='Response pattern simulation')
@click.option('--connection-strategy', default='gradual',
              type=click.Choice(['gradual', 'burst', 'immediate']),
              help='Connection establishment strategy')
@click.option('--connections-per-second', default=10, type=int,
              help='Connection rate for gradual strategy')
@click.option('--max-duration', default=300, type=int,
              help='Maximum test duration in seconds')
@click.option('--output', default='console',
              type=click.Choice(['console', 'json', 'csv']),
              help='Output format')
@click.option('--config', type=click.Path(exists=True),
              help='Load configuration from YAML file')
@click.option('--save-results/--no-save-results', default=True,
              help='Save results to file')
@click.option('--log-level', default='INFO',
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help='Logging level')
@click.option('--dry-run', is_flag=True, help='Validate configuration without running test')
def main(url: str, teams: int, pattern: str, connection_strategy: str,
         connections_per_second: int, max_duration: int, output: str,
         config: Optional[str], save_results: bool, log_level: str, dry_run: bool):
    """CHSH Game Load Testing Script
    
    Creates N teams with 2N players and simulates realistic game interactions.
    """
    
    # Setup logging
    setup_logging(log_level)
    
    console.print("[bold blue]CHSH Game Load Tester[/bold blue]", style="bold")
    console.print("=" * 50)
    
    try:
        # Load configuration
        if config:
            test_config = load_config_from_file(config)
            console.print(f"📁 Loaded configuration from: {config}")
        else:
            test_config = LoadTestConfig(
                deployment_url=url,
                num_teams=teams,
                response_pattern=ResponsePatternType(pattern),
                connection_strategy=ConnectionStrategy(connection_strategy),
                connections_per_second=connections_per_second,
                max_test_duration=max_duration,
                output_format=OutputFormat(output),
                save_results=save_results,
                log_level=log_level
            )
        
        # Display configuration
        console.print("\n[bold green]Configuration:[/bold green]")
        console.print(f"  🌐 Server URL: {test_config.deployment_url}")
        console.print(f"  👥 Teams: {test_config.num_teams} ({test_config.total_players} players)")
        console.print(f"  ⏱️  Max Duration: {test_config.max_test_duration}s")
        console.print(f"  🎯 Response Pattern: {test_config.response_pattern}")
        console.print(f"  🔗 Connection Strategy: {test_config.connection_strategy}")
        
        if dry_run:
            console.print("\n[yellow]✓ Dry run completed - configuration is valid[/yellow]")
            return
        
        # Run the load test
        tester = CHSHLoadTester(test_config)
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            console.print("\n[red]⚠️  Received interrupt signal - shutting down gracefully...[/red]")
            asyncio.create_task(tester.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run the test
        asyncio.run(tester.run())
        
    except KeyboardInterrupt:
        console.print("\n[red]⚠️  Test interrupted by user[/red]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Load test failed: {str(e)}")
        console.print(f"\n[red]❌ Load test failed: {str(e)}[/red]")
        sys.exit(1)

if __name__ == '__main__':
    main()