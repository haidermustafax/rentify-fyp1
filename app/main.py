from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr

from app.db import get_db_connection
from app.dependencies import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.email_utils import generate_otp, send_otp_email


app = FastAPI(title="Rentify FYP-I API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: str


def otp_is_expired(value) -> bool:
    if not value:
        return True
    expires_at = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/login")
def read_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/profile")
def read_profile(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html")


@app.get("/item/{item_id}")
def read_item(request: Request, item_id: int):
    return templates.TemplateResponse(
        request=request, name="item_detail.html", context={"item_id": item_id}
    )


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if not req.full_name.strip():
        raise HTTPException(status_code=400, detail="Full name is required.")

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email = %s", (req.email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered.")
            otp_code = generate_otp()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            cursor.execute(
                """INSERT INTO users
                   (full_name, email, password_hash, is_verified, otp_code, otp_expires_at)
                   VALUES (%s, %s, %s, FALSE, %s, %s)""",
                (req.full_name.strip(), req.email, get_password_hash(req.password), otp_code, expires_at),
            )
            send_otp_email(req.email, otp_code, "Sign-Up Verification")
        db.commit()
        return {"email": req.email, "message": "Verification code sent to your email."}
    finally:
        db.close()

@app.post("/api/auth/verify-signup-otp")
def verify_signup_otp(req: OTPVerifyRequest):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT id, otp_code, otp_expires_at FROM users WHERE email = %s",
                (req.email,),
            )
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=400, detail="User not found.")
            if user["otp_code"] != req.otp_code or otp_is_expired(user["otp_expires_at"]):
                raise HTTPException(status_code=400, detail="Invalid or expired OTP code.")
            cursor.execute(
                """UPDATE users
                   SET is_verified = TRUE, otp_code = NULL, otp_expires_at = NULL
                   WHERE id = %s""",
                (user["id"],),
            )
        db.commit()
        return {
            "access_token": create_access_token({"sub": req.email}),
            "token_type": "bearer",
            "message": "Account verified successfully.",
        }
    finally:
        db.close()


@app.post("/api/auth/login")
def login(req: LoginRequest):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT email, password_hash, is_verified FROM users WHERE email = %s",
                (req.email,),
            )
            user = cursor.fetchone()
            if not user or not verify_password(req.password, user["password_hash"]):
                raise HTTPException(status_code=400, detail="Invalid email or password.")
            if not user["is_verified"]:
                raise HTTPException(status_code=403, detail="Verify your email before signing in.")
            return {
                "access_token": create_access_token({"sub": user["email"]}),
                "token_type": "bearer",
            }
    finally:
        db.close()


@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/api/listings")
def get_listings(category_id: Optional[int] = None, search: Optional[str] = None):
    db = get_db_connection()
    try:
        query = """
            SELECT l.id, l.title, l.description, l.price_per_day, l.deposit_amount,
                   l.location, l.image_url, c.name AS category_name, l.category_id
            FROM listings l
            JOIN categories c ON c.id = l.category_id
            WHERE l.is_available = TRUE
        """
        params = []
        if category_id:
            query += " AND l.category_id = %s"
            params.append(category_id)
        if search:
            query += " AND (l.title LIKE %s OR l.description LIKE %s OR l.location LIKE %s)"
            term = f"%{search}%"
            params.extend([term, term, term])
        query += " ORDER BY l.id DESC"
        with db.cursor() as cursor:
            cursor.execute(query, tuple(params))
            return [
                {
                    **row,
                    "price_per_day": float(row["price_per_day"]),
                    "deposit_amount": float(row["deposit_amount"]),
                }
                for row in cursor.fetchall()
            ]
    finally:
        db.close()


@app.get("/api/listings/{listing_id}")
def get_listing_detail(listing_id: int):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """SELECT l.id, l.title, l.description, l.price_per_day, l.deposit_amount,
                          l.location, l.image_url, c.name AS category_name, l.category_id
                   FROM listings l
                   JOIN categories c ON c.id = l.category_id
                   WHERE l.id = %s AND l.is_available = TRUE""",
                (listing_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Listing not found.")
            row["price_per_day"] = float(row["price_per_day"])
            row["deposit_amount"] = float(row["deposit_amount"])
            return row
    finally:
        db.close()
