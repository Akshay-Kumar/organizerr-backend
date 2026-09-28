from typing import Optional

from pydantic import BaseModel, EmailStr


# ----------------------------
# User schemas
# ----------------------------
class UserCreateIn(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    is_active: bool
    is_admin: bool

    model_config = {
        "from_attributes": True
    }


class TokenOut(BaseModel):
    access_token: str
    token_type: str