FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Incluye dependencias de test para poder correr pytest en el contenedor.
# En una imagen de producción, instala solo requirements.txt.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .
RUN chmod +x entrypoint.sh

# Se invoca vía bash para no depender del bit de ejecución (el bind mount de
# desarrollo sobrescribe el archivo con el del host).
ENTRYPOINT ["bash", "entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
