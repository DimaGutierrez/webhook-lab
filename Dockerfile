FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY webhook_lab ./webhook_lab
RUN pip install --no-cache-dir -r requirements.lock \
    && pip install --no-cache-dir --no-deps . \
    && useradd --create-home lab \
    && mkdir -p /app/data && chown lab:lab /app/data
USER lab
ENV WLAB_HOST=0.0.0.0 WLAB_DATA_DIR=/app/data PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["python", "-m", "webhook_lab"]
