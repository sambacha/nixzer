{ pkgs, lib }:

rec {
  # Capture system metadata (replaces get_metadata function from run_validation.sh)
  captureMetadata = pkgs.writeShellScriptBin "capture-metadata" ''
    set -e
    
    OUTPUT_DIR="$1"
    if [ -z "$OUTPUT_DIR" ]; then
      echo "Error: Output directory required"
      exit 1
    fi
    
    mkdir -p "$OUTPUT_DIR"
    
    # Capture running processes
    ${pkgs.procps}/bin/ps -e -o args | tail -n +2 > "$OUTPUT_DIR/proc"
    
    # Capture current working directory
    pwd > "$OUTPUT_DIR/cwd"
    
    # Capture environment variables
    env > "$OUTPUT_DIR/env"
    
    # Additional Nix-specific metadata
    echo "NIX_PATH=$NIX_PATH" > "$OUTPUT_DIR/nix_path"
    echo "NIX_STORE=$NIX_STORE" > "$OUTPUT_DIR/nix_store"
    
    # Capture installed packages (if in NixOS)
    if command -v nix-store &> /dev/null; then
      nix-store -q --requisites /run/current-system 2>/dev/null > "$OUTPUT_DIR/nix_packages" || true
    fi
  '';

  # Run command with validation (replaces run_validation.sh)
  runWithValidation = pkgs.writeShellScriptBin "run-with-validation" ''
    set -e
    
    VALIDATION_DIR="''${VALIDATION_DIR:-/tmp/validation}"
    PRE_DIR="$VALIDATION_DIR/pre"
    POST_DIR="$VALIDATION_DIR/post"
    
    # Check if command provided
    if [ $# -eq 0 ]; then
      echo "Error: Command required"
      exit 1
    fi
    
    # Create validation directories
    mkdir -p "$PRE_DIR" "$POST_DIR"
    
    # Capture pre-execution state
    echo "Capturing pre-execution state..."
    ${captureMetadata}/bin/capture-metadata "$PRE_DIR"
    
    # Execute the command
    echo "Executing: $@"
    set +e
    eval "$@"
    EXIT_CODE=$?
    set -e
    
    # Capture post-execution state
    echo "Capturing post-execution state..."
    ${captureMetadata}/bin/capture-metadata "$POST_DIR"
    
    # Generate diff report
    echo "Generating state diff..."
    ${pkgs.diffutils}/bin/diff -u "$PRE_DIR" "$POST_DIR" > "$VALIDATION_DIR/diff.txt" 2>/dev/null || true
    
    echo "Validation complete. Results in: $VALIDATION_DIR"
    exit $EXIT_CODE
  '';

  # Trace system calls for a command
  traceCommand = pkgs.writeShellScriptBin "trace-command" ''
    set -e
    
    OUTPUT_FILE="''${1:-trace.log}"
    shift
    
    if [ $# -eq 0 ]; then
      echo "Usage: trace-command <output-file> <command> [args...]"
      exit 1
    fi
    
    echo "Tracing: $@"
    echo "Output: $OUTPUT_FILE"
    
    ${pkgs.strace}/bin/strace -f -e trace=all -o "$OUTPUT_FILE" "$@"
    
    echo "Trace complete: $OUTPUT_FILE"
  '';

  # Compare Ansible and Nix executions
  compareExecutions = pkgs.writeShellScriptBin "compare-executions" ''
    set -e
    
    ANSIBLE_PLAYBOOK="$1"
    NIX_CONFIG="$2"
    
    if [ -z "$ANSIBLE_PLAYBOOK" ] || [ -z "$NIX_CONFIG" ]; then
      echo "Usage: compare-executions <ansible-playbook> <nix-config>"
      exit 1
    fi
    
    WORK_DIR="$(mktemp -d)"
    echo "Working directory: $WORK_DIR"
    
    # Run Ansible in container and capture trace
    echo "Running Ansible playbook..."
    ANSIBLE_DIR="$WORK_DIR/ansible"
    mkdir -p "$ANSIBLE_DIR"
    
    ${pkgs.docker}/bin/docker run --rm \
      -v "$ANSIBLE_PLAYBOOK:/playbook.yml:ro" \
      -v "$ANSIBLE_DIR:/output" \
      ansible/ansible-runner \
      sh -c "${pkgs.strace}/bin/strace -f -o /output/trace.log ansible-playbook /playbook.yml"
    
    # Build Nix configuration and capture trace  
    echo "Building Nix configuration..."
    NIX_DIR="$WORK_DIR/nix"
    mkdir -p "$NIX_DIR"
    
    ${pkgs.strace}/bin/strace -f -o "$NIX_DIR/trace.log" \
      nix-build "$NIX_CONFIG" --no-out-link
    
    # Compare traces
    echo "Comparing system call traces..."
    ${pkgs.python3}/bin/python ${./compare_traces.py} \
      "$ANSIBLE_DIR/trace.log" \
      "$NIX_DIR/trace.log" \
      > "$WORK_DIR/comparison.txt"
    
    cat "$WORK_DIR/comparison.txt"
    
    echo "Comparison complete. Full results in: $WORK_DIR"
  '';

  # Nix-native validation derivation
  validationDerivation = { name, command }:
    pkgs.runCommand "${name}-validation" {
      buildInputs = [ captureMetadata runWithValidation ];
    } ''
      mkdir -p $out
      
      # Run command with validation
      VALIDATION_DIR=$out ${runWithValidation}/bin/run-with-validation "${command}"
      
      # Generate report
      cat > $out/report.json << EOF
      {
        "name": "${name}",
        "command": "${command}",
        "timestamp": "$(date -Iseconds)",
        "pre_state": "$(cat $out/pre/env | wc -l) env vars",
        "post_state": "$(cat $out/post/env | wc -l) env vars",
        "processes_before": "$(cat $out/pre/proc | wc -l)",
        "processes_after": "$(cat $out/post/proc | wc -l)"
      }
      EOF
      
      echo "Validation report saved to: $out/report.json"
    '';

  # Helper to create traced derivation
  tracedDerivation = { name, buildCommand }:
    pkgs.runCommand "${name}-traced" {
      buildInputs = [ traceCommand ];
    } ''
      mkdir -p $out
      
      # Run build with strace
      ${traceCommand}/bin/trace-command $out/trace.log sh -c "${buildCommand}"
      
      # Parse trace for summary
      echo "=== Syscall Summary ===" > $out/summary.txt
      ${pkgs.gawk}/bin/awk -F'(' '{print $1}' $out/trace.log | \
        sort | uniq -c | sort -rn | head -20 >> $out/summary.txt
      
      echo "Trace saved to: $out/trace.log"
      echo "Summary saved to: $out/summary.txt"
    '';

  # Ansible to Nix validation test
  ansibleNixTest = { ansiblePlaybook, nixModule }:
    pkgs.runCommand "ansible-nix-test" {
      buildInputs = [ 
        pkgs.ansible 
        pkgs.docker
        compareExecutions
      ];
    } ''
      mkdir -p $out
      
      echo "Testing Ansible to Nix conversion..."
      echo "Ansible: ${ansiblePlaybook}"
      echo "Nix: ${nixModule}"
      
      # Run comparison
      ${compareExecutions}/bin/compare-executions \
        "${ansiblePlaybook}" \
        "${nixModule}" \
        > $out/results.txt 2>&1
      
      # Check if conversion was successful
      if grep -q "PASS" $out/results.txt; then
        echo "✓ Conversion test passed" > $out/status
        exit 0
      else
        echo "✗ Conversion test failed" > $out/status
        exit 1
      fi
    '';
}