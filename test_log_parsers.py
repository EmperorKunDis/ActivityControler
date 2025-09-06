#!/usr/bin/env python3
"""
Unit tests for Log Parsers
Tests parsing robustness, format handling, and data validation
"""

import unittest
from datetime import datetime, timedelta
from log_parsers import (
    ParsedEvent, EventType, EventCategory, LogParser,
    PmsetLogParser, LastCommandParser, CompositeLogParser,
    filter_events_by_type, filter_events_by_timerange, group_events_by_day
)


class TestParsedEvent(unittest.TestCase):
    """Test cases for ParsedEvent dataclass"""
    
    def test_valid_event_creation(self):
        """Test creation of valid event"""
        event = ParsedEvent(
            timestamp=datetime.now(),
            event_type=EventType.WAKE,
            category=EventCategory.POWER,
            description="Test wake event",
            raw_line="2024-01-15 10:30:45 Wake from sleep",
            details={'wake_reason': 'User Activity'}
        )
        
        self.assertEqual(event.event_type, EventType.WAKE)
        self.assertEqual(event.category, EventCategory.POWER)
        self.assertIsInstance(event.timestamp, datetime)
    
    def test_invalid_timestamp_type(self):
        """Test validation rejects invalid timestamp type"""
        with self.assertRaises(ValueError) as context:
            ParsedEvent(
                timestamp="not a datetime",
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description="Test",
                raw_line="test"
            )
        
        self.assertIn("Neplatný typ timestamp", str(context.exception))
    
    def test_future_timestamp_rejection(self):
        """Test validation rejects future timestamps"""
        with self.assertRaises(ValueError) as context:
            ParsedEvent(
                timestamp=datetime.now() + timedelta(days=1),
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description="Test",
                raw_line="test"
            )
        
        self.assertIn("budoucnosti", str(context.exception))
    
    def test_event_to_dict(self):
        """Test conversion to dictionary"""
        event = ParsedEvent(
            timestamp=datetime(2024, 1, 15, 10, 30, 45),
            event_type=EventType.SLEEP,
            category=EventCategory.POWER,
            description="Sleep event",
            raw_line="test line",
            details={'reason': 'idle'}
        )
        
        event_dict = event.to_dict()
        
        self.assertEqual(event_dict['timestamp'], '2024-01-15T10:30:45')
        self.assertEqual(event_dict['event_type'], 'sleep')
        self.assertEqual(event_dict['category'], 'power')
        self.assertEqual(event_dict['details']['reason'], 'idle')


class TestPmsetLogParser(unittest.TestCase):
    """Test cases for PmsetLogParser"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.parser = PmsetLogParser()
    
    def test_standard_format_parsing(self):
        """Test parsing of standard pmset log format"""
        line = "2024-01-15 10:30:45 +0100 Wake from Normal Sleep [CDNVA] : due to UserActivity Assertion"
        
        self.assertTrue(self.parser.can_parse(line))
        event = self.parser.parse(line)
        
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, EventType.WAKE)
        self.assertEqual(event.category, EventCategory.POWER)
        self.assertEqual(event.timestamp.year, 2024)
        self.assertEqual(event.timestamp.month, 1)
        self.assertEqual(event.timestamp.day, 15)
        self.assertEqual(event.details['wake_reason'], 'UserActivity Assertion')
    
    def test_standard_format_no_timezone(self):
        """Test parsing without timezone"""
        line = "2024-01-15 10:30:45 Entering Sleep state"
        
        event = self.parser.parse(line)
        
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, EventType.SLEEP)
    
    def test_alternate_format_parsing(self):
        """Test parsing of alternate date format"""
        line = "Mon Jan 15 10:30:45 Display is turned on"
        
        event = self.parser.parse(line)
        
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, EventType.DISPLAY_ON)
        self.assertEqual(event.timestamp.hour, 10)
        self.assertEqual(event.timestamp.minute, 30)
    
    def test_sleep_event_reasons(self):
        """Test extraction of different sleep reasons"""
        sleep_lines = [
            ("Clamshell Sleep", "Clamshell"),
            ("Maintenance Sleep", "Maintenance"),
            ("Software Sleep", "Software"),
            ("Idle Sleep", "Idle"),
            ("Entering Sleep", None)  # No specific reason
        ]
        
        for line_content, expected_reason in sleep_lines:
            line = f"2024-01-15 10:30:45 {line_content}"
            event = self.parser.parse(line)
            
            if expected_reason:
                self.assertEqual(event.details.get('sleep_reason'), expected_reason)
    
    def test_wake_event_types(self):
        """Test different wake event types"""
        wake_lines = [
            "Wake from Normal Sleep",
            "DarkWake from Deep Idle",
            "DarkWake to FullWake",
            "Maintenance wake"
        ]
        
        expected_types = [
            EventType.WAKE,
            EventType.DARK_WAKE,
            EventType.DARK_WAKE,
            EventType.MAINTENANCE_WAKE
        ]
        
        for line_content, expected_type in zip(wake_lines, expected_types):
            line = f"2024-01-15 10:30:45 {line_content}"
            event = self.parser.parse(line)
            
            self.assertEqual(event.event_type, expected_type)
    
    def test_assertion_parsing(self):
        """Test parsing of power assertions"""
        create_line = "2024-01-15 10:30:45 Assertion created: PID 123(Safari) Created PreventUserIdleDisplaySleep"
        release_line = "2024-01-15 10:35:00 Assertion released: PID 123(Safari) Released PreventUserIdleDisplaySleep"
        
        create_event = self.parser.parse(create_line)
        self.assertEqual(create_event.event_type, EventType.ASSERTION_CREATE)
        self.assertEqual(create_event.details['pid'], 123)
        self.assertEqual(create_event.details['process'], 'Safari')
        self.assertEqual(create_event.details['assertion_type'], 'PreventUserIdleDisplaySleep')
        
        release_event = self.parser.parse(release_line)
        self.assertEqual(release_event.event_type, EventType.ASSERTION_RELEASE)
    
    def test_display_events(self):
        """Test display on/off events"""
        on_line = "2024-01-15 10:30:45 Display is turned on"
        off_line = "2024-01-15 22:30:45 Display is turned off"
        
        on_event = self.parser.parse(on_line)
        self.assertEqual(on_event.event_type, EventType.DISPLAY_ON)
        
        off_event = self.parser.parse(off_line)
        self.assertEqual(off_event.event_type, EventType.DISPLAY_OFF)
    
    def test_lid_events(self):
        """Test lid open/close events"""
        open_line = "2024-01-15 10:30:45 LidOpen"
        close_line = "2024-01-15 22:30:45 LidClose"
        
        open_event = self.parser.parse(open_line)
        self.assertEqual(open_event.event_type, EventType.LID_OPEN)
        
        close_event = self.parser.parse(close_line)
        self.assertEqual(close_event.event_type, EventType.LID_CLOSE)
    
    def test_invalid_line_handling(self):
        """Test handling of unparseable lines"""
        invalid_lines = [
            "",
            "Random text without timestamp",
            "2024-13-45 25:99:99 Invalid date",
            "\x00\x01\x02 Binary data"
        ]
        
        for line in invalid_lines:
            result = self.parser.parse(line)
            self.assertIsNone(result)
    
    def test_year_correction(self):
        """Test automatic year correction for formats without year"""
        # Simulate parsing at year boundary
        current_year = datetime.now().year
        
        # Date in the past (should use current year)
        past_line = "Mon Jan 15 10:30:45 Wake from sleep"
        past_event = self.parser.parse(past_line)
        
        # Date in the future (should use previous year)
        future_line = "Mon Dec 31 23:59:59 Sleep"
        future_event = self.parser.parse(future_line)
        
        self.assertIsNotNone(past_event)
        self.assertLessEqual(past_event.timestamp, datetime.now())


class TestLastCommandParser(unittest.TestCase):
    """Test cases for LastCommandParser"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.parser = LastCommandParser()
    
    def test_reboot_parsing(self):
        """Test parsing of reboot entries"""
        line = "reboot    ~                         Wed Oct 25 09:15"
        
        self.assertTrue(self.parser.can_parse(line))
        event = self.parser.parse(line)
        
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, EventType.REBOOT)
        self.assertEqual(event.category, EventCategory.SYSTEM)
        self.assertEqual(event.details['console'], 'system')
    
    def test_shutdown_parsing(self):
        """Test parsing of shutdown entries"""
        line = "shutdown  ~                         Tue Oct 24 22:30"
        
        event = self.parser.parse(line)
        
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, EventType.SHUTDOWN)
        self.assertEqual(event.description, "Systém vypnut")
    
    def test_console_parsing(self):
        """Test parsing of console information"""
        line_with_console = "reboot    ttys001                   Wed Oct 25 09:15"
        
        event = self.parser.parse(line_with_console)
        
        self.assertEqual(event.details['console'], 'ttys001')
    
    def test_invalid_last_format(self):
        """Test rejection of invalid formats"""
        invalid_lines = [
            "not a last command output",
            "reboot without proper format",
            "    spaces only    "
        ]
        
        for line in invalid_lines:
            self.assertFalse(self.parser.can_parse(line))
            self.assertIsNone(self.parser.parse(line))


class TestCompositeLogParser(unittest.TestCase):
    """Test cases for CompositeLogParser"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.parser = CompositeLogParser()
    
    def test_mixed_log_parsing(self):
        """Test parsing of mixed log content"""
        content = """
2024-01-15 10:30:45 +0100 Wake from Normal Sleep
2024-01-15 10:30:46 +0100 Display is turned on
reboot    ~                         Wed Jan 15 09:00
2024-01-15 22:30:00 +0100 Entering Sleep
shutdown  ~                         Tue Jan 14 22:30
"""
        
        events = self.parser.parse_content(content)
        
        # Should parse all 5 events
        self.assertEqual(len(events), 5)
        
        # Check event types
        event_types = [e.event_type for e in events]
        self.assertIn(EventType.WAKE, event_types)
        self.assertIn(EventType.DISPLAY_ON, event_types)
        self.assertIn(EventType.REBOOT, event_types)
        self.assertIn(EventType.SLEEP, event_types)
        self.assertIn(EventType.SHUTDOWN, event_types)
        
        # Check events are sorted by time
        timestamps = [e.timestamp for e in events]
        self.assertEqual(timestamps, sorted(timestamps))
    
    def test_parser_statistics(self):
        """Test parser usage statistics"""
        content = """
2024-01-15 10:30:45 Wake from sleep
reboot    ~                         Wed Jan 15 09:00
"""
        
        self.parser.parse_content(content)
        stats = self.parser.get_stats()
        
        self.assertEqual(stats['PmsetLogParser'], 1)
        self.assertEqual(stats['LastCommandParser'], 1)
        
        # Clear and verify
        self.parser.clear_stats()
        stats = self.parser.get_stats()
        self.assertEqual(stats['PmsetLogParser'], 0)
    
    def test_empty_content(self):
        """Test handling of empty content"""
        events = self.parser.parse_content("")
        self.assertEqual(len(events), 0)
        
        events = self.parser.parse_content("\n\n\n")
        self.assertEqual(len(events), 0)
    
    def test_parser_error_handling(self):
        """Test error handling in individual parsers"""
        # Add a mock parser that throws exceptions
        class FaultyParser(LogParser):
            def can_parse(self, line):
                return True
            
            def parse(self, line):
                raise Exception("Test error")
        
        self.parser.add_parser(FaultyParser())
        
        # Should handle the error gracefully
        content = "2024-01-15 10:30:45 Test line"
        events = self.parser.parse_content(content)
        
        # The line should be skipped due to error
        self.assertEqual(len(events), 0)


class TestFilterFunctions(unittest.TestCase):
    """Test cases for filtering functions"""
    
    def setUp(self):
        """Create test events"""
        base_time = datetime.now()
        self.events = [
            ParsedEvent(
                timestamp=base_time - timedelta(days=2),
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description="Wake 1",
                raw_line="test"
            ),
            ParsedEvent(
                timestamp=base_time - timedelta(days=1),
                event_type=EventType.SLEEP,
                category=EventCategory.POWER,
                description="Sleep 1",
                raw_line="test"
            ),
            ParsedEvent(
                timestamp=base_time - timedelta(hours=1),
                event_type=EventType.DISPLAY_ON,
                category=EventCategory.DISPLAY,
                description="Display on",
                raw_line="test"
            ),
        ]
    
    def test_filter_by_type(self):
        """Test filtering events by type"""
        wake_events = filter_events_by_type(self.events, [EventType.WAKE])
        self.assertEqual(len(wake_events), 1)
        self.assertEqual(wake_events[0].event_type, EventType.WAKE)
        
        power_events = filter_events_by_type(
            self.events, 
            [EventType.WAKE, EventType.SLEEP]
        )
        self.assertEqual(len(power_events), 2)
    
    def test_filter_by_timerange(self):
        """Test filtering events by time range"""
        now = datetime.now()
        
        # Last 24 hours
        recent = filter_events_by_timerange(
            self.events,
            now - timedelta(days=1),
            now
        )
        self.assertEqual(len(recent), 2)  # Sleep and Display events
        
        # Specific range
        specific = filter_events_by_timerange(
            self.events,
            now - timedelta(days=2, hours=1),
            now - timedelta(days=1, hours=23)
        )
        self.assertEqual(len(specific), 1)  # Only Wake event
    
    def test_group_by_day(self):
        """Test grouping events by day"""
        grouped = group_events_by_day(self.events)
        
        # Should have 3 different days
        self.assertEqual(len(grouped), 3)
        
        # Each group should contain correct events
        for date, events in grouped.items():
            self.assertIsInstance(date, datetime)
            self.assertTrue(all(e.timestamp.date() == date for e in events))


if __name__ == '__main__':
    unittest.main(verbosity=2)