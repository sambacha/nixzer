"""Nix builder for constructing traces from Nix derivations."""

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from lib.strace.classes import Strace, Syscall
from lib.strace.parser import parse_string


@dataclass
class NixDerivation:
    """Represents a Nix derivation with its dependencies."""
    name: str
    path: Path
    inputs: List[str]
    outputs: Dict[str, str]
    builder: str
    args: List[str]
    env: Dict[str, str]


class NixBuilder:
    """Build and trace Nix derivations with syscall capture."""
    
    def __init__(self, sandbox: bool = True):
        self.sandbox = sandbox
        self.traced_derivations = {}
        
    def trace_derivation(self, drv_path: str) -> Strace:
        """
        Trace a Nix derivation build.
        
        Parameters
        ----------
        drv_path : str
            Path to .drv file
            
        Returns
        -------
        Strace
            Syscall trace of the build
        """
        # Parse derivation
        drv = self._parse_derivation(drv_path)
        
        # Check cache
        drv_hash = self._hash_derivation(drv)
        if drv_hash in self.traced_derivations:
            return self.traced_derivations[drv_hash]
        
        # Build with tracing
        trace = self._build_with_trace(drv)
        
        # Cache result
        self.traced_derivations[drv_hash] = trace
        
        return trace
    
    def _parse_derivation(self, drv_path: str) -> NixDerivation:
        """Parse a .drv file to extract derivation info."""
        cmd = f"nix show-derivation {drv_path}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to parse derivation: {result.stderr}")
        
        drv_json = json.loads(result.stdout)
        drv_key = list(drv_json.keys())[0]
        drv_data = drv_json[drv_key]
        
        return NixDerivation(
            name=drv_data.get('name', 'unknown'),
            path=Path(drv_path),
            inputs=drv_data.get('inputDrvs', []),
            outputs=drv_data.get('outputs', {}),
            builder=drv_data.get('builder', ''),
            args=drv_data.get('args', []),
            env=drv_data.get('env', {})
        )
    
    def _hash_derivation(self, drv: NixDerivation) -> str:
        """Generate hash for derivation to enable caching."""
        content = f"{drv.name}{drv.builder}{drv.args}{drv.env}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _build_with_trace(self, drv: NixDerivation) -> Strace:
        """Build derivation while tracing syscalls."""
        trace_file = tempfile.NamedTemporaryFile(delete=False, suffix='.strace')
        
        try:
            # Build command with strace
            build_cmd = [
                'strace',
                '-f',  # Follow forks
                '-e', 'trace=file,process,network',  # Trace relevant syscalls
                '-o', trace_file.name,
                'nix-build', str(drv.path), '--no-out-link'
            ]
            
            if self.sandbox:
                build_cmd.extend(['--option', 'sandbox', 'true'])
            
            # Run build
            result = subprocess.run(build_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise RuntimeError(f"Build failed: {result.stderr}")
            
            # Parse trace
            with open(trace_file.name, 'r') as f:
                trace_content = f.read()
            
            return parse_string(
                trace_content,
                system='nix',
                executable=drv.builder,
                arguments={'derivation': drv.name},
                collector='NixBuilder',
                metadata={
                    'outputs': drv.outputs,
                    'sandbox': self.sandbox
                }
            )
            
        finally:
            os.unlink(trace_file.name)
    
    def trace_nix_build(self, expr: str, **kwargs) -> Strace:
        """
        Trace building a Nix expression.
        
        Parameters
        ----------
        expr : str
            Nix expression to build
        **kwargs
            Additional nix-build arguments
            
        Returns
        -------
        Strace
            Syscall trace
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nix', delete=False) as f:
            f.write(expr)
            expr_file = f.name
        
        try:
            # First, get the derivation path
            cmd = f"nix-instantiate {expr_file}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to instantiate: {result.stderr}")
            
            drv_path = result.stdout.strip()
            
            # Now trace the build
            return self.trace_derivation(drv_path)
            
        finally:
            os.unlink(expr_file)
    
    def compare_build_runtime(self, 
                            build_trace: Strace, 
                            runtime_trace: Strace) -> Dict[str, Any]:
        """
        Compare build-time and runtime traces.
        
        Parameters
        ----------
        build_trace : Strace
            Build phase trace
        runtime_trace : Strace
            Runtime phase trace
            
        Returns
        -------
        Dict[str, Any]
            Comparison metrics
        """
        build_syscalls = self._extract_syscalls(build_trace)
        runtime_syscalls = self._extract_syscalls(runtime_trace)
        
        # Find overlapping syscalls
        common = build_syscalls.intersection(runtime_syscalls)
        build_only = build_syscalls - runtime_syscalls
        runtime_only = runtime_syscalls - build_syscalls
        
        return {
            'common_syscalls': len(common),
            'build_only': len(build_only),
            'runtime_only': len(runtime_only),
            'overlap_ratio': len(common) / (len(build_syscalls) + len(runtime_syscalls))
            if (build_syscalls or runtime_syscalls) else 0
        }
    
    def _extract_syscalls(self, trace: Strace) -> Set[str]:
        """Extract syscall names from trace."""
        syscalls = set()
        
        for line in trace.trace_lines:
            if hasattr(line, 'syscall') and hasattr(line.syscall, 'name'):
                syscalls.add(line.syscall.name)
                
        return syscalls