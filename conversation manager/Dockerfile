FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copiar dependencias e instalarlas
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar el código
COPY configs /app/configs
COPY routes /app/routes
COPY controller /app/controller
COPY modules /app/modules
COPY app.py /app/app.py

# Establecer PYTHONUNBUFFERED para desactivar el búfer
ENV PYTHONUNBUFFERED=1

# Variables para Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

EXPOSE 5000
CMD ["python", "app.py"]
