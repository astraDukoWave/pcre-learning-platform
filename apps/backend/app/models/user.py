import uuid
import enum
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base


class UserRole(str, enum.Enum):
    """User role enum"""
    admin = "admin"
    student = "student"


class User(Base):
    __tablename__ = "users"
    
    # UUID app-generated (no requiere extensión pgcrypto)
    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Email único (unique=True es suficiente, ya crea índice)
    email = Column(
        String(255), 
        unique=True, 
        nullable=False
    )
    
    password_hash = Column(String(255), nullable=False)
    
    # Enum con name explícito
    role = Column(
        SQLEnum(UserRole, name="userrole"), 
        nullable=False, 
        default=UserRole.student
    )
    
    # Timestamps con server defaults
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role.value})>"