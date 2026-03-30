from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import users, gym_visits, lifting_prs, challenges, ranking, auth, gyms_proxy
from routers.lifting_prs import validate_router

app = FastAPI(
    title="FitCity API",
    description="API REST para la aplicación FitCity — gestión de usuarios, visitas a gimnasios, records personales, retos y ranking.",
    version="1.0.0",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# Allow requests from the Angular frontend (adjust origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",   # Angular dev server
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(gym_visits.router)
app.include_router(lifting_prs.router)
app.include_router(challenges.router)
app.include_router(ranking.router)
app.include_router(gyms_proxy.router)
app.include_router(validate_router)


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "app": "FitCity API", "version": "1.0.0"}
