# syntax=docker/dockerfile:1

# ---- Stage 1: Build ast-index Rust binary ----
FROM rust:1-bookworm AS builder

WORKDIR /build

# Copy source
COPY Cargo.toml Cargo.lock build.rs ./
COPY src/ src/
COPY benches/ benches/
COPY tests/ tests/
COPY tree-sitter-bsl/ tree-sitter-bsl/

# Build release binary
RUN cargo build --release && \
    strip target/release/ast-index

# ---- Stage 2: MCP server runtime ----
FROM python:3.12-slim-bookworm

# Install git (needed for ast-index changed command and .gitignore support)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Copy ast-index binary from builder
COPY --from=builder /build/target/release/ast-index /usr/local/bin/ast-index
RUN chmod +x /usr/local/bin/ast-index

# Install MCP server
WORKDIR /app
COPY pyproject.toml ./
COPY mcp_server/ mcp_server/

RUN pip install --no-cache-dir .

# Environment
ENV AST_INDEX_BIN=/usr/local/bin/ast-index
ENV AST_INDEX_PROJECT_ROOT=/workspace

# The project to index is mounted at /workspace
VOLUME ["/workspace"]

# MCP server communicates over stdio
ENTRYPOINT ["python", "-m", "mcp_server.server"]
