FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Layer II (Playwright + headless Chromium) — the opt-in last-resort job source.
# Official build-your-own-image path (playwright.dev/python/docs/docker): this
# installs the apt system deps AND bundles Chromium, so a deploy can flip
# HIREFLOW_PLAYWRIGHT=1 at runtime without a new build. Soft-fail: if Chromium
# cannot be fetched, the image still builds and PlaywrightSource stays a
# documented no-op instead of bricking the deploy.
RUN python -m playwright install --with-deps chromium || echo "WARN: playwright chromium install failed - PlaywrightSource stays disabled"

COPY hireflow ./hireflow

ENV GCP_PROJECT_ID="hireflow-506207"
ENV VERTEX_LOCATION="global"
ENV GEMINI_MODEL="gemini-3.5-flash"
ENV GEMINI_USE_VERTEX="true"
ENV SEMANTIC_SEARCH="0"
ENV EMBEDDING_MODEL="gemini-embedding-001"
ENV HIREFLOW_PLAYWRIGHT="0"
ENV SANDBOX_ATS_FILE="sandbox_ats.json"

EXPOSE 8080

CMD ["uvicorn", "hireflow.api.app:app", "--host", "0.0.0.0", "--port", "8080"]