FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hireflow ./hireflow

ENV GCP_PROJECT_ID="hireflow-506204"
ENV GEMINI_API_KEY="AQ.Ab8RN6IhMzpu8QgRKLKgyGKYn8nJTazQ_Lnhf6KQNEvuts_Iag"
ENV VERTEX_LOCATION="asia-southeast1"
ENV GEMINI_MODEL="gemini-3.5-flash"
ENV GEMINI_USE_VERTEX="true"

EXPOSE 8080

CMD ["uvicorn", "hireflow.api.app:app", "--host", "0.0.0.0", "--port", "8080"]