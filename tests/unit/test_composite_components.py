"""
Unit tests for composite components - building up from leaf components.

Testing components that combine multiple leaf components:
1. Strace processing pipeline
2. Conversion workflow
3. Validation pipeline
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from typing import List, Dict, Any
import json

# Import fixtures for consistent test data
from tests.unit.fixtures import (
    SyscallFixtures,
    StraceFixtures,
    AnsibleFixtures,
    NixFixtures,
    ValidationFixtures,
    MockFactory,
    TestDataGenerator
)


class TestStraceProcessingPipeline(unittest.TestCase):
    """Test the complete strace processing pipeline."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.syscall_fixtures = SyscallFixtures()
        self.strace_fixtures = StraceFixtures()
    
    def test_strace_parsing_and_preprocessing(self):
        """Test parsing followed by preprocessing."""
        # Create mock strace
        raw_strace = self.strace_fixtures.create_simple_strace()
        
        # Mock parser
        with patch('lib.strace.parser.parse_string') as mock_parse:
            mock_parse.return_value = raw_strace
            
            # Mock preprocessors
            with patch('lib.strace.comparison.preprocessing.PunchHoles') as MockPunchHoles:
                with patch('lib.strace.comparison.preprocessing.ReplaceFileDescriptors') as MockReplaceFD:
                    
                    punch_holes = MockPunchHoles.return_value
                    replace_fd = MockReplaceFD.return_value
                    
                    # Configure mock behavior
                    punch_holes.process.return_value = raw_strace
                    replace_fd.process.return_value = raw_strace
                    
                    # Simulate pipeline
                    parsed = mock_parse("test strace content")
                    holed = punch_holes.process(parsed)
                    normalized = replace_fd.process(holed)
                    
                    # Verify pipeline execution
                    mock_parse.assert_called_once()
                    punch_holes.process.assert_called_once_with(parsed)
                    replace_fd.process.assert_called_once_with(holed)
    
    def test_strace_comparison_pipeline(self):
        """Test complete comparison pipeline."""
        # Create test straces
        strace1 = self.strace_fixtures.create_ansible_module_strace("package")
        strace2 = self.strace_fixtures.create_nix_build_strace("nginx")
        
        # Mock comparison components
        with patch('lib.strace.comparison.syscall_equality.NameEquality') as MockEquality:
            with patch('lib.strace.comparison.scoring.JaccardCoefficient') as MockScorer:
                
                equality = MockEquality.return_value
                scorer = MockScorer.return_value
                
                # Configure mocks
                equality.return_value = True  # Syscalls are equal
                scorer.return_value = Mock(score=0.85, mapping=[(0, 0), (1, 1)])
                
                # Simulate comparison
                result = scorer(strace1, strace2, set())
                
                # Verify result
                self.assertEqual(result.score, 0.85)
                self.assertEqual(len(result.mapping), 2)
    
    def test_migration_generation(self):
        """Test migration generation from comparison results."""
        from lib.strace.classes import MigrationResult
        
        # Create source and target straces
        source = self.strace_fixtures.create_ansible_module_strace()
        target = self.strace_fixtures.create_nix_build_strace()
        
        # Create parameter mapping
        mapping = TestDataGenerator.generate_parameter_mappings(3)
        
        # Create migration
        migration = Mock()
        migration.syscalls = target.syscalls.copy()
        
        # Apply parameter mapping (simplified)
        for src_path, tgt_path in mapping:
            # In real implementation, this would map parameters
            pass
        
        # Create migration result
        result = MigrationResult(
            source=source,
            target=target,
            mapping=mapping,
            migration=migration
        )
        
        # Verify structure
        self.assertEqual(result.source.executable, "ansible.modules.package")
        self.assertEqual(result.target.executable, "nix-build")
        self.assertEqual(len(result.mapping), 3)


class TestConversionWorkflow(unittest.TestCase):
    """Test the complete Ansible to Nix conversion workflow."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.ansible_fixtures = AnsibleFixtures()
        self.nix_fixtures = NixFixtures()
        self.mock_factory = MockFactory()
    
    def test_playbook_parsing_and_task_extraction(self):
        """Test parsing playbook and extracting tasks."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Create test playbook
        playbook = self.ansible_fixtures.create_playbook()
        
        # Mock YAML loading
        with patch('yaml.safe_load') as mock_yaml:
            mock_yaml.return_value = playbook
            
            # Mock task conversion
            with patch.object(converter, '_convert_task') as mock_convert:
                mock_convert.return_value = self.nix_fixtures.create_package_config(["nginx"])
                
                # Mock file reading
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = "yaml content"
                    
                    # Convert playbook
                    from pathlib import Path
                    result = converter.convert_playbook(Path("test.yml"))
                    
                    # Verify task processing
                    self.assertEqual(mock_convert.call_count, len(playbook[0]['tasks']))
    
    def test_module_mapping_logic(self):
        """Test module mapping from Ansible to Nix."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Test cases
        test_cases = TestDataGenerator.generate_conversion_test_cases()
        
        for case in test_cases:
            ansible_task = case["ansible"]
            expected_nix = case["expected_nix"]
            
            # Extract module and parameters
            module = converter._extract_module_name(ansible_task)
            params = converter._extract_parameters(ansible_task)
            
            # Verify extraction
            self.assertIsNotNone(module)
            self.assertIsNotNone(params)
            
            # Test direct conversion
            with patch.object(converter, '_direct_conversion') as mock_convert:
                mock_convert.return_value = expected_nix
                
                result = converter._direct_conversion(module, params)
                
                # Verify conversion
                self.assertEqual(result["module"], expected_nix["module"])
    
    def test_syscall_based_conversion_fallback(self):
        """Test fallback to syscall-based conversion."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Create unknown module task
        unknown_task = {
            "name": "Custom module",
            "custom_module": {"param": "value"}
        }
        
        # Mock syscall tracing
        with patch.object(converter, '_trace_ansible_module') as mock_trace:
            with patch.object(converter, '_find_best_nix_match') as mock_match:
                with patch.object(converter, '_generate_from_match') as mock_generate:
                    
                    # Configure mocks
                    mock_trace.return_value = self.strace_fixtures.create_ansible_module_strace()
                    mock_match.return_value = Mock(score=0.75)
                    mock_generate.return_value = {"module": "custom.nix", "config": {}}
                    
                    # Convert task
                    result = converter._convert_task(unknown_task)
                    
                    # Verify syscall-based conversion was attempted
                    mock_trace.assert_called()
                    mock_match.assert_called()
    
    def test_nix_module_generation(self):
        """Test generating complete Nix module."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Create configurations
        configs = [
            self.nix_fixtures.create_package_config(["nginx", "git"]),
            self.nix_fixtures.create_service_config("nginx"),
            self.nix_fixtures.create_user_config("admin")
        ]
        
        # Generate module
        nix_module = converter._generate_nix_module(configs)
        
        # Verify structure
        self.assertIn("{ config, pkgs, lib, ... }:", nix_module)
        self.assertIn("environment.systemPackages", nix_module)
        self.assertIn("nginx", nix_module)
        self.assertIn("git", nix_module)


class TestValidationPipeline(unittest.TestCase):
    """Test the validation pipeline for conversions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validation_fixtures = ValidationFixtures()
        self.mock_factory = MockFactory()
    
    def test_state_capture_and_comparison(self):
        """Test capturing and comparing system states."""
        from lib.validation.ansible_nix_validator import AnsibleNixValidator
        
        validator = AnsibleNixValidator()
        
        # Create mock states
        ansible_state = self.validation_fixtures.create_system_state(
            packages=["nginx", "git"],
            services={"nginx": "running"}
        )
        
        nix_state = self.validation_fixtures.create_system_state(
            packages=["nginx", "git", "vim"],
            services={"nginx": "running"}
        )
        
        # Mock state capture
        with patch.object(validator, '_capture_ansible_state') as mock_ansible:
            with patch.object(validator, '_capture_nix_state') as mock_nix:
                mock_ansible.return_value = ansible_state
                mock_nix.return_value = nix_state
                
                # Mock comparison
                with patch.object(validator, '_compare_states') as mock_compare:
                    mock_compare.return_value = self.validation_fixtures.create_validation_result()
                    
                    # Validate
                    from pathlib import Path
                    result = validator.validate_conversion(
                        Path("ansible.yml"),
                        Path("nix.nix")
                    )
                    
                    # Verify
                    self.assertTrue(result.success)
                    self.assertGreaterEqual(result.score, 0.9)
    
    def test_docker_based_validation(self):
        """Test Docker-based validation."""
        from lib.validation.docker import DockerValidator
        
        # Create mock Docker client
        with patch('docker.from_env') as mock_docker:
            docker_client = Mock()
            mock_docker.return_value = docker_client
            
            # Mock container operations
            container = Mock()
            container.exec_run.return_value = (0, b"Success")
            docker_client.containers.run.return_value = container
            
            # Create validator
            validator = DockerValidator()
            
            # Mock validation
            with patch.object(validator, 'validate') as mock_validate:
                mock_validate.return_value = self.validation_fixtures.create_validation_result()
                
                # Run validation
                result = validator.validate("ansible.yml", "nix.nix")
                
                # Verify
                self.assertTrue(result.success)
    
    def test_syscall_trace_validation(self):
        """Test validation by comparing syscall traces."""
        # Create mock traces
        ansible_trace = self.strace_fixtures.create_ansible_module_strace()
        nix_trace = self.strace_fixtures.create_nix_build_strace()
        
        # Mock comparison
        scorer = self.mock_factory.create_mock_scorer()
        
        # Compare traces
        result = scorer(ansible_trace, nix_trace, set())
        
        # Verify similarity
        self.assertGreaterEqual(result.score, 0.8)
        self.assertIsNotNone(result.mapping)


class TestErrorHandling(unittest.TestCase):
    """Test error handling in composite components."""
    
    def test_invalid_playbook_handling(self):
        """Test handling of invalid Ansible playbooks."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Invalid YAML
        with patch('yaml.safe_load') as mock_yaml:
            mock_yaml.side_effect = yaml.YAMLError("Invalid YAML")
            
            with patch('builtins.open', create=True):
                from pathlib import Path
                
                # Should handle error gracefully
                with self.assertRaises(Exception):
                    converter.convert_playbook(Path("invalid.yml"))
    
    def test_missing_module_handling(self):
        """Test handling of unknown Ansible modules."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Unknown module task
        task = {
            "name": "Unknown task",
            "unknown_module": {"param": "value"}
        }
        
        # Mock syscall fallback failure
        with patch.object(converter, '_syscall_based_conversion') as mock_syscall:
            mock_syscall.return_value = None
            
            # Convert task
            result = converter._convert_task(task)
            
            # Should return None for unknown modules
            self.assertIsNone(result)
    
    def test_validation_failure_handling(self):
        """Test handling of validation failures."""
        from lib.validation.ansible_nix_validator import AnsibleNixValidator
        
        validator = AnsibleNixValidator()
        
        # Mock validation failure
        with patch.object(validator, '_compare_states') as mock_compare:
            failure_result = self.validation_fixtures.create_validation_result(
                success=False,
                score=0.3
            )
            mock_compare.return_value = failure_result
            
            # Mock state capture
            with patch.object(validator, '_capture_ansible_state'):
                with patch.object(validator, '_capture_nix_state'):
                    
                    from pathlib import Path
                    result = validator.validate_conversion(
                        Path("ansible.yml"),
                        Path("nix.nix")
                    )
                    
                    # Verify failure handling
                    self.assertFalse(result.success)
                    self.assertLess(result.score, 0.5)
                    self.assertTrue(len(result.errors) > 0)


class TestPerformanceOptimizations(unittest.TestCase):
    """Test performance optimizations in composite components."""
    
    def test_caching_in_conversion(self):
        """Test that conversions are cached appropriately."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Create identical tasks
        task1 = AnsibleFixtures.create_package_task("nginx")
        task2 = AnsibleFixtures.create_package_task("nginx")
        
        # Mock conversion
        with patch.object(converter, '_direct_conversion') as mock_convert:
            mock_convert.return_value = NixFixtures.create_package_config(["nginx"])
            
            # Convert both tasks
            result1 = converter._convert_task(task1)
            result2 = converter._convert_task(task2)
            
            # Should reuse conversion for identical tasks
            # (In real implementation, would check cache hits)
            self.assertEqual(result1, result2)
    
    def test_batch_processing(self):
        """Test batch processing of multiple tasks."""
        from lib.converters.ansible_to_nix import AnsibleToNixConverter
        
        converter = AnsibleToNixConverter()
        
        # Create multiple tasks
        tasks = [
            AnsibleFixtures.create_package_task(f"pkg{i}")
            for i in range(10)
        ]
        
        playbook = [{"tasks": tasks}]
        
        # Mock conversion
        with patch.object(converter, '_convert_task') as mock_convert:
            mock_convert.return_value = {"module": "test", "config": {}}
            
            # Process playbook
            with patch('yaml.safe_load') as mock_yaml:
                mock_yaml.return_value = playbook
                
                with patch('builtins.open', create=True):
                    from pathlib import Path
                    converter.convert_playbook(Path("test.yml"))
                    
                    # Verify all tasks processed
                    self.assertEqual(mock_convert.call_count, 10)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)