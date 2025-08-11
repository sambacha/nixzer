#!/usr/bin/env python3
"""
Unit test runner with coverage and reporting.

Features:
- Discovers and runs all unit tests
- Generates coverage reports
- Outputs test results in multiple formats
- Supports test filtering and prioritization
"""

import sys
import unittest
import argparse
from pathlib import Path
import json
import time
from typing import List, Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class TestPrioritizer:
    """Prioritize tests based on criticality and dependencies."""
    
    # Test priority levels
    PRIORITY_CRITICAL = 1  # Core functionality (syscall comparison, scoring)
    PRIORITY_HIGH = 2      # Conversion logic
    PRIORITY_MEDIUM = 3    # Validation and preprocessing
    PRIORITY_LOW = 4       # Utilities and helpers
    
    # Test categories and their priorities
    TEST_PRIORITIES = {
        'test_leaf_components': {
            'TestLiteralValues': PRIORITY_CRITICAL,
            'TestHoleClass': PRIORITY_CRITICAL,
            'TestExecutableParameter': PRIORITY_HIGH,
            'TestCanonicalForm': PRIORITY_HIGH,
            'TestModuleMapping': PRIORITY_HIGH,
            'TestSyscallPattern': PRIORITY_MEDIUM,
            'TestPureTransformFunctions': PRIORITY_MEDIUM,
            'TestValidationResult': PRIORITY_LOW,
            'TestSystemState': PRIORITY_LOW,
            'TestNixDerivation': PRIORITY_LOW,
        },
        'test_critical_path': {
            'TestSyscallEquality': PRIORITY_CRITICAL,
            'TestScoringMethods': PRIORITY_CRITICAL,
            'TestParameterMapping': PRIORITY_CRITICAL,
            'TestConversionLogic': PRIORITY_HIGH,
            'TestSyscallTracing': PRIORITY_HIGH,
            'TestPreprocessors': PRIORITY_MEDIUM,
        },
        'test_composite_components': {
            'TestStraceProcessingPipeline': PRIORITY_HIGH,
            'TestConversionWorkflow': PRIORITY_HIGH,
            'TestValidationPipeline': PRIORITY_MEDIUM,
            'TestErrorHandling': PRIORITY_MEDIUM,
            'TestPerformanceOptimizations': PRIORITY_LOW,
        }
    }
    
    @classmethod
    def get_test_priority(cls, test_module: str, test_class: str) -> int:
        """Get priority for a specific test class."""
        module_name = Path(test_module).stem
        if module_name in cls.TEST_PRIORITIES:
            return cls.TEST_PRIORITIES[module_name].get(test_class, cls.PRIORITY_LOW)
        return cls.PRIORITY_LOW
    
    @classmethod
    def sort_tests(cls, test_suite: unittest.TestSuite) -> unittest.TestSuite:
        """Sort tests by priority (critical first)."""
        # Extract all tests
        tests = []
        for test_group in test_suite:
            if isinstance(test_group, unittest.TestSuite):
                for test in test_group:
                    tests.append(test)
            else:
                tests.append(test_group)
        
        # Sort by priority
        def get_priority(test):
            if hasattr(test, '__class__'):
                module = test.__class__.__module__
                class_name = test.__class__.__name__
                return cls.get_test_priority(module, class_name)
            return cls.PRIORITY_LOW
        
        tests.sort(key=get_priority)
        
        # Create new sorted suite
        sorted_suite = unittest.TestSuite()
        for test in tests:
            sorted_suite.addTest(test)
        
        return sorted_suite


class TestRunner:
    """Custom test runner with enhanced reporting."""
    
    def __init__(self, verbosity: int = 2, failfast: bool = False):
        self.verbosity = verbosity
        self.failfast = failfast
        self.results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'skipped': 0,
            'duration': 0,
            'tests': []
        }
    
    def run_tests(self, test_dir: str = 'tests/unit',
                  pattern: str = 'test_*.py',
                  priority_filter: Optional[int] = None) -> Dict[str, Any]:
        """
        Run unit tests with optional filtering.
        
        Parameters
        ----------
        test_dir : str
            Directory containing tests
        pattern : str
            Pattern for test file discovery
        priority_filter : Optional[int]
            Only run tests with this priority or higher
        
        Returns
        -------
        Dict[str, Any]
            Test results summary
        """
        start_time = time.time()
        
        # Discover tests
        loader = unittest.TestLoader()
        suite = loader.discover(test_dir, pattern=pattern)
        
        # Apply priority sorting
        suite = TestPrioritizer.sort_tests(suite)
        
        # Filter by priority if requested
        if priority_filter is not None:
            filtered_suite = unittest.TestSuite()
            for test in suite:
                if hasattr(test, '__class__'):
                    module = test.__class__.__module__
                    class_name = test.__class__.__name__
                    priority = TestPrioritizer.get_test_priority(module, class_name)
                    if priority <= priority_filter:
                        filtered_suite.addTest(test)
            suite = filtered_suite
        
        # Run tests
        runner = unittest.TextTestRunner(
            verbosity=self.verbosity,
            failfast=self.failfast,
            stream=sys.stdout
        )
        
        logger.info("=" * 70)
        logger.info("RUNNING UNIT TESTS")
        logger.info("=" * 70)
        
        result = runner.run(suite)
        
        # Collect results
        self.results['total'] = result.testsRun
        self.results['failed'] = len(result.failures)
        self.results['errors'] = len(result.errors)
        self.results['skipped'] = len(result.skipped)
        self.results['passed'] = self.results['total'] - self.results['failed'] - self.results['errors'] - self.results['skipped']
        self.results['duration'] = time.time() - start_time
        
        # Collect detailed test results
        for failure in result.failures:
            test, traceback = failure
            self.results['tests'].append({
                'name': str(test),
                'status': 'FAILED',
                'message': traceback
            })
        
        for error in result.errors:
            test, traceback = error
            self.results['tests'].append({
                'name': str(test),
                'status': 'ERROR',
                'message': traceback
            })
        
        # Print summary
        self._print_summary()
        
        return self.results
    
    def _print_summary(self):
        """Print test results summary."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("=" * 70)
        
        # Status line with color (if terminal supports it)
        if self.results['failed'] == 0 and self.results['errors'] == 0:
            status = "✓ PASSED"
            color = '\033[92m'  # Green
        else:
            status = "✗ FAILED"
            color = '\033[91m'  # Red
        reset = '\033[0m'
        
        logger.info(f"{color}{status}{reset}")
        logger.info("")
        
        # Statistics
        logger.info(f"Total Tests:  {self.results['total']}")
        logger.info(f"Passed:       {self.results['passed']}")
        logger.info(f"Failed:       {self.results['failed']}")
        logger.info(f"Errors:       {self.results['errors']}")
        logger.info(f"Skipped:      {self.results['skipped']}")
        logger.info(f"Duration:     {self.results['duration']:.2f}s")
        
        # Pass rate
        if self.results['total'] > 0:
            pass_rate = (self.results['passed'] / self.results['total']) * 100
            logger.info(f"Pass Rate:    {pass_rate:.1f}%")
        
        logger.info("=" * 70)
    
    def export_results(self, output_file: str = 'test_results.json'):
        """Export test results to JSON file."""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Results exported to {output_file}")


class CoverageRunner:
    """Run tests with coverage analysis."""
    
    def __init__(self):
        try:
            import coverage
            self.cov = coverage.Coverage(
                source=['lib'],
                omit=[
                    '*/tests/*',
                    '*/test_*.py',
                    '*/__pycache__/*',
                    '*/antlr_generated/*'
                ]
            )
        except ImportError:
            logger.warning("Coverage module not installed. Install with: pip install coverage")
            self.cov = None
    
    def run_with_coverage(self, test_runner: TestRunner, **kwargs) -> Dict[str, Any]:
        """Run tests with coverage measurement."""
        if self.cov is None:
            return test_runner.run_tests(**kwargs)
        
        # Start coverage
        self.cov.start()
        
        try:
            # Run tests
            results = test_runner.run_tests(**kwargs)
        finally:
            # Stop coverage
            self.cov.stop()
            self.cov.save()
        
        # Generate coverage report
        logger.info("\n" + "=" * 70)
        logger.info("COVERAGE REPORT")
        logger.info("=" * 70)
        
        # Print to console
        self.cov.report()
        
        # Generate HTML report
        self.cov.html_report(directory='htmlcov')
        logger.info("\nDetailed HTML coverage report: htmlcov/index.html")
        
        return results


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(description='Run Dozer unit tests')
    
    parser.add_argument(
        '--verbose', '-v',
        action='count',
        default=2,
        help='Increase verbosity'
    )
    
    parser.add_argument(
        '--failfast', '-f',
        action='store_true',
        help='Stop on first failure'
    )
    
    parser.add_argument(
        '--priority', '-p',
        type=int,
        choices=[1, 2, 3, 4],
        help='Only run tests with this priority or higher (1=critical, 4=low)'
    )
    
    parser.add_argument(
        '--coverage', '-c',
        action='store_true',
        help='Run with coverage analysis'
    )
    
    parser.add_argument(
        '--pattern',
        default='test_*.py',
        help='Pattern for test file discovery'
    )
    
    parser.add_argument(
        '--export', '-e',
        type=str,
        help='Export results to JSON file'
    )
    
    parser.add_argument(
        '--critical-only',
        action='store_true',
        help='Run only critical path tests'
    )
    
    args = parser.parse_args()
    
    # Configure test runner
    runner = TestRunner(
        verbosity=args.verbose,
        failfast=args.failfast
    )
    
    # Set priority filter
    priority_filter = args.priority
    if args.critical_only:
        priority_filter = TestPrioritizer.PRIORITY_CRITICAL
    
    # Run tests
    if args.coverage:
        coverage_runner = CoverageRunner()
        results = coverage_runner.run_with_coverage(
            runner,
            pattern=args.pattern,
            priority_filter=priority_filter
        )
    else:
        results = runner.run_tests(
            pattern=args.pattern,
            priority_filter=priority_filter
        )
    
    # Export results if requested
    if args.export:
        runner.export_results(args.export)
    
    # Exit with appropriate code
    if results['failed'] > 0 or results['errors'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()