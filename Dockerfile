# Dockerfile snippet example
FROM python:3.12-slim

ARG BUILD_SHA=dev
ENV BUILD_SHA=$BUILD_SHA

ARG BUILD_DATE=dev
ENV BUILD_DATE=$BUILD_DATE

ARG DEPLOY_ENV=dev
ENV DEPLOY_ENV=$DEPLOY_ENV

# uv
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/venv
ENV PATH="/app/venv/bin:$PATH"

# Install dependencies from the lock file (production only, no dev group)
COPY pyproject.toml uv.lock .
RUN uv sync --locked --no-dev

# Copy your Django app code
COPY . .

# Collect static files during build with dummy SECRET_KEY
ENV SECRET_KEY=dummy-key-for-build
ENV DEBUG=disabled
RUN python manage.py collectstatic --noinput

# Expose the port (if required)
EXPOSE 8080

# Set the container startup command
CMD ["sh", "scripts/startup.sh"]
