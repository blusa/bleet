FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client git tini && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml /app/
COPY bleetd /app/bleetd
RUN pip install . && groupadd --gid 10001 bleetd && useradd --uid 10001 --gid 10001 --home-dir /var/lib/bleetd --no-create-home bleetd && mkdir -p /var/lib/bleetd && chown 10001:10001 /var/lib/bleetd
USER 10001:10001
EXPOSE 8791
ENTRYPOINT ["tini", "--", "bleetd"]
CMD ["serve", "--config", "/etc/bleetd/config.json", "--host", "0.0.0.0", "--port", "8791"]
