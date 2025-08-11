# Dozer Test Suite

Comprehensive testing infrastructure for the Dozer project, implementing a pure unit testing strategy with bottom-up component testing and critical path prioritization.

## Test Structure

```
tests/
├── unit/                       # Pure unit tests (no I/O or external dependencies)
│   ├── __init__.py            # Test package initialization
│   ├── fixtures.py            # Reusable test fixtures and mock factories
│   ├── run_tests.py           # Advanced test runner with prioritization
│   ├── test_leaf_components.py    # Level 1: Value objects and pure functions
│   ├── test_critical_path.py      # Critical business logic tests
│   ├── test_composite_components.py # Level 2-3: Composed functionality
│   ├── test_property_based.py     # Property-based testing with hypothesis
│   ├── test_benchmarks.py         # Performance benchmarks
│   └── test_contracts.py          # Interface contract validation
└── README.md                  # This file
```

## Testing Philosophy

### 1. Pure Unit Tests Only
- **No I/O operations** - All file system, network, and database operations are mocked
- **No external processes** - No spawning of subprocesses or Docker containers
- **Deterministic** - Tests produce the same results every run
- **Fast** - Each test runs in milliseconds, entire suite in seconds
- **Isolated** - Tests don't depend on each other or external state

### 2. Bottom-Up Testing Approach

```
┌─────────────────────────────────────┐
│   Level 4: System Integration       │ ← Deferred to integration tests
├─────────────────────────────────────┤
│   Level 3: Complex Workflows        │ ← Conversion & validation pipelines
├─────────────────────────────────────┤
│   Level 2: Simple Compositions      │ ← Scorers, preprocessors
├─────────────────────────────────────┤
│   Level 1: Leaf Components         │ ← Value objects, pure functions
└─────────────────────────────────────┘ ← START HERE
```

### 3. Critical Path Prioritization

Tests are prioritized by business criticality:

| Priority | Level | Components | Impact |
|----------|-------|------------|--------|
| CRITICAL | 1 | Syscall comparison, scoring algorithms | Core functionality |
| HIGH | 2 | Conversion logic, parameter mapping | Main features |
| MEDIUM | 3 | Validation, preprocessing | Quality assurance |
| LOW | 4 | Utilities, helpers | Support functions |

## Test Types

### 1. Leaf Component Tests (`test_leaf_components.py`)
Pure value objects and functions with no dependencies:
- Literal values (String, Number, Null)
- Holes and parameter placeholders
- Pure transformation functions
- Immutable data structures

### 2. Critical Path Tests (`test_critical_path.py`)
Core business logic that must work correctly:
- Syscall equality checking algorithms
- Scoring methods (Jaccard, TF-IDF, Maximum Matching)
- Parameter mapping logic
- Ansible to Nix conversion core

### 3. Composite Component Tests (`test_composite_components.py`)
Components that combine multiple leaf components:
- Strace processing pipeline
- Full conversion workflow
- Validation pipeline
- Error handling

### 4. Property-Based Tests (`test_property_based.py`)
Using hypothesis to find edge cases:
- Syscall invariants
- Score bounds (0.0 ≤ score ≤ 1.0)
- Mapping properties
- Conversion idempotency

### 5. Performance Benchmarks (`test_benchmarks.py`)
Measure and track performance:
- Syscall creation and comparison
- Scoring algorithm complexity
- Conversion throughput
- Memory usage patterns

### 6. Contract Tests (`test_contracts.py`)
Verify interface compliance:
- Protocol conformance
- Component composability
- Backward compatibility
- Interface evolution

## Running Tests

### Quick Start

```bash
# Enter development environment
nix develop

# Run all unit tests
python tests/unit/run_tests.py

# Run with coverage
python tests/unit/run_tests.py --coverage
```

### Test Runner Options

```bash
# Run only critical tests (fail fast)
python tests/unit/run_tests.py --critical-only --failfast

# Run by priority level (1=critical, 4=low)
python tests/unit/run_tests.py --priority 2

# Export results to JSON
python tests/unit/run_tests.py --export results.json

# Run specific test file
python -m unittest tests.unit.test_leaf_components

# Run with verbose output
python tests/unit/run_tests.py -vv
```

### Via Nix Flake

```bash
# Run all checks
nix flake check

# Run specific test suites
nix build .#checks.x86_64-linux.unit-tests        # All unit tests
nix build .#checks.x86_64-linux.critical-tests    # Critical only
nix build .#checks.x86_64-linux.leaf-tests        # Leaf components
nix build .#checks.x86_64-linux.test-coverage     # With coverage
```

### Property-Based Testing

```bash
# Install hypothesis (if not in Nix environment)
pip install hypothesis

# Run property tests
python -m unittest tests.unit.test_property_based
```

### Performance Benchmarks

```bash
# Run all benchmarks
python tests/unit/test_benchmarks.py

# Save results
python tests/unit/test_benchmarks.py --output results.json

# Compare two benchmark runs
python tests/unit/test_benchmarks.py --compare old.json new.json
```

## Test Fixtures

The `fixtures.py` module provides reusable test data factories:

```python
from tests.unit.fixtures import (
    SyscallFixtures,      # Create mock syscalls
    StraceFixtures,       # Create mock straces
    AnsibleFixtures,      # Create Ansible tasks/playbooks
    NixFixtures,          # Create Nix configurations
    ValidationFixtures,   # Create validation data
    MockFactory,          # Complex mock objects
    TestDataGenerator     # Generate test scenarios
)

# Example usage
syscall = SyscallFixtures.create_open_syscall("/test/file")
playbook = AnsibleFixtures.create_playbook()
mock_converter = MockFactory.create_mock_converter()
```

## Coverage Goals

| Component | Target | Current | Priority |
|-----------|--------|---------|----------|
| Syscall Comparison | 95% | - | CRITICAL |
| Scoring Algorithms | 90% | - | CRITICAL |
| Parameter Mapping | 85% | - | HIGH |
| Conversion Logic | 85% | - | HIGH |
| Preprocessors | 75% | - | MEDIUM |
| Validators | 70% | - | MEDIUM |
| Utilities | 60% | - | LOW |

## Test Quality Metrics

### Code Coverage
- Line coverage: Percentage of code lines executed
- Branch coverage: Percentage of decision branches taken
- Function coverage: Percentage of functions called

### Test Effectiveness
- Mutation score: Percentage of mutants killed
- Property coverage: Edge cases found by hypothesis
- Contract violations: Interface compatibility issues

### Performance Metrics
- Test execution time: < 1 second for unit tests
- Memory usage: < 100 MB for test suite
- Benchmark stability: < 5% variance between runs

## Best Practices

### 1. Test Naming Convention
```python
def test_<component>_<scenario>_<expected_outcome>():
    """Test that <component> <behavior> when <scenario>."""
```

### 2. Arrange-Act-Assert Pattern
```python
def test_example():
    # Arrange - Set up test data
    input_data = create_test_fixture()
    
    # Act - Execute functionality
    result = function_under_test(input_data)
    
    # Assert - Verify outcome
    assert result == expected_value
```

### 3. Mock Isolation
```python
with patch('module.external_dependency') as mock_dep:
    mock_dep.return_value = "mocked"
    result = function_using_dependency()
    assert result == "expected"
```

### 4. Descriptive Assertions
```python
self.assertEqual(
    actual, 
    expected,
    f"Expected {expected} but got {actual} for input {input_data}"
)
```

## Continuous Integration

The test suite integrates with CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Run Unit Tests
  run: |
    nix flake check
    nix build .#checks.x86_64-linux.critical-tests

- name: Upload Coverage
  run: |
    nix build .#checks.x86_64-linux.test-coverage
    # Upload coverage reports
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure PYTHONPATH includes project root
   ```bash
   export PYTHONPATH="$PWD:$PYTHONPATH"
   ```

2. **Mock failures**: Check that mocks match actual interfaces
   ```python
   mock = Mock(spec=ActualClass)  # Use spec for interface checking
   ```

3. **Flaky tests**: Look for hidden dependencies
   - Random number generation
   - Time-based logic
   - External state

4. **Slow tests**: Profile with cProfile
   ```bash
   python -m cProfile -s cumtime tests/unit/run_tests.py
   ```

## Contributing

When adding new tests:

1. **Choose appropriate test file**:
   - Leaf components → `test_leaf_components.py`
   - Core logic → `test_critical_path.py`
   - Workflows → `test_composite_components.py`

2. **Follow the pattern**:
   - Use fixtures for test data
   - Mock all external dependencies
   - Write descriptive test names
   - Include docstrings

3. **Maintain priorities**:
   - Add to TestPrioritizer.TEST_PRIORITIES
   - Critical components get PRIORITY_CRITICAL
   - Nice-to-have gets PRIORITY_LOW

4. **Update coverage goals**:
   - New critical code needs 90%+ coverage
   - Update this README with targets

## Advanced Features

### Parallel Execution
Tests can run in parallel using pytest-xdist:
```bash
pytest tests/unit -n auto  # Use all CPU cores
```

### Mutation Testing
Validate test quality with mutmut:
```bash
mutmut run --paths-to-mutate lib/
mutmut results
```

### Visual Coverage Reports
HTML coverage reports with highlighted source:
```bash
python tests/unit/run_tests.py --coverage
open htmlcov/index.html
```

### Test Impact Analysis
Identify which tests to run based on code changes:
```bash
# Coming soon: Integration with git diff
python tests/unit/run_tests.py --changed-only
```

## Summary

The Dozer test suite provides:
- ✅ **Fast feedback** - Unit tests run in seconds
- ✅ **High confidence** - Critical paths thoroughly tested
- ✅ **Easy maintenance** - Clear structure and priorities
- ✅ **Scalability** - Easy to add new tests
- ✅ **Quality assurance** - Multiple testing approaches
- ✅ **Performance tracking** - Benchmarks prevent regressions

By following the pure unit testing approach with bottom-up component testing and critical path prioritization, we ensure maximum test value with minimum complexity.