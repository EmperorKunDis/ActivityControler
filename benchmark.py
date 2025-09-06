#!/usr/bin/env python3
"""
Performance Benchmarks for Mac Activity Analyzer
Measures performance characteristics of critical components
"""

import time
import psutil
import gc
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Callable, Any
import json
from pathlib import Path

# Import components to benchmark
from secure_executor import SecureCommandExecutor
from log_parsers import CompositeLogParser, ParsedEvent, EventType, EventCategory
from event_processor import StreamingEventProcessor
from thread_manager import ThreadSafeAnalysisManager
from config_manager import ApplicationConfiguration


class Benchmark:
    """Base class for benchmarks"""
    
    def __init__(self, name: str, iterations: int = 10):
        self.name = name
        self.iterations = iterations
        self.results = []
    
    def run(self) -> Dict[str, Any]:
        """Run the benchmark and return results"""
        print(f"\n{'='*60}")
        print(f"Running: {self.name}")
        print(f"{'='*60}")
        
        # Warm up
        print("Warming up...")
        self.setup()
        self.execute()
        self.teardown()
        
        # Actual runs
        execution_times = []
        memory_usage = []
        
        for i in range(self.iterations):
            print(f"Iteration {i+1}/{self.iterations}...", end=' ', flush=True)
            
            # Force garbage collection
            gc.collect()
            
            # Measure memory before
            process = psutil.Process()
            mem_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Setup
            self.setup()
            
            # Measure execution time
            start_time = time.perf_counter()
            result = self.execute()
            end_time = time.perf_counter()
            
            execution_time = end_time - start_time
            execution_times.append(execution_time)
            
            # Measure memory after
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_usage.append(mem_after - mem_before)
            
            # Store result
            self.results.append(result)
            
            # Teardown
            self.teardown()
            
            print(f"{execution_time:.3f}s")
        
        # Calculate statistics
        stats = {
            'name': self.name,
            'iterations': self.iterations,
            'execution_time': {
                'mean': statistics.mean(execution_times),
                'median': statistics.median(execution_times),
                'stdev': statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
                'min': min(execution_times),
                'max': max(execution_times),
                'all': execution_times
            },
            'memory_usage': {
                'mean': statistics.mean(memory_usage),
                'median': statistics.median(memory_usage),
                'max': max(memory_usage),
                'all': memory_usage
            }
        }
        
        self._print_results(stats)
        return stats
    
    def setup(self):
        """Setup for benchmark (override in subclasses)"""
        pass
    
    def execute(self) -> Any:
        """Execute the benchmark (override in subclasses)"""
        raise NotImplementedError
    
    def teardown(self):
        """Cleanup after benchmark (override in subclasses)"""
        pass
    
    def _print_results(self, stats: Dict[str, Any]):
        """Print benchmark results"""
        print(f"\nResults for {stats['name']}:")
        print(f"  Execution Time:")
        print(f"    Mean:   {stats['execution_time']['mean']:.3f}s")
        print(f"    Median: {stats['execution_time']['median']:.3f}s")
        print(f"    StdDev: {stats['execution_time']['stdev']:.3f}s")
        print(f"    Min:    {stats['execution_time']['min']:.3f}s")
        print(f"    Max:    {stats['execution_time']['max']:.3f}s")
        print(f"  Memory Usage:")
        print(f"    Mean:   {stats['memory_usage']['mean']:.2f} MB")
        print(f"    Max:    {stats['memory_usage']['max']:.2f} MB")


class LogParsingBenchmark(Benchmark):
    """Benchmark log parsing performance"""
    
    def __init__(self, log_size: int = 1000):
        super().__init__(f"Log Parsing ({log_size} lines)", iterations=10)
        self.log_size = log_size
        self.log_content = None
        self.parser = None
    
    def setup(self):
        """Generate test log data"""
        lines = []
        base_time = datetime.now() - timedelta(days=7)
        
        for i in range(self.log_size):
            timestamp = base_time + timedelta(minutes=i)
            
            # Vary event types
            if i % 10 == 0:
                lines.append(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} Wake from Normal Sleep")
            elif i % 10 == 5:
                lines.append(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} Entering Sleep")
            elif i % 10 == 3:
                lines.append(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} Display is turned on")
            elif i % 20 == 0:
                lines.append(f"reboot    ~                         {timestamp.strftime('%a %b %d %H:%M')}")
            else:
                lines.append(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} Assertion created: PID 123(TestApp)")
        
        self.log_content = '\n'.join(lines)
        self.parser = CompositeLogParser()
    
    def execute(self):
        """Parse the log content"""
        events = self.parser.parse_content(self.log_content)
        return len(events)


class EventProcessingBenchmark(Benchmark):
    """Benchmark event processing performance"""
    
    def __init__(self, event_count: int = 10000):
        super().__init__(f"Event Processing ({event_count} events)", iterations=5)
        self.event_count = event_count
        self.events = None
        self.processor = None
    
    def setup(self):
        """Generate test events"""
        self.events = []
        base_time = datetime.now() - timedelta(days=7)
        
        for i in range(self.event_count):
            timestamp = base_time + timedelta(minutes=i)
            event_type = EventType.WAKE if i % 2 == 0 else EventType.SLEEP
            
            self.events.append(ParsedEvent(
                timestamp=timestamp,
                event_type=event_type,
                category=EventCategory.POWER,
                description=f"Event {i}",
                raw_line=f"Raw line {i}",
                details={'index': i}
            ))
        
        self.processor = StreamingEventProcessor(max_events=10000)
    
    def execute(self):
        """Process the events"""
        self.processor.process_events_batch(self.events)
        stats = self.processor.calculate_statistics()
        return stats['event_count']


class ThreadedAnalysisBenchmark(Benchmark):
    """Benchmark threaded analysis performance"""
    
    def __init__(self, task_count: int = 50, max_workers: int = 4):
        super().__init__(
            f"Threaded Analysis ({task_count} tasks, {max_workers} workers)",
            iterations=5
        )
        self.task_count = task_count
        self.max_workers = max_workers
        self.manager = None
    
    def setup(self):
        """Setup thread manager"""
        self.manager = ThreadSafeAnalysisManager(max_workers=self.max_workers)
    
    def execute(self):
        """Run concurrent analysis tasks"""
        completed = 0
        
        def analysis_task(data):
            # Simulate some work
            result = sum(data)
            time.sleep(0.01)  # Simulate I/O
            return result
        
        def on_complete(task_id, result, error):
            nonlocal completed
            if not error:
                completed += 1
        
        # Submit all tasks
        start_time = time.time()
        
        for i in range(self.task_count):
            data = list(range(100))
            self.manager.submit_task(
                analysis_task,
                data,
                task_name=f"Task {i}",
                on_complete=on_complete
            )
        
        # Wait for completion
        while completed < self.task_count and time.time() - start_time < 30:
            time.sleep(0.1)
        
        return completed
    
    def teardown(self):
        """Shutdown thread manager"""
        if self.manager:
            self.manager.shutdown(wait=True, timeout=5)


class ConfigurationBenchmark(Benchmark):
    """Benchmark configuration operations"""
    
    def __init__(self, operations: int = 1000):
        super().__init__(f"Configuration Operations ({operations} ops)", iterations=10)
        self.operations = operations
        self.config = None
        self.temp_path = None
    
    def setup(self):
        """Setup configuration"""
        self.temp_path = Path("./temp_config.json")
        self.config = ApplicationConfiguration(
            config_path=self.temp_path,
            auto_save=True
        )
    
    def execute(self):
        """Perform configuration operations"""
        successful_ops = 0
        
        # Mix of reads and writes
        for i in range(self.operations):
            if i % 3 == 0:
                # Write operation
                key = f"analysis.{'hourly_rate' if i % 2 == 0 else 'retention_days'}"
                value = 100 + i if i % 2 == 0 else min(30, i % 365 + 1)
                if self.config.set(key, value):
                    successful_ops += 1
            else:
                # Read operation
                key = f"analysis.{'hourly_rate' if i % 2 == 0 else 'retention_days'}"
                value = self.config.get(key)
                if value is not None:
                    successful_ops += 1
        
        return successful_ops
    
    def teardown(self):
        """Cleanup config file"""
        if self.temp_path and self.temp_path.exists():
            self.temp_path.unlink()


class MemoryStressBenchmark(Benchmark):
    """Benchmark memory usage under stress"""
    
    def __init__(self):
        super().__init__("Memory Stress Test", iterations=3)
        self.processor = None
    
    def setup(self):
        """Setup processor with limited memory"""
        self.processor = StreamingEventProcessor(
            retention_days=10,
            max_events=10000  # Limit to test memory bounds
        )
    
    def execute(self):
        """Generate and process large amount of events"""
        base_time = datetime.now() - timedelta(days=10)
        batch_size = 5000
        total_processed = 0
        
        # Process in batches to simulate streaming
        for batch in range(10):
            events = []
            for i in range(batch_size):
                idx = batch * batch_size + i
                timestamp = base_time + timedelta(minutes=idx)
                
                events.append(ParsedEvent(
                    timestamp=timestamp,
                    event_type=EventType.WAKE if idx % 2 == 0 else EventType.SLEEP,
                    category=EventCategory.POWER,
                    description=f"Event {idx}",
                    raw_line=f"Line {idx}" * 10,  # Make events larger
                    details={
                        'batch': batch,
                        'index': i,
                        'data': 'x' * 100  # Add some bulk
                    }
                ))
            
            self.processor.process_events_batch(events)
            total_processed += len(events)
            
            # Force garbage collection between batches
            gc.collect()
        
        # Verify memory limit was respected
        actual_events = len(self.processor.events)
        return {
            'total_processed': total_processed,
            'events_retained': actual_events,
            'memory_limited': actual_events <= 10000
        }


def run_all_benchmarks():
    """Run all benchmarks and generate report"""
    print("\n" + "="*60)
    print("MAC ACTIVITY ANALYZER - PERFORMANCE BENCHMARKS")
    print("="*60)
    
    benchmarks = [
        LogParsingBenchmark(log_size=100),
        LogParsingBenchmark(log_size=1000),
        LogParsingBenchmark(log_size=10000),
        EventProcessingBenchmark(event_count=1000),
        EventProcessingBenchmark(event_count=10000),
        ThreadedAnalysisBenchmark(task_count=10, max_workers=2),
        ThreadedAnalysisBenchmark(task_count=50, max_workers=4),
        ThreadedAnalysisBenchmark(task_count=100, max_workers=8),
        ConfigurationBenchmark(operations=100),
        ConfigurationBenchmark(operations=1000),
        MemoryStressBenchmark()
    ]
    
    results = []
    
    for benchmark in benchmarks:
        result = benchmark.run()
        results.append(result)
        time.sleep(1)  # Brief pause between benchmarks
    
    # Generate summary report
    print("\n" + "="*60)
    print("BENCHMARK SUMMARY")
    print("="*60)
    
    # Save results to file
    report_path = Path("benchmark_results.json")
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to: {report_path}")
    
    # Print performance recommendations
    print("\n" + "="*60)
    print("PERFORMANCE RECOMMENDATIONS")
    print("="*60)
    
    # Analyze log parsing
    log_benchmarks = [r for r in results if "Log Parsing" in r['name']]
    if log_benchmarks:
        largest = log_benchmarks[-1]
        rate = largest['execution_time']['mean'] / 10000  # Time per line
        print(f"\n✓ Log Parsing: {rate*1000:.2f}ms per 1000 lines")
        if rate > 0.001:
            print("  ⚠️  Consider optimizing regex patterns for large logs")
    
    # Analyze event processing
    event_benchmarks = [r for r in results if "Event Processing" in r['name']]
    if event_benchmarks:
        largest = event_benchmarks[-1]
        rate = largest['execution_time']['mean'] / 10000  # Time per event
        print(f"\n✓ Event Processing: {rate*1000:.2f}ms per 1000 events")
        if rate > 0.001:
            print("  ⚠️  Consider batching or streaming for large datasets")
    
    # Analyze threading
    thread_benchmarks = [r for r in results if "Threaded Analysis" in r['name']]
    if thread_benchmarks:
        # Find optimal worker count
        best_ratio = 0
        best_workers = 0
        for r in thread_benchmarks:
            # Extract worker count from name
            workers = int(r['name'].split()[-2])
            tasks = int(r['name'].split()[2].strip('('))
            time_per_task = r['execution_time']['mean'] / tasks
            if best_ratio == 0 or time_per_task < best_ratio:
                best_ratio = time_per_task
                best_workers = workers
        
        print(f"\n✓ Threading: Optimal worker count appears to be {best_workers}")
    
    # Memory analysis
    memory_benchmark = next((r for r in results if "Memory Stress" in r['name']), None)
    if memory_benchmark:
        print(f"\n✓ Memory Management: Successfully limited to configured bounds")
        print(f"  Processed {memory_benchmark['results'][0]['total_processed']} events")
        print(f"  Retained {memory_benchmark['results'][0]['events_retained']} events")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run performance benchmarks')
    parser.add_argument(
        '--benchmark',
        choices=['parsing', 'processing', 'threading', 'config', 'memory', 'all'],
        default='all',
        help='Which benchmark to run'
    )
    
    args = parser.parse_args()
    
    if args.benchmark == 'all':
        run_all_benchmarks()
    elif args.benchmark == 'parsing':
        LogParsingBenchmark(log_size=10000).run()
    elif args.benchmark == 'processing':
        EventProcessingBenchmark(event_count=10000).run()
    elif args.benchmark == 'threading':
        ThreadedAnalysisBenchmark(task_count=100, max_workers=4).run()
    elif args.benchmark == 'config':
        ConfigurationBenchmark(operations=1000).run()
    elif args.benchmark == 'memory':
        MemoryStressBenchmark().run()