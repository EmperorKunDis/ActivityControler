#!/usr/bin/env python3
"""
Unit tests for Event Processor
Tests streaming processing, memory limits, and state analysis
"""

import unittest
from datetime import datetime, timedelta
from collections import deque
from event_processor import (
    StreamingEventProcessor, SystemState, StateType,
    ParsedEvent, EventType, EventCategory
)


class TestSystemState(unittest.TestCase):
    """Test cases for SystemState dataclass"""
    
    def test_valid_state_creation(self):
        """Test creation of valid system state"""
        start = datetime.now()
        end = start + timedelta(minutes=30)
        
        state = SystemState(
            start_time=start,
            end_time=end,
            state_type=StateType.ACTIVE,
            duration_seconds=1800
        )
        
        self.assertEqual(state.state_type, StateType.ACTIVE)
        self.assertEqual(state.duration_minutes, 30)
        self.assertEqual(state.duration_hours, 0.5)
    
    def test_invalid_time_range(self):
        """Test validation rejects invalid time ranges"""
        start = datetime.now()
        end = start - timedelta(minutes=10)  # End before start
        
        with self.assertRaises(ValueError) as context:
            SystemState(
                start_time=start,
                end_time=end,
                state_type=StateType.ACTIVE,
                duration_seconds=0
            )
        
        self.assertIn("End time", str(context.exception))
    
    def test_auto_duration_calculation(self):
        """Test automatic duration calculation"""
        start = datetime.now()
        end = start + timedelta(hours=2, minutes=30)
        
        state = SystemState(
            start_time=start,
            end_time=end,
            state_type=StateType.SLEEP,
            duration_seconds=0  # Should be auto-calculated
        )
        
        self.assertEqual(state.duration_seconds, 9000)  # 2.5 hours
        self.assertEqual(state.duration_hours, 2.5)
    
    def test_state_overlap_detection(self):
        """Test overlap detection between states"""
        base_time = datetime.now()
        
        state1 = SystemState(
            start_time=base_time,
            end_time=base_time + timedelta(hours=1),
            state_type=StateType.ACTIVE,
            duration_seconds=3600
        )
        
        # Overlapping state
        state2 = SystemState(
            start_time=base_time + timedelta(minutes=30),
            end_time=base_time + timedelta(hours=1, minutes=30),
            state_type=StateType.PAUSE,
            duration_seconds=3600
        )
        
        # Non-overlapping state
        state3 = SystemState(
            start_time=base_time + timedelta(hours=2),
            end_time=base_time + timedelta(hours=3),
            state_type=StateType.SLEEP,
            duration_seconds=3600
        )
        
        self.assertTrue(state1.overlaps_with(state2))
        self.assertFalse(state1.overlaps_with(state3))


class TestStreamingEventProcessor(unittest.TestCase):
    """Test cases for StreamingEventProcessor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.processor = StreamingEventProcessor(
            retention_days=7,
            max_events=100,
            inactivity_threshold_seconds=60
        )
        
        # Create test events
        self.base_time = datetime.now() - timedelta(days=1)
        self.test_events = self._create_test_events()
    
    def _create_test_events(self):
        """Create a set of test events"""
        events = []
        
        # Wake event
        events.append(ParsedEvent(
            timestamp=self.base_time,
            event_type=EventType.WAKE,
            category=EventCategory.POWER,
            description="System wake",
            raw_line="Wake from sleep",
            details={'wake_reason': 'User Activity'}
        ))
        
        # Display on after 1 minute
        events.append(ParsedEvent(
            timestamp=self.base_time + timedelta(minutes=1),
            event_type=EventType.DISPLAY_ON,
            category=EventCategory.DISPLAY,
            description="Display on",
            raw_line="Display turned on"
        ))
        
        # Sleep after 2 hours (creates pause gap)
        events.append(ParsedEvent(
            timestamp=self.base_time + timedelta(hours=2),
            event_type=EventType.SLEEP,
            category=EventCategory.POWER,
            description="System sleep",
            raw_line="Entering sleep",
            details={'sleep_reason': 'Idle'}
        ))
        
        # Wake after 8 hours
        events.append(ParsedEvent(
            timestamp=self.base_time + timedelta(hours=10),
            event_type=EventType.WAKE,
            category=EventCategory.POWER,
            description="System wake",
            raw_line="Wake from sleep"
        ))
        
        return events
    
    def test_event_retention_filtering(self):
        """Test events outside retention period are filtered"""
        old_event = ParsedEvent(
            timestamp=datetime.now() - timedelta(days=15),  # Outside 7-day retention
            event_type=EventType.WAKE,
            category=EventCategory.POWER,
            description="Old event",
            raw_line="test"
        )
        
        self.processor.process_events_batch([old_event])
        
        # Should not retain the old event
        self.assertEqual(len(self.processor.events), 0)
    
    def test_max_events_limit(self):
        """Test enforcement of maximum events limit"""
        # Create more events than the limit
        many_events = []
        for i in range(150):  # Max is 100
            many_events.append(ParsedEvent(
                timestamp=self.base_time + timedelta(minutes=i),
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description=f"Event {i}",
                raw_line=f"test {i}"
            ))
        
        self.processor.process_events_batch(many_events)
        
        # Should only keep the most recent 100
        self.assertEqual(len(self.processor.events), 100)
        
        # Verify we kept the most recent ones
        oldest_kept = self.processor.events[0].timestamp
        newest_kept = self.processor.events[-1].timestamp
        self.assertEqual(newest_kept, many_events[-1].timestamp)
    
    def test_state_analysis_basic(self):
        """Test basic state analysis"""
        self.processor.process_events_batch(self.test_events)
        
        # Should create states from events
        self.assertGreater(len(self.processor.states), 0)
        
        # First state should be ACTIVE (from wake)
        self.assertEqual(self.processor.states[0].state_type, StateType.ACTIVE)
        
        # Should detect the sleep state
        sleep_states = [s for s in self.processor.states if s.state_type == StateType.SLEEP]
        self.assertGreater(len(sleep_states), 0)
    
    def test_pause_detection(self):
        """Test detection of pause/inactivity gaps"""
        # Create events with a gap
        events = [
            ParsedEvent(
                timestamp=self.base_time,
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description="Wake",
                raw_line="wake"
            ),
            ParsedEvent(
                timestamp=self.base_time + timedelta(minutes=90),  # 90 min gap
                event_type=EventType.DISPLAY_ON,
                category=EventCategory.DISPLAY,
                description="Display on",
                raw_line="display"
            )
        ]
        
        self.processor.process_events_batch(events)
        
        # Should detect pause state for the gap
        pause_states = [s for s in self.processor.states if s.state_type == StateType.PAUSE]
        self.assertEqual(len(pause_states), 1)
        
        # Pause should be ~90 minutes minus active state duration
        pause_duration = pause_states[0].duration_minutes
        self.assertGreater(pause_duration, 60)  # More than threshold
    
    def test_shutdown_detection(self):
        """Test detection of long gaps as shutdown"""
        events = [
            ParsedEvent(
                timestamp=self.base_time,
                event_type=EventType.SLEEP,
                category=EventCategory.POWER,
                description="Sleep",
                raw_line="sleep"
            ),
            ParsedEvent(
                timestamp=self.base_time + timedelta(hours=2),  # 2 hour gap
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description="Wake",
                raw_line="wake"
            )
        ]
        
        self.processor.process_events_batch(events)
        
        # Should detect shutdown for long gap
        shutdown_states = [s for s in self.processor.states if s.state_type == StateType.SHUTDOWN]
        self.assertGreater(len(shutdown_states), 0)
    
    def test_event_indexing(self):
        """Test event indexing for fast retrieval"""
        self.processor.process_events_batch(self.test_events)
        
        # Test retrieval by type
        wake_events = self.processor.get_events_by_type(EventType.WAKE)
        self.assertEqual(len(wake_events), 2)  # We have 2 wake events
        
        sleep_events = self.processor.get_events_by_type(EventType.SLEEP)
        self.assertEqual(len(sleep_events), 1)
    
    def test_date_based_retrieval(self):
        """Test retrieval of events by date"""
        self.processor.process_events_batch(self.test_events)
        
        # Get events for the test date
        test_date = self.base_time.date()
        date_events = self.processor.get_events_by_date(test_date)
        
        # Should get events from that day
        self.assertGreater(len(date_events), 0)
        self.assertTrue(all(e.timestamp.date() == test_date for e in date_events))
    
    def test_statistics_calculation(self):
        """Test comprehensive statistics calculation"""
        self.processor.process_events_batch(self.test_events)
        
        stats = self.processor.calculate_statistics()
        
        # Verify structure
        self.assertIn('event_count', stats)
        self.assertIn('state_count', stats)
        self.assertIn('date_range', stats)
        self.assertIn('event_type_distribution', stats)
        self.assertIn('state_type_distribution', stats)
        self.assertIn('daily_stats', stats)
        self.assertIn('efficiency_metrics', stats)
        
        # Verify values
        self.assertEqual(stats['event_count'], len(self.test_events))
        self.assertGreater(stats['state_count'], 0)
        
        # Check date range
        date_range = stats['date_range']
        self.assertIsNotNone(date_range['first'])
        self.assertIsNotNone(date_range['last'])
        self.assertGreater(date_range['days'], 0)
    
    def test_efficiency_metrics(self):
        """Test efficiency calculations"""
        # Create controlled events for predictable metrics
        events = [
            ParsedEvent(
                timestamp=self.base_time,
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description="Wake",
                raw_line="wake"
            ),
            ParsedEvent(
                timestamp=self.base_time + timedelta(hours=2),
                event_type=EventType.SLEEP,
                category=EventCategory.POWER,
                description="Sleep",
                raw_line="sleep"
            )
        ]
        
        self.processor.process_events_batch(events)
        stats = self.processor.calculate_statistics()
        
        efficiency = stats['efficiency_metrics']
        self.assertIn('total_hours', efficiency)
        self.assertIn('active_hours', efficiency)
        self.assertIn('efficiency_percent', efficiency)
        
        # Should have ~2 hours of active time
        self.assertGreater(efficiency['active_hours'], 1.9)
        self.assertLess(efficiency['active_hours'], 2.1)
    
    def test_streaming_processing(self):
        """Test streaming event processing"""
        processed_events = []
        
        # Register callback to track processing
        def track_event(event):
            processed_events.append(event)
        
        self.processor.register_event_callback(track_event)
        
        # Process as stream
        def event_generator():
            for event in self.test_events:
                yield event
        
        self.processor.process_event_stream(event_generator())
        
        # Verify all events were processed
        self.assertEqual(len(processed_events), len(self.test_events))
    
    def test_state_callbacks(self):
        """Test state change callbacks"""
        state_changes = []
        
        def track_state(state):
            state_changes.append(state)
        
        self.processor.register_state_callback(track_state)
        
        # Process events that should create states
        self.processor.process_events_batch(self.test_events)
        
        # Should have received state callbacks
        self.assertGreater(len(state_changes), 0)
        self.assertIsInstance(state_changes[0], SystemState)
    
    def test_export_functionality(self):
        """Test JSON export of events and states"""
        self.processor.process_events_batch(self.test_events)
        
        # Export events
        events_json = self.processor.export_events_json()
        self.assertIsInstance(events_json, list)
        self.assertGreater(len(events_json), 0)
        self.assertIn('timestamp', events_json[0])
        self.assertIn('event_type', events_json[0])
        
        # Export states
        states_json = self.processor.export_states_json()
        self.assertIsInstance(states_json, list)
        self.assertGreater(len(states_json), 0)
        self.assertIn('start_time', states_json[0])
        self.assertIn('state_type', states_json[0])
    
    def test_app_activity_tracking(self):
        """Test application activity statistics"""
        # Add some assertion events
        app_events = [
            ParsedEvent(
                timestamp=self.base_time,
                event_type=EventType.ASSERTION_CREATE,
                category=EventCategory.APPLICATION,
                description="Assertion created",
                raw_line="test",
                details={'process': 'Safari', 'pid': 123}
            ),
            ParsedEvent(
                timestamp=self.base_time + timedelta(minutes=5),
                event_type=EventType.ASSERTION_RELEASE,
                category=EventCategory.APPLICATION,
                description="Assertion released",
                raw_line="test",
                details={'process': 'Safari', 'pid': 123}
            ),
            ParsedEvent(
                timestamp=self.base_time + timedelta(minutes=10),
                event_type=EventType.ASSERTION_CREATE,
                category=EventCategory.APPLICATION,
                description="Assertion created",
                raw_line="test",
                details={'process': 'Chrome', 'pid': 456}
            )
        ]
        
        self.processor.process_events_batch(app_events)
        stats = self.processor.calculate_statistics()
        
        app_activity = stats['app_activity']
        self.assertIn('Safari', app_activity)
        self.assertEqual(app_activity['Safari']['assertion_count'], 2)
        self.assertEqual(app_activity['Chrome']['assertion_count'], 1)
    
    def test_wake_reason_analysis(self):
        """Test wake reason statistics"""
        wake_events = [
            ParsedEvent(
                timestamp=self.base_time,
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description="Wake",
                raw_line="test",
                details={'wake_reason': 'User Activity'}
            ),
            ParsedEvent(
                timestamp=self.base_time + timedelta(hours=1),
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description="Wake",
                raw_line="test",
                details={'wake_reason': 'User Activity'}
            ),
            ParsedEvent(
                timestamp=self.base_time + timedelta(hours=2),
                event_type=EventType.DARK_WAKE,
                category=EventCategory.POWER,
                description="Dark wake",
                raw_line="test",
                details={'wake_reason': 'Maintenance'}
            )
        ]
        
        self.processor.process_events_batch(wake_events)
        stats = self.processor.calculate_statistics()
        
        wake_reasons = stats['wake_reasons']
        self.assertEqual(wake_reasons['User Activity'], 2)
        self.assertEqual(wake_reasons['Maintenance'], 1)
    
    def test_cache_invalidation(self):
        """Test statistics cache invalidation"""
        self.processor.process_events_batch(self.test_events[:2])
        
        # Calculate stats (should cache)
        stats1 = self.processor.calculate_statistics()
        event_count1 = stats1['event_count']
        
        # Add more events
        self.processor.process_events_batch(self.test_events[2:])
        
        # Stats should be recalculated
        stats2 = self.processor.calculate_statistics()
        event_count2 = stats2['event_count']
        
        self.assertNotEqual(event_count1, event_count2)


class TestEventProcessorEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.processor = StreamingEventProcessor()
    
    def test_empty_processing(self):
        """Test processing with no events"""
        self.processor.process_events_batch([])
        
        self.assertEqual(len(self.processor.events), 0)
        self.assertEqual(len(self.processor.states), 0)
        
        stats = self.processor.calculate_statistics()
        self.assertEqual(stats['event_count'], 0)
    
    def test_single_event_processing(self):
        """Test processing with single event"""
        event = ParsedEvent(
            timestamp=datetime.now(),
            event_type=EventType.WAKE,
            category=EventCategory.POWER,
            description="Wake",
            raw_line="test"
        )
        
        self.processor.process_events_batch([event])
        
        self.assertEqual(len(self.processor.events), 1)
        self.assertGreater(len(self.processor.states), 0)
    
    def test_out_of_order_events(self):
        """Test handling of events not in chronological order"""
        base = datetime.now()
        events = [
            ParsedEvent(
                timestamp=base + timedelta(hours=2),
                event_type=EventType.SLEEP,
                category=EventCategory.POWER,
                description="Sleep",
                raw_line="test"
            ),
            ParsedEvent(
                timestamp=base,  # Earlier event comes second
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description="Wake",
                raw_line="test"
            )
        ]
        
        self.processor.process_events_batch(events)
        
        # Events should be sorted
        self.assertEqual(self.processor.events[0].event_type, EventType.WAKE)
        self.assertEqual(self.processor.events[1].event_type, EventType.SLEEP)
    
    def test_duplicate_timestamps(self):
        """Test handling of events with same timestamp"""
        timestamp = datetime.now()
        events = [
            ParsedEvent(
                timestamp=timestamp,
                event_type=EventType.WAKE,
                category=EventCategory.POWER,
                description="Wake",
                raw_line="test1"
            ),
            ParsedEvent(
                timestamp=timestamp,  # Same timestamp
                event_type=EventType.DISPLAY_ON,
                category=EventCategory.DISPLAY,
                description="Display",
                raw_line="test2"
            )
        ]
        
        self.processor.process_events_batch(events)
        
        # Both events should be kept
        self.assertEqual(len(self.processor.events), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)