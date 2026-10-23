# ---- Python Build Stage ----
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache --no-dev

# ---- Runtime Stage ----
FROM python:3.12-slim-bookworm AS runtime

# msodbcsql18 설치 순서: curl로 MS 저장소 키를 받아야 하므로 curl을 먼저 깔고,
# 설치가 끝나면 지워도 되지만 헬스체크(docker-stack.yaml)가 curl로 /health를
# 찌르므로 다시 설치한다. gnupg2는 키 등록에만 쓰고 남겨두지 않는다.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg2 unixodbc \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | \
        gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
    && ARCH=$(dpkg --print-architecture) \
    && echo "deb [arch=${ARCH} signed-by=/usr/share/keyrings/microsoft.gpg] \
        https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get purge -y --auto-remove gnupg2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY ./app ./app
COPY alembic.ini ./
COPY ./alembic ./alembic

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--log-level", "warning", \
     "--no-access-log"]
