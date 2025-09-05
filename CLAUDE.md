# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ActivityController is a macOS desktop application for analyzing Mac computer activity with financial reporting capabilities. It reads system logs to track computer usage over the past 10 days and provides visual analytics with billing calculations.

## Technology Stack

- **Language**: Python 3.13
- **GUI Framework**: Tkinter with ttk themed widgets
- **Data Processing**: pandas 2.1.4
- **Visualization**: matplotlib 3.8.2 (embedded charts), plotly 5.18.0 (interactive)
- **Platform**: macOS exclusive (requires macOS 11+, optimized for Apple Silicon)

## Common Development Commands

```bash
# Run the application
python3 mac_activity_gui.py

# Run with dependency installation
python3 run_app.py

# Alternative launcher with permissions setup
./START_APP.command

# Install dependencies manually
pip install -r requirements.txt

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
```

## Architecture Overview

### Main Application Structure (mac_activity_gui.py)

The application follows a single-file architecture with clear component separation:

1. **MacActivityGUI Class**: Core application orchestrator
   - Manages 4-tab GUI using tkinter.ttk.Notebook
   - Coordinates data collection, processing, and visualization
   - Handles threading for background analysis

2. **Data Processing Pipeline**:
   ```
   System logs (pmset -g log, last reboot) → Event parsing → State analysis → Visualization
   ```

3. **Tab Structure**:
   - **Graph Tab**: Interactive matplotlib timeline with color-coded activity states
   - **Statistics Tab**: Daily activity breakdown with pandas DataFrames
   - **Finance Tab**: Configurable billing calculations (default: 40h = 10,000 CZK)
   - **Raw Data Tab**: Direct log viewing for debugging

4. **State Classification**:
   - Active (green): <60 seconds between events
   - Pause (red): >60 seconds of inactivity
   - Sleep (gray): System sleep state
   - Shutdown (black): System powered off

### Key Data Structures

- `self.events`: Raw parsed events from system logs
- `self.states`: Processed time intervals with state classifications
- Threading model: Background analysis with queue-based GUI updates
- Interactive features: Click on graph segments for detailed information

### System Integration

The app uses shell commands to read macOS system logs:
- `pmset -g log`: Power management events (sleep/wake)
- `last reboot`: System boot times
- Requires Terminal permissions in System Preferences

## Important Patterns

1. **Event-Driven Design**: All data flows from system events through processing to visualization
2. **Thread Safety**: Background analysis uses queues to update GUI safely
3. **Interactive Visualization**: matplotlib event handling for clickable timeline segments
4. **Financial Calculations**: Configurable hourly rate with automatic weekly/monthly projections

## Development Notes

- Single-file application design for easy distribution
- Czech language UI (per client requirements)
- No real-time monitoring - analyzes historical logs only
- Respects privacy - tracks only activity timing, not content
- HTML export functionality for reports

## Testing Approach

As this is a GUI application analyzing system logs:
1. Manual testing with different activity patterns
2. Verify calculations with known time periods
3. Test on different macOS versions (11+)
4. Check permissions handling for first-time users

## File Structure

```
/ActivityControler/
├── mac_activity_gui.py      # Main application
├── run_app.py              # Python launcher with auto-install
├── START_APP.command       # Bash launcher with venv setup
├── requirements.txt        # Python dependencies
├── README.md              # User documentation (Czech)
└── venv/                  # Virtual environment (generated)
```