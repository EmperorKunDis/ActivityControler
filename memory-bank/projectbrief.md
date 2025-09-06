# MacOS Activity Tracker - Project Brief

## Core Mission
Create a streamlined, beautiful MacOS activity tracker with minute-by-minute precision, financial calculations, and modern glassmorphism design.

## Key Requirements

### 1. Design Philosophy
- **Glassmorphism borderless app style** - translucent, modern UI
- **Minimalist approach** - remove unnecessary complexity
- **MacOS-focused** - leverage native system capabilities

### 2. Core Features
- **Minute-by-minute activity tracking** with precise timeline
- **Financial calculations** with customizable hourly rates
- **Last 10 days analysis** scope
- **Manual refresh** with dedicated refresh controls

### 3. Special Live Monitoring Feature
- **Always-on-top 20x20px square** in left bottom corner
- **Real-time activity indicator**:
  - 🟢 Green: Active (< 60 seconds idle)
  - 🟠 Orange: Short break (60s - 5min idle)  
  - 🔴 Red: Long break (> 5min idle)
- **Toggleable** via special button in main app
- **Data logging** to enhance main timeline analysis

### 4. Data Sources (Full MacOS Potential)
```bash
last reboot | head -20                                    # System reboots
pmset -g log | grep -e "Wake" -e "Sleep" -e "Shutdown"   # Power events
pmset -g log | grep -E "Wake|Sleep|Shutdown" | tail -100  # Recent events
```

### 5. Technical Constraints
- **Python 3.8+** with tkinter
- **Minimal dependencies** - remove heavy libraries
- **MacOS-only** optimization
- **Normal window** for main app, **always-on-top** for indicator

## Success Criteria
1. Beautiful, modern glassmorphism interface
2. Accurate minute-by-minute activity tracking
3. Reliable financial calculations
4. Smooth real-time monitoring capability
5. Clean, maintainable codebase
