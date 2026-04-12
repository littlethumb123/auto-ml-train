FROM python:3.15-rc-alpine3.22

WORKDIR /app

# Unbuffered stdout/stderr so all logs appear immediately in Cloud Logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Log level can be overridden at model-upload time via serving_container_environment_variables
ENV LOG_LEVEL=INFO

# Model filename inside the AIP_STORAGE_URI directory
ENV MODEL_FILENAME=a538985_Models_model.bst

RUN pip install --no-cache-dir \
    fastapi==0.111.0 \
    uvicorn[standard]==0.29.0 \
    xgboost==2.0.3 \
    numpy==1.26.4 \
    pandas==2.2.2 \
    google-cloud-storage==2.16.0 \
    pydantic==2.7.1

COPY server.py /app/server.py

# Vertex AI batch prediction sets AIP_STORAGE_URI automatically
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
