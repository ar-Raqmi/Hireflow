# python:3.11-slim provably boots on Cloud Run (uvicorn :8080, /health 200).
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install chromium

COPY hireflow ./hireflow

ENV GCP_PROJECT_ID="hireflow-506207"
ENV GEMINI_USE_VERTEX="true"

EXPOSE 8080

CMD ["uvicorn", "hireflow.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
