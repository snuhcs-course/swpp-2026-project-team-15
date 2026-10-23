FROM ghcr.io/astral-sh/uv:0.13.4 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY server/app ./app
COPY server/recipe_filtering ./recipe_filtering
COPY server/recipe_revision ./recipe_revision
COPY server/fixtures/vision ./fixtures/vision
COPY server/db ./db
RUN useradd --uid 10001 --create-home chef
USER chef
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
