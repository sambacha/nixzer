## Description
<!-- Provide a brief description of the changes in this PR -->

## Type of Change
<!-- Mark the relevant option with an "x" -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] 🎨 Code style update (formatting, renaming)
- [ ] ♻️ Refactoring (no functional changes)
- [ ] ⚡ Performance improvement
- [ ] ✅ Test addition or update
- [ ] 🔧 Build configuration change
- [ ] 🔀 Other (please describe):

## Related Issues
<!-- Link to related issues -->
Fixes #(issue_number)

## Changes Made
<!-- List the specific changes made in this PR -->

- 
- 
- 

## Testing
<!-- Describe the tests you ran to verify your changes -->

### Test Configuration
- **OS**: [e.g., Ubuntu 22.04, macOS 13]
- **Python Version**: [e.g., 3.11]
- **Nix Version**: [e.g., 2.18.1]

### Test Results
- [ ] All unit tests pass (`python tests/unit/run_tests.py`)
- [ ] Critical path tests pass (`python tests/unit/run_tests.py --critical-only`)
- [ ] Nix flake checks pass (`nix flake check`)
- [ ] Conversion examples work (`nix run .#convert -- examples/ansible_webserver.yml`)

### Coverage
<!-- If applicable, include coverage information -->
- Current coverage: X%
- Coverage change: +/-X%

## Performance Impact
<!-- If applicable, describe any performance implications -->

- [ ] No performance impact
- [ ] Performance improvement (describe below)
- [ ] Potential performance regression (justify below)

## Checklist
<!-- Mark completed items with an "x" -->

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Screenshots
<!-- If applicable, add screenshots to help explain your changes -->

## Additional Notes
<!-- Add any additional notes or context about the PR here -->