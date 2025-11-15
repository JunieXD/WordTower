from passlib.context import CryptContext
from jose import jwt
from app.models.user import User
from app.utils.config import settings
from datetime import datetime, timedelta, timezone
import uuid

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)

def encode_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": user.username,
        "iat": now,
        "exp": now + timedelta(days=1),
        "jti": str(uuid.uuid4())
    }, settings.SECRET_KEY, algorithm="HS256")

def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.JWTError:
        return None
