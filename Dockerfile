# Playwright base image — Chromium + system deps pre-installed, so
# HIREFLOW_PLAYWRIGHT=1 sources (JobStreet, SPA career pages) work out of the
# box. Heavier than slim; deploy with --memory 2Gi (docs/GCP_SETUP.md §5).
# requirements.txt pins playwright>=1.44, matching the v1.44.0 browsers below.
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

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