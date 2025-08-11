#!/usr/bin/env python3
"""Command-line interface for Ansible to Nix conversion."""

import argparse
import logging
import sys
from pathlib import Path

from lib.converters import AnsibleToNixConverter
from lib.validation.ansible_nix_validator import AnsibleNixValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Convert Ansible playbooks to NixOS configurations using Dozer approach'
    )
    
    parser.add_argument(
        'playbook',
        type=Path,
        help='Path to Ansible playbook YAML file'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=None,
        help='Output path for Nix configuration (default: stdout)'
    )
    
    parser.add_argument(
        '-v', '--validate',
        action='store_true',
        help='Validate the conversion by comparing system states'
    )
    
    parser.add_argument(
        '--trace-db',
        type=Path,
        default=None,
        help='Path to trace database for syscall matching'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check if playbook exists
    if not args.playbook.exists():
        logger.error(f"Playbook not found: {args.playbook}")
        sys.exit(1)
    
    # Initialize converter
    converter = AnsibleToNixConverter(trace_db_path=args.trace_db)
    
    try:
        # Convert playbook
        logger.info(f"Converting {args.playbook} to Nix...")
        nix_config = converter.convert_playbook(args.playbook)
        
        # Write output
        if args.output:
            with open(args.output, 'w') as f:
                f.write(nix_config)
            logger.info(f"Nix configuration written to {args.output}")
        else:
            print(nix_config)
        
        # Validate if requested
        if args.validate:
            if not args.output:
                # Write to temp file for validation
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.nix', delete=False) as f:
                    f.write(nix_config)
                    nix_path = Path(f.name)
            else:
                nix_path = args.output
            
            logger.info("Validating conversion...")
            validator = AnsibleNixValidator()
            result = validator.validate_conversion(args.playbook, nix_path)
            
            logger.info(f"Validation score: {result.score:.2%}")
            if result.success:
                logger.info("✓ Conversion validated successfully")
            else:
                logger.warning("⚠ Conversion has differences:")
                for diff in result.differences[:10]:  # Show first 10 differences
                    logger.warning(f"  - {diff}")
                if len(result.differences) > 10:
                    logger.warning(f"  ... and {len(result.differences) - 10} more differences")
            
            if result.warnings:
                logger.warning("Warnings:")
                for warning in result.warnings[:5]:
                    logger.warning(f"  - {warning}")
            
            if result.errors:
                logger.error("Errors:")
                for error in result.errors:
                    logger.error(f"  - {error}")
                sys.exit(1)
    
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()