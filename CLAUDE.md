# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ActivityController is a macOS desktop application for analyzing Mac computer activity with financial reporting capabilities. The project has evolved from a simple pandas-based analyzer to a glassmorphism-styled activity tracker with real-time monitoring.

## Active Applications

The project contains multiple versions of the application:
- **mac_activity_gui.py**: Full-featured GUI with pandas/matplotlib (original version)
- **mac_activity_tracker.py**: Glassmorphism redesign with minimal dependencies
- **activity_monitor.py**: 20x20px live activity indicator

## Technology Stack

### Current Stack (Glassmorphism Version)
- **Language**: Python 3.8+
- **GUI Framework**: Tkinter only
- **Dependencies**: python-dateutil==2.8.2
- **Platform**: macOS 11+ (Big Sur and newer)

### Legacy Stack (GUI Version)
- **Language**: Python 3.13
- **GUI Framework**: Tkinter with ttk themed widgets
- **Data Processing**: pandas 2.1.4
- **Visualization**: matplotlib 3.8.2, plotly 5.18.0
- **Platform**: macOS exclusive (optimized for Apple Silicon)

## Common Development Commands

```bash
# Run the glassmorphism version (minimal dependencies)
python3 mac_activity_tracker.py

# Run the full GUI version (requires pandas/matplotlib)
python3 mac_activity_gui.py

# Run with dependency installation
python3 run_app.py

# Alternative launchers
./run.command           # Glassmorphism version launcher
./START_APP.command     # GUI version launcher

# Install dependencies
pip install -r requirements.txt

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Test system log access
pmset -g log | grep -E 'Wake|Sleep|Shutdown' | tail -10
last reboot | head -5
ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print int($NF/1000000000); exit}'
```

## Architecture Overview

### Data Collection Pipeline

The application extracts activity data from multiple macOS system sources:

1. **Power Management Logs** (`pmset -g log`):
   - Wake/Sleep events
   - Display on/off
   - DarkWake/Maintenance wake
   - PowerButton/LidOpen/LidClose events
   - Shutdown events

2. **System Boot History** (`last reboot/shutdown`):
   - Reboot timestamps with user/console info
   - Shutdown timestamps

3. **Real-time Idle Detection** (`ioreg -c IOHIDSystem`):
   - Current idle time in seconds
   - Used by activity_monitor.py for live tracking

### State Classification

States are determined by idle duration between events:
- **Active** (green): <60 seconds idle
- **Pause/Short Break** (red/orange): 60s-5min idle  
- **Long Break** (red): >5min idle
- **Sleep** (gray): System sleep state
- **Shutdown** (black): System powered off
- **Maintenance** (orange): Background wake events

### Key Components

#### mac_activity_gui.py
- `MacActivityGUI` class: Main application controller
- 4-tab interface (Graph, Statistics, Finance, Raw Data)
- Enhanced data extraction with metadata (wake reasons, users)
- Interactive matplotlib timeline with legend
- Thread-safe background analysis

#### mac_activity_tracker.py
- Single-window glassmorphism design
- Minimal dependencies (no pandas/matplotlib)
- Canvas-based timeline rendering
- Integrated live monitor launcher
- JSON-based settings persistence

#### activity_monitor.py
- 20x20px always-on-top indicator
- Real-time activity state display
- Logs data to `activity_monitor_log.json`
- Minimal resource usage

## Data Structures

### Event Format
```python
{
    'timestamp': datetime,
    'type': str,  # wake, sleep, reboot, shutdown, etc.
    'wake_reason': str,  # Optional: reason for wake
    'user': str,  # Optional: user who triggered event
    'console': str,  # Optional: console/terminal info
    'raw': str  # Original log line
}
```

### State Format
```python
{
    'start': datetime,
    'end': datetime,
    'state': str,  # active, pause, sleep, shutdown, maintenance
    'color': str,  # Color code for visualization
    'duration': float,  # Seconds
    'event_type': str,
    'wake_reason': str,  # Optional metadata
    'user': str,  # Optional metadata
    'raw': str  # Source event data
}
```

## Important Implementation Details

1. **Threading**: Background analysis runs in separate thread with queue-based GUI updates
2. **Permissions**: Requires Terminal access to system logs (System Preferences → Security & Privacy)
3. **Time Handling**: Handles year boundaries for `last` command output
4. **Czech UI**: Interface text is in Czech per client requirements
5. **Financial Calculations**: Default rate 250 Kč/hour (10,000 Kč per 40 hours)

## File Structure

```
/ActivityControler/
├── mac_activity_gui.py         # Full GUI with pandas/matplotlib
├── mac_activity_tracker.py     # Glassmorphism minimal version
├── activity_monitor.py         # Live 20x20px indicator
├── run_app.py                 # Python launcher with auto-install
├── run.command                # Glassmorphism launcher script
├── START_APP.command          # GUI version launcher
├── requirements.txt           # Minimal deps (dateutil only)
├── activity_settings.json     # User preferences (auto-created)
├── activity_monitor_log.json  # Live monitor data (auto-created)
├── activity_monitor.pid       # Monitor process ID (auto-created)
├── README.md                  # User documentation
└── memory-bank/               # Project documentation
```

## Testing Approach

Since this analyzes system logs, testing requires:
1. Manual verification with known activity patterns
2. Cross-checking timestamps with actual usage
3. Testing permission handling for first-time users
4. Verifying calculations match expected values
5. Testing on different macOS versions (11+)

## Recent Enhancements

The data mining capabilities were recently enhanced to extract:
- Extended pmset log patterns (DarkWake, Maintenance, PowerButton, Lid events)
- User and console information from reboot/shutdown logs
- Wake reasons from power management events
- System kernel logs for additional wake information
- Comprehensive event statistics and summaries