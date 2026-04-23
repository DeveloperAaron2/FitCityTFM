# Usa una imagen de Python oficial. La 3.11 es buena opción por compatibilidad y rendimiento.
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instala paquetes del sistema si son necesarios.
# Nota: Como usas `opencv-python-headless`, no hacen falta las librerías gráficas,
# pero build-essential puede venir bien para construir algunas dependencias nativas.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia primero los archivos de dependencias para aprovechar la caché de capas de Docker
COPY requirements.txt .

# Instala las dependencias y evita guardar los archivos caché para reducir el tamaño
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código del backend al directorio de trabajo en el contenedor
COPY . .

# Expone el puerto por defecto en el que correra la aplicación (uvicorn corre en 8000)
EXPOSE 8000

# Comando para arrancar la aplicación de FastAPI usando Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
