"""
Metrics collection and reporting for CHSH Game load testing.

Tracks performance, errors, and system resource usage.
"""

import time
import threading
import psutil
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from statistics import mean, median, stdev
from collections import defaultdict, deque


@dataclass
class TimingMetric:
    """Container for timing measurements."""
    values: List[float] = field(default_factory=list)
    
    def add(self, value: float):
        """Add a timing measurement."""
        self.values.append(value)
    
    def get_stats(self) -> Dict[str, float]:
        """Get statistical summary."""
        if not self.values:
            return {'count': 0, 'mean': 0.0, 'median': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0}
        
        return {
            'count': len(self.values),
            'mean': mean(self.values),
            'median': median(self.values),
            'std': stdev(self.values) if len(self.values) > 1 else 0.0,
            'min': min(self.values),
            'max': max(self.values)
        }


class PlayerMetrics:
    """Metrics collection for individual players."""
    
    def __init__(self, player_id: str):
        self.player_id = player_id
        self.start_time = time.time()
        
        # Connection metrics
        self.connection_times = TimingMetric()
        self.reconnection_count = 0
        
        # Team operation metrics
        self.team_operations = {
            'create': TimingMetric(),
            'join': TimingMetric()
        }
        
        # Game metrics
        self.questions_received = 0
        self.answers_submitted = 0
        self.response_delays = TimingMetric()
        self.response_times = TimingMetric()
        self.total_response_times = TimingMetric()
        
        # Error tracking
        self.errors = defaultdict(int)
        
        # State tracking
        self.state_changes = []
    
    def record_connection_time(self, duration: float):
        """Record connection establishment time."""
        self.connection_times.add(duration)
    
    def record_reconnection(self):
        """Record a reconnection event."""
        self.reconnection_count += 1
    
    def record_team_operation(self, operation: str, duration: float):
        """Record team creation or join time."""
        if operation in self.team_operations:
            self.team_operations[operation].add(duration)
    
    def record_question_response(self, delay: float, response_time: float, total_time: float):
        """Record question response metrics."""
        self.questions_received += 1
        self.answers_submitted += 1
        self.response_delays.add(delay)
        self.response_times.add(response_time)
        self.total_response_times.add(total_time)
    
    def record_answer_confirmed(self):
        """Record answer confirmation."""
        pass  # Could add timing metrics here if needed
    
    def record_error(self, error_type: str):
        """Record an error occurrence."""
        self.errors[error_type] += 1
    
    def record_state_change(self, state: str):
        """Record state change with timestamp."""
        self.state_changes.append({
            'state': state,
            'timestamp': time.time(),
            'elapsed': time.time() - self.start_time
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        return {
            'player_id': self.player_id,
            'duration': time.time() - self.start_time,
            'connections': self.connection_times.get_stats(),
            'reconnections': self.reconnection_count,
            'team_operations': {
                op: metrics.get_stats() for op, metrics in self.team_operations.items()
            },
            'questions_received': self.questions_received,
            'answers_submitted': self.answers_submitted,
            'response_delays': self.response_delays.get_stats(),
            'response_times': self.response_times.get_stats(),
            'total_response_times': self.total_response_times.get_stats(),
            'errors': dict(self.errors),
            'error_count': sum(self.errors.values())
        }


class SystemMetrics:
    """System resource monitoring."""
    
    def __init__(self, collection_interval: float = 1.0):
        self.collection_interval = collection_interval
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Resource usage tracking
        self.cpu_usage = deque(maxlen=1000)
        self.memory_usage = deque(maxlen=1000)
        self.network_sent = deque(maxlen=1000)
        self.network_recv = deque(maxlen=1000)
        
        # Initial network counters
        self.initial_net_io = psutil.net_io_counters()
        self.last_net_io = self.initial_net_io
    
    def start_monitoring(self):
        """Start system monitoring in background thread."""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop system monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.monitoring:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=None)
                self.cpu_usage.append(cpu_percent)
                
                # Memory usage
                memory = psutil.virtual_memory()
                self.memory_usage.append(memory.percent)
                
                # Network usage (rate calculation)
                current_net_io = psutil.net_io_counters()
                sent_rate = (current_net_io.bytes_sent - self.last_net_io.bytes_sent) / self.collection_interval
                recv_rate = (current_net_io.bytes_recv - self.last_net_io.bytes_recv) / self.collection_interval
                
                self.network_sent.append(sent_rate)
                self.network_recv.append(recv_rate)
                self.last_net_io = current_net_io
                
                time.sleep(self.collection_interval)
                
            except Exception as e:
                # Continue monitoring even if individual measurements fail
                time.sleep(self.collection_interval)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get system resource summary."""
        def stats_from_deque(data):
            if not data:
                return {'count': 0, 'mean': 0.0, 'max': 0.0, 'min': 0.0}
            values = list(data)
            return {
                'count': len(values),
                'mean': mean(values),
                'max': max(values),
                'min': min(values),
                'current': values[-1] if values else 0.0
            }
        
        return {
            'cpu_usage_percent': stats_from_deque(self.cpu_usage),
            'memory_usage_percent': stats_from_deque(self.memory_usage),
            'network_sent_bytes_per_sec': stats_from_deque(self.network_sent),
            'network_recv_bytes_per_sec': stats_from_deque(self.network_recv),
            'total_network_sent_mb': (self.last_net_io.bytes_sent - self.initial_net_io.bytes_sent) / (1024 * 1024),
            'total_network_recv_mb': (self.last_net_io.bytes_recv - self.initial_net_io.bytes_recv) / (1024 * 1024)
        }


class LoadTestMetrics:
    """Comprehensive metrics for entire load test."""
    
    def __init__(self, num_teams: int):
        self.num_teams = num_teams
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        
        # Player metrics aggregation
        self.player_metrics: Dict[str, PlayerMetrics] = {}
        
        # Connection tracking
        self.connection_attempts = 0
        self.successful_connections = 0
        self.failed_connections = 0
        self.connection_times = TimingMetric()
        
        # Team tracking
        self.teams_created = 0
        self.teams_joined = 0
        self.team_creation_times = TimingMetric()
        self.team_join_times = TimingMetric()
        
        # Game tracking
        self.total_questions = 0
        self.total_answers = 0
        self.game_started = False
        self.game_start_time: Optional[float] = None
        
        # Error aggregation
        self.total_errors = defaultdict(int)
        
        # System metrics
        self.system_metrics = SystemMetrics()
        
        # Event callbacks for real-time monitoring
        self.callbacks = []
    
    def register_callback(self, callback):
        """Register callback for real-time metrics updates."""
        self.callbacks.append(callback)
    
    def add_player(self, player_id: str) -> PlayerMetrics:
        """Add a player to metrics tracking."""
        player_metrics = PlayerMetrics(player_id)
        self.player_metrics[player_id] = player_metrics
        return player_metrics
    
    def record_event(self, event_type: str, player_id: str, data: Any = None):
        """Record events for real-time monitoring."""
        # Update aggregated metrics based on event type
        if event_type == 'connection_success':
            self.successful_connections += 1
            if isinstance(data, (int, float)):
                self.connection_times.add(data)
        
        elif event_type == 'connection_error' or event_type == 'connection_timeout':
            self.failed_connections += 1
        
        elif event_type == 'team_created':
            self.teams_created += 1
            if isinstance(data, (int, float)):
                self.team_creation_times.add(data)
        
        elif event_type == 'team_joined':
            self.teams_joined += 1
            if isinstance(data, (int, float)):
                self.team_join_times.add(data)
        
        elif event_type == 'answer_submitted':
            self.total_answers += 1
            if isinstance(data, dict):
                self.total_questions += 1
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback(event_type, player_id, data)
            except Exception:
                pass  # Don't let callback errors break metrics
    
    def record_game_start(self):
        """Record game start time."""
        self.game_started = True
        self.game_start_time = time.time()
    
    def start_monitoring(self):
        """Start system monitoring."""
        self.system_metrics.start_monitoring()
    
    def stop_monitoring(self):
        """Stop monitoring and finalize metrics."""
        self.end_time = time.time()
        self.system_metrics.stop_monitoring()
        
        # Aggregate errors from all players
        for player_metrics in self.player_metrics.values():
            for error_type, count in player_metrics.errors.items():
                self.total_errors[error_type] += count
    
    def get_comprehensive_summary(self) -> Dict[str, Any]:
        """Get complete metrics summary."""
        duration = (self.end_time or time.time()) - self.start_time
        
        # Calculate success rates
        total_connections = self.successful_connections + self.failed_connections
        connection_success_rate = self.successful_connections / total_connections if total_connections > 0 else 0.0
        
        expected_teams = self.num_teams
        team_success_rate = self.teams_created / expected_teams if expected_teams > 0 else 0.0
        
        # Aggregate response times from all players
        all_response_times = []
        all_response_delays = []
        for player_metrics in self.player_metrics.values():
            all_response_times.extend(player_metrics.response_times.values)
            all_response_delays.extend(player_metrics.response_delays.values)
        
        return {
            'test_configuration': {
                'num_teams': self.num_teams,
                'expected_players': self.num_teams * 2,
                'duration_seconds': duration
            },
            'connection_metrics': {
                'attempted': total_connections,
                'successful': self.successful_connections,
                'failed': self.failed_connections,
                'success_rate': connection_success_rate,
                'connection_times': self.connection_times.get_stats()
            },
            'team_metrics': {
                'expected_teams': expected_teams,
                'teams_created': self.teams_created,
                'teams_fully_joined': self.teams_joined,
                'team_success_rate': team_success_rate,
                'creation_times': self.team_creation_times.get_stats(),
                'join_times': self.team_join_times.get_stats()
            },
            'game_metrics': {
                'game_started': self.game_started,
                'game_duration': time.time() - self.game_start_time if self.game_start_time else 0,
                'total_questions': self.total_questions,
                'total_answers': self.total_answers,
                'response_times': TimingMetric(all_response_times).get_stats(),
                'response_delays': TimingMetric(all_response_delays).get_stats()
            },
            'error_metrics': {
                'total_errors': sum(self.total_errors.values()),
                'error_rate': sum(self.total_errors.values()) / max(1, self.total_answers),
                'errors_by_type': dict(self.total_errors)
            },
            'system_metrics': self.system_metrics.get_summary(),
            'player_count': len(self.player_metrics),
            'players_with_errors': len([p for p in self.player_metrics.values() if p.errors])
        }
    
    def get_real_time_status(self) -> Dict[str, Any]:
        """Get current status for real-time monitoring."""
        active_players = len([p for p in self.player_metrics.values() 
                            if time.time() - p.start_time < 300])  # Active in last 5 minutes
        
        return {
            'elapsed_time': time.time() - self.start_time,
            'active_players': active_players,
            'successful_connections': self.successful_connections,
            'teams_created': self.teams_created,
            'total_answers': self.total_answers,
            'error_count': sum(self.total_errors.values()),
            'game_started': self.game_started
        }