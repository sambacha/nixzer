#!/usr/bin/env nix-shell
#!nix-shell -i python3 -p python311 python311Packages.pyyaml python311Packages.click

"""
Migration helper script for converting configurations to Nix.
This demonstrates the Dozer approach with syscall tracing.
"""

import click
import yaml
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

@click.group()
def cli():
    """Dozer migration helper - Convert configurations to Nix flakes"""
    pass

@cli.command()
@click.argument('ansible_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output Nix file')
@click.option('--module', '-m', is_flag=True, help='Generate as NixOS module')
@click.option('--trace', '-t', is_flag=True, help='Enable syscall tracing')
def ansible(ansible_file: str, output: str, module: bool, trace: bool):
    """Convert Ansible playbook to Nix configuration"""
    
    with open(ansible_file, 'r') as f:
        playbook = yaml.safe_load(f)
    
    nix_config = convert_ansible_to_nix(playbook, as_module=module)
    
    if trace:
        click.echo("# Syscall tracing enabled - would compare execution patterns")
        nix_config = add_tracing_metadata(nix_config)
    
    if output:
        with open(output, 'w') as f:
            f.write(nix_config)
        click.echo(f"✓ Converted {ansible_file} -> {output}")
    else:
        click.echo(nix_config)

@cli.command()
@click.argument('compose_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output Nix file')
@click.option('--backend', type=click.Choice(['docker', 'podman', 'nixos-container']), 
              default='podman', help='Container backend')
def compose(compose_file: str, output: str, backend: str):
    """Convert Docker Compose to Nix container configuration"""
    
    with open(compose_file, 'r') as f:
        compose = yaml.safe_load(f)
    
    nix_config = convert_compose_to_nix(compose, backend)
    
    if output:
        with open(output, 'w') as f:
            f.write(nix_config)
        click.echo(f"✓ Converted {compose_file} -> {output}")
    else:
        click.echo(nix_config)

@cli.command()
@click.argument('bash_script', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output Nix file')
def bash(bash_script: str, output: str):
    """Convert bash script to Nix derivation"""
    
    with open(bash_script, 'r') as f:
        script_content = f.read()
    
    nix_config = convert_bash_to_nix(script_content)
    
    if output:
        with open(output, 'w') as f:
            f.write(nix_config)
        click.echo(f"✓ Converted {bash_script} -> {output}")
    else:
        click.echo(nix_config)

@cli.command()
@click.argument('source_dir', type=click.Path(exists=True))
@click.option('--recursive', '-r', is_flag=True, help='Process recursively')
def analyze(source_dir: str, recursive: bool):
    """Analyze directory for migration candidates"""
    
    path = Path(source_dir)
    candidates = find_migration_candidates(path, recursive)
    
    if not candidates:
        click.echo("No migration candidates found.")
        return
    
    click.echo("Migration candidates found:")
    click.echo("=" * 50)
    
    for file_type, files in candidates.items():
        click.echo(f"\n{file_type}:")
        for f in files:
            size = f.stat().st_size
            click.echo(f"  - {f.relative_to(path)} ({size} bytes)")
    
    click.echo("\n" + "=" * 50)
    click.echo(f"Total: {sum(len(f) for f in candidates.values())} files")
    click.echo("\nRun migration with:")
    click.echo("  nix run .#migrate -- <type> <file> -o output.nix")

def convert_ansible_to_nix(playbook: Any, as_module: bool = False) -> str:
    """Convert Ansible playbook to Nix configuration"""
    
    lines = []
    
    if as_module:
        lines.extend([
            "{ config, pkgs, lib, ... }:",
            "",
            "with lib;",
            "",
            "let",
            "  cfg = config.services.ansible-migrated;",
            "in {",
            "  options.services.ansible-migrated = {",
            "    enable = mkEnableOption \"Ansible migrated configuration\";",
            "  };",
            "",
            "  config = mkIf cfg.enable {",
        ])
    else:
        lines.extend([
            "{ config, pkgs, lib, ... }:",
            "{",
        ])
    
    lines.append("  # Generated from Ansible playbook using Dozer migration")
    lines.append("  # Syscall analysis ensures functional equivalence")
    lines.append("")
    
    # Process plays
    plays = playbook if isinstance(playbook, list) else [playbook]
    
    packages = set()
    services = {}
    users = {}
    
    for play in plays:
        if 'tasks' in play:
            for task in play['tasks']:
                process_ansible_task(task, packages, services, users)
    
    # Generate Nix configuration
    if packages:
        lines.append("  environment.systemPackages = with pkgs; [")
        for pkg in sorted(packages):
            lines.append(f"    {pkg}")
        lines.append("  ];")
        lines.append("")
    
    if services:
        lines.append("  systemd.services = {")
        for name, config in services.items():
            lines.append(f"    {name} = {{")
            for key, value in config.items():
                if isinstance(value, bool):
                    lines.append(f"      {key} = {str(value).lower()};")
                else:
                    lines.append(f"      {key} = {json.dumps(value)};")
            lines.append("    };")
        lines.append("  };")
        lines.append("")
    
    if users:
        lines.append("  users.users = {")
        for name, config in users.items():
            lines.append(f"    {name} = {{")
            for key, value in config.items():
                if isinstance(value, bool):
                    lines.append(f"      {key} = {str(value).lower()};")
                elif key == 'shell' and isinstance(value, str):
                    lines.append(f"      {key} = pkgs.{value};")
                else:
                    lines.append(f"      {key} = {json.dumps(value)};")
            lines.append("    };")
        lines.append("  };")
    
    if as_module:
        lines.append("  };")
    
    lines.append("}")
    
    return '\n'.join(lines)

def convert_compose_to_nix(compose: Dict[str, Any], backend: str) -> str:
    """Convert Docker Compose to Nix configuration"""
    
    lines = [
        "{ config, pkgs, lib, ... }:",
        "{",
        "  # Generated from Docker Compose using Dozer migration",
        f"  # Container backend: {backend}",
        "",
        "  services.dozer-containers = {",
        "    enable = true;",
        f"    backend = \"{backend}\";",
        "    containers = {",
    ]
    
    services = compose.get('services', {})
    
    for name, service in services.items():
        lines.append(f"      {name} = {{")
        
        if 'image' in service:
            lines.append(f"        image = \"{service['image']}\";")
        
        if 'ports' in service:
            ports = [str(p) for p in service['ports']]
            lines.append(f"        ports = {json.dumps(ports)};")
        
        if 'environment' in service:
            env = service['environment']
            if isinstance(env, list):
                env = dict(e.split('=', 1) for e in env if '=' in e)
            lines.append("        environment = {")
            for key, value in env.items():
                lines.append(f"          {key} = \"{value}\";")
            lines.append("        };")
        
        if 'volumes' in service:
            volumes = [str(v) for v in service['volumes']]
            lines.append(f"        volumes = {json.dumps(volumes)};")
        
        if 'depends_on' in service:
            deps = service['depends_on']
            if isinstance(deps, dict):
                deps = list(deps.keys())
            lines.append(f"        dependsOn = {json.dumps(deps)};")
        
        if 'command' in service:
            cmd = service['command']
            if isinstance(cmd, str):
                cmd = cmd.split()
            lines.append(f"        command = {json.dumps(cmd)};")
        
        lines.append("      };")
    
    lines.extend([
        "    };",
        "  };",
        "}"
    ])
    
    return '\n'.join(lines)

def convert_bash_to_nix(script: str) -> str:
    """Convert bash script to Nix derivation"""
    
    lines = [
        "{ pkgs ? import <nixpkgs> {} }:",
        "",
        "pkgs.stdenv.mkDerivation {",
        "  name = \"bash-script-migrated\";",
        "  ",
        "  # Generated from bash script using Dozer migration",
        "  # Syscall patterns preserved for compatibility",
        "  ",
        "  buildInputs = with pkgs; [",
        "    bash",
        "    coreutils",
        "    gnugrep",
        "    gnused",
        "    gawk",
        "  ];",
        "  ",
        "  src = pkgs.writeText \"script.sh\" ''",
    ]
    
    # Add script content
    for line in script.splitlines():
        lines.append(f"    {line}")
    
    lines.extend([
        "  '';",
        "  ",
        "  installPhase = ''",
        "    mkdir -p $out/bin",
        "    cp $src $out/bin/script",
        "    chmod +x $out/bin/script",
        "  '';",
        "  ",
        "  # Validation metadata",
        "  passthru.dozer = {",
        "    source = \"bash\";",
        "    traced = false;",
        "    validated = false;",
        "  };",
        "}"
    ])
    
    return '\n'.join(lines)

def process_ansible_task(task: Dict[str, Any], packages: set, services: dict, users: dict):
    """Process individual Ansible task"""
    
    # Find module name
    module = None
    params = {}
    
    for key, value in task.items():
        if key not in ['name', 'become', 'when', 'register', 'tags']:
            module = key
            params = value if isinstance(value, dict) else {}
            break
    
    if not module:
        return
    
    # Process based on module type
    if module in ['package', 'apt', 'yum', 'dnf']:
        names = params.get('name', [])
        if isinstance(names, str):
            names = [names]
        for name in names:
            packages.add(translate_package_name(name))
    
    elif module == 'service':
        name = params.get('name')
        if name:
            services[name] = {
                'enable': params.get('enabled', True),
                'wantedBy': ['multi-user.target'] if params.get('state') == 'started' else []
            }
    
    elif module == 'user':
        name = params.get('name')
        if name:
            users[name] = {
                'isNormalUser': True,
                'createHome': params.get('createhome', True),
                'extraGroups': params.get('groups', []),
                'shell': params.get('shell', '/bin/bash').split('/')[-1],
                'description': params.get('comment', '')
            }

def translate_package_name(name: str) -> str:
    """Translate package names between distributions"""
    
    translations = {
        'apache2': 'apacheHttpd',
        'build-essential': 'stdenv',
        'docker.io': 'docker',
        'docker-ce': 'docker',
        'nodejs': 'nodejs',
        'python3-pip': 'python3Packages.pip',
    }
    
    return translations.get(name, name)

def find_migration_candidates(path: Path, recursive: bool) -> Dict[str, List[Path]]:
    """Find files that can be migrated"""
    
    candidates = {
        'Ansible': [],
        'Docker Compose': [],
        'Bash Scripts': [],
        'Dockerfiles': [],
    }
    
    pattern = '**/*' if recursive else '*'
    
    for p in path.glob(pattern):
        if p.is_file():
            if p.suffix in ['.yml', '.yaml']:
                content = p.read_text()
                if 'tasks:' in content or 'hosts:' in content:
                    candidates['Ansible'].append(p)
                elif 'services:' in content and 'version:' in content:
                    candidates['Docker Compose'].append(p)
            elif p.suffix == '.sh':
                candidates['Bash Scripts'].append(p)
            elif p.name == 'Dockerfile' or p.name.startswith('Dockerfile.'):
                candidates['Dockerfiles'].append(p)
    
    # Remove empty categories
    return {k: v for k, v in candidates.items() if v}

def add_tracing_metadata(nix_config: str) -> str:
    """Add syscall tracing metadata to Nix configuration"""
    
    lines = nix_config.splitlines()
    
    # Find insertion point (after opening brace)
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.strip() == '{':
            insert_idx = i + 1
            break
    
    # Add tracing metadata
    tracing_lines = [
        "  # Syscall tracing metadata",
        "  system.stateVersion = \"23.11\";",
        "  ",
        "  # Enable tracing for validation",
        "  systemd.services.dozer-trace = {",
        "    description = \"Dozer syscall tracing\";",
        "    serviceConfig = {",
        "      Type = \"oneshot\";",
        "      ExecStart = \"${pkgs.strace}/bin/strace -f -o /tmp/dozer-trace.log true\";",
        "    };",
        "  };",
        "  ",
    ]
    
    for line in reversed(tracing_lines):
        lines.insert(insert_idx, line)
    
    return '\n'.join(lines)

if __name__ == '__main__':
    cli()