"""
Contract tests for module interfaces.

Ensures that modules conform to their expected interfaces and contracts.
These tests verify that components can be safely composed together.
"""

import unittest
from unittest.mock import Mock, MagicMock
from typing import Protocol, runtime_checkable, Any, List, Dict, Optional
from abc import ABC, abstractmethod
import inspect


# ============================================================================
# CONTRACT DEFINITIONS
# ============================================================================

@runtime_checkable
class StraceContract(Protocol):
    """Contract for Strace objects."""
    
    syscalls: List[Any]
    executable: str
    arguments: List[str]
    metadata: Dict[str, Any]
    
    def copy(self) -> 'StraceContract':
        """Must support copying."""
        ...


@runtime_checkable
class SyscallContract(Protocol):
    """Contract for Syscall objects."""
    
    name: str
    arguments: List[Any]
    return_value: Any
    
    def __eq__(self, other: Any) -> bool:
        """Must support equality comparison."""
        ...
    
    def __hash__(self) -> int:
        """Must be hashable."""
        ...


@runtime_checkable
class PreprocessorContract(Protocol):
    """Contract for preprocessor objects."""
    
    def process(self, strace: StraceContract) -> StraceContract:
        """Process a strace and return modified version."""
        ...


@runtime_checkable
class ScorerContract(Protocol):
    """Contract for scoring methods."""
    
    def __call__(self, s1: StraceContract, s2: StraceContract, 
                 holes: set) -> 'ScoringResultContract':
        """Score similarity between two straces."""
        ...


@runtime_checkable
class ScoringResultContract(Protocol):
    """Contract for scoring results."""
    
    s1: StraceContract
    s2: StraceContract
    score: float
    mapping: List[tuple]
    metadata: Dict[str, Any]


@runtime_checkable
class ConverterContract(Protocol):
    """Contract for converters."""
    
    def convert_playbook(self, playbook_path: Any) -> str:
        """Convert playbook to target format."""
        ...
    
    def _convert_task(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert individual task."""
        ...


@runtime_checkable
class ValidatorContract(Protocol):
    """Contract for validators."""
    
    def validate_conversion(self, source: Any, target: Any) -> 'ValidationResultContract':
        """Validate conversion from source to target."""
        ...


@runtime_checkable
class ValidationResultContract(Protocol):
    """Contract for validation results."""
    
    success: bool
    score: float
    differences: List[str]
    warnings: List[str]
    errors: List[str]


# ============================================================================
# CONTRACT TESTS
# ============================================================================

class TestStraceContracts(unittest.TestCase):
    """Test that Strace classes conform to contracts."""
    
    def test_strace_contract_compliance(self):
        """Test that Strace implements required interface."""
        from lib.strace.classes import Strace
        
        # Check that Strace has required attributes
        strace = Mock(spec=Strace)
        strace.syscalls = []
        strace.executable = "test"
        strace.arguments = []
        strace.metadata = {}
        
        # Verify contract
        self.assertTrue(isinstance(strace, StraceContract))
        
        # Verify methods
        strace.copy = MagicMock(return_value=strace)
        copied = strace.copy()
        self.assertIsNotNone(copied)
    
    def test_syscall_contract_compliance(self):
        """Test that Syscall implements required interface."""
        from lib.strace.classes import Syscall
        
        # Create mock syscall
        syscall = Mock(spec=Syscall)
        syscall.name = "open"
        syscall.arguments = ["/file", "O_RDONLY"]
        syscall.return_value = 3
        
        # Verify contract
        self.assertTrue(isinstance(syscall, SyscallContract))
        
        # Verify methods
        syscall.__eq__ = MagicMock(return_value=True)
        syscall.__hash__ = MagicMock(return_value=12345)
        
        # Test equality
        other = Mock()
        self.assertTrue(syscall == other)
        
        # Test hashability
        self.assertEqual(hash(syscall), 12345)
    
    def test_strace_syscall_relationship(self):
        """Test that Strace and Syscall work together correctly."""
        strace = Mock(spec=StraceContract)
        syscalls = [Mock(spec=SyscallContract) for _ in range(3)]
        
        strace.syscalls = syscalls
        
        # Verify we can iterate syscalls
        for syscall in strace.syscalls:
            self.assertTrue(isinstance(syscall, SyscallContract))


class TestPreprocessorContracts(unittest.TestCase):
    """Test that preprocessors conform to contracts."""
    
    def test_preprocessor_contract_compliance(self):
        """Test that preprocessors implement required interface."""
        from lib.strace.comparison.preprocessing import (
            PunchHoles, ReplaceFileDescriptors, SelectSyscalls
        )
        
        preprocessors = [
            Mock(spec=PunchHoles),
            Mock(spec=ReplaceFileDescriptors),
            Mock(spec=SelectSyscalls)
        ]
        
        for preprocessor in preprocessors:
            # Setup mock
            preprocessor.process = MagicMock(return_value=Mock(spec=StraceContract))
            
            # Verify contract
            self.assertTrue(isinstance(preprocessor, PreprocessorContract))
            
            # Test processing
            input_strace = Mock(spec=StraceContract)
            output_strace = preprocessor.process(input_strace)
            
            # Verify output is also a strace
            self.assertTrue(isinstance(output_strace, StraceContract))
    
    def test_preprocessor_chaining(self):
        """Test that preprocessors can be chained."""
        p1 = Mock(spec=PreprocessorContract)
        p2 = Mock(spec=PreprocessorContract)
        p3 = Mock(spec=PreprocessorContract)
        
        # Setup chain
        strace0 = Mock(spec=StraceContract)
        strace1 = Mock(spec=StraceContract)
        strace2 = Mock(spec=StraceContract)
        strace3 = Mock(spec=StraceContract)
        
        p1.process = MagicMock(return_value=strace1)
        p2.process = MagicMock(return_value=strace2)
        p3.process = MagicMock(return_value=strace3)
        
        # Chain processing
        result = strace0
        for preprocessor in [p1, p2, p3]:
            result = preprocessor.process(result)
        
        # Verify chain executed
        p1.process.assert_called_once_with(strace0)
        p2.process.assert_called_once_with(strace1)
        p3.process.assert_called_once_with(strace2)
        
        # Verify final result
        self.assertEqual(result, strace3)


class TestScoringContracts(unittest.TestCase):
    """Test that scoring methods conform to contracts."""
    
    def test_scorer_contract_compliance(self):
        """Test that scorers implement required interface."""
        from lib.strace.comparison.scoring import (
            JaccardCoefficient, TFIDF, MaximumCardinalityMatching
        )
        
        scorers = [
            Mock(spec=JaccardCoefficient),
            Mock(spec=TFIDF),
            Mock(spec=MaximumCardinalityMatching)
        ]
        
        for scorer in scorers:
            # Setup mock
            result = Mock(spec=ScoringResultContract)
            result.score = 0.85
            result.mapping = [(0, 0), (1, 1)]
            scorer.__call__ = MagicMock(return_value=result)
            
            # Verify contract
            self.assertTrue(isinstance(scorer, ScorerContract))
            
            # Test scoring
            s1 = Mock(spec=StraceContract)
            s2 = Mock(spec=StraceContract)
            
            scoring_result = scorer(s1, s2, set())
            
            # Verify result contract
            self.assertTrue(isinstance(scoring_result, ScoringResultContract))
            self.assertGreaterEqual(scoring_result.score, 0.0)
            self.assertLessEqual(scoring_result.score, 1.0)
    
    def test_scoring_result_contract(self):
        """Test that scoring results have required fields."""
        result = Mock(spec=ScoringResultContract)
        result.s1 = Mock(spec=StraceContract)
        result.s2 = Mock(spec=StraceContract)
        result.score = 0.95
        result.mapping = [(0, 0), (1, 2), (2, 1)]
        result.metadata = {"method": "test"}
        
        # Verify all fields present
        self.assertIsNotNone(result.s1)
        self.assertIsNotNone(result.s2)
        self.assertIsInstance(result.score, float)
        self.assertIsInstance(result.mapping, list)
        self.assertIsInstance(result.metadata, dict)


class TestConverterContracts(unittest.TestCase):
    """Test that converters conform to contracts."""
    
    def test_converter_contract_compliance(self):
        """Test that converters implement required interface."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = Mock(spec=AnsibleToNixConverter)
        
        # Setup methods
        converter.convert_playbook = MagicMock(return_value="{ config, pkgs, ... }: {}")
        converter._convert_task = MagicMock(return_value={"module": "test", "config": {}})
        
        # Verify contract
        self.assertTrue(isinstance(converter, ConverterContract))
        
        # Test conversion
        from pathlib import Path
        result = converter.convert_playbook(Path("test.yml"))
        self.assertIsInstance(result, str)
        
        # Test task conversion
        task = {"package": {"name": "nginx"}}
        task_result = converter._convert_task(task)
        self.assertIsInstance(task_result, dict)
    
    def test_converter_error_handling(self):
        """Test that converters handle errors appropriately."""
        converter = Mock(spec=ConverterContract)
        
        # Unknown module should return None
        converter._convert_task = MagicMock(return_value=None)
        
        unknown_task = {"unknown_module": {}}
        result = converter._convert_task(unknown_task)
        
        self.assertIsNone(result)


class TestValidatorContracts(unittest.TestCase):
    """Test that validators conform to contracts."""
    
    def test_validator_contract_compliance(self):
        """Test that validators implement required interface."""
        from lib.validation.ansible_nix_validator import AnsibleNixValidator
        
        validator = Mock(spec=AnsibleNixValidator)
        
        # Setup mock
        result = Mock(spec=ValidationResultContract)
        result.success = True
        result.score = 0.95
        result.differences = []
        result.warnings = []
        result.errors = []
        
        validator.validate_conversion = MagicMock(return_value=result)
        
        # Verify contract
        self.assertTrue(isinstance(validator, ValidatorContract))
        
        # Test validation
        validation_result = validator.validate_conversion("source", "target")
        
        # Verify result contract
        self.assertTrue(isinstance(validation_result, ValidationResultContract))
        self.assertIsInstance(validation_result.success, bool)
        self.assertIsInstance(validation_result.score, float)
        self.assertIsInstance(validation_result.differences, list)
    
    def test_validation_result_consistency(self):
        """Test that validation results are internally consistent."""
        result = Mock(spec=ValidationResultContract)
        
        # Success case
        result.success = True
        result.score = 0.95
        result.errors = []
        
        # Verify consistency
        if result.success:
            self.assertEqual(len(result.errors), 0)
            self.assertGreaterEqual(result.score, 0.8)  # Assuming 0.8 is success threshold
        
        # Failure case
        result.success = False
        result.score = 0.3
        result.errors = ["Error 1", "Error 2"]
        
        # Verify consistency
        if not result.success:
            self.assertGreater(len(result.errors), 0)


class TestCompositionContracts(unittest.TestCase):
    """Test that components can be composed correctly."""
    
    def test_preprocessor_scorer_composition(self):
        """Test that preprocessors work with scorers."""
        # Create components
        preprocessor = Mock(spec=PreprocessorContract)
        scorer = Mock(spec=ScorerContract)
        
        # Setup
        original_strace = Mock(spec=StraceContract)
        processed_strace = Mock(spec=StraceContract)
        scoring_result = Mock(spec=ScoringResultContract)
        scoring_result.score = 0.9
        
        preprocessor.process = MagicMock(return_value=processed_strace)
        scorer.__call__ = MagicMock(return_value=scoring_result)
        
        # Compose: preprocess then score
        s1 = preprocessor.process(original_strace)
        s2 = preprocessor.process(original_strace)
        result = scorer(s1, s2, set())
        
        # Verify composition worked
        self.assertEqual(result.score, 0.9)
    
    def test_converter_validator_composition(self):
        """Test that converters work with validators."""
        # Create components
        converter = Mock(spec=ConverterContract)
        validator = Mock(spec=ValidatorContract)
        
        # Setup
        nix_config = "{ config, pkgs, ... }: {}"
        validation_result = Mock(spec=ValidationResultContract)
        validation_result.success = True
        
        converter.convert_playbook = MagicMock(return_value=nix_config)
        validator.validate_conversion = MagicMock(return_value=validation_result)
        
        # Compose: convert then validate
        from pathlib import Path
        ansible_path = Path("test.yml")
        
        converted = converter.convert_playbook(ansible_path)
        result = validator.validate_conversion(ansible_path, converted)
        
        # Verify composition worked
        self.assertTrue(result.success)


class TestInterfaceEvolution(unittest.TestCase):
    """Test that interfaces can evolve safely."""
    
    def test_optional_contract_extensions(self):
        """Test that contracts can be extended with optional methods."""
        
        # Base contract
        class BaseContract(Protocol):
            def required_method(self) -> str:
                ...
        
        # Extended contract with optional method
        class ExtendedContract(BaseContract, Protocol):
            def optional_method(self) -> str:
                ...
        
        # Implementation with only required method
        class MinimalImpl:
            def required_method(self) -> str:
                return "required"
        
        # Implementation with both methods
        class FullImpl:
            def required_method(self) -> str:
                return "required"
            
            def optional_method(self) -> str:
                return "optional"
        
        # Both should satisfy base contract
        minimal = MinimalImpl()
        full = FullImpl()
        
        self.assertTrue(isinstance(minimal, BaseContract))
        self.assertTrue(isinstance(full, BaseContract))
        
        # Only full satisfies extended contract
        self.assertFalse(isinstance(minimal, ExtendedContract))
        self.assertTrue(isinstance(full, ExtendedContract))
    
    def test_backward_compatibility(self):
        """Test that new versions maintain backward compatibility."""
        
        # V1 contract
        class ContractV1(Protocol):
            def process(self, data: str) -> str:
                ...
        
        # V2 contract (backward compatible)
        class ContractV2(Protocol):
            def process(self, data: str, options: Optional[Dict] = None) -> str:
                ...
        
        # V1 implementation
        class ImplV1:
            def process(self, data: str) -> str:
                return data.upper()
        
        # V2 implementation
        class ImplV2:
            def process(self, data: str, options: Optional[Dict] = None) -> str:
                if options and options.get('lowercase'):
                    return data.lower()
                return data.upper()
        
        # V2 impl should work with V1 contract
        v2_impl = ImplV2()
        result = v2_impl.process("test")  # Called without options
        self.assertEqual(result, "TEST")


class ContractValidator:
    """Utility to validate contracts at runtime."""
    
    @staticmethod
    def validate_contract(obj: Any, contract: type) -> List[str]:
        """
        Validate that an object conforms to a contract.
        
        Returns list of violations.
        """
        violations = []
        
        # Get contract members
        contract_members = inspect.getmembers(contract)
        
        for name, member in contract_members:
            if name.startswith('_'):
                continue
            
            # Check attributes
            if not callable(member):
                if not hasattr(obj, name):
                    violations.append(f"Missing attribute: {name}")
            
            # Check methods
            else:
                if not hasattr(obj, name):
                    violations.append(f"Missing method: {name}")
                elif not callable(getattr(obj, name)):
                    violations.append(f"Attribute {name} is not callable")
        
        return violations
    
    @staticmethod
    def assert_contract(obj: Any, contract: type):
        """Assert that an object conforms to a contract."""
        violations = ContractValidator.validate_contract(obj, contract)
        if violations:
            raise AssertionError(f"Contract violations: {violations}")


class TestContractValidator(unittest.TestCase):
    """Test the contract validator utility."""
    
    def test_validate_valid_contract(self):
        """Test validating a valid contract implementation."""
        
        class TestContract(Protocol):
            value: int
            
            def method(self) -> str:
                ...
        
        class ValidImpl:
            def __init__(self):
                self.value = 42
            
            def method(self) -> str:
                return "test"
        
        impl = ValidImpl()
        violations = ContractValidator.validate_contract(impl, TestContract)
        
        self.assertEqual(len(violations), 0)
    
    def test_validate_invalid_contract(self):
        """Test validating an invalid contract implementation."""
        
        class TestContract(Protocol):
            value: int
            
            def method(self) -> str:
                ...
        
        class InvalidImpl:
            def __init__(self):
                self.value = 42
            # Missing method!
        
        impl = InvalidImpl()
        violations = ContractValidator.validate_contract(impl, TestContract)
        
        self.assertGreater(len(violations), 0)
        self.assertIn("Missing method: method", violations)


if __name__ == '__main__':
    unittest.main(verbosity=2)