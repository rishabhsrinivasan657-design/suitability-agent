# ShieldWealth advisor console (Streamlit, single container)
#   Build:  docker build -t shieldwealth .
#   Run:    docker run -p 8501:8501 --env-file .env shieldwealth
#   Open:   http://localhost:8501
# Railway and similar hosts inject $PORT; it defaults to 8501.

FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.8.13
WORKDIR /app

# Dependencies first so this layer is cached between code changes.
COPY pyproject.toml README.md uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY .streamlit/ ./.streamlit/
COPY app/ ./app/
COPY ui/ ./ui/
COPY assets/ ./assets/
COPY data/ ./data/
COPY mcp_server.py setup_rag.py streamlit_app.py ./

ENV PORT=8501
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/_stcore/health')"

CMD ["sh", "-c", "uv run --no-sync streamlit run streamlit_app.py --server.port=${PORT} --server.address=0.0.0.0"]
