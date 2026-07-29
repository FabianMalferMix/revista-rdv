# Sidecar de respaldos: pg_dump/pg_restore (de postgres) + restic (off-site cifrado y
# deduplicado) + curl (pings de healthcheck). Los scripts se montan en /scripts en dev;
# aquí se copian también para que la imagen funcione de forma autónoma.
FROM postgres:16@sha256:33f923b05f64ca54ac4401c01126a6b92afe839a0aa0a52bc5aeb5cc958e5f20
RUN apt-get update \
 && apt-get install -y --no-install-recommends restic curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY backup.sh restore.sh entrypoint.sh /scripts/
