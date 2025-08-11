# `nixer` Syscall-based Nix codemod

> Syscall-based migration of Ansible playbooks to Nix configurationss

## Core Components

### `NixTraceCollector` <a name="nix-trace"></a>
```python
# Captures build-time and runtime syscalls
nix_trace = trace_nix_build(derivation)
```

> [!WARNING]
> Experiemental

## References

Based on **Dozer**, by Horton et, al. 2022
> see paper in `docs/` dir

