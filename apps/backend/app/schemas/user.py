import enum
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# Enum (reutiliza el mismo set de valores que model)
class UserRole(str, enum.Enum):
    admin = "admin"
    student = "student"


# Base schemas
class UserBase(BaseModel):
    email: EmailStr


# Create schemas (para registro)
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)


# Response schemas (NUNCA exponer password_hash)
class UserResponse(UserBase):
    id: uuid.UUID
    role: UserRole  # Usa el Enum
    created_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True  # Serializa enums como strings
    )


# Schema detallado (para /auth/me)
class UserDetail(UserResponse):
    updated_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True
    )


# Login schema
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# Token response
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse