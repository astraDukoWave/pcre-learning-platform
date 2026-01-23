from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.base import get_db
from app.models import Course, Class
from app.schemas.course import CourseListItem, CourseDetail, ClassDetail
import json

router = APIRouter() # Router de la API

@router.get("/", response_model=List[CourseListItem])
def get_courses(db: Session = Depends(get_db)): # Obtener todos los cursos
    """Get all courses"""
    courses = db.query(Course).order_by(Course.order).all() # Obtener todos los cursos ordenados por orden
    
    result = [] # Listado de cursos
    for course in courses:
        result.append({
            **course.__dict__, # Convertir el objeto a un diccionario
            "class_count": len(course.classes) # Numero de clases del curso
        })
    
    return result # Devolver el listado de cursos

@router.get("/{course_slug}", response_model=CourseDetail)
def get_course(course_slug: str, db: Session = Depends(get_db)): # Obtener el detalle de un curso
    """Get course detail by slug"""
    course = db.query(Course).filter(Course.slug == course_slug).first() # Obtener el curso por slug
    
    if not course: # Si no se encuentra el curso, devolver un error 404
        raise HTTPException(status_code=404, detail="Course not found")
    
    return course # Devolver el curso

@router.get("/{course_slug}/classes/{class_slug}", response_model=ClassDetail)
def get_class(course_slug: str, class_slug: str, db: Session = Depends(get_db)): # Obtener el detalle de una clase
    """Get class detail by course and class slug"""
    course = db.query(Course).filter(Course.slug == course_slug).first() # Obtener el curso por slug
    if not course: # Si no se encuentra el curso, devolver un error 404
        raise HTTPException(status_code=404, detail="Course not found")
    
    class_ = db.query(Class).filter( # Obtener la clase por slug
        Class.course_id == course.id,
        Class.slug == class_slug
    ).first() # Obtener la clase por slug
    
    if not class_: # Si no se encuentra la clase, devolver un error 404
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Parse quiz questions if exists
    if class_.quiz: # Si la clase tiene un cuestionario, parsear las preguntas
        for question in class_.quiz.questions:
            question.options = json.loads(question.options) # Convertir las opciones a un diccionario
    
    return class_ # Devolver la clase