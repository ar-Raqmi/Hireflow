FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hireflow ./hireflow

ENV GCP_PROJECT_ID="hireflow-506207"
ENV GEMINI_API_KEY="AQ.Ab8RN6IDD5fLBZraT1jOWahv0T5bClegGyPT3D3ll0ALRSy89Q"
ENV VERTEX_LOCATION="global"
ENV GEMINI_MODEL="gemini-3.5-flash"
ENV GEMINI_USE_VERTEX="true"
ENV GOOGLE_GENAI_USE_ENTERPRISE="True"

EXPOSE 8080

CMD ["uvicorn", "hireflow.api.app:app", "--host", "0.0.0.0", "--port", "8080"]