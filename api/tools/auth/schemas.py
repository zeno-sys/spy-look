from __future__ import annotations

from pydantic import BaseModel, Field


class SetupRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    remember: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class LocalResetOwnerRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)


class SetDisabledRequest(BaseModel):
    disabled: bool
