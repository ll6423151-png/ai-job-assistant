from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_qq_email(value: str) -> str:
    email = value.strip().lower()
    local, separator, domain = email.partition("@")
    if separator != "@" or domain != "qq.com" or not local.isdigit() or not 5 <= len(local) <= 12:
        raise ValueError("请输入有效的 QQ 邮箱")
    return email


def validate_password(value: str) -> str:
    if len(value) < 8 or len(value) > 128:
        raise ValueError("密码长度必须为 8-128 位")
    if not any(character.isalpha() for character in value) or not any(character.isdigit() for character in value):
        raise ValueError("密码必须同时包含字母和数字")
    return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_admin: bool
    email_verified: bool


class AuthStatus(BaseModel):
    user: UserRead
    expires_at: str


class EmailCodeRequest(BaseModel):
    email: str
    purpose: str = Field(pattern="^(register|login|reset_password)$")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_qq_email(value)


class EmailCodeSent(BaseModel):
    message: str
    retry_after_seconds: int = 60


class RegisterRequest(BaseModel):
    email: str
    password: str
    verification_code: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_qq_email(value)

    @field_validator("password")
    @classmethod
    def validate_password_value(cls, value: str) -> str:
        return validate_password(value)


class PasswordLoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = True


class CodeLoginRequest(BaseModel):
    email: str
    verification_code: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")
    remember_me: bool = True

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_qq_email(value)


class ResetPasswordRequest(BaseModel):
    email: str
    verification_code: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")
    new_password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_qq_email(value)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password(value)


class MessageResponse(BaseModel):
    message: str
