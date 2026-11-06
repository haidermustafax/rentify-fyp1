import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from app.db import get_db_connection
from app.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
security_bearer = HTTPBearer(auto_error=False)

def get_db():
    return get_db_connection()

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def hash_password(password: str) -> str:
    return get_password_hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def get_current_user(
    bearer_creds: HTTPAuthorizationCredentials = Security(security_bearer),
    token_oauth: str = Depends(oauth2_scheme)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = None
    if bearer_creds and bearer_creds.credentials:
        token = bearer_creds.credentials
    elif token_oauth:
        token = token_oauth

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
    except jwt.PyJWTError:
        raise credentials_exception

    if sub is None:
        raise credentials_exception

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if str(sub).isdigit():
                cursor.execute(
                    "SELECT id, full_name, email, role, wallet_balance, is_verified, two_factor_enabled FROM users WHERE id = %s",
                    (int(sub),)
                )
            else:
                cursor.execute(
                    "SELECT id, full_name, email, role, wallet_balance, is_verified, two_factor_enabled FROM users WHERE email = %s",
                    (str(sub),)
                )

            user = cursor.fetchone()
            if user is None:
                raise credentials_exception

            if isinstance(user, dict):
                user["wallet_balance"] = float(user.get("wallet_balance", 0.0))
            return user
    finally:
        conn.close()

def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user
