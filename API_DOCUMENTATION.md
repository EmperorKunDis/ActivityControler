# Mac Activity Analyzer - API Documentation

## Table of Contents

1. [Overview](#overview)
2. [Security Components](#security-components)
3. [Data Processing](#data-processing)
4. [Thread Management](#thread-management)
5. [Configuration](#configuration)
6. [Logging](#logging)
7. [Integration Guide](#integration-guide)
8. [Best Practices](#best-practices)

## Overview

Mac Activity Analyzer is a secure, high-performance system for analyzing macOS activity logs. The application is built with security-first design principles and modular architecture.

### Key Features

- **Shell injection protection** via command whitelisting
- **Memory-efficient** streaming data processing
- **Thread-safe** concurrent operations
- **Type-safe** configuration management
- **Structured logging** with rotation

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                  GUI Application                     │
├─────────────────────────────────────────────────────┤
│              Thread Manager (Orchestration)          │
├──────────────┬──────────────┬──────────────────────┤
│   Secure     │    Log       │    Event             │
│   Executor   │    Parsers   │    Processor         │
├──────────────┴──────────────┴──────────────────────┤
│         Configuration    │    Logging               │
└──────────────────────────────────────────────────────┘
```

## Security Components

### SecureCommandExecutor

Provides secure execution of system commands with protection against shell injection attacks.

```python
from secure_executor import SecureCommandExecutor, CommandResult

# Initialize executor
executor = SecureCommandExecutor()

# Execute whitelisted command
result = executor.execute_command('pmset_log')

# Check result
if result.return_code == 0:
    print(f"Output: {result.stdout}")
else:
    print(f"Error: {result.stderr}")
```

#### Available Commands

| Command Key | Description | Arguments Allowed |
|------------|-------------|-------------------|
| `pmset_log` | Get power management logs | No |
| `pmset_assertions` | Get power assertions | No |
| `last_reboot` | System reboot history | No |
| `last_shutdown` | System shutdown history | No |
| `log_show` | Show system logs | Yes (validated) |

#### Security Features

- **No shell execution** - All commands run with `shell=False`
- **Command whitelist** - Only pre-approved commands allowed
- **Argument validation** - Prevents injection via arguments
- **Output size limits** - Prevents memory exhaustion
- **Timeout protection** - Commands auto-terminate

### Example: Secure Log Retrieval

```python
# Execute with piping (for whitelisted commands only)
result = executor.execute_piped_command(
    'pmset_log',
    'grep "Wake"'
)

# With custom arguments (validated)
result = executor.execute_command(
    'log_show',
    ['--predicate', 'process == "kernel"', '--last', '1h']
)
```

## Data Processing

### Log Parsers

Robust parsing system with support for multiple log formats.

```python
from log_parsers import CompositeLogParser

# Initialize parser
parser = CompositeLogParser()

# Parse log content
events = parser.parse_content(log_content)

# Events are ParsedEvent objects with:
# - timestamp: datetime
# - event_type: EventType enum
# - category: EventCategory enum  
# - description: str
# - details: dict
```

#### Event Types

```python
from log_parsers import EventType

# Power events
EventType.SLEEP
EventType.WAKE
EventType.DARK_WAKE
EventType.MAINTENANCE_WAKE

# System events
EventType.BOOT
EventType.REBOOT  
EventType.SHUTDOWN

# Display events
EventType.DISPLAY_ON
EventType.DISPLAY_OFF

# User actions
EventType.LID_OPEN
EventType.LID_CLOSE
EventType.POWER_BUTTON
```

### StreamingEventProcessor

Memory-efficient event processing with streaming support.

```python
from event_processor import StreamingEventProcessor

# Initialize with limits
processor = StreamingEventProcessor(
    retention_days=10,      # Keep last 10 days
    max_events=10000,       # Max events in memory
    inactivity_threshold_seconds=60  # Pause detection
)

# Process events
processor.process_events_batch(events)

# Or stream processing
def event_generator():
    for line in large_file:
        event = parser.parse(line)
        if event:
            yield event

processor.process_event_stream(event_generator())

# Get statistics
stats = processor.calculate_statistics()
```

#### Statistics Available

```python
stats = {
    'event_count': int,
    'state_count': int,
    'date_range': {
        'first': datetime,
        'last': datetime,
        'days': int
    },
    'event_type_distribution': Dict[str, int],
    'state_type_distribution': Dict[str, float],  # hours
    'daily_stats': Dict[date, Dict[str, float]],
    'app_activity': Dict[str, Dict[str, Any]],
    'wake_reasons': Dict[str, int],
    'efficiency_metrics': {
        'total_hours': float,
        'active_hours': float,
        'productive_hours': float,
        'efficiency_percent': float
    }
}
```

### Efficient Data Retrieval

```python
# Get events by type
wake_events = processor.get_events_by_type(EventType.WAKE)

# Get events by date
today_events = processor.get_events_by_date(datetime.today())

# Get states by type
active_states = processor.get_states_by_type(StateType.ACTIVE)
```

## Thread Management

### ThreadSafeAnalysisManager

Manages concurrent analysis tasks with graceful shutdown.

```python
from thread_manager import ThreadSafeAnalysisManager

# Initialize manager
manager = ThreadSafeAnalysisManager(max_workers=4)

# Submit analysis task
def analyze_data(data):
    # Perform analysis
    return results

task_id = manager.submit_task(
    analyze_data,
    data,
    task_name="Data Analysis",
    timeout=30,  # seconds
    on_complete=lambda task_id, result, error: print(f"Done: {result}")
)

# Wait for completion
success, result = manager.wait_for_task(task_id, timeout=60)

# Get status
status = manager.get_status()
print(f"Active tasks: {status['active_tasks']}")

# Graceful shutdown
manager.shutdown(wait=True)
```

#### Progress Tracking

```python
def task_with_progress(progress_callback=None):
    for i in range(100):
        # Do work...
        if progress_callback:
            progress_callback(i / 100)
    return "completed"

manager.submit_task(
    task_with_progress,
    task_name="Progress Task",
    on_progress=lambda task_id, progress: print(f"{progress*100:.0f}%")
)
```

#### Task Management

```python
# Cancel task
cancelled = manager.cancel_task(task_id)

# Get task info
task_info = manager.get_task_info(task_id)
print(f"Status: {task_info.status}")
print(f"Duration: {task_info.duration}s")

# Clear finished tasks
cleared = manager.clear_finished_tasks()
```

## Configuration

### ApplicationConfiguration

Type-safe configuration with validation and persistence.

```python
from config_manager import ApplicationConfiguration

# Initialize configuration
config = ApplicationConfiguration()

# Get values
retention_days = config.get('analysis.retention_days', default=10)
hourly_rate = config.get('analysis.hourly_rate')

# Set values (with validation)
success = config.set('analysis.hourly_rate', 300.0)

# Batch update
config.update({
    'analysis.retention_days': 7,
    'performance.thread_pool_size': 6,
    'ui.default_theme': 'dark'
})

# Reset to defaults
config.reset_to_defaults('analysis.hourly_rate')  # Single key
config.reset_to_defaults()  # All settings
```

#### Observer Pattern

```python
# Register observer for changes
def on_config_change(key_path, old_value, new_value):
    print(f"Config changed: {key_path} = {new_value}")

config.register_observer(on_config_change)

# Changes trigger notifications
config.set('ui.default_theme', 'dark')
# Output: Config changed: ui.default_theme = dark
```

#### Import/Export

```python
# Export configuration
config.export_config(Path("./settings_backup.json"))

# Import configuration
success = config.import_config(Path("./settings_backup.json"))
```

## Logging

### Structured Logging Setup

```python
from logging_config import setup_logging, get_logging_manager

# Quick setup
setup_logging(
    app_name="MacActivityAnalyzer",
    version="1.0",
    log_level="INFO",
    structured=False  # Human-readable logs
)

# Or detailed setup
manager = get_logging_manager()

# Configure component logger
logger = manager.setup_logger(
    'analysis',
    level='DEBUG',
    file_output=True,
    file_name='analysis.log'
)

# Error logger with email alerts
error_logger = manager.setup_error_logger(
    email_errors=True,
    email_config={
        'mailhost': 'smtp.example.com',
        'fromaddr': 'app@example.com',
        'toaddrs': ['admin@example.com'],
        'subject': 'Mac Activity Analyzer Error'
    }
)
```

#### Structured Logging

```python
# Enable JSON logging
manager.setup_root_logger(structured_logs=True)

# Log with context
manager.log_with_context(
    'analysis',
    'INFO',
    'Analysis completed',
    duration=125.3,
    event_count=1523,
    status='success'
)
```

## Integration Guide

### Complete Analysis Pipeline

```python
import asyncio
from secure_executor import SecureCommandExecutor
from log_parsers import CompositeLogParser
from event_processor import StreamingEventProcessor
from thread_manager import ThreadSafeAnalysisManager
from config_manager import ApplicationConfiguration
from logging_config import setup_logging

async def analyze_system_activity():
    """Complete analysis pipeline example"""
    
    # 1. Setup
    setup_logging(app_name="ActivityAnalysis")
    config = ApplicationConfiguration()
    executor = SecureCommandExecutor()
    parser = CompositeLogParser()
    processor = StreamingEventProcessor(
        retention_days=config.get('analysis.retention_days')
    )
    manager = ThreadSafeAnalysisManager()
    
    # 2. Collect logs
    log_result = executor.execute_command('pmset_log')
    if log_result.return_code != 0:
        raise Exception(f"Failed to get logs: {log_result.stderr}")
    
    # 3. Parse logs
    events = parser.parse_content(log_result.stdout)
    
    # 4. Process events
    processor.process_events_batch(events)
    
    # 5. Run analysis
    def perform_analysis():
        return processor.calculate_statistics()
    
    task_id = manager.submit_task(
        perform_analysis,
        task_name="System Activity Analysis"
    )
    
    # 6. Get results
    success, stats = manager.wait_for_task(task_id)
    
    # 7. Cleanup
    manager.shutdown()
    
    return stats

# Run analysis
stats = asyncio.run(analyze_system_activity())
print(f"Analyzed {stats['event_count']} events")
```

### GUI Integration Example

```python
import tkinter as tk
from tkinter import ttk

class ActivityAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.setup_components()
        
    def setup_components(self):
        # Initialize secure components
        self.executor = SecureCommandExecutor()
        self.parser = CompositeLogParser()
        self.processor = StreamingEventProcessor()
        self.thread_manager = ThreadSafeAnalysisManager()
        self.config = ApplicationConfiguration()
        
    def analyze_in_background(self):
        """Run analysis without blocking GUI"""
        self.thread_manager.submit_task(
            self._perform_analysis,
            task_name="Background Analysis",
            on_complete=self._on_analysis_complete,
            on_progress=self._on_progress_update
        )
    
    def _perform_analysis(self, progress_callback=None):
        # Get logs
        if progress_callback:
            progress_callback(0.2)
        
        result = self.executor.execute_command('pmset_log')
        
        # Parse
        if progress_callback:
            progress_callback(0.4)
        
        events = self.parser.parse_content(result.stdout)
        
        # Process
        if progress_callback:
            progress_callback(0.6)
        
        self.processor.process_events_batch(events)
        
        # Calculate stats
        if progress_callback:
            progress_callback(0.8)
        
        stats = self.processor.calculate_statistics()
        
        if progress_callback:
            progress_callback(1.0)
        
        return stats
    
    def _on_analysis_complete(self, task_id, result, error):
        """Handle analysis completion in GUI thread"""
        if error:
            messagebox.showerror("Error", str(error))
        else:
            self.display_results(result)
    
    def _on_progress_update(self, task_id, progress):
        """Update progress bar"""
        self.progress_bar['value'] = progress * 100
```

## Best Practices

### 1. Security

```python
# ❌ NEVER do this
result = subprocess.run(user_input, shell=True)

# ✅ ALWAYS use SecureCommandExecutor
executor = SecureCommandExecutor()
result = executor.execute_command('pmset_log')
```

### 2. Memory Management

```python
# ❌ Loading everything into memory
all_logs = load_entire_log_file()  # May cause OOM

# ✅ Use streaming
def log_generator():
    with open(log_file) as f:
        for line in f:
            yield line

processor.process_event_stream(parse_generator(log_generator()))
```

### 3. Error Handling

```python
# ✅ Comprehensive error handling
try:
    result = executor.execute_command('pmset_log')
    if result.return_code != 0:
        logger.error(f"Command failed: {result.stderr}")
        # Graceful fallback
        return cached_data
    
    events = parser.parse_content(result.stdout)
    if not events:
        logger.warning("No events parsed from logs")
        return empty_stats
        
except Exception as e:
    logger.exception("Unexpected error in analysis")
    # Notify user appropriately
    raise
```

### 4. Configuration Validation

```python
# ✅ Always validate configuration changes
new_rate = user_input.get('hourly_rate')

# Validate before setting
if not isinstance(new_rate, (int, float)) or new_rate < 0:
    show_error("Invalid hourly rate")
    return

# Set with validation
if not config.set('analysis.hourly_rate', new_rate):
    show_error("Failed to update configuration")
```

### 5. Resource Cleanup

```python
# ✅ Always clean up resources
manager = ThreadSafeAnalysisManager()
try:
    # Do work
    manager.submit_task(analyze_data)
finally:
    # Ensure cleanup
    manager.shutdown(wait=True)
```

### 6. Logging Best Practices

```python
# ✅ Structured logging with context
logger.info(
    "Analysis completed",
    extra={
        'event_count': stats['event_count'],
        'duration': analysis_time,
        'user_id': current_user
    }
)

# ✅ Different log levels appropriately
logger.debug("Parsing line: %s", line[:50])  # Development
logger.info("Analysis started for %d events", count)  # Normal
logger.warning("Retry attempt %d of %d", attempt, max_retries)  # Issues
logger.error("Failed to parse log: %s", error)  # Errors
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```python
   # Ensure Terminal has Full Disk Access in System Preferences
   # Or use proper error handling:
   if result.stderr and "Operation not permitted" in result.stderr:
       show_permission_dialog()
   ```

2. **Memory Issues**
   ```python
   # Adjust limits based on available memory
   import psutil
   available_mb = psutil.virtual_memory().available / 1024 / 1024
   max_events = min(10000, int(available_mb * 0.1))  # Use 10% of available
   ```

3. **Slow Performance**
   ```python
   # Use appropriate worker count
   import os
   cpu_count = os.cpu_count() or 4
   optimal_workers = min(cpu_count, 8)  # Cap at 8
   ```

## Version History

- **1.0.0** - Initial secure implementation
  - Eliminated shell injection vulnerabilities
  - Added comprehensive input validation
  - Implemented memory-efficient processing
  - Added structured logging support