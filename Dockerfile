FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements-ai.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend /app/backend
COPY data /app/data
ENV PYTHONPATH=/app/backend
ENV ADCRAFT_DATA_DIR=/app/data/runtime
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
