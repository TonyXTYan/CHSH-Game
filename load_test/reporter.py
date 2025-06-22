"""
Report generation for CHSH Game load testing results.

Generates comprehensive reports in multiple formats (console, JSON, CSV).
"""

import json
import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from loguru import logger
import logging

from .config import LoadTestConfig, OutputFormat
from .metrics import LoadTestMetrics
from .utils import format_duration, format_bytes

logger = logging.getLogger(__name__)

class LoadTestReporter:
    """
    Generates comprehensive load test reports.
    
    Supports multiple output formats and detailed analysis.
    """
    
    def __init__(self, config: LoadTestConfig, metrics: LoadTestMetrics):
        self.config = config
        self.metrics = metrics
        self.console = Console()
        
        # Ensure results directory exists
        if config.save_results:
            self.results_dir = Path(config.results_dir)
            self.results_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.results_dir = None
    
    async def generate_report(self):
        """Generate report in the configured format."""
        # Get comprehensive metrics
        summary = self.metrics.get_comprehensive_summary()
        
        # Generate timestamp for file naming
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate report based on format
        if self.config.output_format == OutputFormat.CONSOLE:
            self._generate_console_report(summary)
        elif self.config.output_format == OutputFormat.JSON:
            await self._generate_json_report(summary, timestamp)
        elif self.config.output_format == OutputFormat.CSV:
            await self._generate_csv_report(summary, timestamp)
        
        # Always save detailed data if requested
        if self.config.save_results and self.results_dir:
            await self._save_detailed_data(summary, timestamp)
    
    def _generate_console_report(self, summary: Dict[str, Any]):
        """Generate formatted console report."""
        self.console.print("\n[bold blue]📊 CHSH Game Load Test Results[/bold blue]")
        self.console.print("=" * 60)
        
        # Test Configuration
        config_table = Table(show_header=False, box=None)
        config_table.add_column("Setting", style="bold cyan")
        config_table.add_column("Value", style="white")
        
        test_config = summary['test_configuration']
        config_table.add_row("Server URL", self.config.deployment_url)
        config_table.add_row("Teams", f"{test_config['num_teams']} ({test_config['expected_players']} players)")
        config_table.add_row("Duration", format_duration(test_config['duration_seconds']))
        config_table.add_row("Response Pattern", self.config.response_pattern.value)
        config_table.add_row("Connection Strategy", self.config.connection_strategy.value)
        
        config_panel = Panel(config_table, title="[bold]Configuration[/bold]", border_style="blue")
        self.console.print(config_panel)
        
        # Connection Results
        self._print_connection_results(summary['connection_metrics'])
        
        # Team Management Results
        self._print_team_results(summary['team_metrics'])
        
        # Game Performance
        self._print_game_results(summary['game_metrics'])
        
        # Error Analysis
        self._print_error_analysis(summary['error_metrics'])
        
        # System Performance
        self._print_system_metrics(summary['system_metrics'])
        
        # Final Assessment
        self._print_final_assessment(summary)
    
    def _print_connection_results(self, metrics: Dict[str, Any]):
        """Print connection performance results."""
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")
        
        success_rate = metrics['success_rate']
        table.add_row("Successful Connections", f"{metrics['successful']}/{metrics['attempted']} ({success_rate:.1%})")
        table.add_row("Failed Connections", str(metrics['failed']))
        
        conn_times = metrics['connection_times']
        if conn_times['count'] > 0:
            table.add_row("Avg Connection Time", f"{conn_times['mean']:.2f}s")
            table.add_row("Connection Time Range", f"{conn_times['min']:.2f}s - {conn_times['max']:.2f}s")
        
        # Status indicator
        if success_rate >= 0.95:
            status = "[green]✓ EXCELLENT[/green]"
        elif success_rate >= 0.9:
            status = "[yellow]⚠ GOOD[/yellow]"
        else:
            status = "[red]✗ POOR[/red]"
        table.add_row("Connection Status", status)
        
        panel = Panel(table, title="[bold]Connection Results[/bold]", border_style="green")
        self.console.print(f"\n{panel}")
    
    def _print_team_results(self, metrics: Dict[str, Any]):
        """Print team management results."""
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")
        
        success_rate = metrics['team_success_rate']
        table.add_row("Teams Created", f"{metrics['teams_created']}/{metrics['expected_teams']} ({success_rate:.1%})")
        table.add_row("Teams Fully Joined", str(metrics['teams_fully_joined']))
        
        creation_times = metrics['creation_times']
        if creation_times['count'] > 0:
            table.add_row("Avg Creation Time", f"{creation_times['mean']:.2f}s")
        
        join_times = metrics['join_times']
        if join_times['count'] > 0:
            table.add_row("Avg Join Time", f"{join_times['mean']:.2f}s")
        
        # Status indicator
        if success_rate >= 0.95:
            status = "[green]✓ EXCELLENT[/green]"
        elif success_rate >= 0.9:
            status = "[yellow]⚠ GOOD[/yellow]"
        else:
            status = "[red]✗ POOR[/red]"
        table.add_row("Team Management", status)
        
        panel = Panel(table, title="[bold]Team Management[/bold]", border_style="green")
        self.console.print(f"\n{panel}")
    
    def _print_game_results(self, metrics: Dict[str, Any]):
        """Print game performance results."""
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Game Started", "✓" if metrics['game_started'] else "✗")
        if metrics['game_started']:
            table.add_row("Game Duration", format_duration(metrics['game_duration']))
        
        table.add_row("Questions Received", str(metrics['total_questions']))
        table.add_row("Answers Submitted", str(metrics['total_answers']))
        
        response_times = metrics['response_times']
        if response_times['count'] > 0:
            table.add_row("Avg Response Time", f"{response_times['mean']:.2f}s ± {response_times['std']:.2f}s")
            table.add_row("Response Time Range", f"{response_times['min']:.2f}s - {response_times['max']:.2f}s")
        
        response_delays = metrics['response_delays']
        if response_delays['count'] > 0:
            table.add_row("Avg Response Delay", f"{response_delays['mean']:.2f}s")
        
        panel = Panel(table, title="[bold]Game Performance[/bold]", border_style="green")
        self.console.print(f"\n{panel}")
    
    def _print_error_analysis(self, metrics: Dict[str, Any]):
        """Print error analysis."""
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")
        
        error_rate = metrics['error_rate']
        table.add_row("Total Errors", str(metrics['total_errors']))
        table.add_row("Error Rate", f"{error_rate:.2%}")
        
        # Error breakdown
        if metrics['errors_by_type']:
            table.add_row("", "")  # Spacer
            table.add_row("Error Breakdown", "")
            for error_type, count in sorted(metrics['errors_by_type'].items()):
                table.add_row(f"  {error_type}", str(count))
        
        # Status indicator
        if error_rate <= 0.01:
            status = "[green]✓ EXCELLENT[/green]"
        elif error_rate <= 0.05:
            status = "[yellow]⚠ ACCEPTABLE[/yellow]"
        else:
            status = "[red]✗ HIGH[/red]"
        table.add_row("Error Level", status)
        
        panel = Panel(table, title="[bold]Error Analysis[/bold]", border_style="red" if error_rate > 0.05 else "green")
        self.console.print(f"\n{panel}")
    
    def _print_system_metrics(self, metrics: Dict[str, Any]):
        """Print system resource metrics."""
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")
        
        cpu_usage = metrics['cpu_usage_percent']
        memory_usage = metrics['memory_usage_percent']
        
        table.add_row("Peak CPU Usage", f"{cpu_usage['max']:.1f}%")
        table.add_row("Avg CPU Usage", f"{cpu_usage['mean']:.1f}%")
        table.add_row("Peak Memory Usage", f"{memory_usage['max']:.1f}%")
        table.add_row("Avg Memory Usage", f"{memory_usage['mean']:.1f}%")
        
        total_sent = metrics['total_network_sent_mb'] * 1024 * 1024
        total_recv = metrics['total_network_recv_mb'] * 1024 * 1024
        table.add_row("Network Data Sent", format_bytes(total_sent))
        table.add_row("Network Data Received", format_bytes(total_recv))
        
        panel = Panel(table, title="[bold]System Resources[/bold]", border_style="blue")
        self.console.print(f"\n{panel}")
    
    def _print_final_assessment(self, summary: Dict[str, Any]):
        """Print final test assessment."""
        connection_rate = summary['connection_metrics']['success_rate']
        team_rate = summary['team_metrics']['team_success_rate']
        error_rate = summary['error_metrics']['error_rate']
        
        # Overall assessment
        if connection_rate >= 0.95 and team_rate >= 0.95 and error_rate <= 0.01:
            assessment = "[green]🎯 EXCELLENT PERFORMANCE[/green]"
            detail = "Server handled load exceptionally well"
        elif connection_rate >= 0.9 and team_rate >= 0.9 and error_rate <= 0.05:
            assessment = "[yellow]⚡ GOOD PERFORMANCE[/yellow]"
            detail = "Server performance is acceptable under load"
        elif connection_rate >= 0.8 and team_rate >= 0.8 and error_rate <= 0.1:
            assessment = "[orange]⚠ MODERATE PERFORMANCE[/orange]"
            detail = "Server shows some stress under load"
        else:
            assessment = "[red]🔥 POOR PERFORMANCE[/red]"
            detail = "Server struggles significantly under load"
        
        table = Table(show_header=False, box=None)
        table.add_column("Assessment", style="bold")
        table.add_row(assessment)
        table.add_row(f"[dim]{detail}[/dim]")
        
        # Recommendations
        recommendations = self._generate_recommendations(summary)
        if recommendations:
            table.add_row("")  # Spacer
            table.add_row("[bold]Recommendations:[/bold]")
            for rec in recommendations:
                table.add_row(f"• {rec}")
        
        panel = Panel(table, title="[bold]Final Assessment[/bold]", border_style="magenta")
        self.console.print(f"\n{panel}")
    
    def _generate_recommendations(self, summary: Dict[str, Any]) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        connection_rate = summary['connection_metrics']['success_rate']
        error_rate = summary['error_metrics']['error_rate']
        cpu_usage = summary['system_metrics']['cpu_usage_percent']['max']
        memory_usage = summary['system_metrics']['memory_usage_percent']['max']
        
        if connection_rate < 0.9:
            recommendations.append("Consider increasing server connection limits or improving connection handling")
        
        if error_rate > 0.05:
            recommendations.append("Investigate error sources and improve error handling")
        
        if cpu_usage > 80:
            recommendations.append("Consider CPU optimization or scaling to handle higher loads")
        
        if memory_usage > 80:
            recommendations.append("Monitor memory usage and consider memory optimization")
        
        response_times = summary['game_metrics']['response_times']
        if response_times['count'] > 0 and response_times['mean'] > 2.0:
            recommendations.append("Server response times are high - investigate performance bottlenecks")
        
        if not recommendations:
            recommendations.append("Performance is excellent - server is well-optimized for this load")
        
        return recommendations
    
    async def _generate_json_report(self, summary: Dict[str, Any], timestamp: str):
        """Generate JSON format report."""
        report_data = {
            'test_metadata': {
                'timestamp': timestamp,
                'config': self.config.to_dict(),
                'generated_at': datetime.now().isoformat()
            },
            'results': summary
        }
        
        if self.results_dir:
            json_file = self.results_dir / f"load_test_report_{timestamp}.json"
            with open(json_file, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            logger.info(f"JSON report saved to: {json_file}")
        
        # JSON output for programmatic consumption
        logger.info(json.dumps(report_data, indent=2, default=str))
    
    async def _generate_csv_report(self, summary: Dict[str, Any], timestamp: str):
        """Generate CSV format report."""
        if not self.results_dir:
            logger.warning("Cannot generate CSV report: no results directory configured")
            return
        
        csv_file = self.results_dir / f"load_test_summary_{timestamp}.csv"
        
        # Flatten summary data for CSV
        flattened_data = self._flatten_dict(summary)
        
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value'])
            for key, value in flattened_data.items():
                writer.writerow([key, value])
        
        logger.info(f"CSV report saved to: {csv_file}")
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flatten nested dictionary for CSV export."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    async def _save_detailed_data(self, summary: Dict[str, Any], timestamp: str):
        """Save detailed player and metrics data."""
        if not self.results_dir:
            return
        
        # Save individual player metrics
        player_data = []
        for player_id, player_metrics in self.metrics.player_metrics.items():
            player_data.append(player_metrics.get_summary())
        
        player_file = self.results_dir / f"player_metrics_{timestamp}.json"
        with open(player_file, 'w') as f:
            json.dump(player_data, f, indent=2, default=str)
        
        # Save system metrics timeline
        system_data = {
            'cpu_usage': list(self.metrics.system_metrics.cpu_usage),
            'memory_usage': list(self.metrics.system_metrics.memory_usage),
            'network_sent': list(self.metrics.system_metrics.network_sent),
            'network_recv': list(self.metrics.system_metrics.network_recv)
        }
        
        system_file = self.results_dir / f"system_metrics_{timestamp}.json"
        with open(system_file, 'w') as f:
            json.dump(system_data, f, indent=2, default=str)
        
        logger.info(f"Detailed data saved to: {self.results_dir}")