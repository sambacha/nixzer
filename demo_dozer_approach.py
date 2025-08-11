#!/usr/bin/env python3
"""
Demo showing how Dozer's syscall-based approach works for Ansible->Nix conversion.

This simulates the syscall analysis that would happen in a full implementation.
"""

from dataclasses import dataclass
from typing import Dict, List, Set
import json


@dataclass
class SyscallPattern:
    """Represents a pattern of syscalls for a module."""
    module_name: str
    syscalls: List[str]
    file_operations: Set[str]
    network_operations: Set[str]
    process_operations: Set[str]


class DozerAnalysisDemo:
    """Demo of Dozer's syscall analysis approach."""
    
    def __init__(self):
        # Simulated syscall patterns for Ansible modules (would be collected via strace)
        self.ansible_patterns = {
            'package': SyscallPattern(
                module_name='package',
                syscalls=['execve', 'open', 'write', 'close', 'rename', 'unlink'],
                file_operations={'/var/lib/dpkg/', '/usr/bin/', '/usr/lib/'},
                network_operations={'connect', 'recv', 'send'},  # for downloads
                process_operations={'fork', 'execve', 'wait4'}
            ),
            'service': SyscallPattern(
                module_name='service', 
                syscalls=['open', 'write', 'close', 'kill', 'execve'],
                file_operations={'/etc/systemd/', '/run/systemd/', '/proc/'},
                network_operations=set(),
                process_operations={'execve', 'kill', 'getpid'}
            ),
            'file': SyscallPattern(
                module_name='file',
                syscalls=['open', 'write', 'close', 'chmod', 'chown', 'mkdir'],
                file_operations={'target_path'},
                network_operations=set(),
                process_operations=set()
            ),
            'user': SyscallPattern(
                module_name='user',
                syscalls=['open', 'write', 'close', 'execve', 'mkdir'],
                file_operations={'/etc/passwd', '/etc/group', '/etc/shadow', '/home/'},
                network_operations=set(),
                process_operations={'execve'}  # useradd command
            )
        }
        
        # Simulated syscall patterns for NixOS modules (would be collected from Nix builds/activations)
        self.nix_patterns = {
            'environment.systemPackages': SyscallPattern(
                module_name='environment.systemPackages',
                syscalls=['open', 'write', 'close', 'symlink', 'readlink'],
                file_operations={'/nix/store/', '/run/current-system/sw/bin/'},
                network_operations={'connect', 'recv'},  # for downloads during build
                process_operations={'fork', 'execve'}
            ),
            'systemd.services': SyscallPattern(
                module_name='systemd.services',
                syscalls=['open', 'write', 'close', 'symlink'],
                file_operations={'/etc/systemd/system/', '/run/systemd/'},
                network_operations=set(),
                process_operations=set()
            ),
            'environment.etc': SyscallPattern(
                module_name='environment.etc',
                syscalls=['open', 'write', 'close', 'symlink', 'chmod'],
                file_operations={'/etc/', '/nix/store/'},
                network_operations=set(),
                process_operations=set()
            ),
            'users.users': SyscallPattern(
                module_name='users.users',
                syscalls=['open', 'write', 'close', 'mkdir', 'chmod'],
                file_operations={'/etc/passwd', '/etc/group', '/var/lib/nixos/'},
                network_operations=set(),
                process_operations=set()
            )
        }
    
    def analyze_ansible_module(self, module_name: str, params: Dict) -> SyscallPattern:
        """Simulate syscall analysis of Ansible module execution."""
        base_pattern = self.ansible_patterns.get(module_name)
        if not base_pattern:
            return None
        
        print(f"\n🔍 Analyzing Ansible module: {module_name}")
        print(f"   Parameters: {params}")
        print(f"   Expected syscalls: {', '.join(base_pattern.syscalls)}")
        print(f"   File operations: {', '.join(base_pattern.file_operations)}")
        
        return base_pattern
    
    def find_best_nix_match(self, ansible_pattern: SyscallPattern) -> str:
        """Find best matching NixOS module based on syscall similarity."""
        print(f"\n🎯 Finding Nix module match for: {ansible_pattern.module_name}")
        
        best_match = None
        best_score = 0
        
        for nix_name, nix_pattern in self.nix_patterns.items():
            # Calculate similarity score
            syscall_overlap = set(ansible_pattern.syscalls).intersection(set(nix_pattern.syscalls))
            file_ops_overlap = ansible_pattern.file_operations.intersection(nix_pattern.file_operations)
            
            # Weight different types of syscalls
            score = (
                len(syscall_overlap) * 0.4 +  # Basic syscall similarity
                len(file_ops_overlap) * 0.6    # File operation similarity (more important)
            )
            
            total_possible = len(set(ansible_pattern.syscalls).union(set(nix_pattern.syscalls)))
            normalized_score = score / max(total_possible, 1)
            
            print(f"   {nix_name}: score={normalized_score:.3f}")
            print(f"     Syscall overlap: {syscall_overlap}")
            print(f"     File ops overlap: {file_ops_overlap}")
            
            if normalized_score > best_score:
                best_score = normalized_score
                best_match = nix_name
        
        print(f"   🏆 Best match: {best_match} (score: {best_score:.3f})")
        return best_match
    
    def demonstrate_conversion(self, ansible_tasks: List[Dict]):
        """Demonstrate the full Dozer conversion process."""
        print("=" * 80)
        print("DOZER ANSIBLE → NIX CONVERSION ANALYSIS")
        print("=" * 80)
        
        conversions = []
        
        for i, task in enumerate(ansible_tasks, 1):
            print(f"\n{'─' * 60}")
            print(f"TASK {i}: {task.get('name', 'Unnamed task')}")
            print(f"{'─' * 60}")
            
            # Extract module and params
            module_name = None
            params = {}
            
            for key, value in task.items():
                if key not in ['name', 'become', 'when']:
                    module_name = key
                    params = value if isinstance(value, dict) else {'name': value}
                    break
            
            if not module_name:
                print("   ⚠️  Could not identify module")
                continue
            
            # Step 1: Analyze Ansible module syscalls
            ansible_pattern = self.analyze_ansible_module(module_name, params)
            if not ansible_pattern:
                print(f"   ⚠️  No pattern available for module: {module_name}")
                continue
            
            # Step 2: Find best Nix match
            nix_module = self.find_best_nix_match(ansible_pattern)
            
            # Step 3: Parameter mapping (simplified)
            nix_config = self.map_parameters(module_name, params, nix_module)
            
            conversions.append({
                'ansible_module': module_name,
                'ansible_params': params,
                'nix_module': nix_module,
                'nix_config': nix_config,
                'confidence': 'High' if nix_module else 'Low'
            })
        
        # Summary
        print(f"\n{'=' * 80}")
        print("CONVERSION SUMMARY")
        print(f"{'=' * 80}")
        
        for conv in conversions:
            print(f"✅ {conv['ansible_module']} → {conv['nix_module']} ({conv['confidence']} confidence)")
        
        return conversions
    
    def map_parameters(self, ansible_module: str, ansible_params: Dict, nix_module: str) -> Dict:
        """Map parameters from Ansible to Nix (simplified demo)."""
        print(f"\n🔗 Mapping parameters: {ansible_module} → {nix_module}")
        
        # This would use the parameter mapping discovered through syscall analysis
        # For demo, using predefined mappings
        mappings = {
            ('package', 'environment.systemPackages'): {
                'name': 'packages'
            },
            ('service', 'systemd.services'): {
                'name': 'service_name',
                'state': 'enable',
                'enabled': 'wantedBy'
            },
            ('user', 'users.users'): {
                'name': 'username',
                'groups': 'extraGroups',
                'shell': 'shell'
            },
            ('file', 'environment.etc'): {
                'path': 'target',
                'content': 'text',
                'mode': 'mode'
            }
        }
        
        mapping = mappings.get((ansible_module, nix_module), {})
        nix_config = {}
        
        for ansible_param, nix_param in mapping.items():
            if ansible_param in ansible_params:
                nix_config[nix_param] = ansible_params[ansible_param]
                print(f"   {ansible_param} → {nix_param}: {ansible_params[ansible_param]}")
        
        return nix_config


def main():
    """Run the demo with sample tasks."""
    demo = DozerAnalysisDemo()
    
    # Sample Ansible tasks to analyze
    sample_tasks = [
        {
            'name': 'Install nginx',
            'package': {
                'name': 'nginx',
                'state': 'present'
            }
        },
        {
            'name': 'Create web user',
            'user': {
                'name': 'webadmin',
                'groups': ['wheel'],
                'shell': '/bin/bash'
            }
        },
        {
            'name': 'Start nginx service',
            'service': {
                'name': 'nginx',
                'state': 'started',
                'enabled': True
            }
        },
        {
            'name': 'Deploy config file',
            'file': {
                'path': '/etc/nginx/nginx.conf',
                'content': 'server { listen 80; }',
                'mode': '0644'
            }
        }
    ]
    
    # Run the demonstration
    conversions = demo.demonstrate_conversion(sample_tasks)
    
    # Show what the actual conversion would produce
    print(f"\n{'=' * 80}")
    print("GENERATED NIX CONFIGURATION")
    print(f"{'=' * 80}")
    
    print("{ config, pkgs, ... }:")
    print("{")
    print("  # Generated using Dozer syscall analysis")
    print()
    
    for conv in conversions:
        nix_module = conv['nix_module']
        nix_config = conv['nix_config']
        
        if nix_module == 'environment.systemPackages':
            packages = nix_config.get('packages', conv['ansible_params'].get('name', ''))
            print(f"  environment.systemPackages = with pkgs; [ {packages} ];")
        elif nix_module == 'users.users':
            username = nix_config.get('username', conv['ansible_params'].get('name', ''))
            print(f"  users.users.{username} = {{")
            print("    isNormalUser = true;")
            if 'extraGroups' in nix_config:
                print(f"    extraGroups = {json.dumps(nix_config['extraGroups'])};")
            print("  };")
        elif nix_module == 'systemd.services':
            service = nix_config.get('service_name', conv['ansible_params'].get('name', ''))
            print(f"  systemd.services.{service}.enable = true;")
        elif nix_module == 'environment.etc':
            target = nix_config.get('target', conv['ansible_params'].get('path', ''))
            if target.startswith('/etc/'):
                target = target[5:]  # Remove /etc/
            print(f"  environment.etc.\"{target}\".text = \"{nix_config.get('text', '')}\";")
    
    print("}")


if __name__ == '__main__':
    main()