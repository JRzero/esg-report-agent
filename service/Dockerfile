FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system esg && useradd --system --gid esg --create-home esg

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY --chown=esg:esg . .
RUN mkdir -p /app/.storage && chown -R esg:esg /app/.storage

USER esg

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
