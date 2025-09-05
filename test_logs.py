#!/usr/bin/env python3
"""
Test script to verify system log parsing
"""

import subprocess
import re
from datetime import datetime, timedelta

def test_command(cmd, description):
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
        else:
            output = result.stdout.strip()
            lines = output.split('\n')
            print(f"Output lines: {len(lines)}")
            print("\nFirst 10 lines:")
            for i, line in enumerate(lines[:10]):
                print(f"{i+1}: {line}")
            
            if len(lines) > 10:
                print(f"\n... and {len(lines) - 10} more lines")
                
        return result.stdout
    except Exception as e:
        print(f"Exception: {e}")
        return ""

def analyze_pmset_patterns(output):
    """Analyze different patterns in pmset output"""
    print("\n" + "="*60)
    print("Analyzing pmset patterns:")
    print("="*60)
    
    patterns = {
        'Sleep': r'Sleep',
        'Wake': r'Wake',
        'DarkWake': r'DarkWake',
        'Entering Sleep': r'Entering Sleep',
        'Display is turned': r'Display is turned',
        'Assertions': r'Assertions',
        'SystemWake': r'SystemWake',
        'kernel': r'kernel',
    }
    
    for name, pattern in patterns.items():
        matches = len(re.findall(pattern, output, re.IGNORECASE))
        print(f"{name}: {matches} matches")

def find_actual_sleep_wake():
    """Try different pmset commands to find actual sleep/wake events"""
    print("\n" + "="*60)
    print("Searching for actual sleep/wake events:")
    print("="*60)
    
    # Try different grep patterns
    commands = [
        ('pmset -g log | grep -i "sleep"', 'All sleep events'),
        ('pmset -g log | grep -i "wake"', 'All wake events'),
        ('pmset -g log | grep "kernel" | grep -E "sleep|wake"', 'Kernel sleep/wake'),
        ('pmset -g log | grep "Display is turned"', 'Display events'),
        ('pmset -g log | grep "Entering Sleep"', 'Entering sleep events'),
        ('pmset -g log | grep -E "Sleep|Wake" | grep -v "Assertions"', 'Sleep/Wake without Assertions'),
        ('log show --style syslog --predicate \'eventMessage contains "sleep"\' --last 1h', 'System log sleep events'),
    ]
    
    for cmd, desc in commands:
        output = test_command(cmd, desc)
        if output and len(output.strip()) > 0:
            lines = output.strip().split('\n')
            if len(lines) < 50:  # Only show if reasonable number of results
                print("\nParsing attempts:")
                for line in lines[:5]:
                    # Try to extract timestamp
                    match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if match:
                        print(f"  Timestamp found: {match.group(1)}")

def main():
    print("System Activity Log Parser Test")
    print("="*60)
    
    # Test last reboot
    reboot_output = test_command('last reboot | head -20', 'Last reboot times')
    
    # Test shutdown
    shutdown_output = test_command('last shutdown | head -10', 'Last shutdown times')
    
    # Test pmset
    pmset_output = test_command('pmset -g log | tail -100', 'Recent pmset log')
    
    # Analyze patterns
    if pmset_output:
        analyze_pmset_patterns(pmset_output)
    
    # Try to find actual sleep/wake events
    find_actual_sleep_wake()
    
    # Test date parsing for reboot
    print("\n" + "="*60)
    print("Testing date parsing for reboot/shutdown:")
    print("="*60)
    
    if reboot_output:
        for line in reboot_output.split('\n')[:5]:
            if 'reboot' in line or 'shutdown' in line:
                print(f"\nLine: {line}")
                # Try to extract the date
                # Pattern: "reboot    ~                         Sat Aug 30 10:21"
                match = re.search(r'(reboot|shutdown)\s+~?\s+(.+)', line)
                if match:
                    date_str = match.group(2).strip()
                    print(f"  Extracted date string: '{date_str}'")
                    
                    # Try parsing different formats
                    formats = [
                        '%a %b %d %H:%M',
                        '%a %b %d %H:%M:%S %Y',
                        '%a %b %d %H:%M %Y',
                    ]
                    
                    for fmt in formats:
                        try:
                            parsed = datetime.strptime(date_str[:15], fmt[:15])
                            print(f"  Parsed with format '{fmt}': {parsed}")
                            break
                        except:
                            continue

if __name__ == "__main__":
    main()