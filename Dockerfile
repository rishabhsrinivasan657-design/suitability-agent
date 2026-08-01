# ─────────────────────────────────────────────────────────────────────────────
# ShieldWealth AI — Docker Image (Option A: Single Container / Streamlit)
# ─────────────────────────────────────────────────────────────────────────────
# Build:  docker build -t shieldwealth .
# Run:    docker run -p 8501:8501 --env-file .env shieldwealth
# Open:   http://localhost:8501
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# Install uv (fast dependency installer used by this project)
RUN pip install --no-cache-dir uv==0.8.13

# Set working directory inside the container
WORKDIR /app

# ── Copy dependency files first (so Docker caches this layer) ────────────────
COPY pyproject.toml README.md uv.lock* ./

# ── Install all Python dependencies (no venv, straight into system Python) ───
RUN uv sync --frozen --no-dev

# ── Copy application source code ─────────────────────────────────────────────
COPY app.py ./
COPY mcp_server.py ./
COPY app/ ./app/
COPY data/ ./data/

# ── Streamlit config: disable the "Deploy" button & browser auto-open ────────
RUN mkdir -p /app/.streamlit && printf "\
[server]\nheadless = true\nport = 8501\naddress = 0.0.0.0\n\
[browser]\ngatherUsageStats = false\n" > /app/.streamlit/config.toml

# ── Expose Streamlit's default port ──────────────────────────────────────────
EXPOSE 8501

# ── Health check so Docker/orchestrators know the app is alive ────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ── Launch the Streamlit app ─────────────────────────────────────────────────
CMD ["uv", "run", "streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]