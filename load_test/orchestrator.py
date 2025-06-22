"""
Main orchestrator for CHSH Game load testing.

Coordinates all components and manages the overall test execution flow.
"""

import asyncio
import time
import signal
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .config import LoadTestConfig
from .team_manager import TeamManager
from .dashboard import DashboardSimulator
from .metrics import LoadTestMetrics
from .reporter import LoadTestReporter
from .utils import format_duration, format_bytes

logger = logging.getLogger(__name__)


class CHSHLoadTester:
    """
    Main orchestrator for CHSH Game load testing.
    
    Coordinates connection establishment, team creation, game simulation,
    and result reporting.
    """
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.console = Console()
        
        # Core components
        self.metrics = LoadTestMetrics(config.num_teams)
        self.team_manager = TeamManager(config, self.metrics)
        self.dashboard = DashboardSimulator(config)
        self.reporter = LoadTestReporter(config, self.metrics)
        
        # Test state
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.should_shutdown = False
        self.shutdown_event = asyncio.Event()
        
        # Test results
        self.players: List = []
        self.teams: List = []
        
        # Real-time monitoring
        self.live_display: Optional[Live] = None
        self.progress: Optional[Progress] = None
        
        # Task tracking for proper cleanup
        self.running_tasks: List[asyncio.Task] = []
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown signal handlers."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.should_shutdown = True
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run_load_test(self) -> bool:
        """Run the complete load test."""
        # Setup signal handlers after getting event loop
        self._setup_signal_handlers()
        
        try:
            self.start_time = time.time()
            self.metrics.start_monitoring()
            
            success = await self._run_load_test()
            
            if success:
                self.console.print("\n[bold green]✓ Load test completed successfully![/bold green]")
                logger.info("Load test completed successfully")
                return True
            else:
                self.console.print("\n[bold red]✗ Load test failed[/bold red]")
                logger.error("Load test failed")
                return False
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⚠️  Test interrupted by user (Ctrl+C)[/yellow]")
            logger.warning("Test interrupted by user")
            return False
            
        except asyncio.CancelledError:
            self.console.print("\n[yellow]⚠️  Test cancelled gracefully[/yellow]")
            logger.warning("Test cancelled gracefully")
            return False
            
        except Exception as e:
            logger.error(f"Load test failed: {str(e)}")
            self.console.print(f"\n[red]❌ Load test failed: {str(e)}[/red]")
            return False
            
        finally:
            # Always cleanup
            self.metrics.stop_monitoring()
            await self.shutdown()

    async def _run_load_test(self) -> bool:
        """Execute the load test phases."""
        self.console.print("\n[bold blue]🚀 Starting CHSH Game Load Test[/bold blue]")
        logger.info("Starting CHSH Game Load Test")

        # Show configuration
        config_panel = Panel(
            f"""[bold]Configuration:[/bold]
🎯 Target URL: {self.config.deployment_url}
👥 Total Players: {self.config.total_players}
🏆 Teams: {self.config.num_teams}
⏱️  Max Duration: {self.config.max_test_duration}s
🔗 Connection Strategy: {self.config.connection_strategy.value}
🎯 Response Pattern: {self.config.response_pattern.value}
📈 Dashboard Simulation: {'✓' if self.config.enable_dashboard_simulation else '✗'}
[dim]Press Ctrl+C for graceful shutdown[/dim]""",
            title="Load Test Parameters",
            border_style="blue"
        )
        self.console.print(config_panel)

        # Execute test phases
        phases = [
            ("Player Creation & Connection", self._create_and_connect_players),
            ("Team Formation", self._create_teams),
            ("Dashboard Setup", self._setup_dashboard),
            ("Game Initialization", self._start_game),
            ("Load Test Execution", self._execute_load_test),
            ("Results Collection", self._collect_results)
        ]

        for phase_name, phase_func in phases:
            # Check for shutdown signal
            if self.should_shutdown:
                self.console.print(f"\n[yellow]⚠️  Shutdown requested, stopping at {phase_name}[/yellow]")
                logger.info(f"Shutdown requested, stopping at {phase_name}")
                return False
                
            try:
                self.console.print(f"\n[bold yellow]📋 {phase_name}...[/bold yellow]")
                logger.info(f"Starting phase: {phase_name}")
                success = await phase_func()
                if not success:
                    self.console.print(f"[red]❌ {phase_name} failed[/red]")
                    logger.error(f"Phase failed: {phase_name}")
                    return False
                self.console.print(f"[green]✓ {phase_name} completed[/green]")
                logger.info(f"Phase completed: {phase_name}")
            except asyncio.CancelledError:
                self.console.print(f"\n[yellow]⚠️  {phase_name} cancelled[/yellow]")
                logger.info(f"Phase cancelled: {phase_name}")
                return False
            except Exception as e:
                self.console.print(f"[red]❌ {phase_name} failed: {str(e)}[/red]")
                logger.error(f"Phase failed: {phase_name} - {str(e)}")
                return False
        
        return True

    async def _create_and_connect_players(self) -> bool:
        """Create player instances and establish connections."""
        logger.info(f"Creating {self.config.total_players} player instances...")
        
        # Create players
        players = await self.team_manager.create_players()
        
        # Establish connections
        success_rate = await self.team_manager.establish_connections()
        
        if success_rate < 0.8:  # Require 80% connection success
            self.console.print(f"[red]Connection success rate too low: {success_rate:.1%}[/red]")
            logger.error(f"Connection success rate too low: {success_rate:.1%}")
            return False
        
        self.console.print(f"Connection success rate: {success_rate:.1%}")
        logger.info(f"Connection success rate: {success_rate:.1%}")
        self.players = players
        return True

    async def _create_teams(self) -> bool:
        """Form teams from connected players."""
        teams = await self.team_manager.create_teams()
        
        if len(teams) < self.config.num_teams * 0.8:  # Allow 20% failure rate
            self.console.print(f"[red]Too few teams created: {len(teams)}/{self.config.num_teams}[/red]")
            logger.error(f"Too few teams created: {len(teams)}/{self.config.num_teams}")
            return False
        
        self.console.print(f"Created {len(teams)} teams")
        logger.info(f"Created {len(teams)} teams")
        self.teams = teams
        return True

    async def _setup_dashboard(self) -> bool:
        """Setup dashboard monitoring if enabled."""
        if not self.config.enable_dashboard_simulation:
            self.console.print("Dashboard simulation disabled - skipping")
            logger.info("Dashboard simulation disabled - skipping")
            return True
        
        connected = await self.dashboard.connect()
        if not connected:
            self.console.print("[red]Dashboard connection failed[/red]")
            logger.error("Dashboard connection failed")
            return False
        
        return True

    async def _start_game(self) -> bool:
        """Start the game if teams are ready."""
        ready_teams = [team for team in self.teams if len(team.players) == 2]
        
        if len(ready_teams) < len(self.teams) * 0.8:
            self.console.print("[red]Teams not ready for game start[/red]")
            logger.error("Teams not ready for game start")
            return False
        
        # Wait for teams to be ready if dashboard simulation is enabled
        if self.config.enable_dashboard_simulation:
            teams_ready = await self.dashboard.wait_for_teams(len(ready_teams))
            if not teams_ready:
                self.console.print("[red]Teams not detected by dashboard[/red]")
                logger.error("Teams not detected by dashboard")
                return False
        
        # Start game simulation
        success = await self.dashboard.start_game()
        
        if not success:
            self.console.print("[red]Failed to start game[/red]")
            logger.error("Failed to start game")
            return False
        
        # Wait for players to be ready
        await asyncio.sleep(2)
        connected_players = len([p for p in self.players if p.state.name == 'CONNECTED'])
        self.console.print(f"{connected_players} players ready for game")
        logger.info(f"{connected_players} players ready for game")
        return True

    async def _execute_load_test(self) -> bool:
        """Run the game simulation."""
        # Start monitoring tasks
        monitor_tasks = [
            asyncio.create_task(self.team_manager.monitor_game_progress()),
            asyncio.create_task(self._update_live_display())
        ]
        
        # Add dashboard monitoring if enabled
        if self.config.enable_dashboard_simulation:
            monitor_tasks.append(
                asyncio.create_task(self.dashboard.monitor_dashboard(self.config.max_test_duration))
            )
        
        # Track tasks for cleanup
        self.running_tasks.extend(monitor_tasks)
        
        try:
            # Run until completion or shutdown
            done, pending = await asyncio.wait(
                monitor_tasks + [asyncio.create_task(self.shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Check if shutdown was requested
            if self.should_shutdown:
                self.console.print("\n[yellow]⚠️  Load test interrupted by user[/yellow]")
                logger.info("Load test interrupted by user")
                return True  # Still consider it successful if we can report
            
            return True
            
        except asyncio.CancelledError:
            logger.info("Load test execution was cancelled")
            return True
        except Exception as e:
            logger.error(f"Game simulation error: {str(e)}")
            return False
        finally:
            # Cancel and cleanup all monitoring tasks
            for task in monitor_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
    
    async def _collect_results(self) -> bool:
        """Collect and generate test results."""
        try:
            self.console.print("\n[bold blue]📊 Generating Test Report...[/bold blue]")
            logger.info("Generating test report...")
            
            await self.reporter.generate_report()
            self.console.print("[green]✓ Report generated successfully[/green]")
            logger.info("Report generated successfully")
            return True
        except Exception as e:
            self.console.print(f"[red]❌ Report generation failed: {str(e)}[/red]")
            logger.error(f"Report generation failed: {str(e)}")
            return False
    
    async def _update_live_display(self):
        """Update live display periodically."""
        try:
            while not self.should_shutdown:
                if self.live_display:
                    self.live_display.update(self._generate_status_display())
                
                # Use asyncio.wait_for with shutdown event for interruptible sleep
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=1.0)
                    break  # Shutdown event was set
                except asyncio.TimeoutError:
                    continue  # Normal timeout, continue loop
                    
        except asyncio.CancelledError:
            logger.debug("Live display update task was cancelled")
            raise
        except Exception as e:
            logger.error(f"Live display update error: {str(e)}")
    
    async def shutdown(self):
        """Gracefully shutdown the load tester."""
        if self.should_shutdown:
            return
            
        logger.info("Initiating graceful shutdown...")
        self.should_shutdown = True
        self.shutdown_event.set()
        
        # Stop live display
        if self.live_display:
            try:
                self.live_display.stop()
            except Exception as e:
                logger.debug(f"Error stopping live display: {e}")
        
        # Cancel all running tasks
        for task in self.running_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete cancellation
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
        
        # Shutdown components
        shutdown_tasks = [
            asyncio.create_task(self.team_manager.shutdown()),
            asyncio.create_task(self.dashboard.disconnect())
        ]
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*shutdown_tasks, return_exceptions=True),
                timeout=5.0  # 5 second timeout for shutdown
            )
        except asyncio.TimeoutError:
            logger.warning("Shutdown timeout reached, forcing exit")
        
        logger.info("Shutdown complete")
    
    def _generate_status_display(self) -> Panel:
        """Generate real-time status display."""
        if not self.start_time:
            return Panel("Initializing...", title="Status")
        
        elapsed = time.time() - self.start_time
        status = self.metrics.get_real_time_status()
        
        # Status table
        status_table = Table(show_header=False, box=None)
        status_table.add_column("Metric", style="bold cyan")
        status_table.add_column("Value", style="white")
        
        status_table.add_row("Elapsed Time", format_duration(elapsed))
        status_table.add_row("Active Players", str(status.get('active_players', 0)))
        status_table.add_row("Successful Connections", f"{status.get('successful_connections', 0)}/{self.config.total_players}")
        status_table.add_row("Teams Created", f"{status.get('teams_created', 0)}/{self.config.num_teams}")
        status_table.add_row("Total Answers", str(status.get('total_answers', 0)))
        status_table.add_row("Error Count", str(status.get('error_count', 0)))
        status_table.add_row("Game Started", "✓" if status.get('game_started', False) else "✗")
        
        # Add shutdown status
        if self.should_shutdown:
            status_table.add_row("Status", "[yellow]Shutting down...[/yellow]")
        
        return Panel(status_table, title="[bold]Real-time Status[/bold] [dim](Ctrl+C to exit)[/dim]", border_style="green")