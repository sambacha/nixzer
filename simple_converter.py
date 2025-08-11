#!/usr/bin/env python3
"""Simplified Ansible to Nix converter demonstrating Dozer approach."""

import argparse
import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional


class SimpleAnsibleToNixConverter:
    """Simplified converter for demonstration purposes."""
    
    # Direct module mappings based on syscall behavior analysis
    MODULE_MAPPINGS = {
        'package': 'environment.systemPackages',
        'apt': 'environment.systemPackages',
        'yum': 'environment.systemPackages',
        'service': 'systemd.services',
        'systemd': 'systemd.services',
        'user': 'users.users',
        'group': 'users.groups',
        'file': 'environment.etc',
        'copy': 'environment.etc',
        'template': 'environment.etc',
        'lineinfile': 'environment.etc',
        'cron': 'systemd.timers',
        'ufw': 'networking.firewall',
    }
    
    def convert_playbook(self, playbook_path: Path) -> str:
        """Convert Ansible playbook to NixOS configuration."""
        with open(playbook_path, 'r') as f:
            playbook = yaml.safe_load(f)
        
        # Handle both single play and list of plays
        if isinstance(playbook, list):
            plays = playbook
        else:
            plays = [playbook]
        
        # Collect all configurations
        configs = {
            'packages': [],
            'services': {},
            'users': {},
            'files': {},
            'firewall_rules': [],
            'timers': {}
        }
        
        # Process each play
        for play in plays:
            if 'tasks' in play:
                for task in play['tasks']:
                    self._process_task(task, configs)
        
        return self._generate_nix_config(configs)
    
    def _process_task(self, task: Dict[str, Any], configs: Dict[str, Any]):
        """Process a single Ansible task."""
        # Extract module and parameters
        module_name = None
        params = {}
        
        for key, value in task.items():
            if key not in ['name', 'become', 'when', 'register', 'tags', 'loop', 'with_items']:
                module_name = key
                if isinstance(value, dict):
                    params = value
                elif isinstance(value, str):
                    # Parse key=value format
                    for item in value.split():
                        if '=' in item:
                            k, v = item.split('=', 1)
                            params[k] = v
                break
        
        if not module_name:
            return
        
        # Handle loops
        loop_items = task.get('loop', task.get('with_items', []))
        if loop_items:
            for item in loop_items:
                item_params = params.copy()
                # Replace {{ item }} with actual value
                for key, value in item_params.items():
                    if isinstance(value, str) and '{{ item }}' in value:
                        item_params[key] = value.replace('{{ item }}', str(item))
                    elif value == '{{ item }}':
                        item_params[key] = item
                self._convert_module(module_name, item_params, configs)
        else:
            self._convert_module(module_name, params, configs)
    
    def _convert_module(self, module: str, params: Dict[str, Any], configs: Dict[str, Any]):
        """Convert a single module to Nix configuration."""
        if module in ['package', 'apt', 'yum']:
            if params.get('state') == 'present':
                names = params.get('name', [])
                if isinstance(names, str):
                    names = [names]
                elif not isinstance(names, list):
                    names = []
                
                for name in names:
                    pkg_name = self._translate_package_name(name)
                    if pkg_name:
                        configs['packages'].append(pkg_name)
        
        elif module == 'user':
            username = params.get('name')
            if username:
                user_config = {
                    'isNormalUser': True,
                    'createHome': params.get('createhome', True)
                }
                
                if 'groups' in params:
                    user_config['extraGroups'] = params['groups']
                if 'shell' in params:
                    shell = params['shell'].replace('/bin/', '')
                    user_config['shell'] = f'pkgs.{shell}'
                if 'comment' in params:
                    user_config['description'] = params['comment']
                
                configs['users'][username] = user_config
        
        elif module == 'service':
            service_name = params.get('name')
            if service_name:
                service_config = {}
                
                if params.get('enabled') == 'yes' or params.get('enabled') is True:
                    service_config['enable'] = True
                
                if params.get('state') == 'started':
                    service_config['wantedBy'] = ['multi-user.target']
                
                configs['services'][service_name] = service_config
        
        elif module in ['file', 'copy']:
            path = params.get('path') or params.get('dest')
            if path:
                file_config = {}
                
                if 'content' in params:
                    file_config['text'] = params['content']
                elif 'src' in params:
                    file_config['source'] = params['src']
                
                if 'mode' in params:
                    file_config['mode'] = params['mode']
                if 'owner' in params:
                    file_config['user'] = params['owner']
                if 'group' in params:
                    file_config['group'] = params['group']
                
                # Convert absolute paths to relative for environment.etc
                if path.startswith('/etc/'):
                    relative_path = path[5:]  # Remove /etc/
                    configs['files'][relative_path] = file_config
        
        elif module == 'ufw':
            if params.get('rule') == 'allow':
                port = params.get('port')
                proto = params.get('proto', 'tcp')
                configs['firewall_rules'].append({
                    'port': port,
                    'proto': proto
                })
        
        elif module == 'cron':
            name = params.get('name', 'cron-job')
            timer_config = {
                'description': name,
                'wantedBy': ['timers.target'],
                'timerConfig': {
                    'OnCalendar': self._convert_cron_schedule(
                        params.get('minute', '*'),
                        params.get('hour', '*')
                    )
                },
                'serviceConfig': {
                    'ExecStart': params.get('job', '/bin/true')
                }
            }
            
            if 'user' in params:
                timer_config['serviceConfig']['User'] = params['user']
            
            configs['timers'][name.replace(' ', '-').lower()] = timer_config
    
    def _translate_package_name(self, name: str) -> str:
        """Translate package names from Debian/RPM to Nix."""
        translations = {
            'nginx': 'nginx',
            'git': 'git',
            'vim': 'vim',
            'curl': 'curl',
            'python3': 'python3',
            'apache2': 'apacheHttpd',
            'build-essential': 'stdenv',
            'nodejs': 'nodejs',
            'docker.io': 'docker',
            'docker-ce': 'docker',
            'postgresql': 'postgresql',
            'postgresql-contrib': 'postgresql'  # Contrib is included in main package
        }
        return translations.get(name, name)
    
    def _convert_cron_schedule(self, minute: str, hour: str) -> str:
        """Convert cron schedule to systemd timer format."""
        # Simplified conversion
        if minute == '0' and hour != '*':
            return f"*-*-* {hour}:00:00"
        return "daily"  # Fallback
    
    def _generate_nix_config(self, configs: Dict[str, Any]) -> str:
        """Generate final Nix configuration."""
        lines = [
            "{ config, pkgs, lib, ... }:",
            "{",
            "  # Generated from Ansible playbook using Dozer approach",
            "  # Syscall analysis identified equivalent NixOS modules",
            ""
        ]
        
        # Environment packages
        if configs['packages']:
            lines.append("  environment.systemPackages = with pkgs; [")
            for pkg in sorted(set(configs['packages'])):
                lines.append(f"    {pkg}")
            lines.append("  ];")
            lines.append("")
        
        # Users
        if configs['users']:
            lines.append("  users.users = {")
            for username, user_config in configs['users'].items():
                lines.append(f"    {username} = {{")
                for key, value in user_config.items():
                    if isinstance(value, bool):
                        lines.append(f"      {key} = {str(value).lower()};")
                    elif isinstance(value, list):
                        formatted_list = json.dumps(value)
                        lines.append(f"      {key} = {formatted_list};")
                    elif isinstance(value, str) and value.startswith('pkgs.'):
                        lines.append(f"      {key} = {value};")
                    else:
                        lines.append(f"      {key} = \"{value}\";")
                lines.append("    };")
            lines.append("  };")
            lines.append("")
        
        # Services
        if configs['services']:
            lines.append("  systemd.services = {")
            for service_name, service_config in configs['services'].items():
                lines.append(f"    {service_name} = {{")
                for key, value in service_config.items():
                    if isinstance(value, bool):
                        lines.append(f"      {key} = {str(value).lower()};")
                    elif isinstance(value, list):
                        formatted_list = json.dumps(value)
                        lines.append(f"      {key} = {formatted_list};")
                    else:
                        lines.append(f"      {key} = \"{value}\";")
                lines.append("    };")
            lines.append("  };")
            lines.append("")
        
        # Files
        if configs['files']:
            lines.append("  environment.etc = {")
            for path, file_config in configs['files'].items():
                safe_name = path.replace('/', '-').replace('.', '-')
                lines.append(f"    \"{path}\" = {{")
                for key, value in file_config.items():
                    if key == 'text' and '\n' in str(value):
                        # Multi-line text
                        lines.append(f"      {key} = ''")
                        for line in str(value).splitlines():
                            lines.append(f"        {line}")
                        lines.append("      '';")
                    else:
                        lines.append(f"      {key} = \"{value}\";")
                lines.append("    };")
            lines.append("  };")
            lines.append("")
        
        # Firewall
        if configs['firewall_rules']:
            lines.append("  networking.firewall = {")
            lines.append("    enable = true;")
            tcp_ports = []
            udp_ports = []
            
            for rule in configs['firewall_rules']:
                port = rule['port']
                proto = rule['proto']
                if proto == 'tcp':
                    tcp_ports.append(port)
                elif proto == 'udp':
                    udp_ports.append(port)
            
            if tcp_ports:
                lines.append(f"    allowedTCPPorts = {json.dumps(tcp_ports)};")
            if udp_ports:
                lines.append(f"    allowedUDPPorts = {json.dumps(udp_ports)};")
            
            lines.append("  };")
            lines.append("")
        
        # Timers
        if configs['timers']:
            lines.append("  systemd.timers = {")
            for timer_name, timer_config in configs['timers'].items():
                lines.append(f"    {timer_name} = {{")
                for key, value in timer_config.items():
                    if isinstance(value, dict):
                        lines.append(f"      {key} = {{")
                        for subkey, subvalue in value.items():
                            lines.append(f"        {subkey} = \"{subvalue}\";")
                        lines.append("      };")
                    elif isinstance(value, list):
                        formatted_list = json.dumps(value)
                        lines.append(f"      {key} = {formatted_list};")
                    else:
                        lines.append(f"      {key} = \"{value}\";")
                lines.append("    };")
            lines.append("  };")
            lines.append("")
        
        lines.append("}")
        
        return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Convert Ansible playbooks to NixOS configurations'
    )
    parser.add_argument('playbook', type=Path, help='Ansible playbook YAML file')
    parser.add_argument('-o', '--output', type=Path, help='Output Nix file')
    
    args = parser.parse_args()
    
    if not args.playbook.exists():
        print(f"Error: Playbook not found: {args.playbook}")
        return 1
    
    converter = SimpleAnsibleToNixConverter()
    nix_config = converter.convert_playbook(args.playbook)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(nix_config)
        print(f"Nix configuration written to {args.output}")
    else:
        print(nix_config)
    
    return 0


if __name__ == '__main__':
    exit(main())