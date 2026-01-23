from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Course(Base):
    __tablename__ = "courses" # Nombre de la tabla en la base de datos
    
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True) # Slug del curso
    title = Column(String(500), nullable=False) # Titulo del curso
    description = Column(Text) # Descripcion del curso
    order = Column(Integer, default=0) # Orden del curso
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # Fecha de creacion del curso
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) # Fecha de actualizacion del curso
    
    # Relationships
    classes = relationship("Class", back_populates="course", cascade="all, delete-orphan") # Relacion con las clases del curso

class Class(Base):
    __tablename__ = "classes" # Nombre de la tabla en la base de datos
    
    id = Column(Integer, primary_key=True, index=True) # ID de la clase
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False) # ID del curso
    slug = Column(String(255), nullable=False, index=True) # Slug de la clase
    title = Column(String(500), nullable=False) # Titulo de la clase
    order = Column(Integer, default=0) # Orden de la clase
    markdown_content = Column(Text, nullable=False) # Contenido markdown de la clase
    has_quiz = Column(Boolean, default=False) # Indica si la clase tiene un cuestionario
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # Fecha de creacion de la clase
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) # Fecha de actualizacion de la clase
    
    # Relationships
    course = relationship("Course", back_populates="classes") # Relacion con el curso
    quiz = relationship("Quiz", back_populates="class_", uselist=False, cascade="all, delete-orphan") # Relacion con el cuestionario

class Quiz(Base):
    __tablename__ = "quizzes" # Nombre de la tabla en la base de datos
    
    id = Column(Integer, primary_key=True, index=True) # ID del cuestionario
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, unique=True) # ID de la clase
    
    # Relationships
    class_ = relationship("Class", back_populates="quiz") # Relacion con la clase
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan") # Relacion con las preguntas

class Question(Base):
    __tablename__ = "questions" # Nombre de la tabla en la base de datos
    
    id = Column(Integer, primary_key=True, index=True) # ID de la pregunta
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False) # ID del cuestionario
    text = Column(Text, nullable=False)
    options = Column(Text, nullable=False)  # JSON string de las opciones
    correct_index = Column(Integer, nullable=False)
    hint = Column(Text) # Indica si la pregunta tiene un hint
    explanation = Column(Text) # Explicacion de la pregunta
    order = Column(Integer, default=0) # Orden de la pregunta   
    
    # Relationships
    quiz = relationship("Quiz", back_populates="questions") # Relacion con el cuestionario