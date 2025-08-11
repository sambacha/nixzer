"""Validation framework for Ansible to Nix conversions."""

import difflib
import hashlib
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating an Ansible to Nix conversion."""
    success: bool
    score: float
    ansible_state: Dict[str, Any]
    nix_state: Dict[str, Any]
    differences: List[str]
    warnings: List[str]
    errors: List[str]


@dataclass
class SystemState:
    """Represents system state after configuration."""
    packages: Set[str]
    services: Dict[str, str]  # service -> status
    users: Dict[str, Dict[str, Any]]
    groups: Dict[str, List[str]]
    files: Dict[str, str]  # path -> hash
    processes: List[str]
    network_ports: Set[int]


class AnsibleNixValidator:
    """Validate Ansible to Nix conversions by comparing system states."""
    
    def __init__(self, docker_compose_file: Optional[Path] = None):
        self.docker_compose = docker_compose_file or Path("docker-compose.validation.yml")
        self._setup_validation_environment()
    
    def _setup_validation_environment(self):
        """Create Docker Compose configuration for validation."""
        compose_config = """
version: '3.8'

services:
  ansible-test:
    image: debian:11
    container_name: dozer-ansible-test
    volumes:
      - ./ansible-playbooks:/playbooks
      - ./traces:/traces
    command: tail -f /dev/null
    
  nix-test:
    image: nixos/nix:latest
    container_name: dozer-nix-test
    volumes:
      - ./nix-configs:/configs
      - ./traces:/traces
    command: tail -f /dev/null
    privileged: true

networks:
  default:
    name: dozer-validation
"""
        
        with open(self.docker_compose, 'w') as f:
            f.write(compose_config)
    
    def validate_conversion(self,
                          ansible_playbook: Path,
                          nix_config: Path) -> ValidationResult:
        """
        Validate that Nix config produces equivalent state to Ansible playbook.
        
        Parameters
        ----------
        ansible_playbook : Path
            Path to Ansible playbook
        nix_config : Path
            Path to generated Nix configuration
            
        Returns
        -------
        ValidationResult
            Validation results with score and differences
        """
        logger.info(f"Validating conversion: {ansible_playbook} -> {nix_config}")
        
        # Start validation containers
        self._start_containers()
        
        try:
            # Run Ansible playbook
            ansible_state = self._run_ansible_playbook(ansible_playbook)
            
            # Run Nix configuration
            nix_state = self._run_nix_config(nix_config)
            
            # Compare states
            result = self._compare_states(ansible_state, nix_state)
            
            return result
            
        finally:
            # Clean up containers
            self._stop_containers()
    
    def _start_containers(self):
        """Start validation Docker containers."""
        cmd = f"docker-compose -f {self.docker_compose} up -d"
        subprocess.run(cmd, shell=True, check=True)
        
        # Wait for containers to be ready
        import time
        time.sleep(5)
    
    def _stop_containers(self):
        """Stop and remove validation containers."""
        cmd = f"docker-compose -f {self.docker_compose} down"
        subprocess.run(cmd, shell=True, check=True)
    
    def _run_ansible_playbook(self, playbook: Path) -> SystemState:
        """
        Run Ansible playbook in container and capture state.
        
        Parameters
        ----------
        playbook : Path
            Path to Ansible playbook
            
        Returns
        -------
        SystemState
            System state after running playbook
        """
        container = "dozer-ansible-test"
        
        # Install Ansible in container
        install_cmd = f"docker exec {container} bash -c 'apt-get update && apt-get install -y ansible'"
        subprocess.run(install_cmd, shell=True, check=True)
        
        # Copy playbook to container
        copy_cmd = f"docker cp {playbook} {container}:/tmp/playbook.yml"
        subprocess.run(copy_cmd, shell=True, check=True)
        
        # Run playbook
        run_cmd = f"docker exec {container} ansible-playbook -i localhost, -c local /tmp/playbook.yml"
        result = subprocess.run(run_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Ansible playbook failed: {result.stderr}")
        
        # Capture system state
        return self._capture_container_state(container)
    
    def _run_nix_config(self, config: Path) -> SystemState:
        """
        Run Nix configuration in container and capture state.
        
        Parameters
        ----------
        config : Path
            Path to Nix configuration
            
        Returns
        -------
        SystemState
            System state after applying configuration
        """
        container = "dozer-nix-test"
        
        # Copy config to container
        copy_cmd = f"docker cp {config} {container}:/tmp/config.nix"
        subprocess.run(copy_cmd, shell=True, check=True)
        
        # Build and activate configuration
        # Note: This is simplified - real NixOS would use nixos-rebuild
        build_cmd = f"""docker exec {container} bash -c '
            nix-build /tmp/config.nix -A system
            ./result/activate
        '"""
        
        result = subprocess.run(build_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Nix configuration failed: {result.stderr}")
        
        # Capture system state
        return self._capture_container_state(container)
    
    def _capture_container_state(self, container: str) -> SystemState:
        """
        Capture system state from container.
        
        Parameters
        ----------
        container : str
            Container name
            
        Returns
        -------
        SystemState
            Current system state
        """
        state = SystemState(
            packages=set(),
            services={},
            users={},
            groups={},
            files={},
            processes=[],
            network_ports=set()
        )
        
        # Capture installed packages
        pkg_cmd = f"docker exec {container} dpkg -l 2>/dev/null || rpm -qa 2>/dev/null || apk list --installed 2>/dev/null"
        pkg_result = subprocess.run(pkg_cmd, shell=True, capture_output=True, text=True)
        if pkg_result.returncode == 0:
            for line in pkg_result.stdout.splitlines():
                if line and not line.startswith('Listing'):
                    parts = line.split()
                    if parts:
                        state.packages.add(parts[0])
        
        # Capture services
        svc_cmd = f"docker exec {container} systemctl list-units --type=service --all --no-pager 2>/dev/null"
        svc_result = subprocess.run(svc_cmd, shell=True, capture_output=True, text=True)
        if svc_result.returncode == 0:
            for line in svc_result.stdout.splitlines():
                if '.service' in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        service_name = parts[0].replace('.service', '')
                        status = parts[3]
                        state.services[service_name] = status
        
        # Capture users
        user_cmd = f"docker exec {container} getent passwd"
        user_result = subprocess.run(user_cmd, shell=True, capture_output=True, text=True)
        if user_result.returncode == 0:
            for line in user_result.stdout.splitlines():
                parts = line.split(':')
                if len(parts) >= 7:
                    username = parts[0]
                    state.users[username] = {
                        'uid': parts[2],
                        'gid': parts[3],
                        'home': parts[5],
                        'shell': parts[6]
                    }
        
        # Capture groups
        group_cmd = f"docker exec {container} getent group"
        group_result = subprocess.run(group_cmd, shell=True, capture_output=True, text=True)
        if group_result.returncode == 0:
            for line in group_result.stdout.splitlines():
                parts = line.split(':')
                if len(parts) >= 4:
                    groupname = parts[0]
                    members = parts[3].split(',') if parts[3] else []
                    state.groups[groupname] = members
        
        # Capture key files
        files_to_check = [
            '/etc/nginx/nginx.conf',
            '/etc/apache2/apache2.conf',
            '/etc/ssh/sshd_config',
            '/etc/systemd/system/*.service'
        ]
        
        for file_pattern in files_to_check:
            hash_cmd = f"docker exec {container} bash -c 'for f in {file_pattern}; do [ -f \"$f\" ] && echo \"$f:$(sha256sum \"$f\" | cut -d\" \" -f1)\"; done'"
            hash_result = subprocess.run(hash_cmd, shell=True, capture_output=True, text=True)
            if hash_result.returncode == 0:
                for line in hash_result.stdout.splitlines():
                    if ':' in line:
                        path, file_hash = line.split(':', 1)
                        state.files[path] = file_hash
        
        # Capture running processes
        ps_cmd = f"docker exec {container} ps aux"
        ps_result = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True)
        if ps_result.returncode == 0:
            for line in ps_result.stdout.splitlines()[1:]:  # Skip header
                parts = line.split(None, 10)
                if len(parts) > 10:
                    state.processes.append(parts[10])
        
        # Capture network ports
        port_cmd = f"docker exec {container} netstat -tln 2>/dev/null || ss -tln 2>/dev/null"
        port_result = subprocess.run(port_cmd, shell=True, capture_output=True, text=True)
        if port_result.returncode == 0:
            for line in port_result.stdout.splitlines():
                if 'LISTEN' in line or 'listening' in line.lower():
                    parts = line.split()
                    for part in parts:
                        if ':' in part:
                            try:
                                port = int(part.split(':')[-1])
                                state.network_ports.add(port)
                            except ValueError:
                                pass
        
        return state
    
    def _compare_states(self,
                       ansible_state: SystemState,
                       nix_state: SystemState) -> ValidationResult:
        """
        Compare two system states and calculate similarity.
        
        Parameters
        ----------
        ansible_state : SystemState
            State after Ansible execution
        nix_state : SystemState
            State after Nix execution
            
        Returns
        -------
        ValidationResult
            Comparison results
        """
        differences = []
        warnings = []
        errors = []
        scores = []
        
        # Compare packages
        pkg_diff = ansible_state.packages.symmetric_difference(nix_state.packages)
        if pkg_diff:
            differences.append(f"Package differences: {pkg_diff}")
        pkg_score = len(ansible_state.packages.intersection(nix_state.packages)) / max(
            len(ansible_state.packages.union(nix_state.packages)), 1
        )
        scores.append(('packages', pkg_score, 0.3))
        
        # Compare services
        svc_matches = 0
        for service, status in ansible_state.services.items():
            if service in nix_state.services:
                if nix_state.services[service] == status:
                    svc_matches += 1
                else:
                    differences.append(f"Service {service}: {status} vs {nix_state.services[service]}")
            else:
                differences.append(f"Service {service} missing in Nix")
        
        svc_score = svc_matches / max(len(ansible_state.services), 1)
        scores.append(('services', svc_score, 0.3))
        
        # Compare users
        user_matches = 0
        for username, user_info in ansible_state.users.items():
            if username in nix_state.users:
                nix_user = nix_state.users[username]
                if user_info == nix_user:
                    user_matches += 1
                else:
                    for key in user_info:
                        if user_info[key] != nix_user.get(key):
                            differences.append(f"User {username}.{key}: {user_info[key]} vs {nix_user.get(key)}")
            elif username not in ['root', 'nobody', 'daemon']:  # Ignore system users
                differences.append(f"User {username} missing in Nix")
        
        user_score = user_matches / max(len(ansible_state.users), 1)
        scores.append(('users', user_score, 0.2))
        
        # Compare files
        file_matches = 0
        for path, hash_val in ansible_state.files.items():
            if path in nix_state.files:
                if nix_state.files[path] == hash_val:
                    file_matches += 1
                else:
                    differences.append(f"File {path} content differs")
            else:
                warnings.append(f"File {path} missing in Nix")
        
        file_score = file_matches / max(len(ansible_state.files), 1)
        scores.append(('files', file_score, 0.2))
        
        # Calculate weighted total score
        total_score = sum(score * weight for _, score, weight in scores)
        
        # Determine success
        success = total_score >= 0.8 and len(errors) == 0
        
        return ValidationResult(
            success=success,
            score=total_score,
            ansible_state=self._state_to_dict(ansible_state),
            nix_state=self._state_to_dict(nix_state),
            differences=differences,
            warnings=warnings,
            errors=errors
        )
    
    def _state_to_dict(self, state: SystemState) -> Dict[str, Any]:
        """Convert SystemState to dictionary."""
        return {
            'packages': list(state.packages),
            'services': state.services,
            'users': state.users,
            'groups': state.groups,
            'files': state.files,
            'processes': state.processes,
            'network_ports': list(state.network_ports)
        }