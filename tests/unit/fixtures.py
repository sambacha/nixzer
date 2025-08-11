"""
Test fixtures and mock factories for unit tests.

Provides:
- Reusable test data
- Mock object factories
- Fixture generators
"""

from typing import List, Dict, Any, Optional
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
import json


# ============================================================================
# SYSCALL FIXTURES
# ============================================================================

class SyscallFixtures:
    """Factory for creating syscall test fixtures."""
    
    @staticmethod
    def create_open_syscall(path: str = "/test/file", 
                           flags: str = "O_RDONLY",
                           fd: int = 3) -> Mock:
        """Create a mock open syscall."""
        syscall = Mock()
        syscall.name = "open"
        syscall.arguments = [path, flags]
        syscall.return_value = fd
        syscall.raw = f'open("{path}", {flags}) = {fd}'
        return syscall
    
    @staticmethod
    def create_read_syscall(fd: int = 3, 
                           size: int = 1024,
                           actual: int = 1024) -> Mock:
        """Create a mock read syscall."""
        syscall = Mock()
        syscall.name = "read"
        syscall.arguments = [fd, size]
        syscall.return_value = actual
        syscall.raw = f'read({fd}, "...", {size}) = {actual}'
        return syscall
    
    @staticmethod
    def create_write_syscall(fd: int = 1,
                            data: str = "test data",
                            size: int = 9) -> Mock:
        """Create a mock write syscall."""
        syscall = Mock()
        syscall.name = "write"
        syscall.arguments = [fd, data, len(data)]
        syscall.return_value = size
        syscall.raw = f'write({fd}, "{data}", {len(data)}) = {size}'
        return syscall
    
    @staticmethod
    def create_close_syscall(fd: int = 3) -> Mock:
        """Create a mock close syscall."""
        syscall = Mock()
        syscall.name = "close"
        syscall.arguments = [fd]
        syscall.return_value = 0
        syscall.raw = f'close({fd}) = 0'
        return syscall
    
    @staticmethod
    def create_stat_syscall(path: str = "/test/file",
                           success: bool = True) -> Mock:
        """Create a mock stat syscall."""
        syscall = Mock()
        syscall.name = "stat"
        syscall.arguments = [path, Mock()]
        syscall.return_value = 0 if success else -1
        syscall.raw = f'stat("{path}", {{...}}) = {syscall.return_value}'
        return syscall
    
    @staticmethod
    def create_file_operation_trace() -> List[Mock]:
        """Create a typical file operation syscall sequence."""
        return [
            SyscallFixtures.create_open_syscall("/etc/config", "O_RDONLY", 3),
            SyscallFixtures.create_read_syscall(3, 4096, 2048),
            SyscallFixtures.create_close_syscall(3)
        ]
    
    @staticmethod
    def create_network_operation_trace() -> List[Mock]:
        """Create a typical network operation syscall sequence."""
        syscalls = []
        
        # Socket creation
        socket_call = Mock()
        socket_call.name = "socket"
        socket_call.arguments = ["AF_INET", "SOCK_STREAM", 0]
        socket_call.return_value = 4
        syscalls.append(socket_call)
        
        # Connect
        connect_call = Mock()
        connect_call.name = "connect"
        connect_call.arguments = [4, Mock()]
        connect_call.return_value = 0
        syscalls.append(connect_call)
        
        # Send data
        send_call = Mock()
        send_call.name = "send"
        send_call.arguments = [4, "GET / HTTP/1.1", 14, 0]
        send_call.return_value = 14
        syscalls.append(send_call)
        
        # Receive data
        recv_call = Mock()
        recv_call.name = "recv"
        recv_call.arguments = [4, Mock(), 4096, 0]
        recv_call.return_value = 1024
        syscalls.append(recv_call)
        
        # Close socket
        syscalls.append(SyscallFixtures.create_close_syscall(4))
        
        return syscalls


# ============================================================================
# STRACE FIXTURES
# ============================================================================

class StraceFixtures:
    """Factory for creating strace test fixtures."""
    
    @staticmethod
    def create_empty_strace() -> Mock:
        """Create an empty mock strace."""
        strace = Mock()
        strace.syscalls = []
        strace.executable = "test"
        strace.arguments = []
        strace.metadata = {}
        return strace
    
    @staticmethod
    def create_simple_strace(syscalls: Optional[List[Mock]] = None) -> Mock:
        """Create a simple mock strace with given syscalls."""
        strace = Mock()
        strace.syscalls = syscalls or SyscallFixtures.create_file_operation_trace()
        strace.executable = "test_program"
        strace.arguments = ["arg1", "arg2"]
        strace.metadata = {"version": "1.0"}
        return strace
    
    @staticmethod
    def create_ansible_module_strace(module: str = "package") -> Mock:
        """Create a mock strace for an Ansible module."""
        strace = Mock()
        strace.executable = f"ansible.modules.{module}"
        strace.arguments = ["name=nginx", "state=present"]
        strace.syscalls = SyscallFixtures.create_file_operation_trace()
        strace.metadata = {
            "module": module,
            "params": {"name": "nginx", "state": "present"}
        }
        return strace
    
    @staticmethod
    def create_nix_build_strace(package: str = "nginx") -> Mock:
        """Create a mock strace for a Nix build."""
        strace = Mock()
        strace.executable = "nix-build"
        strace.arguments = ["-A", package]
        strace.syscalls = [
            SyscallFixtures.create_stat_syscall(f"/nix/store/hash-{package}"),
            *SyscallFixtures.create_file_operation_trace()
        ]
        strace.metadata = {
            "package": package,
            "derivation": f"/nix/store/hash-{package}.drv"
        }
        return strace


# ============================================================================
# ANSIBLE FIXTURES
# ============================================================================

class AnsibleFixtures:
    """Factory for creating Ansible test fixtures."""
    
    @staticmethod
    def create_package_task(name: str = "nginx", 
                           state: str = "present") -> Dict[str, Any]:
        """Create an Ansible package installation task."""
        return {
            "name": f"Install {name}",
            "package": {
                "name": name,
                "state": state
            }
        }
    
    @staticmethod
    def create_service_task(name: str = "nginx",
                           state: str = "started",
                           enabled: bool = True) -> Dict[str, Any]:
        """Create an Ansible service task."""
        return {
            "name": f"Manage {name} service",
            "service": {
                "name": name,
                "state": state,
                "enabled": enabled
            }
        }
    
    @staticmethod
    def create_user_task(username: str = "testuser",
                        groups: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create an Ansible user task."""
        return {
            "name": f"Create user {username}",
            "user": {
                "name": username,
                "groups": groups or ["wheel"],
                "shell": "/bin/bash",
                "createhome": True,
                "comment": f"Test user {username}"
            }
        }
    
    @staticmethod
    def create_file_task(path: str = "/etc/test.conf",
                        state: str = "touch") -> Dict[str, Any]:
        """Create an Ansible file task."""
        return {
            "name": f"Manage file {path}",
            "file": {
                "path": path,
                "state": state,
                "mode": "0644",
                "owner": "root",
                "group": "root"
            }
        }
    
    @staticmethod
    def create_copy_task(src: str = "files/config",
                        dest: str = "/etc/config") -> Dict[str, Any]:
        """Create an Ansible copy task."""
        return {
            "name": f"Copy {src} to {dest}",
            "copy": {
                "src": src,
                "dest": dest,
                "mode": "0644",
                "owner": "root",
                "group": "root"
            }
        }
    
    @staticmethod
    def create_playbook(tasks: Optional[List[Dict]] = None) -> List[Dict]:
        """Create a complete Ansible playbook."""
        if tasks is None:
            tasks = [
                AnsibleFixtures.create_package_task("nginx"),
                AnsibleFixtures.create_service_task("nginx"),
                AnsibleFixtures.create_user_task("webadmin")
            ]
        
        return [{
            "name": "Test playbook",
            "hosts": "localhost",
            "become": True,
            "tasks": tasks
        }]


# ============================================================================
# NIX FIXTURES
# ============================================================================

class NixFixtures:
    """Factory for creating Nix test fixtures."""
    
    @staticmethod
    def create_package_config(packages: List[str]) -> Dict[str, Any]:
        """Create a Nix package configuration."""
        return {
            "module": "environment.systemPackages",
            "config": {
                "packages": packages
            }
        }
    
    @staticmethod
    def create_service_config(name: str = "nginx",
                             enable: bool = True) -> Dict[str, Any]:
        """Create a Nix service configuration."""
        return {
            "module": f"services.{name}",
            "config": {
                "enable": enable,
                "package": f"pkgs.{name}"
            }
        }
    
    @staticmethod
    def create_user_config(username: str = "testuser",
                          groups: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a Nix user configuration."""
        return {
            "module": "users.users",
            "config": {
                username: {
                    "isNormalUser": True,
                    "createHome": True,
                    "extraGroups": groups or ["wheel"],
                    "shell": "pkgs.bash",
                    "description": f"Test user {username}"
                }
            }
        }
    
    @staticmethod
    def create_nix_module(configs: Optional[List[Dict]] = None) -> str:
        """Create a complete Nix module."""
        if configs is None:
            configs = [
                NixFixtures.create_package_config(["nginx", "git", "vim"]),
                NixFixtures.create_service_config("nginx"),
                NixFixtures.create_user_config("webadmin")
            ]
        
        lines = [
            "{ config, pkgs, lib, ... }:",
            "{",
            "  # Test Nix configuration",
            ""
        ]
        
        for config in configs:
            module = config["module"]
            settings = config["config"]
            lines.append(f"  {module} = {json.dumps(settings, indent=2)};")
            lines.append("")
        
        lines.append("}")
        return "\n".join(lines)


# ============================================================================
# VALIDATION FIXTURES
# ============================================================================

class ValidationFixtures:
    """Factory for creating validation test fixtures."""
    
    @staticmethod
    def create_system_state(packages: Optional[List[str]] = None,
                           services: Optional[Dict[str, str]] = None,
                           users: Optional[List[str]] = None) -> Mock:
        """Create a mock system state."""
        state = Mock()
        state.packages = packages or ["nginx", "git", "vim"]
        state.services = services or {"nginx": "running", "ssh": "running"}
        state.files = {"/etc/nginx.conf": "hash123"}
        state.users = users or ["root", "webadmin"]
        state.groups = ["wheel", "www-data"]
        return state
    
    @staticmethod
    def create_validation_result(success: bool = True,
                                score: float = 0.95) -> Mock:
        """Create a mock validation result."""
        result = Mock()
        result.success = success
        result.score = score
        result.differences = [] if success else ["Package mismatch: nginx"]
        result.warnings = ["FD numbers may differ"]
        result.errors = [] if success else ["Service failed to start"]
        return result
    
    @staticmethod
    def create_docker_metadata() -> Dict[str, Any]:
        """Create Docker container metadata."""
        return {
            "container_id": "abc123",
            "image": "ubuntu:20.04",
            "command": "ansible-playbook test.yml",
            "environment": {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "ANSIBLE_VERSION": "2.10.0"
            },
            "volumes": ["/tmp/test:/data"],
            "ports": []
        }


# ============================================================================
# MOCK FACTORIES
# ============================================================================

class MockFactory:
    """Factory for creating complex mock objects."""
    
    @staticmethod
    def create_mock_converter() -> Mock:
        """Create a mock Ansible to Nix converter."""
        converter = Mock()
        converter.convert_playbook = MagicMock(return_value=NixFixtures.create_nix_module())
        converter._extract_module_name = MagicMock(return_value="package")
        converter._extract_parameters = MagicMock(return_value={"name": "nginx"})
        converter._translate_package_name = MagicMock(side_effect=lambda x: x)
        return converter
    
    @staticmethod
    def create_mock_validator() -> Mock:
        """Create a mock validator."""
        validator = Mock()
        validator.validate_conversion = MagicMock(
            return_value=ValidationFixtures.create_validation_result()
        )
        validator.compare_states = MagicMock(return_value=0.95)
        return validator
    
    @staticmethod
    def create_mock_scorer() -> Mock:
        """Create a mock scoring method."""
        scorer = Mock()
        result = Mock()
        result.score = 0.85
        result.mapping = [(0, 0), (1, 1), (2, 2)]
        result.metadata = {"method": "test"}
        scorer.return_value = result
        return scorer
    
    @staticmethod
    def create_mock_preprocessor() -> Mock:
        """Create a mock preprocessor."""
        preprocessor = Mock()
        preprocessor.process = MagicMock(side_effect=lambda x: x)
        return preprocessor


# ============================================================================
# TEST DATA GENERATORS
# ============================================================================

class TestDataGenerator:
    """Generate test data for various scenarios."""
    
    @staticmethod
    def generate_parameter_mappings(count: int = 5) -> List[tuple]:
        """Generate parameter mappings."""
        mappings = []
        for i in range(count):
            mappings.append((
                ("source", i),
                ("target", i * 2 if i % 2 == 0 else i)
            ))
        return mappings
    
    @staticmethod
    def generate_syscall_patterns(count: int = 10) -> List[Dict]:
        """Generate syscall patterns."""
        patterns = []
        syscall_names = ["open", "read", "write", "close", "stat", 
                        "socket", "connect", "send", "recv", "ioctl"]
        
        for i in range(count):
            patterns.append({
                "name": syscall_names[i % len(syscall_names)],
                "frequency": i + 1,
                "args_pattern": f"pattern_{i}"
            })
        return patterns
    
    @staticmethod
    def generate_conversion_test_cases() -> List[Dict]:
        """Generate test cases for conversion testing."""
        return [
            {
                "ansible": AnsibleFixtures.create_package_task("nginx"),
                "expected_nix": NixFixtures.create_package_config(["nginx"])
            },
            {
                "ansible": AnsibleFixtures.create_service_task("ssh"),
                "expected_nix": NixFixtures.create_service_config("ssh")
            },
            {
                "ansible": AnsibleFixtures.create_user_task("admin"),
                "expected_nix": NixFixtures.create_user_config("admin")
            }
        ]


# Export all fixture classes
__all__ = [
    'SyscallFixtures',
    'StraceFixtures',
    'AnsibleFixtures',
    'NixFixtures',
    'ValidationFixtures',
    'MockFactory',
    'TestDataGenerator'
]