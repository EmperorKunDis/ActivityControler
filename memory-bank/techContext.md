# Technical Context

## Current Technology Stack
- **Python 3.8+** - Core runtime
- **tkinter** - GUI framework (native to Python)
- **subprocess** - MacOS system command execution
- **datetime** - Time handling and calculations
- **threading** - Background data processing
- **queue** - Thread-safe communication

## Dependencies to Remove
- **pandas** - Heavy data processing (replace with native Python)
- **matplotlib** - Complex plotting (replace with tkinter Canvas)
- **plotly** - Web-based plotting (not needed)
- **pillow** - Image processing (not needed for this use case)

## New Minimal Dependencies
```txt
python-dateutil==2.8.2  # Keep for robust date parsing
```

## MacOS System Integration

### Primary Data Sources
```bash
# System reboot history
last reboot | head -20

# Power management events
pmset -g log | grep -e "Wake" -e "Sleep" -e "Shutdown"
pmset -g log | grep -E "Wake|Sleep|Shutdown" | tail -100

# Real-time idle detection (for live monitoring)
ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print int($NF/1000000000); exit}'
```

### System Requirements
- **macOS 11+** (Big Sur and newer)
- **Terminal permissions** for system log access
- **Accessibility permissions** for idle time detection

## Architecture Design

### Main Application (`mac_activity_tracker.py`)
- **Glassmorphism UI** with borderless window
- **Manual refresh** data collection
- **Financial calculations** with customizable rates
- **Timeline visualization** using tkinter Canvas

### Live Monitor (`activity_monitor.py`)
- **20x20px always-on-top window**
- **Real-time idle detection**
- **Color-coded status indicator**
- **Data logging** for main app integration

### Data Processing Pipeline
1. **Collection** - Execute MacOS commands
2. **Parsing** - Extract timestamps and events
3. **Analysis** - Calculate minute-by-minute states
4. **Visualization** - Render timeline blocks
5. **Financial** - Compute earnings and rates

## Performance Considerations
- **Lazy loading** - Only process data when needed
- **Caching** - Store parsed results to avoid re-computation
- **Efficient rendering** - Use Canvas for smooth graphics
- **Memory management** - Limit data retention to 10 days
