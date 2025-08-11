"""
Pure unit tests for Dozer components.

Testing strategy:
1. Pure unit tests only - no external dependencies or I/O
2. Bottom-up approach - test leaf components first
3. Critical path prioritization - focus on syscall comparison and conversion logic
"""