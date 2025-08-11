"""Ansible to Nix converter using Dozer's syscall-based approach."""

import json
import logging
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.strace.classes import Strace, MigrationResult, ParameterMapping
from lib.strace.collection.nix import NixTraceCollector, NixBuilder
from lib.strace.comparison.scoring import ScoringMethod, ScoringResult
from lib.strace.comparison.preprocessing import SinglePreprocessor, PairPreprocessor

logger = logging.getLogger(__name__)


@dataclass
class ModuleMapping:
    """Mapping between Ansible module and NixOS equivalent."""
    ansible_module: str
    nix_module: str
    param_mapping: Dict[str, str]
    confidence: float


class AnsibleToNixConverter:
    """Convert Ansible playbooks to NixOS configurations."""
    
    # Direct module mappings
    MODULE_MAPPINGS = {
        'package': {
            'nix': 'environment.systemPackages',
            'params': {'name': 'package', 'state': '_ignore'}
        },
        'apt': {
            'nix': 'environment.systemPackages',
            'params': {'name': 'package', 'state': '_ignore'}
        },
        'yum': {
            'nix': 'environment.systemPackages', 
            'params': {'name': 'package', 'state': '_ignore'}
        },
        'service': {
            'nix': 'systemd.services',
            'params': {'name': 'service', 'enabled': 'enable', 'state': 'wantedBy'}
        },
        'systemd': {
            'nix': 'systemd.services',
            'params': {'name': 'service', 'enabled': 'enable', 'state': 'wantedBy'}
        },
        'user': {
            'nix': 'users.users',
            'params': {
                'name': 'username',
                'groups': 'extraGroups',
                'shell': 'shell',
                'home': 'home',
                'createhome': 'createHome',
                'uid': 'uid',
                'comment': 'description'
            }
        },
        'group': {
            'nix': 'users.groups',
            'params': {'name': 'groupname', 'gid': 'gid'}
        },
        'file': {
            'nix': 'environment.etc',
            'params': {
                'path': 'target',
                'state': 'enable',
                'mode': 'mode',
                'owner': 'user',
                'group': 'group',
                'content': 'text'
            }
        },
        'copy': {
            'nix': 'environment.etc',
            'params': {
                'dest': 'target',
                'src': 'source',
                'content': 'text',
                'mode': 'mode',
                'owner': 'user',
                'group': 'group'
            }
        },
        'template': {
            'nix': 'environment.etc',
            'params': {
                'dest': 'target',
                'src': 'source',
                'mode': 'mode',
                'owner': 'user',
                'group': 'group'
            }
        },
        'lineinfile': {
            'nix': 'programs._generic.extraConfig',
            'params': {
                'path': 'file',
                'line': 'content',
                'regexp': 'pattern',
                'state': 'enable'
            }
        },
        'cron': {
            'nix': 'systemd.timers',
            'params': {
                'name': 'name',
                'minute': 'OnCalendar.minute',
                'hour': 'OnCalendar.hour',
                'job': 'ExecStart',
                'user': 'User'
            }
        },
        'git': {
            'nix': 'fetchGit',
            'params': {
                'repo': 'url',
                'dest': 'path',
                'version': 'rev'
            }
        }
    }
    
    def __init__(self, trace_db_path: Optional[Path] = None):
        self.nix_collector = NixTraceCollector()
        self.nix_builder = NixBuilder()
        self.scoring_method = ScoringMethod()
        self.trace_database = {}
        
        if trace_db_path and trace_db_path.exists():
            self._load_trace_database(trace_db_path)
    
    def _load_trace_database(self, path: Path):
        """Load pre-computed trace database."""
        with open(path, 'r') as f:
            self.trace_database = json.load(f)
    
    def convert_playbook(self, playbook_path: Path) -> str:
        """
        Convert an Ansible playbook to NixOS configuration.
        
        Parameters
        ----------
        playbook_path : Path
            Path to Ansible playbook YAML file
            
        Returns
        -------
        str
            Generated NixOS configuration
        """
        # Parse playbook
        with open(playbook_path, 'r') as f:
            playbook = yaml.safe_load(f)
        
        # Process each play
        nix_configs = []
        for play in playbook:
            if 'tasks' in play:
                for task in play['tasks']:
                    nix_config = self._convert_task(task)
                    if nix_config:
                        nix_configs.append(nix_config)
        
        # Combine into final configuration
        return self._generate_nix_module(nix_configs)
    
    def _convert_task(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert a single Ansible task to Nix configuration.
        
        Parameters
        ----------
        task : Dict[str, Any]
            Ansible task definition
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Nix configuration dict or None if conversion failed
        """
        # Extract module and parameters
        module_name = self._extract_module_name(task)
        params = self._extract_parameters(task)
        
        if not module_name:
            logger.warning(f"Could not determine module for task: {task.get('name', 'unnamed')}")
            return None
        
        # Try direct mapping first
        if module_name in self.MODULE_MAPPINGS:
            return self._direct_conversion(module_name, params)
        
        # Fall back to syscall-based matching
        return self._syscall_based_conversion(module_name, params)
    
    def _extract_module_name(self, task: Dict[str, Any]) -> Optional[str]:
        """Extract Ansible module name from task."""
        # Common Ansible task formats
        for key in task:
            if key not in ['name', 'register', 'when', 'with_items', 'loop', 'vars', 'tags']:
                return key
        return None
    
    def _extract_parameters(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Extract module parameters from task."""
        module = self._extract_module_name(task)
        if module and module in task:
            params = task[module]
            if isinstance(params, dict):
                return params
            elif isinstance(params, str):
                # Handle string format like "name=nginx state=present"
                params_dict = {}
                for item in params.split():
                    if '=' in item:
                        key, value = item.split('=', 1)
                        params_dict[key] = value
                return params_dict
        return {}
    
    def _direct_conversion(self, module: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Direct conversion using known module mappings.
        
        Parameters
        ----------
        module : str
            Ansible module name
        params : Dict[str, Any]
            Module parameters
            
        Returns
        -------
        Dict[str, Any]
            Nix configuration
        """
        mapping = self.MODULE_MAPPINGS[module]
        nix_module = mapping['nix']
        param_mapping = mapping['params']
        
        nix_config = {'module': nix_module, 'config': {}}
        
        # Map parameters
        for ansible_param, nix_param in param_mapping.items():
            if ansible_param in params and nix_param != '_ignore':
                value = params[ansible_param]
                
                # Handle special conversions
                if module in ['package', 'apt', 'yum'] and ansible_param == 'name':
                    # Package names might need translation
                    value = self._translate_package_name(value)
                elif module == 'service' and ansible_param == 'state':
                    # Convert service state to systemd targets
                    value = ['multi-user.target'] if value == 'started' else []
                    
                nix_config['config'][nix_param] = value
        
        return nix_config
    
    def _syscall_based_conversion(self, module: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert using syscall trace matching.
        
        Parameters
        ----------
        module : str
            Ansible module name
        params : Dict[str, Any]
            Module parameters
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Nix configuration or None
        """
        # Trace Ansible module execution
        ansible_trace = self._trace_ansible_module(module, params)
        
        if not ansible_trace:
            return None
        
        # Find best matching Nix module
        best_match = self._find_best_nix_match(ansible_trace)
        
        if best_match and best_match.score > 0.6:  # Confidence threshold
            return self._generate_from_match(best_match, params)
        
        return None
    
    def _trace_ansible_module(self, module: str, params: Dict[str, Any]) -> Optional[Strace]:
        """Trace Ansible module execution."""
        # Check cache first
        cache_key = f"{module}:{json.dumps(params, sort_keys=True)}"
        if cache_key in self.trace_database:
            return self.trace_database[cache_key]
        
        # Create minimal playbook for tracing
        playbook = [{
            'hosts': 'localhost',
            'tasks': [{
                'name': f'Trace {module}',
                module: params
            }]
        }]
        
        # TODO: Implement actual tracing
        # This would run the playbook in a container with strace
        logger.info(f"Would trace Ansible module: {module} with params: {params}")
        
        return None
    
    def _find_best_nix_match(self, ansible_trace: Strace) -> Optional[ScoringResult]:
        """Find best matching Nix module trace."""
        best_score = 0
        best_result = None
        
        # Compare against known Nix module traces
        for nix_module, nix_trace in self.trace_database.items():
            if nix_module.startswith('nix:'):
                result = self.scoring_method(ansible_trace, nix_trace, set())
                if result.score > best_score:
                    best_score = result.score
                    best_result = result
        
        return best_result
    
    def _generate_from_match(self, match: ScoringResult, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Nix config from syscall match."""
        # Extract Nix module from match
        nix_module = match.s2.metadata.get('module', 'unknown')
        
        # Map parameters using match mapping
        nix_params = {}
        for (ansible_key, nix_key) in match.mapping:
            if ansible_key in params:
                nix_params[nix_key] = params[ansible_key]
        
        return {
            'module': nix_module,
            'config': nix_params,
            'confidence': match.score
        }
    
    def _translate_package_name(self, name: str) -> str:
        """Translate package name from Ansible to Nix."""
        # Common package name mappings
        translations = {
            'apache2': 'apacheHttpd',
            'build-essential': 'stdenv',
            'libssl-dev': 'openssl.dev',
            'python-pip': 'python3Packages.pip',
            'nodejs': 'nodejs',
            'docker.io': 'docker',
            'docker-ce': 'docker'
        }
        
        return translations.get(name, name)
    
    def _generate_nix_module(self, configs: List[Dict[str, Any]]) -> str:
        """
        Generate final NixOS module from configurations.
        
        Parameters
        ----------
        configs : List[Dict[str, Any]]
            List of Nix configurations
            
        Returns
        -------
        str
            Complete NixOS module
        """
        # Group configs by module path
        grouped = {}
        for config in configs:
            module_path = config['module']
            if module_path not in grouped:
                grouped[module_path] = []
            grouped[module_path].append(config['config'])
        
        # Generate Nix expression
        nix_lines = [
            "{ config, pkgs, lib, ... }:",
            "{",
            "  # Generated from Ansible playbook by Dozer",
            ""
        ]
        
        for module_path, configs in grouped.items():
            parts = module_path.split('.')
            
            # Handle different module types
            if module_path == 'environment.systemPackages':
                packages = []
                for cfg in configs:
                    if 'package' in cfg:
                        packages.append(cfg['package'])
                
                nix_lines.append(f"  environment.systemPackages = with pkgs; [")
                for pkg in packages:
                    nix_lines.append(f"    {pkg}")
                nix_lines.append("  ];")
                
            elif module_path.startswith('users.users'):
                for cfg in configs:
                    if 'username' in cfg:
                        user = cfg['username']
                        nix_lines.append(f"  users.users.{user} = {{")
                        nix_lines.append(f"    isNormalUser = true;")
                        
                        if 'extraGroups' in cfg:
                            groups = json.dumps(cfg['extraGroups'])
                            nix_lines.append(f"    extraGroups = {groups};")
                        
                        if 'shell' in cfg:
                            nix_lines.append(f"    shell = pkgs.{cfg['shell']};")
                        
                        nix_lines.append("  };")
                        
            elif module_path.startswith('systemd.services'):
                for cfg in configs:
                    if 'service' in cfg:
                        service = cfg['service']
                        nix_lines.append(f"  systemd.services.{service} = {{")
                        
                        if cfg.get('enable'):
                            nix_lines.append(f"    enable = true;")
                        
                        if 'wantedBy' in cfg and cfg['wantedBy']:
                            nix_lines.append(f"    wantedBy = {json.dumps(cfg['wantedBy'])};")
                        
                        nix_lines.append("  };")
            
            nix_lines.append("")
        
        nix_lines.append("}")
        
        return '\n'.join(nix_lines)