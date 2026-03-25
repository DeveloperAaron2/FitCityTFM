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
- Node.js (v18+) y npm.
- Angular CLI (`npm install -g @angular/cli`).
- Python 3.10+.
- Una cuenta y proyecto en [Supabase](https://supabase.com/).

## Configuración y Ejecución

### 1. Configuración del Backend (FastAPI)
1. Navega a la carpeta del backend: `cd backend`
2. Crea un entorno virtual e instálalo: 
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Configura las variables de entorno. Crea un archivo `.env` en la carpeta `backend` con las siguientes variables:
   ```env
   SUPABASE_URL=tu_supabase_url
   SUPABASE_KEY=tu_supabase_key
   ```
4. Ejecuta el servidor de desarrollo:
   ```bash
   uvicorn main:app --reload
   ```
   El backend estará disponible en `http://localhost:8000`. Puedes consultar la documentación interactiva en `http://localhost:8000/docs`.

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
