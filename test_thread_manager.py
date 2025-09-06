#!/usr/bin/env python3
"""
Unit tests for Thread Manager
Tests thread-safe operations, task management, and graceful shutdown
"""

import unittest
import time
import threading
from unittest.mock import patch, MagicMock
from concurrent.futures import TimeoutError as FutureTimeoutError
from thread_manager import (
    ThreadSafeAnalysisManager, TaskInfo, TaskStatus,
    create_progress_tracker
)


class TestTaskInfo(unittest.TestCase):
    """Test cases for TaskInfo dataclass"""
    
    def test_task_info_creation(self):
        """Test creation of task info"""
        task = TaskInfo(
            task_id="test-123",
            name="Test Task",
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
        
        self.assertEqual(task.task_id, "test-123")
        self.assertEqual(task.status, TaskStatus.PENDING)
        self.assertIsNone(task.started_at)
        self.assertIsNone(task.completed_at)
        self.assertEqual(task.progress, 0.0)
    
    def test_task_duration_calculation(self):
        """Test duration calculation"""
        now = datetime.now()
        
        # Completed task
        task = TaskInfo(
            task_id="test",
            name="Test",
            status=TaskStatus.COMPLETED,
            created_at=now - timedelta(minutes=5),
            started_at=now - timedelta(minutes=4),
            completed_at=now - timedelta(minutes=1)
        )
        
        self.assertAlmostEqual(task.duration, 180, delta=1)  # 3 minutes
        
        # Running task
        running_task = TaskInfo(
            task_id="test2",
            name="Test2",
            status=TaskStatus.RUNNING,
            created_at=now - timedelta(minutes=2),
            started_at=now - timedelta(minutes=1)
        )
        
        # Should calculate duration from start to now
        self.assertGreater(running_task.duration, 59)
        self.assertLess(running_task.duration, 65)
    
    def test_task_state_properties(self):
        """Test is_running and is_finished properties"""
        # Running task
        running = TaskInfo(
            task_id="1",
            name="Running",
            status=TaskStatus.RUNNING,
            created_at=datetime.now()
        )
        self.assertTrue(running.is_running)
        self.assertFalse(running.is_finished)
        
        # Finished tasks
        for status in [TaskStatus.COMPLETED, TaskStatus.FAILED, 
                      TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
            task = TaskInfo(
                task_id="2",
                name="Finished",
                status=status,
                created_at=datetime.now()
            )
            self.assertFalse(task.is_running)
            self.assertTrue(task.is_finished)


class TestThreadSafeAnalysisManager(unittest.TestCase):
    """Test cases for ThreadSafeAnalysisManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = ThreadSafeAnalysisManager(max_workers=2)
    
    def tearDown(self):
        """Clean up after tests"""
        self.manager.shutdown(wait=True, timeout=5)
    
    def test_simple_task_submission(self):
        """Test basic task submission and completion"""
        result_container = []
        
        def simple_task():
            time.sleep(0.1)
            result_container.append("completed")
            return "success"
        
        task_id = self.manager.submit_task(
            simple_task,
            task_name="Simple Test"
        )
        
        self.assertIsNotNone(task_id)
        
        # Wait for completion
        success, result = self.manager.wait_for_task(task_id, timeout=2)
        
        self.assertTrue(success)
        self.assertEqual(result, "success")
        self.assertEqual(result_container[0], "completed")
    
    def test_task_with_arguments(self):
        """Test task with arguments"""
        def task_with_args(a, b, multiplier=2):
            return (a + b) * multiplier
        
        task_id = self.manager.submit_task(
            task_with_args,
            5, 3,
            task_name="Args Test",
            multiplier=3
        )
        
        success, result = self.manager.wait_for_task(task_id, timeout=2)
        
        self.assertTrue(success)
        self.assertEqual(result, 24)  # (5 + 3) * 3
    
    def test_task_cancellation(self):
        """Test cancellation of pending tasks"""
        def slow_task():
            time.sleep(2)
            return "should not complete"
        
        # Submit multiple tasks to fill the pool
        task_ids = []
        for i in range(5):  # More than max_workers
            task_id = self.manager.submit_task(
                slow_task,
                task_name=f"Slow Task {i}"
            )
            task_ids.append(task_id)
        
        # Cancel a pending task
        time.sleep(0.1)  # Let some tasks start
        
        # At least one task should be cancellable (pending)
        cancelled = False
        for task_id in task_ids[2:]:  # Try to cancel later tasks
            if self.manager.cancel_task(task_id):
                cancelled = True
                break
        
        self.assertTrue(cancelled, "Should be able to cancel at least one pending task")
    
    def test_task_exception_handling(self):
        """Test proper exception handling in tasks"""
        def failing_task():
            raise ValueError("Test exception")
        
        completion_called = False
        exception_received = None
        
        def on_complete(task_id, result, error):
            nonlocal completion_called, exception_received
            completion_called = True
            exception_received = error
        
        task_id = self.manager.submit_task(
            failing_task,
            task_name="Failing Task",
            on_complete=on_complete
        )
        
        # Wait for task
        success, result = self.manager.wait_for_task(task_id, timeout=2)
        
        self.assertFalse(success)
        
        # Give callback time to execute
        time.sleep(0.1)
        
        self.assertTrue(completion_called)
        self.assertIsInstance(exception_received, ValueError)
        
        # Check task info
        task_info = self.manager.get_task_info(task_id)
        self.assertEqual(task_info.status, TaskStatus.FAILED)
        self.assertIsInstance(task_info.error, ValueError)
    
    def test_task_timeout(self):
        """Test task timeout handling"""
        def long_task():
            time.sleep(3)
            return "completed"
        
        task_id = self.manager.submit_task(
            long_task,
            task_name="Long Task",
            timeout=0.5  # 500ms timeout
        )
        
        # Wait for timeout
        time.sleep(1)
        
        task_info = self.manager.get_task_info(task_id)
        self.assertEqual(task_info.status, TaskStatus.TIMEOUT)
    
    def test_progress_reporting(self):
        """Test progress reporting functionality"""
        progress_updates = []
        
        def on_progress(task_id, progress):
            progress_updates.append((task_id, progress))
        
        def task_with_progress(progress_callback=None):
            for i in range(5):
                time.sleep(0.1)
                if progress_callback:
                    progress_callback((i + 1) / 5)
            return "done"
        
        task_id = self.manager.submit_task(
            task_with_progress,
            task_name="Progress Task",
            on_progress=on_progress
        )
        
        success, result = self.manager.wait_for_task(task_id, timeout=3)
        
        self.assertTrue(success)
        
        # Give progress callbacks time to execute
        time.sleep(0.2)
        
        # Should have received progress updates
        self.assertGreater(len(progress_updates), 0)
        
        # Progress should increase
        progress_values = [p[1] for p in progress_updates]
        self.assertEqual(sorted(progress_values), progress_values)
        
        # Final progress should be 1.0
        task_info = self.manager.get_task_info(task_id)
        self.assertEqual(task_info.progress, 1.0)
    
    def test_concurrent_task_execution(self):
        """Test concurrent execution of multiple tasks"""
        results = []
        lock = threading.Lock()
        
        def concurrent_task(task_num):
            time.sleep(0.1)
            with lock:
                results.append(task_num)
            return f"Task {task_num} done"
        
        # Submit tasks
        task_ids = []
        for i in range(4):
            task_id = self.manager.submit_task(
                concurrent_task,
                i,
                task_name=f"Concurrent {i}"
            )
            task_ids.append(task_id)
        
        # Wait for all tasks
        for task_id in task_ids:
            success, _ = self.manager.wait_for_task(task_id, timeout=2)
            self.assertTrue(success)
        
        # All tasks should complete
        self.assertEqual(len(results), 4)
        self.assertEqual(set(results), {0, 1, 2, 3})
    
    def test_duplicate_task_id_rejection(self):
        """Test rejection of duplicate task IDs"""
        def dummy_task():
            return "done"
        
        # Submit first task
        task_id = self.manager.submit_task(
            dummy_task,
            task_id="duplicate-test",
            task_name="First"
        )
        
        # Try to submit with same ID
        with self.assertRaises(ValueError) as context:
            self.manager.submit_task(
                dummy_task,
                task_id="duplicate-test",
                task_name="Second"
            )
        
        self.assertIn("již existuje", str(context.exception))
    
    def test_shutdown_behavior(self):
        """Test graceful shutdown"""
        def long_task():
            time.sleep(1)
            return "completed"
        
        # Submit tasks
        task_ids = []
        for i in range(3):
            task_id = self.manager.submit_task(
                long_task,
                task_name=f"Shutdown Test {i}"
            )
            task_ids.append(task_id)
        
        # Quick check of status before shutdown
        status = self.manager.get_status()
        self.assertFalse(status['is_shutdown'])
        self.assertGreater(status['task_stats']['pending'] + 
                          status['task_stats']['running'], 0)
        
        # Shutdown without waiting
        self.manager.shutdown(wait=False, timeout=0.5)
        
        # Check shutdown state
        status = self.manager.get_status()
        self.assertTrue(status['is_shutdown'])
        
        # Should not accept new tasks
        with self.assertRaises(RuntimeError):
            self.manager.submit_task(long_task, task_name="After shutdown")
    
    def test_task_status_tracking(self):
        """Test accurate task status tracking"""
        def controlled_task(event):
            event.wait()  # Wait for signal
            return "done"
        
        event = threading.Event()
        
        task_id = self.manager.submit_task(
            controlled_task,
            event,
            task_name="Status Test"
        )
        
        # Check pending status
        task_info = self.manager.get_task_info(task_id)
        # May be PENDING or RUNNING depending on thread scheduling
        self.assertIn(task_info.status, [TaskStatus.PENDING, TaskStatus.RUNNING])
        
        # Let task complete
        event.set()
        time.sleep(0.1)
        
        # Check completed status
        task_info = self.manager.get_task_info(task_id)
        self.assertEqual(task_info.status, TaskStatus.COMPLETED)
    
    def test_get_all_tasks_filtering(self):
        """Test retrieval of tasks with filtering"""
        # Submit various tasks
        def quick_task():
            return "done"
        
        def failing_task():
            raise Exception("fail")
        
        # Submit tasks
        self.manager.submit_task(quick_task, task_name="Quick 1")
        self.manager.submit_task(quick_task, task_name="Quick 2")
        self.manager.submit_task(failing_task, task_name="Failing")
        
        time.sleep(0.5)  # Let tasks complete
        
        # Get all tasks
        all_tasks = self.manager.get_all_tasks()
        self.assertEqual(len(all_tasks), 3)
        
        # Get only completed tasks
        completed = self.manager.get_all_tasks(status_filter=TaskStatus.COMPLETED)
        self.assertEqual(len(completed), 2)
        
        # Get only failed tasks
        failed = self.manager.get_all_tasks(status_filter=TaskStatus.FAILED)
        self.assertEqual(len(failed), 1)
    
    def test_clear_finished_tasks(self):
        """Test clearing of finished tasks"""
        # Submit and complete some tasks
        def quick_task():
            return "done"
        
        for i in range(3):
            self.manager.submit_task(quick_task, task_name=f"Clear Test {i}")
        
        time.sleep(0.5)  # Let tasks complete
        
        # Verify tasks exist
        all_tasks = self.manager.get_all_tasks()
        self.assertEqual(len(all_tasks), 3)
        
        # Clear finished tasks
        cleared = self.manager.clear_finished_tasks()
        self.assertEqual(cleared, 3)
        
        # Verify tasks are gone
        all_tasks = self.manager.get_all_tasks()
        self.assertEqual(len(all_tasks), 0)
    
    def test_task_metadata(self):
        """Test task metadata storage"""
        metadata = {
            'user': 'test_user',
            'priority': 'high',
            'tags': ['important', 'batch']
        }
        
        def task_with_metadata():
            return "done"
        
        task_id = self.manager.submit_task(
            task_with_metadata,
            task_name="Metadata Test",
            metadata=metadata
        )
        
        task_info = self.manager.get_task_info(task_id)
        self.assertEqual(task_info.metadata, metadata)
    
    def test_nonexistent_task_handling(self):
        """Test handling of nonexistent tasks"""
        # Get info for nonexistent task
        task_info = self.manager.get_task_info("nonexistent")
        self.assertIsNone(task_info)
        
        # Cancel nonexistent task
        cancelled = self.manager.cancel_task("nonexistent")
        self.assertFalse(cancelled)
        
        # Wait for nonexistent task
        success, result = self.manager.wait_for_task("nonexistent", timeout=0.1)
        self.assertFalse(success)
        self.assertIsNone(result)


class TestProgressTracker(unittest.TestCase):
    """Test cases for progress tracker utility"""
    
    def test_progress_tracker_basic(self):
        """Test basic progress tracking"""
        update_progress, get_progress = create_progress_tracker()
        
        # Initial progress should be 0
        self.assertEqual(get_progress(), 0.0)
        
        # Update progress
        update_progress(0.5)
        self.assertEqual(get_progress(), 0.5)
        
        update_progress(1.0)
        self.assertEqual(get_progress(), 1.0)
    
    def test_progress_clamping(self):
        """Test progress value clamping"""
        update_progress, get_progress = create_progress_tracker()
        
        # Test clamping to [0, 1]
        update_progress(-0.5)
        self.assertEqual(get_progress(), 0.0)
        
        update_progress(1.5)
        self.assertEqual(get_progress(), 1.0)
    
    def test_thread_safe_progress(self):
        """Test thread safety of progress tracker"""
        update_progress, get_progress = create_progress_tracker()
        
        def update_in_thread(value):
            for _ in range(100):
                update_progress(value)
                time.sleep(0.001)
        
        # Start multiple threads updating progress
        threads = []
        for i in range(5):
            t = threading.Thread(target=update_in_thread, args=(i / 10,))
            t.start()
            threads.append(t)
        
        # Wait for threads
        for t in threads:
            t.join()
        
        # Progress should be valid (no corruption)
        final_progress = get_progress()
        self.assertGreaterEqual(final_progress, 0.0)
        self.assertLessEqual(final_progress, 1.0)


class TestThreadManagerEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = ThreadSafeAnalysisManager(max_workers=1)
    
    def tearDown(self):
        """Clean up after tests"""
        self.manager.shutdown(wait=True, timeout=5)
    
    def test_callback_exception_handling(self):
        """Test handling of exceptions in callbacks"""
        def task():
            return "done"
        
        def failing_callback(task_id, result, error):
            raise RuntimeError("Callback error")
        
        # Submit task with failing callback
        task_id = self.manager.submit_task(
            task,
            task_name="Callback Exception Test",
            on_complete=failing_callback
        )
        
        # Should complete despite callback error
        success, result = self.manager.wait_for_task(task_id, timeout=2)
        self.assertTrue(success)
        self.assertEqual(result, "done")
    
    def test_zero_timeout_handling(self):
        """Test handling of zero timeout"""
        def task():
            time.sleep(0.1)
            return "done"
        
        task_id = self.manager.submit_task(
            task,
            task_name="Zero Timeout Test",
            timeout=0  # No timeout
        )
        
        success, result = self.manager.wait_for_task(task_id, timeout=2)
        self.assertTrue(success)
        self.assertEqual(result, "done")
    
    def test_rapid_submit_cancel(self):
        """Test rapid submission and cancellation"""
        def task():
            time.sleep(0.1)
            return "done"
        
        # Rapidly submit and cancel
        for i in range(10):
            task_id = self.manager.submit_task(
                task,
                task_name=f"Rapid {i}"
            )
            # Immediately try to cancel
            self.manager.cancel_task(task_id)
        
        # Manager should remain stable
        status = self.manager.get_status()
        self.assertIsNotNone(status)


# Import statements fix
from datetime import datetime, timedelta


if __name__ == '__main__':
    unittest.main(verbosity=2)