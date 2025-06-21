"""
Main orchestrator for CHSH Game load testing.

Coordinates all components and manages the overall test execution flow.
"""

import asyncio
import time
import signal
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from loguru import logger

from .config import LoadTestConfig
from .team_manager import TeamManager
from .dashboard import DashboardSimulator
from .metrics import LoadTestMetrics
from .reporter import LoadTestReporter
from .utils import format_duration, format_bytes


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
        
        # Real-time monitoring
        self.live_display: Optional[Live] = None
        self.progress: Optional[Progress] = None
        
        # Setup signal handlers
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown signal handlers."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run_load_test(self):
        """
        Execute the complete load test workflow.
        """
        try:
            self.start_time = time.time()
            self.metrics.start_monitoring()
            
            # Display test start
            self._display_test_start()
            
            # Setup real-time monitoring
            await self._setup_monitoring()
            
            # Execute test phases
            success = await self._execute_test_phases()
            
            if success:
                self.console.print("\n[bold green]✓ Load test completed successfully![/bold green]")
            else:
                self.console.print("\n[bold red]✗ Load test completed with errors[/bold red]")
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⚠️  Test interrupted by user[/yellow]")
        except Exception as e:
            logger.error(f"Load test failed: {str(e)}")
            self.console.print(f"\n[red]❌ Load test failed: {str(e)}[/red]")
        finally:
            await self._cleanup()
    
    def _display_test_start(self):
        """Display test configuration and start message."""
        self.console.print("\n[bold blue]🚀 Starting CHSH Game Load Test[/bold blue]")
        
        # Configuration panel
        config_table = Table(show_header=False, box=None)
        config_table.add_column("Setting", style="bold cyan")
        config_table.add_column("Value", style="white")
        
        config_table.add_row("Server URL", self.config.deployment_url)
        config_table.add_row("Teams", f"{self.config.num_teams} ({self.config.total_players} players)")
        config_table.add_row("Connection Strategy", self.config.connection_strategy.value)
        config_table.add_row("Response Pattern", self.config.response_pattern.value)
        config_table.add_row("Max Duration", f"{self.config.max_test_duration}s")
        config_table.add_row("Dashboard Simulation", "✓" if self.config.enable_dashboard_simulation else "✗")
        
        config_panel = Panel(config_table, title="[bold]Test Configuration[/bold]", border_style="blue")
        self.console.print(config_panel)
    
    async def _setup_monitoring(self):
        """Setup real-time monitoring display."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        )
        
        # Start live display
        self.live_display = Live(
            self._generate_status_display(),
            console=self.console,
            refresh_per_second=1
        )
        self.live_display.start()
    
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
        
        return Panel(status_table, title="[bold]Real-time Status[/bold]", border_style="green")
    
    async def _execute_test_phases(self) -> bool:
        """Execute all test phases in sequence."""
        phases = [
            ("Connecting Players", self._phase_connect_players),
            ("Creating Teams", self._phase_create_teams),
            ("Starting Dashboard", self._phase_setup_dashboard),
            ("Starting Game", self._phase_start_game),
            ("Running Game Simulation", self._phase_run_game),
        ]
        
        for phase_name, phase_func in phases:
            if self.should_shutdown:
                return False
                
            self.console.print(f"\n[bold yellow]📋 {phase_name}...[/bold yellow]")
            
            try:
                success = await phase_func()
                if not success:
                    self.console.print(f"[red]❌ {phase_name} failed[/red]")
                    return False
                else:
                    self.console.print(f"[green]✓ {phase_name} completed[/green]")
            except Exception as e:
                logger.error(f"Phase '{phase_name}' failed: {str(e)}")
                self.console.print(f"[red]❌ {phase_name} failed: {str(e)}[/red]")
                return False
        
        return True
    
    async def _phase_connect_players(self) -> bool:
        """Phase 1: Create players and establish connections."""
        # Create players
        players = await self.team_manager.create_players()
        self.console.print(f"Created {len(players)} player instances")
        
        # Establish connections
        success_rate = await self.team_manager.establish_connections()
        
        if success_rate < 0.8:  # Require 80% success rate
            self.console.print(f"[red]Connection success rate too low: {success_rate:.1%}[/red]")
            return False
        
        self.console.print(f"Connection success rate: {success_rate:.1%}")
        return True
    
    async def _phase_create_teams(self) -> bool:
        """Phase 2: Create teams and pair players."""
        teams = await self.team_manager.create_teams()
        
        if len(teams) < self.config.num_teams * 0.8:  # Require 80% of expected teams
            self.console.print(f"[red]Too few teams created: {len(teams)}/{self.config.num_teams}[/red]")
            return False
        
        self.console.print(f"Created {len(teams)} teams")
        return True
    
    async def _phase_setup_dashboard(self) -> bool:
        """Phase 3: Setup dashboard connection."""
        if not self.config.enable_dashboard_simulation:
            self.console.print("Dashboard simulation disabled - skipping")
            return True
        
        success = await self.dashboard.connect()
        if not success:
            self.console.print("[red]Dashboard connection failed[/red]")
            return False
        
        # Wait for teams to be ready
        teams_ready = await self.dashboard.wait_for_teams(
            expected_teams=len(self.team_manager.teams),
            timeout=60.0
        )
        
        if not teams_ready:
            self.console.print("[red]Teams not ready for game start[/red]")
            return False
        
        return True
    
    async def _phase_start_game(self) -> bool:
        """Phase 4: Start the game."""
        # Start game via dashboard
        game_started = await self.dashboard.start_game()
        if not game_started:
            self.console.print("[red]Failed to start game[/red]")
            return False
        
        # Wait for players to receive game start
        await asyncio.sleep(2.0)
        
        # Verify players received game start
        players_ready = sum(1 for p in self.team_manager.players if p.game_started)
        self.console.print(f"{players_ready} players ready for game")
        
        return players_ready > 0
    
    async def _phase_run_game(self) -> bool:
        """Phase 5: Run the game simulation."""
        # Start monitoring tasks
        monitor_tasks = [
            asyncio.create_task(self.team_manager.monitor_game_progress()),
            asyncio.create_task(self.dashboard.monitor_dashboard(self.config.max_test_duration)),
            asyncio.create_task(self._update_live_display())
        ]
        
        try:
            # Run until completion or shutdown
            await asyncio.gather(*monitor_tasks, return_exceptions=True)
            return True
        except Exception as e:
            logger.error(f"Game simulation error: {str(e)}")
            return False
        finally:
            # Cancel remaining tasks
            for task in monitor_tasks:
                if not task.done():
                    task.cancel()
    
    async def _update_live_display(self):
        """Update live display periodically."""
        while not self.should_shutdown:
            if self.live_display:
                self.live_display.update(self._generate_status_display())
            await asyncio.sleep(1.0)
    
    async def shutdown(self):
        """Gracefully shutdown the load tester."""
        if self.should_shutdown:
            return
            
        logger.info("Initiating graceful shutdown...")
        self.should_shutdown = True
        
        # Stop live display
        if self.live_display:
            self.live_display.stop()
        
        # Shutdown components
        shutdown_tasks = [
            asyncio.create_task(self.team_manager.shutdown()),
            asyncio.create_task(self.dashboard.disconnect())
        ]
        
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        logger.info("Shutdown complete")
    
    async def _cleanup(self):
        """Cleanup and generate final report."""
        self.end_time = time.time()
        
        # Stop monitoring
        self.metrics.stop_monitoring()
        
        # Stop live display
        if self.live_display:
            self.live_display.stop()
        
        # Ensure shutdown
        await self.shutdown()
        
        # Generate final report
        self.console.print("\n[bold blue]📊 Generating Test Report...[/bold blue]")
        
        try:
            await self.reporter.generate_report()
            self.console.print("[green]✓ Report generated successfully[/green]")
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            self.console.print(f"[red]❌ Report generation failed: {str(e)}[/red]")
        
        # Display summary
        self._display_test_summary()
    
    def _display_test_summary(self):
        """Display final test summary."""
        if not self.start_time or not self.end_time:
            return
        
        duration = self.end_time - self.start_time
        summary = self.metrics.get_comprehensive_summary()
        
        # Summary table
        summary_table = Table(show_header=False, box=None)
        summary_table.add_column("Metric", style="bold cyan")
        summary_table.add_column("Value", style="white")
        
        # Test overview
        summary_table.add_row("Test Duration", format_duration(duration))
        summary_table.add_row("Teams Created", f"{summary['team_metrics']['teams_created']}/{self.config.num_teams}")
        summary_table.add_row("Successful Connections", f"{summary['connection_metrics']['successful']}/{self.config.total_players}")
        summary_table.add_row("Total Answers", str(summary['game_metrics']['total_answers']))
        summary_table.add_row("Total Errors", str(summary['error_metrics']['total_errors']))
        
        # Performance metrics
        conn_stats = summary['connection_metrics']['connection_times']
        if conn_stats['count'] > 0:
            summary_table.add_row("Avg Connection Time", f"{conn_stats['mean']:.2f}s")
        
        response_stats = summary['game_metrics']['response_times']
        if response_stats['count'] > 0:
            summary_table.add_row("Avg Response Time", f"{response_stats['mean']:.2f}s")
        
        # System resources
        system_stats = summary['system_metrics']
        summary_table.add_row("Peak CPU Usage", f"{system_stats['cpu_usage_percent']['max']:.1f}%")
        summary_table.add_row("Peak Memory Usage", f"{system_stats['memory_usage_percent']['max']:.1f}%")
        summary_table.add_row("Network Data Sent", format_bytes(system_stats['total_network_sent_mb'] * 1024 * 1024))
        
        # Success indicators
        success_rate = summary['connection_metrics']['success_rate']
        error_rate = summary['error_metrics']['error_rate']
        
        if success_rate >= 0.95 and error_rate <= 0.05:
            status_style = "green"
            status_text = "✓ PASSED"
        elif success_rate >= 0.8 and error_rate <= 0.1:
            status_style = "yellow"
            status_text = "⚠ PARTIAL SUCCESS"
        else:
            status_style = "red"
            status_text = "✗ FAILED"
        
        summary_table.add_row("Test Result", f"[{status_style}]{status_text}[/{status_style}]")
        
        summary_panel = Panel(summary_table, title="[bold]Test Summary[/bold]", border_style="blue")
        self.console.print(f"\n{summary_panel}")
        
        # Results location
        if self.config.save_results:
            results_dir = Path(self.config.results_dir)
            self.console.print(f"\n[dim]📁 Detailed results saved to: {results_dir}[/dim]")