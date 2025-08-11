"""
Unit tests for leaf components - the fundamental building blocks.

Testing priority:
1. Value objects (immutable data structures)
2. Pure functions (no side effects)
3. Stateless transformers
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# Test the most fundamental leaf components first

class TestLiteralValues(unittest.TestCase):
    """Test the literal value classes - pure value objects with no dependencies."""
    
    def setUp(self):
        """Create isolated test fixtures."""
        self.mock_attributes = {
            'value': 'test_value',
            'raw': 'raw_value'
        }
    
    def test_string_literal_creation(self):
        """Test StringLiteral creation - pure value object."""
        from lib.strace.classes import StringLiteral
        
        # Pure creation with no dependencies
        literal = StringLiteral(value="hello", raw='"hello"')
        
        self.assertEqual(literal.value, "hello")
        self.assertEqual(literal.raw, '"hello"')
        self.assertIsInstance(literal, StringLiteral)
    
    def test_number_literal_creation(self):
        """Test NumberLiteral creation - pure value object."""
        from lib.strace.classes import NumberLiteral
        
        # Test integer
        int_literal = NumberLiteral(value=42, raw='42')
        self.assertEqual(int_literal.value, 42)
        self.assertEqual(int_literal.raw, '42')
        
        # Test float
        float_literal = NumberLiteral(value=3.14, raw='3.14')
        self.assertEqual(float_literal.value, 3.14)
        self.assertEqual(float_literal.raw, '3.14')
    
    def test_null_literal_creation(self):
        """Test NullLiteral creation - pure value object."""
        from lib.strace.classes import NullLiteral
        
        null = NullLiteral(value=None, raw='NULL')
        self.assertIsNone(null.value)
        self.assertEqual(null.raw, 'NULL')
    
    def test_identifier_creation(self):
        """Test Identifier creation - pure value object."""
        from lib.strace.classes import Identifier
        
        identifier = Identifier(value='EINVAL', raw='EINVAL')
        self.assertEqual(identifier.value, 'EINVAL')
        self.assertEqual(identifier.raw, 'EINVAL')


class TestHoleClass(unittest.TestCase):
    """Test the Hole class - represents parameter placeholders."""
    
    def test_hole_creation(self):
        """Test Hole creation with various indexes."""
        from lib.strace.classes import Hole
        
        # Test basic hole
        hole = Hole(index=0)
        self.assertEqual(hole.index, 0)
        self.assertEqual(hole.value, None)
        
        # Test indexed hole
        indexed_hole = Hole(index=5)
        self.assertEqual(indexed_hole.index, 5)
    
    def test_hole_equality(self):
        """Test Hole equality comparison."""
        from lib.strace.classes import Hole
        
        hole1 = Hole(index=1)
        hole2 = Hole(index=1)
        hole3 = Hole(index=2)
        
        # Same index should be equal
        self.assertEqual(hole1, hole2)
        # Different index should not be equal
        self.assertNotEqual(hole1, hole3)


class TestExecutableParameter(unittest.TestCase):
    """Test ExecutableParameter - parameter definitions for executables."""
    
    def test_parameter_creation(self):
        """Test ExecutableParameter creation."""
        from lib.strace.classes import ExecutableParameter
        
        param = ExecutableParameter(
            name="file",
            description="File path",
            required=True,
            default=None
        )
        
        self.assertEqual(param.name, "file")
        self.assertEqual(param.description, "File path")
        self.assertTrue(param.required)
        self.assertIsNone(param.default)
    
    def test_optional_parameter(self):
        """Test optional parameter with default value."""
        from lib.strace.classes import ExecutableParameter
        
        param = ExecutableParameter(
            name="verbose",
            description="Verbose output",
            required=False,
            default=False
        )
        
        self.assertFalse(param.required)
        self.assertEqual(param.default, False)


class TestCanonicalForm(unittest.TestCase):
    """Test CanonicalForm - pure transformation functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        from lib.strace.comparison.canonical_form import CanonicalForm
        self.canonical = CanonicalForm()
    
    def test_path_canonicalization(self):
        """Test path canonicalization - pure function."""
        # Test absolute path
        result = self.canonical.canonicalize_path("/usr/local/bin/test")
        self.assertEqual(result, "/usr/local/bin/test")
        
        # Test relative path
        result = self.canonical.canonicalize_path("./test/file.txt")
        self.assertTrue(result.startswith("/"))
        
        # Test home directory
        with patch('os.path.expanduser') as mock_expand:
            mock_expand.return_value = "/home/user/file"
            result = self.canonical.canonicalize_path("~/file")
            self.assertEqual(result, "/home/user/file")
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization - pure function."""
        # Multiple spaces
        result = self.canonical.normalize_whitespace("hello    world")
        self.assertEqual(result, "hello world")
        
        # Tabs and newlines
        result = self.canonical.normalize_whitespace("hello\t\nworld")
        self.assertEqual(result, "hello world")
        
        # Leading/trailing whitespace
        result = self.canonical.normalize_whitespace("  hello world  ")
        self.assertEqual(result, "hello world")


class TestModuleMapping(unittest.TestCase):
    """Test ModuleMapping dataclass - pure data structure."""
    
    def test_module_mapping_creation(self):
        """Test ModuleMapping creation and field access."""
        from lib.converters.ansible_to_nix import ModuleMapping
        
        mapping = ModuleMapping(
            ansible_module="package",
            nix_module="environment.systemPackages",
            param_mapping={"name": "package", "state": "_ignore"},
            confidence=0.95
        )
        
        self.assertEqual(mapping.ansible_module, "package")
        self.assertEqual(mapping.nix_module, "environment.systemPackages")
        self.assertEqual(mapping.param_mapping["name"], "package")
        self.assertEqual(mapping.confidence, 0.95)
    
    def test_module_mapping_immutability(self):
        """Test that ModuleMapping is immutable (dataclass frozen=True)."""
        from lib.converters.ansible_to_nix import ModuleMapping
        
        mapping = ModuleMapping(
            ansible_module="service",
            nix_module="systemd.services",
            param_mapping={"name": "service"},
            confidence=0.8
        )
        
        # Attempting to modify should raise an error if frozen
        with self.assertRaises(AttributeError):
            mapping.confidence = 0.9


class TestSyscallPattern(unittest.TestCase):
    """Test SyscallPattern - pattern matching for syscalls."""
    
    def test_syscall_pattern_creation(self):
        """Test SyscallPattern creation."""
        from demo_dozer_approach import SyscallPattern
        
        pattern = SyscallPattern(
            name="open",
            args_pattern=r".*\.txt.*",
            frequency=10
        )
        
        self.assertEqual(pattern.name, "open")
        self.assertEqual(pattern.args_pattern, r".*\.txt.*")
        self.assertEqual(pattern.frequency, 10)
    
    def test_syscall_pattern_matching(self):
        """Test pattern matching logic."""
        import re
        from demo_dozer_approach import SyscallPattern
        
        pattern = SyscallPattern(
            name="open",
            args_pattern=r".*\.conf$",
            frequency=1
        )
        
        # Should match
        self.assertTrue(re.match(pattern.args_pattern, "/etc/nginx.conf"))
        # Should not match
        self.assertFalse(re.match(pattern.args_pattern, "/etc/nginx.conf.bak"))


class TestPureTransformFunctions(unittest.TestCase):
    """Test pure transformation functions with no side effects."""
    
    def test_translate_package_name(self):
        """Test package name translation - pure function."""
        from simple_converter import SimpleAnsibleToNixConverter
        
        converter = SimpleAnsibleToNixConverter()
        
        # Known translations
        self.assertEqual(converter._translate_package_name("apache2"), "apacheHttpd")
        self.assertEqual(converter._translate_package_name("docker.io"), "docker")
        self.assertEqual(converter._translate_package_name("build-essential"), "stdenv")
        
        # Unknown package (passthrough)
        self.assertEqual(converter._translate_package_name("unknown-pkg"), "unknown-pkg")
    
    def test_convert_cron_schedule(self):
        """Test cron schedule conversion - pure function."""
        from simple_converter import SimpleAnsibleToNixConverter
        
        converter = SimpleAnsibleToNixConverter()
        
        # Specific time
        result = converter._convert_cron_schedule("0", "2")
        self.assertEqual(result, "*-*-* 2:00:00")
        
        # Wildcard (fallback)
        result = converter._convert_cron_schedule("*", "*")
        self.assertEqual(result, "daily")


class TestValidationResult(unittest.TestCase):
    """Test ValidationResult dataclass - pure data structure."""
    
    def test_validation_result_creation(self):
        """Test ValidationResult creation with all fields."""
        from lib.validation.ansible_nix_validator import ValidationResult
        
        result = ValidationResult(
            success=True,
            score=0.95,
            differences=["diff1", "diff2"],
            warnings=["warning1"],
            errors=[]
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.score, 0.95)
        self.assertEqual(len(result.differences), 2)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(len(result.errors), 0)
    
    def test_validation_result_failure(self):
        """Test ValidationResult in failure state."""
        from lib.validation.ansible_nix_validator import ValidationResult
        
        result = ValidationResult(
            success=False,
            score=0.3,
            differences=["major diff"],
            warnings=[],
            errors=["error1", "error2"]
        )
        
        self.assertFalse(result.success)
        self.assertLess(result.score, 0.5)
        self.assertEqual(len(result.errors), 2)


class TestSystemState(unittest.TestCase):
    """Test SystemState dataclass - system state representation."""
    
    def test_system_state_creation(self):
        """Test SystemState creation."""
        from lib.validation.ansible_nix_validator import SystemState
        
        state = SystemState(
            packages=["nginx", "git"],
            services={"nginx": "running"},
            files={"/etc/nginx.conf": "hash123"},
            users=["webadmin"],
            groups=["www-data"]
        )
        
        self.assertEqual(len(state.packages), 2)
        self.assertEqual(state.services["nginx"], "running")
        self.assertEqual(state.files["/etc/nginx.conf"], "hash123")
        self.assertIn("webadmin", state.users)
        self.assertIn("www-data", state.groups)


class TestNixDerivation(unittest.TestCase):
    """Test NixDerivation dataclass - Nix build representation."""
    
    def test_nix_derivation_creation(self):
        """Test NixDerivation creation."""
        from lib.strace.collection.nix.builder import NixDerivation
        
        derivation = NixDerivation(
            name="test-package",
            version="1.0.0",
            src="/path/to/src",
            buildInputs=["gcc", "make"],
            buildPhase="make",
            installPhase="make install"
        )
        
        self.assertEqual(derivation.name, "test-package")
        self.assertEqual(derivation.version, "1.0.0")
        self.assertEqual(len(derivation.buildInputs), 2)
        self.assertIn("gcc", derivation.buildInputs)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)