FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hireflow ./hireflow

ENV GCP_PROJECT_ID=""
ENV GEMINI_API_KEY=""
ENV VERTEX_LOCATION="us-central1"
ENV GEMINI_MODEL="gemini-3.5-flash"
ENV GEMINI_USE_VERTEX="true"

EXPOSE 8080

CMD ["uvicorn", "hireflow.api.app:app", "--host", "0.0.0.0", "--port", "8080"]