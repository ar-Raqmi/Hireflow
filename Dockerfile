# python:3.11-slim provably boots on Cloud Run (uvicorn :8080, /health 200).
# Chromium (Playwright) is installed HERE on the proven base instead of using
# the heavy mcr playwright image (which failed to boot inside Cloud Run).
# Chromium is fetched at build time; deploy needs --memory 2Gi+.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcb1 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install chromium

COPY hireflow ./hireflow

ENV GCP_PROJECT_ID="hireflow-506207"
ENV VERTEX_LOCATION="global"
ENV GEMINI_MODEL="gemini-3.5-flash"
ENV GEMINI_USE_VERTEX="true"
ENV SEMANTIC_SEARCH="1"
ENV EMBEDDING_MODEL="gemini-embedding-001"
ENV HIREFLOW_PLAYWRIGHT="1"
ENV JOBSTREET_ENABLED="true"
ENV USE_UNVERIFIED_SOURCES="1"
ENV SANDBOX_ATS_FILE="sandbox_ats.json"

EXPOSE 8080

CMD ["uvicorn", "hireflow.api.app:app", "--host", "0.0.0.0", "--port", "8080"]