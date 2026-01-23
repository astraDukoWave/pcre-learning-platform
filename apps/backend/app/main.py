from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router

app = FastAPI( # FastAPI app
    title=settings.PROJECT_NAME, # Titulo de la app (config.py)
    openapi_url=f"{settings.API_V1_STR}/openapi.json" # URL de la API (config.py)
)

# CORS
app.add_middleware( # Middleware de CORS
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL (config.py)
    allow_credentials=True, # Permitir credenciales
    allow_methods=["*"], # Permitir todos los metodos
    allow_headers=["*"], # Permitir todos los headers
)

# Health check
@app.get("/health") # Endpoint de health check
def health_check():
    return {"status": "ok"} # Devolver el estado de la app

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR) # Incluir el router de la API (api.py)