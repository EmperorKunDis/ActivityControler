# Mac Activity Analyzer - Advanced Version 🚀

## Comprehensive macOS Activity Analysis with 7 Specialized Modules

### 🎯 Quick Start

**Double-click `START_APP.command`**
- First run: Allow in Settings → Privacy & Security
- Automatically installs all dependencies
- Creates virtual environment
- Launches the advanced analyzer

That's it! The script handles everything automatically.

### ✨ Advanced Features

#### 📊 7 Comprehensive Analysis Tabs

1. **📊 Graf aktivity (Activity Graph)**
   - Interactive matplotlib timeline
   - Color-coded activity states
   - Click for detailed information

2. **📋 Přehled (Overview)**
   - Summary statistics
   - System health metrics
   - Quick insights

3. **📱 Aplikace (Application Analysis)** 
   - Track which apps prevent sleep
   - App activity pie charts
   - Power assertion analysis
   - Identify battery-draining apps

4. **😴 Spánek/Probuzení (Sleep/Wake Analysis)**
   - Sleep duration histograms
   - Wake reason categorization
   - Sleep pattern heatmaps
   - Identify sleep disruptions

5. **📈 Statistiky (Statistics)**
   - Mean, median, std deviation
   - Activity distribution
   - Pattern detection
   - Trend analysis

6. **🕒 Timeline**
   - Granular event display
   - All event types in one view
   - Interactive selection
   - Event filtering

7. **💰 Finance**
   - Configurable hourly rate
   - Earnings calculation
   - Productivity metrics
   - Work hour tracking

### 📊 Data Sources

The advanced version analyzes multiple macOS system logs:

```bash
# Power management events
pmset -g log | grep -E "Wake|Sleep|Shutdown|Display"

# Application assertions (NEW)
pmset -g log | grep "Assertions"

# System boot/shutdown
last reboot | head -50
last shutdown | head -20

# Kernel logs
log show --style syslog --predicate 'process == "kernel"'
```

### 🔍 Unique Advanced Capabilities

1. **Application Tracking**
   - Monitors which apps hold wake locks
   - Tracks app-specific power usage
   - Identifies problematic applications

2. **Advanced Sleep Analysis**
   - Statistical sleep pattern analysis
   - Wake reason categorization
   - Sleep quality metrics

3. **Export/Import**
   - Save analysis results
   - Load historical data
   - Generate reports

4. **Pattern Detection**
   - Identifies recurring issues
   - Suggests optimizations
   - Trend analysis

### 🛠️ Technical Details

#### Dependencies
- **Python 3.8+**
- **pandas** - Data analysis
- **matplotlib** - Visualization
- **tkinter** - GUI (built-in)

#### System Requirements
- **macOS 11+** (Big Sur and newer)
- **Terminal permissions** for system log access
- **50 MB** free space (with dependencies)

### 📁 File Structure

```
ActivityControler/
├── mac_activity_advanced.py  # Main advanced application (1,232 lines)
├── START_APP.command        # One-click launcher
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── CLAUDE.md              # AI assistant documentation
└── memory-bank/           # Project documentation
```

### 🎯 Use Cases

1. **Developers**: Identify apps causing battery drain
2. **Power Users**: Optimize system performance
3. **IT Administrators**: Analyze usage patterns
4. **Freelancers**: Track billable hours accurately
5. **Troubleshooting**: Find sleep/wake issues

### 💡 Key Insights Provided

- Which applications prevent your Mac from sleeping
- How long your system actually sleeps vs stays awake
- Detailed breakdown of wake reasons
- Application-specific power impact
- Work session patterns and productivity metrics

### 🆘 Troubleshooting

**"Permission denied"**
```bash
chmod +x START_APP.command
```

**"No module named pandas"**
```bash
pip install -r requirements.txt
```

**"No data found"**
- Ensure Terminal has Full Disk Access in System Preferences
- Mac must have been running for several hours
- Try running with sudo if needed

### 🔧 Advanced Configuration

The application supports various configuration options:
- Adjustable analysis time window
- Configurable idle thresholds
- Custom export formats
- Filtering options

### 📈 What Makes This "Advanced"?

1. **7 tabs** instead of 4 (standard version)
2. **Application-level tracking** with power assertions
3. **Statistical analysis** with pandas
4. **Pattern detection** algorithms
5. **Export/Import** capabilities
6. **More granular data** extraction

---

**Version:** Advanced Edition  
**Language:** Czech UI with English documentation  
**Optimized for:** Power users and system administrators  
**Last Updated:** 2024