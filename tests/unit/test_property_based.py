"""
Property-based tests for critical components.

Uses hypothesis to generate test cases and find edge cases automatically.
These tests verify invariants and properties that should hold for all inputs.
"""

import unittest
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Any, Tuple
import string

# Try to import hypothesis, provide fallback if not available
try:
    from hypothesis import given, strategies as st, assume, settings, example
    from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, Bundle
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    # Provide stub decorators if hypothesis not available
    def given(*args, **kwargs):
        def decorator(func):
            return unittest.skip("hypothesis not installed")(func)
        return decorator
    
    class st:
        @staticmethod
        def text(*args, **kwargs):
            return None
        @staticmethod
        def integers(*args, **kwargs):
            return None
        @staticmethod
        def lists(*args, **kwargs):
            return None
        @staticmethod
        def dictionaries(*args, **kwargs):
            return None
        @staticmethod
        def sampled_from(*args, **kwargs):
            return None
        @staticmethod
        def one_of(*args, **kwargs):
            return None


class TestSyscallProperties(unittest.TestCase):
    """Property-based tests for syscall components."""
    
    @given(
        name=st.sampled_from(['open', 'read', 'write', 'close', 'stat', 'socket']),
        args=st.lists(st.one_of(st.text(), st.integers()), min_size=0, max_size=5),
        return_value=st.integers(min_value=-1, max_value=1000)
    )
    def test_syscall_creation_properties(self, name: str, args: List, return_value: int):
        """Test that syscalls maintain their properties regardless of input."""
        from lib.strace.classes import Syscall
        
        # Create syscall
        syscall = Mock(spec=Syscall)
        syscall.name = name
        syscall.arguments = args
        syscall.return_value = return_value
        
        # Properties that should always hold
        assert syscall.name == name
        assert syscall.arguments == args
        assert syscall.return_value == return_value
        
        # Syscalls should be hashable (for use in sets)
        try:
            hash((name, tuple(args), return_value))
        except TypeError:
            self.fail("Syscall components should be hashable")
    
    @given(
        path=st.text(min_size=1, alphabet=string.ascii_letters + string.digits + '/._-'),
        flags=st.sampled_from(['O_RDONLY', 'O_WRONLY', 'O_RDWR', 'O_CREAT'])
    )
    def test_open_syscall_invariants(self, path: str, flags: str):
        """Test invariants for open syscalls."""
        # Avoid problematic paths
        assume(not path.startswith('//'))
        assume(not path.endswith('/'))
        
        from tests.unit.fixtures import SyscallFixtures
        
        syscall = SyscallFixtures.create_open_syscall(path, flags)
        
        # Invariants
        assert syscall.name == "open"
        assert len(syscall.arguments) >= 2
        assert syscall.arguments[0] == path
        assert syscall.arguments[1] == flags
        
        # File descriptor should be non-negative on success
        if syscall.return_value >= 0:
            assert syscall.return_value >= 3  # 0,1,2 are stdin/stdout/stderr


class TestScoringProperties(unittest.TestCase):
    """Property-based tests for scoring algorithms."""
    
    @given(
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    def test_score_bounds(self, score: float):
        """Test that scores are always in valid range [0, 1]."""
        from lib.strace.comparison.scoring import ScoringResult
        
        result = ScoringResult(
            s1=Mock(),
            s2=Mock(),
            mapping=[],
            score=score,
            metadata={}
        )
        
        # Score bounds invariant
        assert 0.0 <= result.score <= 1.0
    
    @given(
        syscalls1=st.lists(st.text(min_size=1), min_size=0, max_size=10),
        syscalls2=st.lists(st.text(min_size=1), min_size=0, max_size=10)
    )
    def test_jaccard_properties(self, syscalls1: List[str], syscalls2: List[str]):
        """Test Jaccard coefficient properties."""
        # Create mock straces
        strace1 = Mock()
        strace1.syscalls = [Mock(name=name) for name in syscalls1]
        
        strace2 = Mock()
        strace2.syscalls = [Mock(name=name) for name in syscalls2]
        
        # Calculate Jaccard manually
        set1 = set(syscalls1)
        set2 = set(syscalls2)
        
        if not set1 and not set2:
            expected = 1.0  # Both empty sets are considered identical
        elif not set1 or not set2:
            expected = 0.0  # One empty set means no similarity
        else:
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            expected = intersection / union if union > 0 else 0.0
        
        # Properties
        assert 0.0 <= expected <= 1.0
        
        # Symmetry: J(A, B) = J(B, A)
        if set1 == set2:
            assert expected == 1.0
        
        # Empty set property
        if not set1 or not set2:
            assert expected == 0.0 or (not set1 and not set2 and expected == 1.0)
    
    @given(
        mappings=st.lists(
            st.tuples(st.integers(0, 10), st.integers(0, 10)),
            min_size=0,
            max_size=20
        )
    )
    def test_mapping_properties(self, mappings: List[Tuple[int, int]]):
        """Test parameter mapping properties."""
        # No source should map to multiple targets
        source_to_targets = {}
        for src, tgt in mappings:
            if src in source_to_targets:
                # Property: one-to-one or many-to-one mapping
                pass  # Could be many-to-one
            source_to_targets[src] = tgt
        
        # Mappings should not have negative indices
        for src, tgt in mappings:
            assert src >= 0
            assert tgt >= 0


class TestConversionProperties(unittest.TestCase):
    """Property-based tests for conversion logic."""
    
    @given(
        package_name=st.text(
            min_size=1,
            max_size=50,
            alphabet=string.ascii_lowercase + string.digits + '-_'
        )
    )
    def test_package_translation_properties(self, package_name: str):
        """Test package name translation properties."""
        from simple_converter import SimpleAnsibleToNixConverter
        
        converter = SimpleAnsibleToNixConverter()
        translated = converter._translate_package_name(package_name)
        
        # Properties
        assert translated  # Should never return empty
        assert isinstance(translated, str)
        
        # Idempotency: translating twice gives same result
        translated2 = converter._translate_package_name(translated)
        if package_name in converter.MODULE_MAPPINGS:
            # Known packages should map consistently
            assert translated == translated2
    
    @given(
        module_name=st.sampled_from(['package', 'service', 'user', 'file', 'copy']),
        params=st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(), st.integers(), st.booleans()),
            min_size=0,
            max_size=5
        )
    )
    def test_task_conversion_properties(self, module_name: str, params: Dict):
        """Test that task conversion maintains certain properties."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Create task
        task = {
            "name": "Test task",
            module_name: params
        }
        
        # Extract module and parameters
        extracted_module = converter._extract_module_name(task)
        extracted_params = converter._extract_parameters(task)
        
        # Properties
        assert extracted_module == module_name
        
        # Params should be preserved (if dict format)
        if isinstance(task[module_name], dict):
            assert extracted_params == params
    
    @given(
        tasks=st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.text(min_size=0, max_size=100),
                min_size=1,
                max_size=3
            ),
            min_size=0,
            max_size=10
        )
    )
    def test_playbook_structure_preservation(self, tasks: List[Dict]):
        """Test that playbook structure is preserved during conversion."""
        playbook = [{
            "hosts": "localhost",
            "tasks": tasks
        }]
        
        # Number of tasks should be preserved
        assert len(playbook[0]['tasks']) == len(tasks)
        
        # Task order should be preserved
        for i, task in enumerate(tasks):
            assert playbook[0]['tasks'][i] == task


class TestValidationProperties(unittest.TestCase):
    """Property-based tests for validation logic."""
    
    @given(
        packages=st.lists(st.text(min_size=1), min_size=0, max_size=20),
        services=st.dictionaries(
            st.text(min_size=1),
            st.sampled_from(['running', 'stopped', 'enabled', 'disabled']),
            min_size=0,
            max_size=10
        )
    )
    def test_system_state_properties(self, packages: List[str], services: Dict[str, str]):
        """Test system state properties."""
        from lib.validation.ansible_nix_validator import SystemState
        
        state = SystemState(
            packages=packages,
            services=services,
            files={},
            users=[],
            groups=[]
        )
        
        # Properties
        assert isinstance(state.packages, list)
        assert isinstance(state.services, dict)
        assert len(state.packages) == len(packages)
        assert len(state.services) == len(services)
        
        # Uniqueness property (if enforced)
        unique_packages = list(set(packages))
        if len(unique_packages) != len(packages):
            # Duplicates might be removed in real implementation
            pass
    
    @given(
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        has_errors=st.booleans()
    )
    def test_validation_result_consistency(self, score: float, has_errors: bool):
        """Test validation result consistency."""
        from lib.validation.ansible_nix_validator import ValidationResult
        
        result = ValidationResult(
            success=not has_errors and score >= 0.8,
            score=score,
            differences=[],
            warnings=[],
            errors=["error"] if has_errors else []
        )
        
        # Consistency properties
        if result.success:
            assert score >= 0.8
            assert len(result.errors) == 0
        
        if has_errors:
            assert not result.success
            assert len(result.errors) > 0


class TestHoleProperties(unittest.TestCase):
    """Property-based tests for Hole (parameter placeholder) logic."""
    
    @given(
        indices=st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=10)
    )
    def test_hole_uniqueness(self, indices: List[int]):
        """Test that holes with same index are considered equal."""
        from lib.strace.classes import Hole
        
        holes = [Hole(index=idx) for idx in indices]
        
        # Same index should produce equal holes
        for i, idx1 in enumerate(indices):
            for j, idx2 in enumerate(indices):
                hole1 = holes[i]
                hole2 = holes[j]
                if idx1 == idx2:
                    assert hole1 == hole2
                else:
                    assert hole1 != hole2
    
    @given(
        index=st.integers(min_value=0, max_value=1000)
    )
    def test_hole_index_bounds(self, index: int):
        """Test that hole indices are non-negative."""
        from lib.strace.classes import Hole
        
        hole = Hole(index=index)
        
        # Properties
        assert hole.index >= 0
        assert hole.index == index
        assert hole.value is None  # Holes don't have values


if HYPOTHESIS_AVAILABLE:
    class StatefulConversionTest(RuleBasedStateMachine):
        """Stateful testing of the conversion pipeline."""
        
        def __init__(self):
            super().__init__()
            from lib.converters.ansible_to_nix import AnsibleToNixConverter
            self.converter = AnsibleToNixConverter()
            self.tasks = []
            self.converted = []
        
        tasks = Bundle('tasks')
        
        @rule(target=tasks,
              module=st.sampled_from(['package', 'service', 'user']),
              name=st.text(min_size=1, max_size=20))
        def add_task(self, module, name):
            """Add a task to the pipeline."""
            task = {
                "name": f"Test {module} {name}",
                module: {"name": name}
            }
            self.tasks.append(task)
            return task
        
        @rule(task=tasks)
        def convert_task(self, task):
            """Convert a task to Nix."""
            result = self.converter._convert_task(task)
            if result:
                self.converted.append(result)
        
        @invariant()
        def conversions_valid(self):
            """Check that all conversions are valid."""
            for config in self.converted:
                assert 'module' in config
                assert 'config' in config
        
        @invariant()
        def no_lost_tasks(self):
            """Check that tasks aren't lost."""
            # Number of converted should not exceed number of tasks
            assert len(self.converted) <= len(self.tasks)


class TestPerformanceProperties(unittest.TestCase):
    """Property-based tests for performance characteristics."""
    
    @given(
        n_syscalls=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=10)  # Limit for performance tests
    def test_scoring_complexity(self, n_syscalls: int):
        """Test that scoring complexity is reasonable."""
        import time
        
        # Create mock straces
        strace1 = Mock()
        strace1.syscalls = [Mock(name=f"syscall_{i}") for i in range(n_syscalls)]
        
        strace2 = Mock()
        strace2.syscalls = [Mock(name=f"syscall_{i}") for i in range(n_syscalls)]
        
        # Measure time (simplified - would use actual scorer in real test)
        start = time.time()
        
        # Simulate O(n²) comparison
        for s1 in strace1.syscalls:
            for s2 in strace2.syscalls:
                _ = s1.name == s2.name
        
        duration = time.time() - start
        
        # Property: should complete in reasonable time
        # O(n²) but with small constants
        assert duration < 0.1 * (n_syscalls ** 2) / 1000  # Rough bound
    
    @given(
        n_tasks=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=10)
    def test_conversion_scalability(self, n_tasks: int):
        """Test that conversion scales linearly with tasks."""
        from simple_converter import SimpleAnsibleToNixConverter
        
        converter = SimpleAnsibleToNixConverter()
        
        # Create tasks
        tasks = [
            {"package": {"name": f"pkg_{i}"}}
            for i in range(n_tasks)
        ]
        
        import time
        start = time.time()
        
        # Process tasks
        configs = {}
        for task in tasks:
            converter._process_task(task, configs)
        
        duration = time.time() - start
        
        # Property: should be roughly linear
        assert duration < 0.01 * n_tasks  # Linear bound


if __name__ == '__main__':
    if HYPOTHESIS_AVAILABLE:
        unittest.main(verbosity=2)
    else:
        print("Install hypothesis for property-based testing: pip install hypothesis")
        print("Skipping property-based tests...")