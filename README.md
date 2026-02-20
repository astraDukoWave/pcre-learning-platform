# PCRE Learning Platform 🚀

Sistema de aprendizaje de inglés con apuntes en formato PCRE (Pattern, Concept, Rules, Examples) y cuestionarios interactivos. Desarrollado con una arquitectura SaaS escalable.

## 🛠️ Stack Tecnológico

### Backend (Implementado - Fase 1 & 1.5)
- **Framework:** FastAPI (Python 3.11)
- **Base de Datos:** PostgreSQL 15
- **ORM & Migraciones:** SQLAlchemy 2.0 + Alembic
- **Validación y Serialización:** Pydantic V2
- **Seguridad:** Modelos preparados para JWT y hashing con bcrypt
- **Infraestructura:** Docker & Docker Compose

### Frontend (Próxima Fase)
- Next.js 15 (App Router)
- TypeScript estricto
- Tailwind CSS + shadcn/ui

## Características del Backend Actual
- **Diseño Modular:** Arquitectura estructurada separando modelos, esquemas y endpoints.
- **Gestión de Usuarios:** Modelos de usuario seguros con UUIDs autogenerados, roles (`admin`, `student`) mediante Enums nativos de PostgreSQL y restricciones de unicidad.
- **Gestión de Contenidos:** Esquema relacional completo para Cursos, Clases (con soporte Markdown) y Quizzes interactivos.
- **Buenas Prácticas:** Configuración protegida por variables de entorno y documentación automática con Swagger UI.

## Instalación y Ejecución Local

Sigue estos pasos para levantar el entorno de desarrollo en tu máquina:

1. **Clonar el repositorio:**
    git clone [https://github.com/astraDukoWave/pcre-learning-platform.git](https://github.com/astraDukoWave/pcre-learning-platform.git)
    cd pcre-learning-platform

2. **Configurar variables de entorno:**    
    cd apps/backend
    cp .env.example .env    

3. **Levantar los contenedores con Docker:**  
    Asegúrate de tener Docker corriendo en tu sistema.
    docker-compose up -d

4. **Levantar los contenedores con Docker:**  
    Ejecuta las migraciones de Alembic para crear las tablas (users, courses, classes, etc.) y puebla la base de datos con el primer curso.
    docker-compose exec backend alembic upgrade head
    docker-compose exec backend python app/db/seed.py

5. **Levantar los contenedores con Docker:** 
    Visita http://localhost:8000/docs en tu navegador para interactuar con la documentación auto-generada.

## Estructura del Proyecto
```
pcre-learning-platform/
├── apps/
│   ├── frontend/    # Aplicación Next.js (Fase 2)
│   └── backend/     # API FastAPI (Fase Actual)
└── docs/            # Documentación técnica y Handoff

## Autor

Desarrollado por Jonathan Muñoz(astradukowave) - Software Engineer

## Licencia

Privado - Uso educativo
