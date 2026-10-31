FROM python:3.14-slim AS app
WORKDIR /lab
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
CMD ["python", "-m", "authflow.run"]

FROM app AS test
RUN apt-get update && apt-get install -y --no-install-recommends libnss3-tools \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["sh", "scripts/test-entrypoint.sh"]
CMD ["python", "-m", "pytest", "-q", "--junitxml=test-results/results.xml"]

