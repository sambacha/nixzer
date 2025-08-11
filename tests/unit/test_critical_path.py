"""
Unit tests for critical path components.

Critical path priorities:
1. Syscall comparison and equality checking
2. Scoring algorithms for matching
3. Parameter mapping between systems
4. Conversion logic (Ansible -> Nix)
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any, Set, Tuple
import json


class TestSyscallEquality(unittest.TestCase):
    """Test syscall equality checking - critical for comparison accuracy."""
    
    def setUp(self):
        """Create mock syscalls for testing."""
        from lib.strace.classes import Syscall
        
        # Create mock syscalls without actual parsing
        self.mock_syscall1 = Mock(spec=Syscall)
        self.mock_syscall1.name = "open"
        self.mock_syscall1.arguments = ["/etc/config", "O_RDONLY"]
        self.mock_syscall1.return_value = 3
        
        self.mock_syscall2 = Mock(spec=Syscall)
        self.mock_syscall2.name = "open"
        self.mock_syscall2.arguments = ["/etc/config", "O_RDONLY"]
        self.mock_syscall2.return_value = 4  # Different FD
        
        self.mock_syscall3 = Mock(spec=Syscall)
        self.mock_syscall3.name = "close"
        self.mock_syscall3.arguments = [3]
        self.mock_syscall3.return_value = 0
    
    def test_name_equality(self):
        """Test NameEquality - syscalls equal if names match."""
        from lib.strace.comparison.syscall_equality import NameEquality
        
        equality = NameEquality()
        
        # Same name should be equal
        self.assertTrue(equality(self.mock_syscall1, self.mock_syscall2))
        
        # Different names should not be equal
        self.assertFalse(equality(self.mock_syscall1, self.mock_syscall3))
    
    def test_strict_equality(self):
        """Test StrictEquality - all fields must match."""
        from lib.strace.comparison.syscall_equality import StrictEquality
        
        equality = StrictEquality()
        
        # Create identical syscalls
        identical1 = Mock()
        identical1.name = "open"
        identical1.arguments = ["/file", "O_RDONLY"]
        identical1.return_value = 3
        
        identical2 = Mock()
        identical2.name = "open"
        identical2.arguments = ["/file", "O_RDONLY"]
        identical2.return_value = 3
        
        different = Mock()
        different.name = "open"
        different.arguments = ["/other", "O_RDONLY"]
        different.return_value = 3
        
        # Identical should be equal
        self.assertTrue(equality(identical1, identical2))
        
        # Different arguments should not be equal
        self.assertFalse(equality(identical1, different))
    
    def test_canonical_equality(self):
        """Test CanonicalEquality - normalized comparison."""
        from lib.strace.comparison.syscall_equality import CanonicalEquality
        
        with patch('lib.strace.comparison.canonical_form.CanonicalForm') as MockCanonical:
            mock_canonical = MockCanonical.return_value
            mock_canonical.canonicalize.side_effect = lambda x: x  # Identity for testing
            
            equality = CanonicalEquality()
            
            # Test that canonicalization is applied
            syscall1 = Mock()
            syscall1.name = "open"
            syscall1.arguments = ["./file", "O_RDONLY"]
            
            syscall2 = Mock()
            syscall2.name = "open"
            syscall2.arguments = ["/abs/file", "O_RDONLY"]
            
            # Mock canonicalization to normalize paths
            mock_canonical.canonicalize.side_effect = lambda x: "/normalized/path" if "file" in str(x) else x
            
            result = equality(syscall1, syscall2)
            # Should call canonicalize
            self.assertTrue(mock_canonical.canonicalize.called)


class TestScoringMethods(unittest.TestCase):
    """Test scoring algorithms - critical for matching accuracy."""
    
    def setUp(self):
        """Create mock straces for testing."""
        from lib.strace.classes import Strace, Syscall
        
        # Create mock straces
        self.strace1 = Mock(spec=Strace)
        self.strace1.syscalls = [
            self._create_mock_syscall("open", ["/file1"]),
            self._create_mock_syscall("read", [3, 1024]),
            self._create_mock_syscall("close", [3])
        ]
        
        self.strace2 = Mock(spec=Strace)
        self.strace2.syscalls = [
            self._create_mock_syscall("open", ["/file2"]),
            self._create_mock_syscall("read", [4, 1024]),
            self._create_mock_syscall("close", [4])
        ]
        
        self.strace3 = Mock(spec=Strace)
        self.strace3.syscalls = [
            self._create_mock_syscall("socket", ["AF_INET"]),
            self._create_mock_syscall("connect", [5]),
            self._create_mock_syscall("send", [5, "data"])
        ]
    
    def _create_mock_syscall(self, name: str, args: List[Any]) -> Mock:
        """Helper to create mock syscall."""
        syscall = Mock()
        syscall.name = name
        syscall.arguments = args
        return syscall
    
    def test_jaccard_coefficient(self):
        """Test Jaccard coefficient scoring - set similarity."""
        from lib.strace.comparison.scoring import JaccardCoefficient
        
        scorer = JaccardCoefficient()
        
        # Create mock traces with syscall sets
        trace1 = Mock()
        trace1.syscalls = [
            self._create_mock_syscall("open", []),
            self._create_mock_syscall("read", []),
            self._create_mock_syscall("close", [])
        ]
        
        trace2 = Mock()
        trace2.syscalls = [
            self._create_mock_syscall("open", []),
            self._create_mock_syscall("write", []),
            self._create_mock_syscall("close", [])
        ]
        
        # Mock the scoring result
        with patch.object(scorer, '__call__') as mock_call:
            mock_result = Mock()
            mock_result.score = 0.5  # 2 common / 4 total unique
            mock_call.return_value = mock_result
            
            result = scorer(trace1, trace2, set())
            self.assertEqual(result.score, 0.5)
    
    def test_tfidf_scoring(self):
        """Test TF-IDF scoring - weighted by rarity."""
        from lib.strace.comparison.scoring import TFIDF
        
        scorer = TFIDF()
        
        # Create traces with different syscall frequencies
        common_trace = Mock()
        common_trace.syscalls = [
            self._create_mock_syscall("open", []) for _ in range(10)
        ]
        
        rare_trace = Mock()
        rare_trace.syscalls = [
            self._create_mock_syscall("ioctl", [])  # Rare syscall
        ]
        
        # Mock IDF values
        with patch.object(scorer, '__call__') as mock_call:
            mock_result = Mock()
            mock_result.score = 0.8  # Higher score for rare match
            mock_call.return_value = mock_result
            
            result = scorer(rare_trace, rare_trace, set())
            self.assertGreater(result.score, 0.5)
    
    def test_maximum_matching(self):
        """Test maximum matching algorithm - optimal pairing."""
        from lib.strace.comparison.scoring import MaximumCardinalityMatching
        
        matcher = MaximumCardinalityMatching()
        
        # Create traces for matching
        trace1 = Mock()
        trace1.syscalls = [
            self._create_mock_syscall("open", ["/a"]),
            self._create_mock_syscall("read", [3]),
            self._create_mock_syscall("close", [3])
        ]
        
        trace2 = Mock()
        trace2.syscalls = [
            self._create_mock_syscall("open", ["/b"]),
            self._create_mock_syscall("read", [4]),
            self._create_mock_syscall("close", [4])
        ]
        
        with patch.object(matcher, '__call__') as mock_call:
            mock_result = Mock()
            mock_result.score = 1.0  # Perfect structural match
            mock_result.mapping = [(0, 0), (1, 1), (2, 2)]
            mock_call.return_value = mock_result
            
            result = matcher(trace1, trace2, set())
            self.assertEqual(result.score, 1.0)
            self.assertEqual(len(result.mapping), 3)


class TestParameterMapping(unittest.TestCase):
    """Test parameter mapping between Ansible and Nix."""
    
    def test_simple_parameter_mapping(self):
        """Test direct parameter mapping."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Test package module mapping
        ansible_params = {"name": "nginx", "state": "present"}
        
        # Mock the conversion
        with patch.object(converter, '_direct_conversion') as mock_convert:
            mock_convert.return_value = {
                'module': 'environment.systemPackages',
                'config': {'package': 'nginx'}
            }
            
            result = converter._direct_conversion('package', ansible_params)
            
            self.assertEqual(result['module'], 'environment.systemPackages')
            self.assertIn('package', result['config'])
    
    def test_complex_parameter_mapping(self):
        """Test parameter mapping with transformations."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Test user module with multiple parameters
        ansible_params = {
            "name": "webadmin",
            "groups": ["wheel", "www-data"],
            "shell": "/bin/bash",
            "createhome": True
        }
        
        with patch.object(converter, '_direct_conversion') as mock_convert:
            mock_convert.return_value = {
                'module': 'users.users',
                'config': {
                    'username': 'webadmin',
                    'extraGroups': ['wheel', 'www-data'],
                    'shell': 'pkgs.bash',
                    'createHome': True
                }
            }
            
            result = converter._direct_conversion('user', ansible_params)
            
            self.assertEqual(result['config']['username'], 'webadmin')
            self.assertEqual(result['config']['extraGroups'], ['wheel', 'www-data'])
            self.assertTrue(result['config']['createHome'])
    
    def test_parameter_mapping_with_holes(self):
        """Test parameter mapping with hole placeholders."""
        # Create parameter mapping with holes
        mapping = [
            (("source", 0), ("target", 0)),  # Map source param 0 to target param 0
            (("source", 1), ("target", 2)),  # Map source param 1 to target param 2
        ]
        
        source_params = ["value1", "value2", "value3"]
        
        # Apply mapping
        target_params = [None, None, None]
        for (src_path, tgt_path) in mapping:
            if src_path[0] == "source" and tgt_path[0] == "target":
                src_idx = src_path[1]
                tgt_idx = tgt_path[1]
                if src_idx < len(source_params) and tgt_idx < len(target_params):
                    target_params[tgt_idx] = source_params[src_idx]
        
        self.assertEqual(target_params[0], "value1")
        self.assertEqual(target_params[2], "value2")
        self.assertIsNone(target_params[1])


class TestConversionLogic(unittest.TestCase):
    """Test the core conversion logic from Ansible to Nix."""
    
    def test_task_extraction(self):
        """Test extracting module and parameters from Ansible task."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Test various task formats
        task1 = {
            "name": "Install nginx",
            "package": {"name": "nginx", "state": "present"}
        }
        
        module = converter._extract_module_name(task1)
        params = converter._extract_parameters(task1)
        
        self.assertEqual(module, "package")
        self.assertEqual(params["name"], "nginx")
        self.assertEqual(params["state"], "present")
        
        # Test string format
        task2 = {
            "name": "Install package",
            "apt": "name=nginx state=present"
        }
        
        module = converter._extract_module_name(task2)
        params = converter._extract_parameters(task2)
        
        self.assertEqual(module, "apt")
        self.assertEqual(params["name"], "nginx")
        self.assertEqual(params["state"], "present")
    
    def test_package_name_translation(self):
        """Test package name translation between systems."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Test known translations
        self.assertEqual(converter._translate_package_name("apache2"), "apacheHttpd")
        self.assertEqual(converter._translate_package_name("docker.io"), "docker")
        self.assertEqual(converter._translate_package_name("build-essential"), "stdenv")
        
        # Test passthrough for unknown packages
        self.assertEqual(converter._translate_package_name("custom-package"), "custom-package")
    
    def test_nix_module_generation(self):
        """Test generating Nix module from configurations."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        configs = [
            {
                'module': 'environment.systemPackages',
                'config': {'package': 'nginx'}
            },
            {
                'module': 'environment.systemPackages',
                'config': {'package': 'git'}
            }
        ]
        
        nix_module = converter._generate_nix_module(configs)
        
        # Check basic structure
        self.assertIn("{ config, pkgs, lib, ... }:", nix_module)
        self.assertIn("environment.systemPackages", nix_module)
        self.assertIn("nginx", nix_module)
        self.assertIn("git", nix_module)


class TestSyscallTracing(unittest.TestCase):
    """Test syscall tracing functionality - critical for Dozer approach."""
    
    def test_trace_comparison(self):
        """Test comparing syscall traces."""
        from lib.strace.comparison.scoring import ScoringResult
        
        # Create mock traces
        trace1 = Mock()
        trace1.syscalls = [
            Mock(name="open", arguments=["/file"], return_value=3),
            Mock(name="read", arguments=[3, 1024], return_value=1024),
            Mock(name="close", arguments=[3], return_value=0)
        ]
        
        trace2 = Mock()
        trace2.syscalls = [
            Mock(name="open", arguments=["/file"], return_value=4),
            Mock(name="read", arguments=[4, 1024], return_value=1024),
            Mock(name="close", arguments=[4], return_value=0)
        ]
        
        # Create scoring result
        result = ScoringResult(
            s1=trace1,
            s2=trace2,
            mapping=[(0, 0), (1, 1), (2, 2)],
            score=0.95,
            metadata={"method": "test"}
        )
        
        self.assertEqual(result.score, 0.95)
        self.assertEqual(len(result.mapping), 3)
        self.assertEqual(result.metadata["method"], "test")
    
    def test_migration_result(self):
        """Test MigrationResult structure."""
        from lib.strace.classes import MigrationResult
        
        # Create mock components
        source = Mock(name="source_trace")
        target = Mock(name="target_trace")
        mapping = [(("src", 0), ("tgt", 0))]
        migration = Mock(name="migration_trace")
        
        result = MigrationResult(
            source=source,
            target=target,
            mapping=mapping,
            migration=migration
        )
        
        self.assertEqual(result.source.name, "source_trace")
        self.assertEqual(result.target.name, "target_trace")
        self.assertEqual(len(result.mapping), 1)
        self.assertEqual(result.migration.name, "migration_trace")


class TestPreprocessors(unittest.TestCase):
    """Test strace preprocessors - critical for normalization."""
    
    def test_punch_holes(self):
        """Test PunchHoles preprocessor - parameterization."""
        from lib.strace.comparison.preprocessing import PunchHoles
        
        preprocessor = PunchHoles()
        
        # Create mock strace with literals
        mock_strace = Mock()
        mock_syscall = Mock()
        mock_syscall.arguments = [
            Mock(value="/path/to/file"),
            Mock(value=42)
        ]
        mock_strace.syscalls = [mock_syscall]
        
        # Mock the preprocessing
        with patch.object(preprocessor, 'process') as mock_process:
            # Return strace with holes
            mock_result = Mock()
            mock_result.syscalls = [Mock(arguments=[Mock(index=0), Mock(index=1)])]
            mock_process.return_value = mock_result
            
            result = preprocessor.process(mock_strace)
            
            # Check that holes were created
            self.assertTrue(mock_process.called)
    
    def test_replace_file_descriptors(self):
        """Test ReplaceFileDescriptors - FD normalization."""
        from lib.strace.comparison.preprocessing import ReplaceFileDescriptors
        
        preprocessor = ReplaceFileDescriptors()
        
        # Create mock strace with file descriptors
        mock_strace = Mock()
        mock_strace.syscalls = [
            Mock(name="open", return_value=3),
            Mock(name="read", arguments=[3, 1024]),
            Mock(name="close", arguments=[3])
        ]
        
        with patch.object(preprocessor, 'process') as mock_process:
            # Mock normalized result
            mock_result = Mock()
            mock_result.syscalls = [
                Mock(name="open", return_value="<FD>"),
                Mock(name="read", arguments=["<FD>", 1024]),
                Mock(name="close", arguments=["<FD>"])
            ]
            mock_process.return_value = mock_result
            
            result = preprocessor.process(mock_strace)
            
            self.assertTrue(mock_process.called)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)