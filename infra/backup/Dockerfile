# Sidecar de respaldos: pg_dump/pg_restore (de postgres) + restic (off-site cifrado y
# deduplicado) + curl (pings de healthcheck). Los scripts se montan en /scripts en dev;
# aquí se copian también para que la imagen funcione de forma autónoma.
FROM postgres:16@sha256:95206741a5b214807675e14165369d05b93a9cf692223b616d07cca227e74b0b
RUN apt-get update \
 && apt-get install -y --no-install-recommends restic curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY backup.sh restore.sh entrypoint.sh /scripts/
