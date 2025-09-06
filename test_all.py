#!/usr/bin/env python3
"""
Test Suite Runner
Runs all unit tests and generates coverage report
"""

import unittest
import sys
import os
from pathlib import Path

# Add project directory to Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

# Import all test modules
from test_secure_executor import *
from test_log_parsers import *
from test_event_processor import *
from test_thread_manager import *
from test_config_manager import *


def run_all_tests():
    """Run all test suites"""
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test modules
    test_modules = [
        'test_secure_executor',
        'test_log_parsers',
        'test_event_processor',
        'test_thread_manager',
        'test_config_manager'
    ]
    
    for module in test_modules:
        suite.addTests(loader.loadTestsFromName(module))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED!")
        return 1


def run_with_coverage():
    """Run tests with coverage reporting"""
    try:
        import coverage
    except ImportError:
        print("Coverage module not installed. Install with: pip install coverage")
        return run_all_tests()
    
    # Start coverage
    cov = coverage.Coverage(source=['.'])
    cov.start()
    
    # Run tests
    exit_code = run_all_tests()
    
    # Stop coverage and generate report
    cov.stop()
    cov.save()
    
    print("\n" + "="*70)
    print("COVERAGE REPORT")
    print("="*70)
    
    # Print coverage report
    cov.report(include=[
        'secure_executor.py',
        'log_parsers.py',
        'event_processor.py',
        'thread_manager.py',
        'config_manager.py',
        'logging_config.py'
    ])
    
    # Generate HTML report
    cov.html_report(directory='htmlcov')
    print("\nDetailed HTML coverage report generated in 'htmlcov' directory")
    
    return exit_code


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Mac Activity Analyzer tests')
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Run with coverage reporting'
    )
    parser.add_argument(
        '--module',
        help='Run tests for specific module only'
    )
    
    args = parser.parse_args()
    
    if args.module:
        # Run specific module
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(f'test_{args.module}')
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        return 0 if result.wasSuccessful() else 1
    elif args.coverage:
        return run_with_coverage()
    else:
        return run_all_tests()


if __name__ == '__main__':
    sys.exit(main())