# PCRE Learning Platform 

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

Sistema de aprendizaje de inglés con apuntes en formato PCRE (Pattern, Concept, Rules, Examples) y cuestionarios interactivos. Desarrollado con una arquitectura SaaS escalable.

## Stack tecnologico

### Backend (Implementado - Fase 1 & 1.5)

- Framework: FastAPI (Python 3.11)
- Base de datos: PostgreSQL 15
- ORM & migraciones: SQLAlchemy 2.0 + Alembic
- Validación y serialización: Pydantic v2
- Seguridad: Modelos preparados para JWT y hashing con bcrypt
- Infraestructura: Docker & Docker Compose

### Frontend (Proxima fase)

- Next.js 15 (App Router)
- TypeScript estricto
- Tailwind CSS + shadcn/ui

## Características del backend actual

- Diseño modular: Arquitectura estructurada separando modelos, esquemas y endpoints.
- Gestion de usuarios: Modelos de usuario seguros con UUIDs autogenerados, roles (admin, student) mediante Enums nativos de PostgreSQL y restricciones de unicidad.
- Gestion de contenidos: Esquema relacional completo para Cursos, Clases (con soporte Markdown) y Quizzes interactivos.
- Buenas prácticas: Configuración protegida por variables de entorno y documentación automática con Swagger UI.

## Instalación y ejecución local

Sigue estos pasos para levantar el entorno de desarrollo en tu máquina.

1) Clonar el repositorio:

```bash
git clone https://github.com/astraDukoWave/pcre-learning-platform.git
cd pcre-learning-platform
```
2) Configurar variables de entorno:
```bash
cd apps/backend
cp .env.example .env
```
3) Levantar contenedores:
```bash
docker-compose up -d
```
4) Ejecutar migraciones y seed inicial:
```bash
docker-compose exec backend alembic upgrade head
docker-compose exec backend python app/db/seed.py
```
5) Abrir la documentación de la API (Swagger):
http://localhost:8000/docs


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
