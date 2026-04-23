# FitCity

FitCity es una plataforma completa (Full Stack) orientada al mundo del fitness, que permite gestionar usuarios, visitas a gimnasios, validación de marcas personales (PRs) de levantamiento de potencia (Powerlifting) mediante IA, y participación en retos y rankings. 

El proyecto consta de dos partes principales:
- **Frontend**: Aplicación web SPA desarrollada con Angular 19 y TailwindCSS.
- **Backend**: API REST desarrollada con FastAPI (Python) y base de datos gestionada por Supabase (PostgreSQL).

## Funcionalidades Principales
- **Gestión de Usuarios y Autenticación**: Registro e inicio de sesión seguros.
- **Registro de Visitas a Gimnasios**: Permite realizar check-in a usuarios en diferentes centros deportivos.
- **Validación de PRs con Inteligencia Artificial**: Integración de IA para validar automáticamente videos de levantamientos de Powerlifting (Sentadilla, Press Banca, Peso Muerto) en base a las normativas de la federación.
- **Rankings y Retos**: Visualización de los usuarios más fuertes, gimnasios donde se consiguieron las marcas y retos vigentes de la comunidad.

## Requisitos Previos
- Docker y Docker Compose (Recomendado para desplegar el Backend y la IA integrada).
- Node.js (v18+) y npm.
- Angular CLI (`npm install -g @angular/cli`).
- Python 3.10+ (Sólo si decides ejecutar el backend en local sin Docker).
- Una cuenta y proyecto en [Supabase](https://supabase.com/).

## Configuración y Ejecución

### 1. Configuración del Backend e IA (Recomendado con Docker)
El backend y su ecosistema de Inteligencia Artificial (Ollama + LLaVA) han sido contenerizados para evitar problemas de compatibilidad y configuraciones manuales complejas.

1. Configura tus tokens secretos. Crea un archivo `.env` dentro de la carpeta `backend` con lo siguiente:
   ```env
   SUPABASE_URL=tu_supabase_url
   SUPABASE_KEY=tu_supabase_key
   ```
2. Navega a la raíz de tu proyecto (donde está el archivo `docker-compose.yml`) y levanta los servicios en segundo plano:
   ```bash
   docker-compose up -d --build
   ```
3. **Paso importante (Primera ejecución)**: El inicializador automático detectará que es la primera vez y comenzará a descargar el modelo inteligente que valida los vídeos (`llava:13b`). Al pesar unos 8 Gigabytes, esto llevará unos minutos. Puedes chequear el progreso en vivo con este comando:
   ```bash
   docker logs -f fitcity_ollama_init
   ```
4. Cuando el log indique que ha terminado de bajar, tu backend estará escuchando activamente en `http://localhost:8000`. Puedes revisar los *endpoints* interactivos en `http://localhost:8000/docs`.

*(Alternativa Local: Si prefieres no usar Docker, debes entrar en `/backend`, configurar un entorno virtual de `Python 3.10+`, lanzar `pip install -r requirements.txt`, asegurarte de tener la herramienta `ollama` nativa con `llava:13b` corriendo en tu máquina, y finalmente levantar el propio back ejecutando `uvicorn main:app --reload`)*

### 2. Configuración del Frontend (Angular)
1. Navega a la carpeta del frontend: `cd frontend`
2. Instala las dependencias:
   ```bash
   npm install
   ```
3. Ejecuta el servidor de desarrollo:
   ```bash
   ng serve -o
   ```
   La aplicación se abrirá automáticamente en tu navegador por defecto en `http://localhost:4200`.

## Tecnologías Utilizadas
- **Frontend**: Angular 19, TypeScript, TailwindCSS 4, Karma/Jasmine (Testing).
- **Backend**: Python 3.10, FastAPI, Uvicorn, Pydantic, Supabase Python Client.
- **Base de datos**: PostgreSQL (Supabase) con políticas RLS (Row Level Security).
- **Inteligencia Artificial**: Integración con Inteligencia Artificial y OpenCV para validación de videos mediante modelos de visión.
