# Active Context

## Current Work Focus
Building a completely new MacOS Activity Tracker to replace the existing complex application with a streamlined, beautiful glassmorphism design.

## Key Changes from Original
1. **UI Transformation**: From complex multi-tab interface to clean glassmorphism single-view
2. **Feature Reduction**: Remove unnecessary complexity, keep only essential features
3. **Enhanced Data Collection**: Fully utilize MacOS system commands for precise tracking
4. **Live Monitoring**: Add real-time 20x20px indicator with always-on-top behavior

## Implementation Strategy

### Phase 1: Core Application (Current)
- Create new `mac_activity_tracker.py` with glassmorphism UI
- Implement minute-by-minute data collection and analysis
- Build financial calculation engine
- Create timeline visualization with tkinter Canvas

### Phase 2: Live Monitor
- Create separate `activity_monitor.py` for real-time tracking
- Implement always-on-top 20x20px indicator window
- Add real-time idle detection using `ioreg` command
- Integrate with main application data

### Phase 3: Integration & Polish
- Update requirements.txt with minimal dependencies
- Test and refine glassmorphism styling
- Ensure smooth data flow between components
- Update documentation and launchers

## Technical Decisions Made
- **Remove heavy dependencies**: pandas, matplotlib, plotly, pillow
- **Keep minimal stack**: tkinter, subprocess, datetime, threading
- **Use native Canvas**: Replace matplotlib with tkinter drawing
- **MacOS-specific optimization**: Leverage system commands fully

## Current File Structure Plan
```
ActivityController/
├── mac_activity_tracker.py     # New main application (glassmorphism)
├── activity_monitor.py         # Live monitoring indicator
├── requirements.txt            # Simplified dependencies
├── run.command                # Updated launcher
└── memory-bank/               # Project documentation
    ├── projectbrief.md
    ├── techContext.md
    └── activeContext.md
```

## Next Immediate Steps
1. Create new simplified requirements.txt
2. Build main application with glassmorphism UI
3. Implement data collection and analysis engine
4. Create timeline visualization
5. Add financial calculations with customizable rates
