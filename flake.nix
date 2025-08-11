{
  description = "Dozer: Syscall-based migration of Ansible playbooks to Nix configurations";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    
    # Python dependency management
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication mkPoetryEnv;
        
        # Python environment with dependencies
        pythonEnv = pkgs.python311.withPackages (ps: with ps; [
          pyyaml
          click
          antlr4-python3-runtime
          docker
          jsonschema
          pytest
          pytest-cov
        ]);

        # ANTLR4 for grammar processing
        antlr4 = pkgs.antlr4_13;

        # Dozer application
        dozer = pkgs.stdenv.mkDerivation rec {
          pname = "dozer";
          version = "0.1.0";
          
          src = ./.;
          
          buildInputs = [ pythonEnv antlr4 ];
          
          nativeBuildInputs = [ pkgs.makeWrapper ];
          
          buildPhase = ''
            # Generate ANTLR parser from grammar files
            ${antlr4}/bin/antlr4 -Dlanguage=Python3 -visitor -o lib/antlr_generated/strace StraceLexer.g4 StraceParser.g4
          '';
          
          installPhase = ''
            mkdir -p $out/bin $out/lib
            cp -r lib $out/
            cp *.py $out/
            
            # Create wrapper scripts
            makeWrapper ${pythonEnv}/bin/python $out/bin/dozer \
              --add-flags "$out/dozer.py" \
              --prefix PYTHONPATH : "$out"
            
            makeWrapper ${pythonEnv}/bin/python $out/bin/ansible-to-nix \
              --add-flags "$out/ansible_to_nix.py" \
              --prefix PYTHONPATH : "$out"
            
            makeWrapper ${pythonEnv}/bin/python $out/bin/simple-converter \
              --add-flags "$out/simple_converter.py" \
              --prefix PYTHONPATH : "$out"
          '';
        };

        # Validation environment (replaces Docker-based validation)
        validationEnv = pkgs.stdenv.mkDerivation {
          name = "dozer-validation-env";
          
          buildInputs = with pkgs; [
            strace
            ltrace
            docker
            ansible
          ];
          
          shellHook = ''
            echo "Dozer validation environment loaded"
            echo "Available tools: strace, ltrace, docker, ansible"
          '';
        };

        # Function to convert Ansible playbook to Nix module
        convertPlaybook = playbook: pkgs.runCommand "convert-playbook" {
          buildInputs = [ dozer ];
        } ''
          dozer ansible-to-nix ${playbook} -o $out
        '';

        # Function to validate conversion
        validateConversion = { ansiblePlaybook, nixConfig }: pkgs.runCommand "validate-conversion" {
          buildInputs = [ dozer validationEnv ];
        } ''
          # Run validation
          python ${./lib/validation/ansible_nix_validator.py} \
            ${ansiblePlaybook} ${nixConfig} > $out
        '';

      in {
        # Packages
        packages = {
          default = dozer;
          inherit dozer validationEnv;
          
          # Example converters as packages
          convertWebserver = convertPlaybook ./examples/ansible_webserver.yml;
          convertDatabase = convertPlaybook ./examples/ansible_database.yml;
        };

        # Development shell
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonEnv
            antlr4
            strace
            ltrace
            docker
            ansible
            nixpkgs-fmt
            nil  # Nix language server
            
            # Additional dev tools
            git
            ripgrep
            fd
            jq
            yq-go
          ];
          
          shellHook = ''
            echo "Dozer Development Environment"
            echo "================================"
            echo "Available commands:"
            echo "  python dozer.py              - Run main Dozer tool"
            echo "  python ansible_to_nix.py     - Convert Ansible to Nix"
            echo "  python simple_converter.py   - Simple converter"
            echo "  antlr4                      - ANTLR grammar processor"
            echo "  strace                      - System call tracer"
            echo ""
            echo "Nix flake commands:"
            echo "  nix run .#dozer             - Run Dozer"
            echo "  nix build                   - Build Dozer package"
            echo "  nix develop                 - Enter dev shell"
            echo "  nix flake check            - Run tests"
            echo ""
            
            # Set up Python path
            export PYTHONPATH="$PWD:$PYTHONPATH"
            
            # Ensure ANTLR generated files are up to date
            if [ ! -d "lib/antlr_generated/strace" ] || [ StraceLexer.g4 -nt lib/antlr_generated/strace/StraceLexer.py ]; then
              echo "Regenerating ANTLR parser..."
              ${antlr4}/bin/antlr4 -Dlanguage=Python3 -visitor -o lib/antlr_generated/strace StraceLexer.g4 StraceParser.g4
            fi
          '';
        };

        # Apps (convenient command runners)
        apps = {
          default = flake-utils.lib.mkApp {
            drv = dozer;
            exePath = "/bin/dozer";
          };
          
          dozer = flake-utils.lib.mkApp {
            drv = dozer;
            exePath = "/bin/dozer";
          };
          
          convert = flake-utils.lib.mkApp {
            drv = dozer;
            exePath = "/bin/ansible-to-nix";
          };
          
          simple-convert = flake-utils.lib.mkApp {
            drv = dozer;
            exePath = "/bin/simple-converter";
          };
        };

        # Checks (tests and validation)
        checks = {
          # Unit tests - pure, isolated tests only
          unit-tests = pkgs.runCommand "unit-tests" {
            buildInputs = [ pythonEnv ];
            src = ./.;
          } ''
            mkdir -p $out
            cd $src
            
            # Run unit tests with priority ordering
            echo "Running unit tests (bottom-up, critical path first)..."
            ${pythonEnv}/bin/python tests/unit/run_tests.py \
              --verbose \
              --export $out/results.json \
              > $out/test.log 2>&1
            
            # Check results
            if grep -q "PASSED" $out/test.log; then
              echo "✓ Unit tests passed" > $out/status
              exit 0
            else
              echo "✗ Unit tests failed" > $out/status
              cat $out/test.log
              exit 1
            fi
          '';
          
          # Critical path tests only
          critical-tests = pkgs.runCommand "critical-tests" {
            buildInputs = [ pythonEnv ];
            src = ./.;
          } ''
            mkdir -p $out
            cd $src
            
            echo "Running critical path tests only..."
            ${pythonEnv}/bin/python tests/unit/run_tests.py \
              --critical-only \
              --failfast \
              > $out/test.log 2>&1
            
            # These must pass
            if grep -q "PASSED" $out/test.log; then
              echo "✓ Critical tests passed" > $out/status
              exit 0
            else
              echo "✗ Critical tests failed" > $out/status
              cat $out/test.log
              exit 1
            fi
          '';
          
          # Leaf component tests
          leaf-tests = pkgs.runCommand "leaf-tests" {
            buildInputs = [ pythonEnv ];
            src = ./.;
          } ''
            mkdir -p $out
            cd $src
            
            echo "Running leaf component tests..."
            ${pythonEnv}/bin/python -m unittest tests.unit.test_leaf_components -v \
              > $out/test.log 2>&1
            
            if [ $? -eq 0 ]; then
              echo "✓ Leaf tests passed" > $out/status
              exit 0
            else
              echo "✗ Leaf tests failed" > $out/status
              cat $out/test.log
              exit 1
            fi
          '';
          
          # Test with coverage (development only)
          test-coverage = pkgs.runCommand "test-coverage" {
            buildInputs = [ 
              (pythonEnv.withPackages (ps: with ps; [ coverage ]))
            ];
            src = ./.;
          } ''
            mkdir -p $out
            cd $src
            
            echo "Running tests with coverage..."
            ${pythonEnv}/bin/python tests/unit/run_tests.py \
              --coverage \
              --export $out/results.json \
              > $out/test.log 2>&1
            
            # Copy coverage report
            if [ -d htmlcov ]; then
              cp -r htmlcov $out/
              echo "Coverage report available at $out/htmlcov/index.html"
            fi
            
            cat $out/test.log
          '';
          
          # Validate example conversions
          validateWebserver = validateConversion {
            ansiblePlaybook = ./examples/ansible_webserver.yml;
            nixConfig = ./examples/webserver.nix;
          };
        };

        # NixOS modules for converted configurations
        nixosModules = {
          # Module generator from Ansible playbook
          fromAnsible = playbook: { config, pkgs, lib, ... }:
            let
              nixConfig = convertPlaybook playbook;
            in
            import nixConfig { inherit config pkgs lib; };
          
          # Example modules
          webserver = import ./examples/webserver.nix;
          database = import ./examples/database.nix;
        };

        # Overlays for extending nixpkgs
        overlays.default = final: prev: {
          dozer = dozer;
        };
      });

  # Additional flake-level NixOS configurations
  nixConfig = {
    # Enable flakes
    experimental-features = [ "nix-command" "flakes" ];
    
    # Binary cache settings
    substituters = [
      "https://cache.nixos.org"
      "https://nix-community.cachix.org"
    ];
    
    trusted-public-keys = [
      "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
      "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
    ];
  };
}