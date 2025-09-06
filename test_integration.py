#!/usr/bin/env python3
"""
Integration Tests for Mac Activity Analyzer
Tests complete workflows and component interactions
"""

import unittest
import tempfile
import shutil
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Import all components
from secure_executor import SecureCommandExecutor
from log_parsers import CompositeLogParser, ParsedEvent, EventType
from event_processor import StreamingEventProcessor
from thread_manager import ThreadSafeAnalysisManager
from config_manager import ApplicationConfiguration
from logging_config import LoggingManager, setup_logging


class TestSecurityIntegration(unittest.TestCase):
    """Integration tests for security components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.executor = SecureCommandExecutor()
        self.parser = CompositeLogParser()
    
    def test_secure_log_retrieval_pipeline(self):
        """Test secure retrieval and parsing of logs"""
        # Mock subprocess to return sample log data
        sample_log = """
2024-01-15 10:30:45 +0100 Wake from Normal Sleep
2024-01-15 10:30:46 +0100 Display is turned on
2024-01-15 14:15:00 +0100 Entering Sleep
"""
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout=sample_log,
                stderr="",
                returncode=0
            )
            
            # Execute secure command
            result = self.executor.execute_command('pmset_log')
            
            # Parse the output
            events = self.parser.parse_content(result.stdout)
            
            # Verify pipeline works end-to-end
            self.assertEqual(len(events), 3)
            self.assertEqual(events[0].event_type, EventType.WAKE)
            self.assertEqual(events[1].event_type, EventType.DISPLAY_ON)
            self.assertEqual(events[2].event_type, EventType.SLEEP)
    
    def test_malicious_input_handling(self):
        """Test handling of malicious inputs throughout the system"""
        malicious_inputs = [
            "; rm -rf /",
            "$(cat /etc/passwd)",
            "../../../etc/passwd",
            "test\x00binary",
            "'; DROP TABLE events; --"
        ]
        
        for malicious in malicious_inputs:
            # Test command executor
            with self.assertRaises(Exception):
                self.executor.execute_command('log_show', [malicious])
            
            # Test parser (should handle gracefully)
            events = self.parser.parse_content(malicious)
            # Should either parse nothing or handle safely
            self.assertIsInstance(events, list)


class TestDataFlowIntegration(unittest.TestCase):
    """Integration tests for data flow through components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = ApplicationConfiguration(
            config_path=Path(self.temp_dir) / "config.json"
        )
        self.processor = StreamingEventProcessor()
        self.thread_manager = ThreadSafeAnalysisManager(max_workers=2)
    
    def tearDown(self):
        """Clean up test fixtures"""
        self.thread_manager.shutdown(wait=True)
        shutil.rmtree(self.temp_dir)
    
    def test_complete_analysis_workflow(self):
        """Test complete workflow from log parsing to analysis"""
        # Sample log data
        log_content = """
2024-01-15 09:00:00 +0100 Wake from Normal Sleep
2024-01-15 09:00:05 +0100 Display is turned on
2024-01-15 12:00:00 +0100 Entering Sleep
2024-01-15 14:00:00 +0100 Wake from Normal Sleep
2024-01-15 18:00:00 +0100 Entering Sleep
"""
        
        # Parse logs
        parser = CompositeLogParser()
        events = parser.parse_content(log_content)
        
        # Process events
        self.processor.process_events_batch(events)
        
        # Calculate statistics
        stats = self.processor.calculate_statistics()
        
        # Verify complete workflow
        self.assertEqual(stats['event_count'], 5)
        self.assertGreater(stats['state_count'], 0)
        self.assertIn('efficiency_metrics', stats)
        self.assertIn('daily_stats', stats)
    
    def test_threaded_analysis_workflow(self):
        """Test concurrent analysis with thread manager"""
        results = []
        
        def analysis_task(data):
            """Simulate analysis task"""
            time.sleep(0.1)
            return f"Analyzed {len(data)} items"
        
        def on_complete(task_id, result, error):
            """Callback to collect results"""
            if result:
                results.append(result)
        
        # Submit multiple analysis tasks
        for i in range(3):
            data = list(range(i * 10, (i + 1) * 10))
            self.thread_manager.submit_analysis(
                task_id=f"analysis-{i}",
                analysis_func=analysis_task,
                data,
                on_complete=on_complete
            )
        
        # Wait for completion
        time.sleep(0.5)
        
        # Verify all tasks completed
        self.assertEqual(len(results), 3)
        self.assertIn("Analyzed 10 items", results)
    
    def test_configuration_driven_processing(self):
        """Test processing controlled by configuration"""
        # Set custom configuration
        self.config.set('analysis.retention_days', 5)
        self.config.set('analysis.inactivity_threshold', 30)
        
        # Create processor with config values
        processor = StreamingEventProcessor(
            retention_days=self.config.get('analysis.retention_days'),
            inactivity_threshold_seconds=self.config.get('analysis.inactivity_threshold')
        )
        
        # Create test events
        base_time = datetime.now() - timedelta(days=3)
        events = [
            ParsedEvent(
                timestamp=base_time,
                event_type=EventType.WAKE,
                category="power",
                description="Wake",
                raw_line="test"
            ),
            ParsedEvent(
                timestamp=base_time + timedelta(minutes=45),  # Gap > 30s threshold
                event_type=EventType.SLEEP,
                category="power",
                description="Sleep",
                raw_line="test"
            )
        ]
        
        processor.process_events_batch(events)
        
        # Should detect pause due to custom threshold
        pause_states = [s for s in processor.states if s.state_type.value == "pause"]
        self.assertGreater(len(pause_states), 0)


class TestErrorRecoveryIntegration(unittest.TestCase):
    """Integration tests for error recovery and resilience"""
    
    def test_cascading_error_handling(self):
        """Test error handling across components"""
        # Create components
        executor = SecureCommandExecutor()
        parser = CompositeLogParser()
        processor = StreamingEventProcessor()
        
        # Test with command that fails
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Command failed")
            
            result = executor.execute_command('pmset_log')
            
            # Should return error result, not crash
            self.assertEqual(result.return_code, -1)
            self.assertIn("Error", result.stderr)
        
        # Parser should handle empty/error input
        events = parser.parse_content(result.stdout)
        self.assertEqual(len(events), 0)
        
        # Processor should handle empty events
        processor.process_events_batch(events)
        stats = processor.calculate_statistics()
        self.assertEqual(stats['event_count'], 0)
    
    def test_concurrent_error_recovery(self):
        """Test error recovery in concurrent operations"""
        manager = ThreadSafeAnalysisManager(max_workers=2)
        
        successful_results = []
        failed_tasks = []
        
        def task_that_might_fail(task_num):
            if task_num % 2 == 0:
                raise ValueError(f"Task {task_num} failed")
            return f"Task {task_num} succeeded"
        
        def on_complete(task_id, result, error):
            if error:
                failed_tasks.append(task_id)
            else:
                successful_results.append(result)
        
        # Submit mixed tasks
        for i in range(4):
            manager.submit_analysis(
                task_id=f"task-{i}",
                analysis_func=task_that_might_fail,
                i,
                on_complete=on_complete
            )
        
        # Wait for completion
        time.sleep(0.5)
        
        # Verify partial success
        self.assertEqual(len(successful_results), 2)
        self.assertEqual(len(failed_tasks), 2)
        
        # Manager should still be operational
        status = manager.get_status()
        self.assertFalse(status['is_shutdown'])
        
        manager.shutdown()


class TestLoggingIntegration(unittest.TestCase):
    """Integration tests for logging system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir)
    
    def test_integrated_logging_setup(self):
        """Test complete logging setup with all components"""
        # Setup logging
        setup_logging(
            app_name="TestApp",
            version="1.0",
            log_level="DEBUG",
            structured=False,
            log_dir=self.log_dir
        )
        
        # Get logger manager
        from logging_config import get_logging_manager
        manager = get_logging_manager()
        
        # Create component loggers
        executor_logger = manager.setup_logger(
            'secure_executor',
            level='INFO',
            file_name='executor.log'
        )
        
        parser_logger = manager.setup_logger(
            'log_parser',
            level='DEBUG',
            file_name='parser.log'
        )
        
        # Log from components
        executor_logger.info("Executing secure command")
        parser_logger.debug("Parsing log line")
        
        # Verify log files created
        self.assertTrue((self.log_dir / 'executor.log').exists())
        self.assertTrue((self.log_dir / 'parser.log').exists())
        
        # Test error logger
        error_logger = manager.setup_error_logger()
        
        try:
            1 / 0
        except Exception:
            error_logger.exception("Test exception")
        
        # Verify error log
        self.assertTrue((self.log_dir / 'errors.log').exists())


class TestPerformanceIntegration(unittest.TestCase):
    """Integration tests for performance characteristics"""
    
    def test_large_dataset_processing(self):
        """Test processing large amounts of data"""
        processor = StreamingEventProcessor(max_events=1000)
        
        # Generate large dataset
        base_time = datetime.now() - timedelta(days=7)
        events = []
        
        for day in range(7):
            for hour in range(24):
                for minute in range(0, 60, 15):
                    timestamp = base_time + timedelta(days=day, hours=hour, minutes=minute)
                    events.append(ParsedEvent(
                        timestamp=timestamp,
                        event_type=EventType.WAKE if minute == 0 else EventType.DISPLAY_ON,
                        category="test",
                        description=f"Event {day}-{hour}-{minute}",
                        raw_line="test"
                    ))
        
        # Time the processing
        start_time = time.time()
        processor.process_events_batch(events)
        stats = processor.calculate_statistics()
        end_time = time.time()
        
        # Verify processing completed reasonably fast
        processing_time = end_time - start_time
        self.assertLess(processing_time, 5.0)  # Should complete within 5 seconds
        
        # Verify memory limits enforced
        self.assertLessEqual(len(processor.events), 1000)
        
        # Verify statistics calculated correctly
        self.assertGreater(stats['event_count'], 0)
        self.assertEqual(len(stats['daily_stats']), 7)
    
    def test_concurrent_load_handling(self):
        """Test system under concurrent load"""
        manager = ThreadSafeAnalysisManager(max_workers=4)
        
        completed_count = 0
        lock = threading.Lock()
        
        def increment_counter():
            nonlocal completed_count
            time.sleep(0.01)
            with lock:
                completed_count += 1
        
        # Submit many tasks rapidly
        start_time = time.time()
        
        for i in range(50):
            manager.submit_analysis(
                task_id=f"load-{i}",
                analysis_func=increment_counter
            )
        
        # Wait for completion with timeout
        timeout = 10
        while completed_count < 50 and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        # Verify all completed
        self.assertEqual(completed_count, 50)
        
        # Verify completed within reasonable time
        total_time = time.time() - start_time
        self.assertLess(total_time, 5.0)
        
        manager.shutdown()


class TestEndToEndIntegration(unittest.TestCase):
    """Complete end-to-end integration tests"""
    
    def test_full_application_workflow(self):
        """Test complete application workflow"""
        # Setup
        temp_dir = tempfile.mkdtemp()
        
        try:
            # 1. Initialize configuration
            config = ApplicationConfiguration(
                config_path=Path(temp_dir) / "config.json"
            )
            config.set('analysis.retention_days', 7)
            
            # 2. Setup logging
            setup_logging(
                app_name="IntegrationTest",
                log_dir=Path(temp_dir) / "logs"
            )
            
            # 3. Create secure executor
            executor = SecureCommandExecutor()
            
            # 4. Mock command execution
            sample_logs = """
2024-01-15 09:00:00 Wake from Normal Sleep
2024-01-15 12:00:00 Entering Sleep  
2024-01-15 14:00:00 Wake from Normal Sleep
2024-01-15 18:00:00 Entering Sleep
"""
            
            with patch.object(executor, 'execute_command') as mock_exec:
                mock_exec.return_value = MagicMock(
                    stdout=sample_logs,
                    stderr="",
                    return_code=0
                )
                
                # 5. Execute command
                result = executor.execute_command('pmset_log')
                
                # 6. Parse logs
                parser = CompositeLogParser()
                events = parser.parse_content(result.stdout)
                
                # 7. Process events
                processor = StreamingEventProcessor(
                    retention_days=config.get('analysis.retention_days')
                )
                processor.process_events_batch(events)
                
                # 8. Run analysis in thread
                manager = ThreadSafeAnalysisManager()
                
                analysis_result = None
                
                def analyze_data():
                    return processor.calculate_statistics()
                
                def on_complete(task_id, result, error):
                    nonlocal analysis_result
                    analysis_result = result
                
                manager.submit_analysis(
                    task_id="full-analysis",
                    analysis_func=analyze_data,
                    on_complete=on_complete
                )
                
                # Wait for analysis
                success, stats = manager.wait_for_task("full-analysis")
                
                # 9. Verify complete workflow
                self.assertTrue(success)
                self.assertIsNotNone(stats)
                self.assertEqual(stats['event_count'], 4)
                self.assertIn('efficiency_metrics', stats)
                
                # 10. Export results
                export_path = Path(temp_dir) / "results.json"
                with open(export_path, 'w') as f:
                    json.dump({
                        'events': processor.export_events_json(),
                        'states': processor.export_states_json(),
                        'statistics': stats
                    }, f, indent=2)
                
                self.assertTrue(export_path.exists())
                
                # Cleanup
                manager.shutdown()
                
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir)


# Import threading for concurrent tests
import threading


if __name__ == '__main__':
    unittest.main(verbosity=2)