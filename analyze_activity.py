#!/usr/bin/env python3
"""
Command-line activity analyzer for debugging
"""

import subprocess
import re
from datetime import datetime, timedelta
from collections import defaultdict

def run_command(cmd):
    """Run command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout
    except Exception as e:
        print(f"Error running command: {e}")
        return ""

def parse_display_events():
    """Parse display on/off events"""
    print("\nParsing display events...")
    output = run_command('pmset -g log | grep "Display is turned" | tail -100')
    
    events = []
    for line in output.strip().split('\n'):
        if not line:
            continue
            
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if match:
            timestamp_str = match.group(1)
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            
            if 'turned on' in line:
                events.append({'time': timestamp, 'type': 'display_on'})
            else:
                events.append({'time': timestamp, 'type': 'display_off'})
                
    print(f"Found {len(events)} display events")
    return events

def parse_sleep_events():
    """Parse sleep events"""
    print("\nParsing sleep events...")
    output = run_command('pmset -g log | grep "Entering Sleep" | tail -100')
    
    events = []
    for line in output.strip().split('\n'):
        if not line:
            continue
            
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if match:
            timestamp_str = match.group(1)
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            
            # Extract reason
            reason_match = re.search(r"due to '([^']+)'", line)
            reason = reason_match.group(1) if reason_match else "Unknown"
            
            events.append({
                'time': timestamp,
                'type': 'sleep',
                'reason': reason
            })
            
    print(f"Found {len(events)} sleep events")
    return events

def parse_wake_events():
    """Parse wake events (DarkWake and regular)"""
    print("\nParsing wake events...")
    output = run_command('pmset -g log | grep -E "DarkWake|Wake from" | tail -100')
    
    events = []
    for line in output.strip().split('\n'):
        if not line:
            continue
            
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if match:
            timestamp_str = match.group(1)
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            
            if 'DarkWake' in line:
                events.append({'time': timestamp, 'type': 'darkwake'})
            else:
                events.append({'time': timestamp, 'type': 'wake'})
                
    print(f"Found {len(events)} wake events")
    return events

def calculate_active_time(events):
    """Calculate active time based on events"""
    # Sort all events by time
    all_events = sorted(events, key=lambda x: x['time'])
    
    # Group by day
    daily_stats = defaultdict(lambda: {
        'first_activity': None,
        'last_activity': None,
        'display_on_count': 0,
        'sleep_count': 0,
        'active_periods': []
    })
    
    for event in all_events:
        date = event['time'].date()
        stats = daily_stats[date]
        
        # Update first/last activity
        if stats['first_activity'] is None or event['time'] < stats['first_activity']:
            stats['first_activity'] = event['time']
        if stats['last_activity'] is None or event['time'] > stats['last_activity']:
            stats['last_activity'] = event['time']
            
        # Count events
        if event['type'] == 'display_on':
            stats['display_on_count'] += 1
        elif event['type'] == 'sleep':
            stats['sleep_count'] += 1
            
    return daily_stats

def main():
    print("="*60)
    print("MAC ACTIVITY ANALYZER")
    print("="*60)
    
    # Collect all events
    all_events = []
    
    # Get display events
    display_events = parse_display_events()
    all_events.extend(display_events)
    
    # Get sleep events
    sleep_events = parse_sleep_events()
    all_events.extend(sleep_events)
    
    # Get wake events
    wake_events = parse_wake_events()
    all_events.extend(wake_events)
    
    # Calculate daily statistics
    print("\nCalculating daily statistics...")
    daily_stats = calculate_active_time(all_events)
    
    # Print results
    print("\n" + "="*60)
    print("DAILY ACTIVITY SUMMARY (Last 10 Days)")
    print("="*60)
    
    # Sort dates in reverse order
    sorted_dates = sorted(daily_stats.keys(), reverse=True)
    
    # Limit to last 10 days
    cutoff_date = datetime.now().date() - timedelta(days=10)
    
    for date in sorted_dates:
        if date < cutoff_date:
            continue
            
        stats = daily_stats[date]
        
        print(f"\n{date.strftime('%Y-%m-%d (%A)')}")
        print("-" * 40)
        
        if stats['first_activity'] and stats['last_activity']:
            print(f"First activity: {stats['first_activity'].strftime('%H:%M:%S')}")
            print(f"Last activity:  {stats['last_activity'].strftime('%H:%M:%S')}")
            
            # Calculate total time span
            total_span = stats['last_activity'] - stats['first_activity']
            hours = total_span.total_seconds() / 3600
            print(f"Total span:     {hours:.1f} hours")
            
        print(f"Display on:     {stats['display_on_count']} times")
        print(f"Sleep events:   {stats['sleep_count']} times")
        
    # Print recent events for debugging
    print("\n" + "="*60)
    print("RECENT EVENTS (Last 20)")
    print("="*60)
    
    recent_events = sorted(all_events, key=lambda x: x['time'], reverse=True)[:20]
    
    for event in recent_events:
        time_str = event['time'].strftime('%Y-%m-%d %H:%M:%S')
        event_type = event['type']
        
        if event_type == 'sleep' and 'reason' in event:
            print(f"{time_str} - {event_type} ({event['reason']})")
        else:
            print(f"{time_str} - {event_type}")

if __name__ == "__main__":
    main()