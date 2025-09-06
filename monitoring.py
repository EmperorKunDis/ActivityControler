#!/usr/bin/env python3
"""
Monitoring and Metrics Module

Provides application monitoring, metrics collection, and health checks
for production deployments of Mac Activity Analyzer.
"""

import time
import psutil
import threading
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from pathlib import Path
import logging


@dataclass
class Metric:
    """Individual metric data point"""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram


@dataclass
class HealthCheckResult:
    """Health check result"""
    name: str
    status: str  # healthy, degraded, unhealthy
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    Collects and manages application metrics
    
    @description Central metrics collection with time-series storage
    """
    
    def __init__(self, retention_minutes: int = 60):
        """
        Initialize metrics collector
        
        @param retention_minutes: How long to keep metrics in memory
        """
        self.retention_minutes = retention_minutes
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=retention_minutes * 60))
        self.counters: Dict[str, float] = defaultdict(float)
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
    
    def record_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """
        Record a gauge metric (point-in-time value)
        
        @param name: Metric name
        @param value: Metric value
        @param labels: Optional labels
        """
        with self.lock:
            metric = Metric(
                name=name,
                value=value,
                timestamp=datetime.now(),
                labels=labels or {},
                metric_type="gauge"
            )
            self.metrics[name].append(metric)
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """
        Increment a counter metric
        
        @param name: Counter name
        @param value: Increment value
        @param labels: Optional labels
        """
        with self.lock:
            key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            self.counters[key] += value
            
            metric = Metric(
                name=name,
                value=self.counters[key],
                timestamp=datetime.now(),
                labels=labels or {},
                metric_type="counter"
            )
            self.metrics[name].append(metric)
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """
        Record a histogram metric (for distributions)
        
        @param name: Metric name
        @param value: Observed value
        @param labels: Optional labels
        """
        with self.lock:
            metric = Metric(
                name=name,
                value=value,
                timestamp=datetime.now(),
                labels=labels or {},
                metric_type="histogram"
            )
            self.metrics[name].append(metric)
    
    def get_metrics(self, name: str, last_minutes: int = None) -> List[Metric]:
        """
        Get metrics by name
        
        @param name: Metric name
        @param last_minutes: Get only metrics from last N minutes
        @returns: List of metrics
        """
        with self.lock:
            metrics = list(self.metrics.get(name, []))
            
            if last_minutes:
                cutoff = datetime.now() - timedelta(minutes=last_minutes)
                metrics = [m for m in metrics if m.timestamp >= cutoff]
            
            return metrics
    
    def get_all_metrics(self) -> Dict[str, List[Metric]]:
        """Get all current metrics"""
        with self.lock:
            return {name: list(values) for name, values in self.metrics.items()}
    
    def calculate_statistics(self, name: str, last_minutes: int = 5) -> Dict[str, float]:
        """
        Calculate statistics for a metric
        
        @param name: Metric name
        @param last_minutes: Time window for calculation
        @returns: Dict with min, max, avg, p50, p95, p99
        """
        metrics = self.get_metrics(name, last_minutes)
        
        if not metrics:
            return {}
        
        values = sorted([m.value for m in metrics])
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'p50': values[int(len(values) * 0.5)],
            'p95': values[int(len(values) * 0.95)] if len(values) > 20 else max(values),
            'p99': values[int(len(values) * 0.99)] if len(values) > 100 else max(values)
        }
    
    def export_prometheus_format(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        with self.lock:
            for name, metrics in self.metrics.items():
                if not metrics:
                    continue
                
                # Get latest value for each unique label combination
                latest_by_labels = {}
                for metric in metrics:
                    label_key = json.dumps(metric.labels, sort_keys=True)
                    latest_by_labels[label_key] = metric
                
                # Format metrics
                for label_key, metric in latest_by_labels.items():
                    labels_str = ""
                    if metric.labels:
                        label_parts = [f'{k}="{v}"' for k, v in metric.labels.items()]
                        labels_str = f"{{{','.join(label_parts)}}}"
                    
                    lines.append(f"# TYPE {name} {metric.metric_type}")
                    lines.append(f"{name}{labels_str} {metric.value}")
        
        return "\n".join(lines)


class SystemMonitor:
    """
    Monitors system resources and application performance
    
    @description Tracks CPU, memory, disk usage and application-specific metrics
    """
    
    def __init__(self, metrics_collector: MetricsCollector):
        """Initialize system monitor"""
        self.metrics = metrics_collector
        self.process = psutil.Process()
        self.monitoring = False
        self.monitor_thread = None
        self.logger = logging.getLogger(__name__)
    
    def start_monitoring(self, interval: int = 10):
        """
        Start monitoring system resources
        
        @param interval: Monitoring interval in seconds
        """
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info(f"System monitoring started (interval: {interval}s)")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("System monitoring stopped")
    
    def _monitor_loop(self, interval: int):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                self._collect_metrics()
            except Exception as e:
                self.logger.error(f"Error collecting metrics: {e}")
            
            time.sleep(interval)
    
    def _collect_metrics(self):
        """Collect system metrics"""
        # CPU metrics
        cpu_percent = self.process.cpu_percent(interval=1)
        self.metrics.record_gauge('process_cpu_percent', cpu_percent)
        
        system_cpu = psutil.cpu_percent(interval=1)
        self.metrics.record_gauge('system_cpu_percent', system_cpu)
        
        # Memory metrics
        memory_info = self.process.memory_info()
        self.metrics.record_gauge('process_memory_rss_mb', memory_info.rss / 1024 / 1024)
        self.metrics.record_gauge('process_memory_vms_mb', memory_info.vms / 1024 / 1024)
        
        system_memory = psutil.virtual_memory()
        self.metrics.record_gauge('system_memory_percent', system_memory.percent)
        self.metrics.record_gauge('system_memory_available_mb', system_memory.available / 1024 / 1024)
        
        # Disk I/O (if available)
        try:
            io_counters = self.process.io_counters()
            self.metrics.record_gauge('process_disk_read_mb', io_counters.read_bytes / 1024 / 1024)
            self.metrics.record_gauge('process_disk_write_mb', io_counters.write_bytes / 1024 / 1024)
        except:
            pass  # Not available on all systems
        
        # Thread count
        self.metrics.record_gauge('process_thread_count', self.process.num_threads())
        
        # File descriptors (Unix only)
        try:
            self.metrics.record_gauge('process_open_files', len(self.process.open_files()))
        except:
            pass


class ApplicationMetrics:
    """
    Application-specific metrics tracking
    
    @description Tracks analysis performance, errors, and business metrics
    """
    
    def __init__(self, metrics_collector: MetricsCollector):
        """Initialize application metrics"""
        self.metrics = metrics_collector
        self.logger = logging.getLogger(__name__)
    
    def track_analysis_duration(self, duration: float, analysis_type: str):
        """Track analysis duration"""
        self.metrics.record_histogram(
            'analysis_duration_seconds',
            duration,
            labels={'type': analysis_type}
        )
    
    def track_events_processed(self, count: int, source: str):
        """Track events processed"""
        self.metrics.increment_counter(
            'events_processed_total',
            count,
            labels={'source': source}
        )
    
    def track_error(self, error_type: str, component: str):
        """Track errors"""
        self.metrics.increment_counter(
            'errors_total',
            labels={'type': error_type, 'component': component}
        )
    
    def track_command_execution(self, command: str, success: bool, duration: float):
        """Track command executions"""
        self.metrics.increment_counter(
            'commands_executed_total',
            labels={'command': command, 'status': 'success' if success else 'failure'}
        )
        
        self.metrics.record_histogram(
            'command_duration_seconds',
            duration,
            labels={'command': command}
        )
    
    def track_cache_performance(self, hits: int, misses: int):
        """Track cache performance"""
        self.metrics.record_gauge('cache_hits', hits)
        self.metrics.record_gauge('cache_misses', misses)
        
        hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0
        self.metrics.record_gauge('cache_hit_rate', hit_rate)
    
    def track_active_users(self, count: int):
        """Track active users"""
        self.metrics.record_gauge('active_users', count)
    
    def track_business_metrics(self, hours_analyzed: float, billable_amount: float):
        """Track business-related metrics"""
        self.metrics.record_gauge('hours_analyzed_today', hours_analyzed)
        self.metrics.record_gauge('billable_amount_today', billable_amount)


class HealthChecker:
    """
    Application health checking system
    
    @description Performs various health checks and provides status endpoint
    """
    
    def __init__(self):
        """Initialize health checker"""
        self.checks: Dict[str, Callable[[], HealthCheckResult]] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_check(self, name: str, check_func: Callable[[], HealthCheckResult]):
        """
        Register a health check
        
        @param name: Check name
        @param check_func: Function that returns HealthCheckResult
        """
        self.checks[name] = check_func
        self.logger.info(f"Registered health check: {name}")
    
    def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks"""
        results = {}
        
        for name, check_func in self.checks.items():
            try:
                results[name] = check_func()
            except Exception as e:
                results[name] = HealthCheckResult(
                    name=name,
                    status="unhealthy",
                    message=f"Check failed: {str(e)}",
                    timestamp=datetime.now()
                )
        
        return results
    
    def get_overall_status(self) -> str:
        """Get overall health status"""
        results = self.run_all_checks()
        
        if not results:
            return "unknown"
        
        statuses = [r.status for r in results.values()]
        
        if "unhealthy" in statuses:
            return "unhealthy"
        elif "degraded" in statuses:
            return "degraded"
        else:
            return "healthy"
    
    def to_json(self) -> str:
        """Export health status as JSON"""
        results = self.run_all_checks()
        overall = self.get_overall_status()
        
        data = {
            'status': overall,
            'timestamp': datetime.now().isoformat(),
            'checks': {
                name: {
                    'status': result.status,
                    'message': result.message,
                    'timestamp': result.timestamp.isoformat(),
                    'details': result.details
                }
                for name, result in results.items()
            }
        }
        
        return json.dumps(data, indent=2)


# Pre-built health checks

def create_disk_space_check(min_free_gb: float = 1.0) -> Callable[[], HealthCheckResult]:
    """Create disk space health check"""
    def check():
        try:
            disk_usage = psutil.disk_usage('/')
            free_gb = disk_usage.free / (1024 ** 3)
            
            if free_gb < min_free_gb:
                return HealthCheckResult(
                    name="disk_space",
                    status="unhealthy",
                    message=f"Low disk space: {free_gb:.2f} GB free",
                    timestamp=datetime.now(),
                    details={'free_gb': free_gb, 'percent_used': disk_usage.percent}
                )
            elif free_gb < min_free_gb * 2:
                return HealthCheckResult(
                    name="disk_space",
                    status="degraded",
                    message=f"Disk space warning: {free_gb:.2f} GB free",
                    timestamp=datetime.now(),
                    details={'free_gb': free_gb, 'percent_used': disk_usage.percent}
                )
            else:
                return HealthCheckResult(
                    name="disk_space",
                    status="healthy",
                    message=f"Disk space OK: {free_gb:.2f} GB free",
                    timestamp=datetime.now(),
                    details={'free_gb': free_gb, 'percent_used': disk_usage.percent}
                )
        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status="unhealthy",
                message=f"Failed to check disk space: {e}",
                timestamp=datetime.now()
            )
    
    return check


def create_memory_check(max_percent: float = 90.0) -> Callable[[], HealthCheckResult]:
    """Create memory usage health check"""
    def check():
        try:
            memory = psutil.virtual_memory()
            
            if memory.percent > max_percent:
                return HealthCheckResult(
                    name="memory",
                    status="unhealthy",
                    message=f"High memory usage: {memory.percent:.1f}%",
                    timestamp=datetime.now(),
                    details={'percent': memory.percent, 'available_mb': memory.available / 1024 / 1024}
                )
            elif memory.percent > max_percent * 0.8:
                return HealthCheckResult(
                    name="memory",
                    status="degraded",
                    message=f"Memory usage warning: {memory.percent:.1f}%",
                    timestamp=datetime.now(),
                    details={'percent': memory.percent, 'available_mb': memory.available / 1024 / 1024}
                )
            else:
                return HealthCheckResult(
                    name="memory",
                    status="healthy",
                    message=f"Memory usage OK: {memory.percent:.1f}%",
                    timestamp=datetime.now(),
                    details={'percent': memory.percent, 'available_mb': memory.available / 1024 / 1024}
                )
        except Exception as e:
            return HealthCheckResult(
                name="memory",
                status="unhealthy",
                message=f"Failed to check memory: {e}",
                timestamp=datetime.now()
            )
    
    return check


def create_process_check(process_name: str) -> Callable[[], HealthCheckResult]:
    """Create process existence health check"""
    def check():
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] == process_name:
                    return HealthCheckResult(
                        name=f"process_{process_name}",
                        status="healthy",
                        message=f"Process {process_name} is running",
                        timestamp=datetime.now()
                    )
            
            return HealthCheckResult(
                name=f"process_{process_name}",
                status="unhealthy",
                message=f"Process {process_name} not found",
                timestamp=datetime.now()
            )
        except Exception as e:
            return HealthCheckResult(
                name=f"process_{process_name}",
                status="unhealthy",
                message=f"Failed to check process: {e}",
                timestamp=datetime.now()
            )
    
    return check


class MetricsServer:
    """
    Simple HTTP server for metrics and health endpoints
    
    @description Exposes /metrics and /health endpoints
    """
    
    def __init__(
        self,
        metrics_collector: MetricsCollector,
        health_checker: HealthChecker,
        host: str = "localhost",
        port: int = 9090
    ):
        """Initialize metrics server"""
        self.metrics = metrics_collector
        self.health = health_checker
        self.host = host
        self.port = port
        self.server = None
        self.logger = logging.getLogger(__name__)
    
    def start(self):
        """Start the metrics server"""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        
        class MetricsHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/metrics':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain; version=0.0.4')
                    self.end_headers()
                    self.wfile.write(self.server.metrics.export_prometheus_format().encode())
                    
                elif self.path == '/health':
                    status = self.server.health.get_overall_status()
                    status_code = 200 if status == "healthy" else 503
                    
                    self.send_response(status_code)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(self.server.health.to_json().encode())
                    
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                pass  # Suppress default logging
        
        self.server = HTTPServer((self.host, self.port), MetricsHandler)
        self.server.metrics = self.metrics
        self.server.health = self.health
        
        server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        server_thread.start()
        
        self.logger.info(f"Metrics server started on http://{self.host}:{self.port}")
    
    def stop(self):
        """Stop the metrics server"""
        if self.server:
            self.server.shutdown()
            self.logger.info("Metrics server stopped")


# Example usage and integration
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize components
    metrics_collector = MetricsCollector()
    system_monitor = SystemMonitor(metrics_collector)
    app_metrics = ApplicationMetrics(metrics_collector)
    health_checker = HealthChecker()
    
    # Register health checks
    health_checker.register_check("disk_space", create_disk_space_check(min_free_gb=5.0))
    health_checker.register_check("memory", create_memory_check(max_percent=80.0))
    
    # Start monitoring
    system_monitor.start_monitoring(interval=5)
    
    # Start metrics server
    metrics_server = MetricsServer(metrics_collector, health_checker, port=9090)
    metrics_server.start()
    
    # Simulate some activity
    print("Monitoring started. Press Ctrl+C to stop.")
    print("Metrics available at: http://localhost:9090/metrics")
    print("Health check at: http://localhost:9090/health")
    
    try:
        # Simulate application activity
        while True:
            # Track some metrics
            app_metrics.track_events_processed(100, "test")
            app_metrics.track_analysis_duration(2.5, "full_analysis")
            
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nStopping monitoring...")
        system_monitor.stop_monitoring()
        metrics_server.stop()