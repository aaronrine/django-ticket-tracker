FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY . .

CMD ["sh", "-c", "uv run python manage.py migrate && uv run python manage.py collectstatic --noinput && exec uv run gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]