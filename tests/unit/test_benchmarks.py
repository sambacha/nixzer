"""
Performance benchmarks for critical components.

Measures execution time and memory usage of key algorithms.
Helps identify performance regressions and optimization opportunities.
"""

import unittest
import time
import gc
import sys
from typing import List, Dict, Any, Callable
from unittest.mock import Mock
import json
from pathlib import Path
from dataclasses import dataclass
from contextlib import contextmanager
import tracemalloc


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    memory_peak: int  # bytes
    memory_avg: int   # bytes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'iterations': self.iterations,
            'total_time': self.total_time,
            'avg_time': self.avg_time,
            'min_time': self.min_time,
            'max_time': self.max_time,
            'memory_peak': self.memory_peak,
            'memory_avg': self.memory_avg,
            'time_per_iteration_ms': self.avg_time * 1000,
            'memory_peak_mb': self.memory_peak / (1024 * 1024)
        }


class BenchmarkRunner:
    """Run and collect benchmark results."""
    
    def __init__(self, warmup: int = 5, iterations: int = 100):
        self.warmup = warmup
        self.iterations = iterations
        self.results = []
    
    @contextmanager
    def measure_memory(self):
        """Context manager to measure memory usage."""
        tracemalloc.start()
        gc.collect()
        
        snapshot_before = tracemalloc.take_snapshot()
        
        yield
        
        snapshot_after = tracemalloc.take_snapshot()
        stats = snapshot_after.compare_to(snapshot_before, 'lineno')
        
        total = sum(stat.size_diff for stat in stats)
        tracemalloc.stop()
        
        return total
    
    def benchmark(self, name: str, func: Callable, *args, **kwargs) -> BenchmarkResult:
        """Run a benchmark on a function."""
        print(f"\nBenchmarking: {name}")
        print(f"  Warmup: {self.warmup} iterations")
        print(f"  Benchmark: {self.iterations} iterations")
        
        # Warmup
        for _ in range(self.warmup):
            func(*args, **kwargs)
        
        # Collect garbage before benchmark
        gc.collect()
        
        # Run benchmark
        times = []
        memory_usage = []
        
        for i in range(self.iterations):
            # Measure memory
            tracemalloc.start()
            mem_before = tracemalloc.get_traced_memory()[0]
            
            # Measure time
            start = time.perf_counter()
            func(*args, **kwargs)
            end = time.perf_counter()
            
            # Record memory
            mem_after = tracemalloc.get_traced_memory()[0]
            memory_usage.append(mem_after - mem_before)
            tracemalloc.stop()
            
            times.append(end - start)
            
            # Progress indicator
            if (i + 1) % (self.iterations // 10) == 0:
                print(f"    {i + 1}/{self.iterations} iterations complete")
        
        # Calculate statistics
        result = BenchmarkResult(
            name=name,
            iterations=self.iterations,
            total_time=sum(times),
            avg_time=sum(times) / len(times),
            min_time=min(times),
            max_time=max(times),
            memory_peak=max(memory_usage) if memory_usage else 0,
            memory_avg=sum(memory_usage) // len(memory_usage) if memory_usage else 0
        )
        
        self.results.append(result)
        
        # Print summary
        print(f"  Average: {result.avg_time * 1000:.3f} ms")
        print(f"  Min: {result.min_time * 1000:.3f} ms")
        print(f"  Max: {result.max_time * 1000:.3f} ms")
        print(f"  Memory (avg): {result.memory_avg / 1024:.1f} KB")
        
        return result
    
    def save_results(self, filepath: str = "benchmark_results.json"):
        """Save benchmark results to JSON file."""
        data = {
            'timestamp': time.time(),
            'results': [r.to_dict() for r in self.results]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\nResults saved to {filepath}")


class TestSyscallBenchmarks(unittest.TestCase):
    """Benchmarks for syscall operations."""
    
    @classmethod
    def setUpClass(cls):
        """Set up benchmark runner."""
        cls.runner = BenchmarkRunner(warmup=5, iterations=100)
    
    def test_benchmark_syscall_creation(self):
        """Benchmark syscall creation."""
        from tests.unit.fixtures import SyscallFixtures
        
        def create_syscalls():
            syscalls = []
            for i in range(100):
                syscalls.append(
                    SyscallFixtures.create_open_syscall(f"/file_{i}", "O_RDONLY", i)
                )
            return syscalls
        
        self.runner.benchmark("Syscall Creation (100 syscalls)", create_syscalls)
    
    def test_benchmark_syscall_equality(self):
        """Benchmark syscall equality checking."""
        from lib.strace.comparison.syscall_equality import NameEquality, StrictEquality
        from tests.unit.fixtures import SyscallFixtures
        
        # Create test syscalls
        syscalls1 = [SyscallFixtures.create_open_syscall(f"/file_{i}") for i in range(50)]
        syscalls2 = [SyscallFixtures.create_open_syscall(f"/file_{i}") for i in range(50)]
        
        # Benchmark name equality
        name_eq = NameEquality()
        
        def check_name_equality():
            matches = 0
            for s1 in syscalls1:
                for s2 in syscalls2:
                    if name_eq(s1, s2):
                        matches += 1
            return matches
        
        self.runner.benchmark("Name Equality (50x50)", check_name_equality)
        
        # Benchmark strict equality
        strict_eq = StrictEquality()
        
        def check_strict_equality():
            matches = 0
            for s1 in syscalls1:
                for s2 in syscalls2:
                    if strict_eq(s1, s2):
                        matches += 1
            return matches
        
        self.runner.benchmark("Strict Equality (50x50)", check_strict_equality)


class TestScoringBenchmarks(unittest.TestCase):
    """Benchmarks for scoring algorithms."""
    
    @classmethod
    def setUpClass(cls):
        """Set up benchmark runner."""
        cls.runner = BenchmarkRunner(warmup=3, iterations=50)
    
    def create_mock_strace(self, n_syscalls: int) -> Mock:
        """Create a mock strace with n syscalls."""
        from tests.unit.fixtures import SyscallFixtures
        
        strace = Mock()
        strace.syscalls = []
        
        for i in range(n_syscalls):
            if i % 3 == 0:
                strace.syscalls.append(SyscallFixtures.create_open_syscall(f"/file_{i}"))
            elif i % 3 == 1:
                strace.syscalls.append(SyscallFixtures.create_read_syscall(3, 1024))
            else:
                strace.syscalls.append(SyscallFixtures.create_close_syscall(3))
        
        return strace
    
    def test_benchmark_jaccard_scoring(self):
        """Benchmark Jaccard coefficient scoring."""
        # Mock the Jaccard scorer
        def jaccard_score(trace1, trace2):
            set1 = set(s.name for s in trace1.syscalls)
            set2 = set(s.name for s in trace2.syscalls)
            
            if not set1 and not set2:
                return 1.0
            
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            return intersection / union if union > 0 else 0.0
        
        # Test different sizes
        for size in [10, 50, 100, 200]:
            trace1 = self.create_mock_strace(size)
            trace2 = self.create_mock_strace(size)
            
            self.runner.benchmark(
                f"Jaccard Score ({size} syscalls)",
                jaccard_score,
                trace1,
                trace2
            )
    
    def test_benchmark_maximum_matching(self):
        """Benchmark maximum matching algorithm."""
        # Simplified maximum matching
        def maximum_matching(trace1, trace2):
            matches = []
            used_targets = set()
            
            for i, s1 in enumerate(trace1.syscalls):
                for j, s2 in enumerate(trace2.syscalls):
                    if j not in used_targets and s1.name == s2.name:
                        matches.append((i, j))
                        used_targets.add(j)
                        break
            
            return len(matches) / max(len(trace1.syscalls), len(trace2.syscalls))
        
        # Test different sizes
        for size in [10, 25, 50, 100]:
            trace1 = self.create_mock_strace(size)
            trace2 = self.create_mock_strace(size)
            
            self.runner.benchmark(
                f"Maximum Matching ({size} syscalls)",
                maximum_matching,
                trace1,
                trace2
            )


class TestConversionBenchmarks(unittest.TestCase):
    """Benchmarks for conversion operations."""
    
    @classmethod
    def setUpClass(cls):
        """Set up benchmark runner."""
        cls.runner = BenchmarkRunner(warmup=3, iterations=50)
    
    def test_benchmark_task_extraction(self):
        """Benchmark task extraction from playbook."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        from tests.unit.fixtures import AnsibleFixtures
        
        converter = AnsibleToNixConverter()
        
        # Create test tasks
        tasks = []
        for i in range(20):
            if i % 3 == 0:
                tasks.append(AnsibleFixtures.create_package_task(f"pkg_{i}"))
            elif i % 3 == 1:
                tasks.append(AnsibleFixtures.create_service_task(f"svc_{i}"))
            else:
                tasks.append(AnsibleFixtures.create_user_task(f"user_{i}"))
        
        def extract_all_tasks():
            results = []
            for task in tasks:
                module = converter._extract_module_name(task)
                params = converter._extract_parameters(task)
                results.append((module, params))
            return results
        
        self.runner.benchmark("Task Extraction (20 tasks)", extract_all_tasks)
    
    def test_benchmark_package_translation(self):
        """Benchmark package name translation."""
        from simple_converter import SimpleAnsibleToNixConverter
        
        converter = SimpleAnsibleToNixConverter()
        
        # Create package list
        packages = [
            "nginx", "apache2", "mysql", "postgresql", "redis",
            "docker", "docker.io", "docker-ce", "nodejs", "python3",
            "build-essential", "git", "vim", "curl", "wget",
            "openssh-server", "fail2ban", "ufw", "htop", "tmux"
        ] * 5  # 100 packages total
        
        def translate_packages():
            translated = []
            for pkg in packages:
                translated.append(converter._translate_package_name(pkg))
            return translated
        
        self.runner.benchmark("Package Translation (100 packages)", translate_packages)
    
    def test_benchmark_nix_generation(self):
        """Benchmark Nix configuration generation."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        from tests.unit.fixtures import NixFixtures
        
        converter = AnsibleToNixConverter()
        
        # Create configurations
        configs = []
        for i in range(10):
            configs.append(NixFixtures.create_package_config([f"pkg_{i}"]))
            configs.append(NixFixtures.create_service_config(f"svc_{i}"))
            configs.append(NixFixtures.create_user_config(f"user_{i}"))
        
        def generate_nix_module():
            return converter._generate_nix_module(configs)
        
        self.runner.benchmark("Nix Module Generation (30 configs)", generate_nix_module)


class TestPreprocessingBenchmarks(unittest.TestCase):
    """Benchmarks for preprocessing operations."""
    
    @classmethod
    def setUpClass(cls):
        """Set up benchmark runner."""
        cls.runner = BenchmarkRunner(warmup=3, iterations=50)
    
    def test_benchmark_hole_punching(self):
        """Benchmark hole punching preprocessor."""
        from tests.unit.fixtures import StraceFixtures
        
        # Create strace with many literals
        strace = StraceFixtures.create_simple_strace()
        strace.syscalls = strace.syscalls * 20  # 60 syscalls
        
        def punch_holes():
            # Simulate hole punching
            holed = []
            for syscall in strace.syscalls:
                args = []
                for i, arg in enumerate(syscall.arguments):
                    if isinstance(arg, str) and len(arg) > 5:
                        args.append(f"<HOLE_{i}>")
                    else:
                        args.append(arg)
                holed.append(args)
            return holed
        
        self.runner.benchmark("Hole Punching (60 syscalls)", punch_holes)
    
    def test_benchmark_fd_replacement(self):
        """Benchmark file descriptor replacement."""
        from tests.unit.fixtures import SyscallFixtures
        
        # Create syscalls with file descriptors
        syscalls = []
        for i in range(100):
            syscalls.append(SyscallFixtures.create_open_syscall(f"/file_{i}", "O_RDONLY", i))
            syscalls.append(SyscallFixtures.create_read_syscall(i, 1024))
            syscalls.append(SyscallFixtures.create_close_syscall(i))
        
        def replace_fds():
            fd_map = {}
            next_fd = 0
            
            normalized = []
            for syscall in syscalls:
                args = []
                for arg in syscall.arguments:
                    if isinstance(arg, int) and arg >= 3:  # File descriptor
                        if arg not in fd_map:
                            fd_map[arg] = f"<FD_{next_fd}>"
                            next_fd += 1
                        args.append(fd_map[arg])
                    else:
                        args.append(arg)
                normalized.append(args)
            return normalized
        
        self.runner.benchmark("FD Replacement (300 syscalls)", replace_fds)


class TestMemoryBenchmarks(unittest.TestCase):
    """Benchmarks focusing on memory usage."""
    
    @classmethod
    def setUpClass(cls):
        """Set up benchmark runner with focus on memory."""
        cls.runner = BenchmarkRunner(warmup=2, iterations=10)
    
    def test_benchmark_large_strace_memory(self):
        """Benchmark memory usage with large straces."""
        from tests.unit.fixtures import SyscallFixtures
        
        def create_large_strace(size):
            syscalls = []
            for i in range(size):
                syscalls.append(SyscallFixtures.create_open_syscall(f"/very/long/path/to/file_{i}"))
                syscalls.append(SyscallFixtures.create_read_syscall(i % 100, 4096))
                syscalls.append(SyscallFixtures.create_write_syscall(1, f"data_{i}" * 100))
                syscalls.append(SyscallFixtures.create_close_syscall(i % 100))
            
            strace = Mock()
            strace.syscalls = syscalls
            return strace
        
        for size in [100, 500, 1000]:
            self.runner.benchmark(
                f"Large Strace Creation ({size * 4} syscalls)",
                create_large_strace,
                size
            )
    
    def test_benchmark_playbook_memory(self):
        """Benchmark memory usage for large playbooks."""
        from tests.unit.fixtures import AnsibleFixtures
        
        def create_large_playbook(n_tasks):
            tasks = []
            for i in range(n_tasks):
                task_type = i % 4
                if task_type == 0:
                    tasks.append(AnsibleFixtures.create_package_task(f"pkg_{i}"))
                elif task_type == 1:
                    tasks.append(AnsibleFixtures.create_service_task(f"svc_{i}"))
                elif task_type == 2:
                    tasks.append(AnsibleFixtures.create_user_task(f"user_{i}"))
                else:
                    tasks.append(AnsibleFixtures.create_file_task(f"/etc/file_{i}"))
            
            return AnsibleFixtures.create_playbook(tasks)
        
        for size in [50, 100, 200]:
            self.runner.benchmark(
                f"Large Playbook Creation ({size} tasks)",
                create_large_playbook,
                size
            )


class BenchmarkComparison:
    """Compare benchmark results across runs."""
    
    @staticmethod
    def compare_results(file1: str, file2: str):
        """Compare two benchmark result files."""
        with open(file1, 'r') as f:
            data1 = json.load(f)
        
        with open(file2, 'r') as f:
            data2 = json.load(f)
        
        print("\nBenchmark Comparison")
        print("=" * 70)
        print(f"File 1: {file1}")
        print(f"File 2: {file2}")
        print("=" * 70)
        
        # Create lookup for second file
        results2 = {r['name']: r for r in data2['results']}
        
        # Compare each benchmark
        for result1 in data1['results']:
            name = result1['name']
            if name in results2:
                result2 = results2[name]
                
                time_diff = (result2['avg_time'] - result1['avg_time']) / result1['avg_time'] * 100
                mem_diff = (result2['memory_avg'] - result1['memory_avg']) / result1['memory_avg'] * 100 if result1['memory_avg'] > 0 else 0
                
                print(f"\n{name}:")
                print(f"  Time: {result1['time_per_iteration_ms']:.3f} ms -> {result2['time_per_iteration_ms']:.3f} ms ({time_diff:+.1f}%)")
                print(f"  Memory: {result1['memory_avg']/1024:.1f} KB -> {result2['memory_avg']/1024:.1f} KB ({mem_diff:+.1f}%)")
                
                # Flag regressions
                if time_diff > 10:
                    print("  ⚠️  Performance regression detected!")
                elif time_diff < -10:
                    print("  ✓ Performance improvement!")


def run_benchmarks(save_file: str = "benchmark_results.json"):
    """Run all benchmarks and save results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add benchmark test cases
    suite.addTests(loader.loadTestsFromTestCase(TestSyscallBenchmarks))
    suite.addTests(loader.loadTestsFromTestCase(TestScoringBenchmarks))
    suite.addTests(loader.loadTestsFromTestCase(TestConversionBenchmarks))
    suite.addTests(loader.loadTestsFromTestCase(TestPreprocessingBenchmarks))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryBenchmarks))
    
    # Run benchmarks
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
    
    # Save all results
    all_results = []
    for test_case in [TestSyscallBenchmarks, TestScoringBenchmarks, 
                     TestConversionBenchmarks, TestPreprocessingBenchmarks,
                     TestMemoryBenchmarks]:
        if hasattr(test_case, 'runner'):
            all_results.extend(test_case.runner.results)
    
    # Save combined results
    data = {
        'timestamp': time.time(),
        'results': [r.to_dict() for r in all_results]
    }
    
    with open(save_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nAll benchmark results saved to {save_file}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run performance benchmarks')
    parser.add_argument('--compare', nargs=2, help='Compare two result files')
    parser.add_argument('--output', default='benchmark_results.json', help='Output file')
    
    args = parser.parse_args()
    
    if args.compare:
        BenchmarkComparison.compare_results(args.compare[0], args.compare[1])
    else:
        run_benchmarks(args.output)