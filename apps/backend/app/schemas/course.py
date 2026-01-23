from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Question Schemas
class QuestionBase(BaseModel): # Esquema base de la pregunta
    text: str # Texto de la pregunta
    options: List[str] # Opciones de la pregunta
    hint: Optional[str] = None # Hint de la pregunta
    explanation: str # Explicacion de la pregunta
    order: int = 0 # Orden de la pregunta

class QuestionResponse(QuestionBase):
    id: int # ID de la pregunta
    
    class Config:
        from_attributes = True # Indica que se debe usar el nombre de los atributos de la clase

class QuestionWithAnswer(QuestionResponse):
    correct_index: int # Indice de la respuesta correcta

# Quiz Schemas
class QuizResponse(BaseModel): # Esquema de la respuesta del cuestionario
    id: int # ID del cuestionario
    questions: List[QuestionResponse] # Listado de preguntas
    
    class Config:
        from_attributes = True # Indica que se debe usar el nombre de los atributos de la clase

# Class Schemas
class ClassBase(BaseModel): # Esquema base de la clase
    slug: str
    title: str # Titulo de la clase
    order: int = 0 # Orden de la clase

class ClassListItem(ClassBase): # Esquema de la lista de clases
    id: int # ID de la clase
    has_quiz: bool # Indica si la clase tiene un cuestionario
    
    class Config:
        from_attributes = True # Indica que se debe usar el nombre de los atributos de la clase

class ClassDetail(ClassBase):
    id: int
    markdown_content: str # Contenido markdown de la clase
    has_quiz: bool # Indica si la clase tiene un cuestionario
    quiz: Optional[QuizResponse] = None # Cuestionario de la clase
    
    class Config:
        from_attributes = True # Indica que se debe usar el nombre de los atributos de la clase

# Course Schemas
class CourseBase(BaseModel): # Esquema base del curso
    slug: str
    title: str # Titulo del curso
    description: Optional[str] = None # Descripcion del curso
    order: int = 0 # Orden del curso

class CourseListItem(CourseBase): # Esquema de la lista de cursos   
    id: int # ID del curso
    class_count: int = 0 # Numero de clases del curso
    
    class Config:
        from_attributes = True # Indica que se debe usar el nombre de los atributos de la clase

class CourseDetail(CourseBase):
    id: int # ID del curso
    classes: List[ClassListItem] = [] # Listado de clases del curso
    
    class Config:
        from_attributes = True # Indica que se debe usar el nombre de los atributos de la clase