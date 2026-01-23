from fastapi import APIRouter
from app.api.v1.endpoints import courses

api_router = APIRouter() # Router de la API
api_router.include_router(courses.router, prefix="/courses", tags=["courses"]) # Incluir el router de cursos