#!/usr/bin/env python3
"""
Simplified MacMini Activity Analyzer
Using actual log formats found on the system
"""

import subprocess
import re
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, scrolledtext

class SimpleActivityAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("Mac Activity Analyzer - Simple")
        self.root.geometry("1200x800")
        
        # Main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Button(btn_frame, text="Analyze Last 10 Days", command=self.analyze).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear", command=self.clear).pack(side='left', padx=5)
        
        # Text output
        self.output = scrolledtext.ScrolledText(main_frame, wrap='word', height=40)
        self.output.pack(fill='both', expand=True)
        
    def clear(self):
        self.output.delete('1.0', 'end')
        
    def log(self, text):
        self.output.insert('end', text + '\n')
        self.output.see('end')
        self.root.update()
        
    def run_command(self, cmd):
        """Run command and return output"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout
        except Exception as e:
            self.log(f"Error running command: {e}")
            return ""
            
    def analyze(self):
        self.clear()
        self.log("="*60)
        self.log("MAC ACTIVITY ANALYSIS")
        self.log("="*60)
        
        # 1. Get reboot/shutdown times
        self.log("\n1. SYSTEM BOOT/SHUTDOWN TIMES:")
        self.log("-"*40)
        
        reboot_output = self.run_command("last reboot | head -20")
        shutdown_output = self.run_command("last shutdown | head -20")
        
        # Parse reboot times
        reboots = []
        for line in reboot_output.split('\n'):
            if 'reboot' in line and 'time' in line:
                # Extract date from line like "reboot time                                Tue Sep  2 17:39"
                match = re.search(r'reboot\s+time\s+(\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2})', line)
                if match:
                    date_str = match.group(1)
                    self.log(f"Boot: {date_str}")
                    reboots.append(date_str)
                    
        # Parse shutdown times  
        shutdowns = []
        for line in shutdown_output.split('\n'):
            if 'shutdown' in line and 'time' in line:
                match = re.search(r'shutdown\s+time\s+(\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2})', line)
                if match:
                    date_str = match.group(1)
                    self.log(f"Shutdown: {date_str}")
                    shutdowns.append(date_str)
                    
        # 2. Get display on/off events (good indicator of user activity)
        self.log("\n2. DISPLAY ACTIVITY (User Presence):")
        self.log("-"*40)
        
        display_output = self.run_command('pmset -g log | grep "Display is turned" | tail -50')
        
        display_events = []
        for line in display_output.split('\n'):
            if 'Display is turned' in line:
                # Parse: "2025-08-29 09:46:29 +0200 Notification        Display is turned on"
                match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    timestamp = match.group(1)
                    if 'turned on' in line:
                        self.log(f"Display ON:  {timestamp}")
                        display_events.append(('on', timestamp))
                    else:
                        self.log(f"Display OFF: {timestamp}")
                        display_events.append(('off', timestamp))
                        
        # 3. Get sleep events
        self.log("\n3. SLEEP EVENTS:")
        self.log("-"*40)
        
        sleep_output = self.run_command('pmset -g log | grep "Entering Sleep" | tail -50')
        
        sleep_count = 0
        for line in sleep_output.split('\n'):
            if 'Entering Sleep' in line:
                match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    timestamp = match.group(1)
                    # Extract reason
                    reason_match = re.search(r"due to '([^']+)'", line)
                    reason = reason_match.group(1) if reason_match else "Unknown"
                    self.log(f"Sleep: {timestamp} - Reason: {reason}")
                    sleep_count += 1
                    
        # 4. Calculate daily activity summary
        self.log("\n4. DAILY ACTIVITY SUMMARY:")
        self.log("-"*40)
        
        # Get current time
        now = datetime.now()
        
        # Analyze last 10 days
        for days_ago in range(10):
            date = now - timedelta(days=days_ago)
            date_str = date.strftime('%Y-%m-%d')
            day_name = date.strftime('%A')
            
            # Count display events for this day
            day_display_on = sum(1 for event, ts in display_events if event == 'on' and date_str in ts)
            day_display_off = sum(1 for event, ts in display_events if event == 'off' and date_str in ts)
            
            if day_display_on > 0 or day_display_off > 0:
                self.log(f"\n{date_str} ({day_name}):")
                self.log(f"  Display turned on: {day_display_on} times")
                self.log(f"  Display turned off: {day_display_off} times")
                
                # Find first and last activity
                day_events = [(ts, event) for event, ts in display_events if date_str in ts]
                if day_events:
                    day_events.sort()
                    first = day_events[0][0].split()[1]
                    last = day_events[-1][0].split()[1]
                    self.log(f"  First activity: {first}")
                    self.log(f"  Last activity: {last}")
                    
        # 5. System health check
        self.log("\n5. SYSTEM HEALTH CHECK:")
        self.log("-"*40)
        
        # Check if pmset log is accessible
        test_output = self.run_command("pmset -g log | wc -l")
        if test_output.strip():
            line_count = int(test_output.strip())
            self.log(f"✓ pmset log accessible: {line_count} lines")
        else:
            self.log("✗ Cannot access pmset log - may need permissions")
            
        # Check last reboot
        last_output = self.run_command("last reboot | head -1")
        if last_output.strip():
            self.log(f"✓ Last command working: {last_output.strip()[:50]}...")
        else:
            self.log("✗ Cannot access last command")
            
        self.log("\n" + "="*60)
        self.log("ANALYSIS COMPLETE")
        self.log("="*60)

def main():
    root = tk.Tk()
    app = SimpleActivityAnalyzer(root)
    root.mainloop()

if __name__ == "__main__":
    main()