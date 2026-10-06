"""Tablas legadas de la fase 1, congeladas (ADR-08).

Se movieron sin cambios desde `app/models/course.py` (@ 133c5e3) para que sigan en la
metadata. Nada las lee ni las escribe; se retiran en un ciclo posterior con su spec (LB-11).
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    classes = relationship("Class", back_populates="course", cascade="all, delete-orphan")


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    order = Column(Integer, default=0)
    markdown_content = Column(Text, nullable=False)
    has_quiz = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    course = relationship("Course", back_populates="classes")
    quiz = relationship(
        "Quiz", back_populates="class_", uselist=False, cascade="all, delete-orphan"
    )


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, unique=True)

    class_ = relationship("Class", back_populates="quiz")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    text = Column(Text, nullable=False)
    options = Column(Text, nullable=False)
    correct_index = Column(Integer, nullable=False)
    hint = Column(Text)
    explanation = Column(Text)
    order = Column(Integer, default=0)

    quiz = relationship("Quiz", back_populates="questions")
