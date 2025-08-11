# Multi-stage Dockerfile for Dozer
# Supports both development and production builds

# Stage 1: Nix builder
FROM nixos/nix:latest AS nix-builder

# Enable flakes
RUN echo "experimental-features = nix-command flakes" >> /etc/nix/nix.conf

# Copy source
WORKDIR /build
COPY . .

# Build the Dozer package
RUN nix build .#dozer --no-link -o result

# Stage 2: Python builder (alternative without Nix)
FROM python:3.11-slim AS python-builder

WORKDIR /build

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    antlr4 \
    strace \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY Pipfile Pipfile.lock ./
RUN pip install pipenv && pipenv install --system --deploy

# Copy source
COPY . .

# Generate ANTLR parsers
RUN antlr4 -Dlanguage=Python3 -visitor -o lib/antlr_generated/strace StraceLexer.g4 StraceParser.g4

# Stage 3: Runtime (from Nix build)
FROM debian:bookworm-slim AS runtime-nix

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    strace \
    && rm -rf /var/lib/apt/lists/*

# Copy built package from Nix
COPY --from=nix-builder /build/result /opt/dozer

# Create symlinks
RUN ln -s /opt/dozer/bin/dozer /usr/local/bin/dozer && \
    ln -s /opt/dozer/bin/ansible-to-nix /usr/local/bin/ansible-to-nix

# Stage 4: Runtime (from Python build)
FROM python:3.11-slim AS runtime-python

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    strace \
    && rm -rf /var/lib/apt/lists/*

# Copy Python environment
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-builder /build /app

WORKDIR /app

# Add to PATH
ENV PYTHONPATH=/app:$PYTHONPATH

# Create entrypoint script
RUN echo '#!/bin/bash\npython /app/dozer.py "$@"' > /usr/local/bin/dozer && \
    chmod +x /usr/local/bin/dozer && \
    echo '#!/bin/bash\npython /app/ansible_to_nix.py "$@"' > /usr/local/bin/ansible-to-nix && \
    chmod +x /usr/local/bin/ansible-to-nix

# Stage 5: Development environment
FROM python:3.11 AS development

# Install development tools
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    git \
    vim \
    curl \
    antlr4 \
    strace \
    ltrace \
    docker.io \
    ansible \
    && rm -rf /var/lib/apt/lists/*

# Install Python development packages
RUN pip install \
    pipenv \
    pytest \
    pytest-cov \
    hypothesis \
    black \
    flake8 \
    mypy \
    ipython \
    jupyter

WORKDIR /workspace

# Copy source
COPY . .

# Install dependencies
RUN pipenv install --dev --system

# Generate ANTLR parsers
RUN antlr4 -Dlanguage=Python3 -visitor -o lib/antlr_generated/strace StraceLexer.g4 StraceParser.g4

# Set up development environment
ENV PYTHONPATH=/workspace:$PYTHONPATH
ENV DOZER_DEV=1

# Default command for development
CMD ["/bin/bash"]

# Stage 6: Testing environment
FROM development AS testing

# Run tests by default
CMD ["python", "tests/unit/run_tests.py", "--coverage"]

# Stage 7: Final production image (choose Nix or Python)
FROM runtime-nix AS production

# Add non-root user
RUN useradd -m -s /bin/bash dozer
USER dozer

# Set working directory
WORKDIR /home/dozer

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD dozer --version || exit 1

# Labels
LABEL org.opencontainers.image.title="Dozer"
LABEL org.opencontainers.image.description="Syscall-based migration of Ansible playbooks to Nix configurations"
LABEL org.opencontainers.image.vendor="Dozer Project"
LABEL org.opencontainers.image.source="https://github.com/yourusername/dozer"
LABEL org.opencontainers.image.documentation="https://github.com/yourusername/dozer/blob/main/README.md"

# Default command
ENTRYPOINT ["dozer"]
CMD ["--help"]