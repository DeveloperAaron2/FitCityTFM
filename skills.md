# FitCity - Skills Configuration

## Skills Disponibles

### 1. fastapi-dev
**Archivos clave:** backend/main.py, backend/routers/*.py, backend/Services/AIService.py
**Quick commands:**
- `cd backend && uvicorn main:app --reload`
- API docs: http://localhost:8000/docs

### 2. angular-dev
**Archivos clave:** frontend/src/app/pages/*.ts, frontend/src/app/services/*.ts
**Quick commands:**
- `cd frontend && ng serve -o`
- App: http://localhost:4200

### 3. supabase-ops
**Archivos clave:** backend/schema_supabase.sql, backend/database.py
**Tablas:** users, gym_visits, lifting_prs, challenges, user_challenges, gym_best_lifts

### 4. ollama-ai (Validación de vídeos)
**Archivo clave:** backend/Services/AIService.py
**Modelo:** llava (valida sentadilla, press banca, peso muerto)
**Container:** fitcity_ollama (puerto 11434)

### 5. docker-dev
**Archivo clave:** docker-compose.yml
**Quick commands:**
- `docker-compose up -d --build`
- `docker logs -f fitcity_ollama_init` (primera ejecución)

---

## Stack Completo
- Backend: FastAPI + Python 3.10+
- Frontend: Angular 19 + TailwindCSS
- DB: Supabase (PostgreSQL)
- IA: Ollama + LLaVA
- Docker: backend + ollama