# Sidecar de respaldos: pg_dump/pg_restore (de postgres) + restic (off-site cifrado y
# deduplicado) + curl (pings de healthcheck). Los scripts se montan en /scripts en dev;
# aquí se copian también para que la imagen funcione de forma autónoma.
FROM postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94
RUN apt-get update \
 && apt-get install -y --no-install-recommends restic curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY backup.sh restore.sh entrypoint.sh /scripts/
