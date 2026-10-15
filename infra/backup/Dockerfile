# Sidecar de respaldos: pg_dump/pg_restore (de postgres) + restic (off-site cifrado y
# deduplicado) + curl (pings de healthcheck). Los scripts se montan en /scripts en dev;
# aquí se copian también para que la imagen funcione de forma autónoma.
FROM postgres:16@sha256:ca0bd484cb98bf4b24eb1010e73fb3fcbd6714d240fbc1a10eea5b7dbecb641d
RUN apt-get update \
 && apt-get install -y --no-install-recommends restic curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY backup.sh restore.sh entrypoint.sh /scripts/
