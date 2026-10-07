FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system launchguard && useradd --system --gid launchguard launchguard

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
COPY evals ./evals

RUN python -m pip install --upgrade pip && python -m pip install .

RUN mkdir -p /app/data && chown -R launchguard:launchguard /app
USER launchguard

EXPOSE 8080
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"

CMD ["launchguard", "serve", "--host", "0.0.0.0", "--port", "8080"]
