import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from app.db import get_db_connection
from app.dependencies import hash_password, verify_password, create_access_token, get_current_user
from app.email_utils import generate_otp, send_otp_email

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OTPVerify(BaseModel):
    email: EmailStr
    otp_code: str

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class Toggle2FA(BaseModel):
    enabled: bool

PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?])[^\s]{6,}$"

@router.post("/register")
def register(user: UserRegister):
    if not re.match(PASSWORD_REGEX, user.password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters long, contain uppercase, lowercase, numbers, special characters, and no spaces."
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (user.email,))
            existing = cursor.fetchone()
            
            otp = generate_otp()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            hashed_pw = hash_password(user.password)

            if existing:
                if existing["is_verified"]:
                    raise HTTPException(status_code=400, detail="Email is already registered and verified.")
                # Update OTP for unverified existing account
                cursor.execute(
                    "UPDATE users SET full_name=%s, password_hash=%s, otp_code=%s, otp_expires_at=%s WHERE id=%s",
                    (user.full_name, hashed_pw, otp, expires_at, existing["id"])
                )
            else:
                cursor.execute(
                    """INSERT INTO users (full_name, email, password_hash, wallet_balance, is_verified, otp_code, otp_expires_at) 
                       VALUES (%s, %s, %s, 10000.00, FALSE, %s, %s)""",
                    (user.full_name, user.email, hashed_pw, otp, expires_at)
                )
            conn.commit()
            
            send_otp_email(user.email, otp, "Sign-Up Verification")
            return {
                "message": "Verification OTP sent to your Gmail address.",
                "requires_otp": True,
                "email": user.email
            }
    finally:
        conn.close()

@router.post("/verify-signup-otp")
def verify_signup_otp(data: OTPVerify):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (data.email,))
            user = cursor.fetchone()
            if not user or user["otp_code"] != data.otp_code:
                raise HTTPException(status_code=400, detail="Invalid verification code.")
            
            if user["otp_expires_at"] and user["otp_expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Verification code has expired.")
            
            cursor.execute("UPDATE users SET is_verified = TRUE, otp_code = NULL, otp_expires_at = NULL WHERE id = %s", (user["id"],))
            conn.commit()

            token = create_access_token({"sub": user["id"], "role": user["role"]})
            return {
                "message": "Account verified successfully!",
                "access_token": token,
                "token_type": "bearer"
            }
    finally:
        conn.close()

@router.post("/login")
def login(user: UserLogin):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (user.email,))
            db_user = cursor.fetchone()
            if not db_user or not verify_password(user.password, db_user["password_hash"]):
                raise HTTPException(status_code=400, detail="Invalid email or password")
            
            if not db_user["is_verified"]:
                # Resend sign-up verification OTP
                otp = generate_otp()
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
                cursor.execute("UPDATE users SET otp_code=%s, otp_expires_at=%s WHERE id=%s", (otp, expires_at, db_user["id"]))
                conn.commit()
                send_otp_email(user.email, otp, "Sign-Up Verification")
                return {
                    "requires_signup_otp": True,
                    "email": user.email,
                    "message": "Please verify your email address to complete registration."
                }

            # Check if 2FA is turned on
            if db_user["two_factor_enabled"]:
                otp = generate_otp()
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
                cursor.execute("UPDATE users SET otp_code=%s, otp_expires_at=%s WHERE id=%s", (otp, expires_at, db_user["id"]))
                conn.commit()
                send_otp_email(user.email, otp, "2FA Login Verification")
                return {
                    "requires_2fa": True,
                    "email": user.email,
                    "message": "2FA code sent to your email address."
                }
            
            token = create_access_token({"sub": db_user["id"], "role": db_user["role"]})
            return {
                "access_token": token,
                "token_type": "bearer"
            }
    finally:
        conn.close()

@router.post("/verify-2fa-otp")
def verify_2fa_otp(data: OTPVerify):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (data.email,))
            user = cursor.fetchone()
            if not user or user["otp_code"] != data.otp_code:
                raise HTTPException(status_code=400, detail="Invalid 2FA code.")
            
            if user["otp_expires_at"] and user["otp_expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="2FA code has expired.")
            
            cursor.execute("UPDATE users SET otp_code = NULL, otp_expires_at = NULL WHERE id = %s", (user["id"],))
            conn.commit()

            token = create_access_token({"sub": user["id"], "role": user["role"]})
            return {
                "access_token": token,
                "token_type": "bearer"
            }
    finally:
        conn.close()

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@router.post("/toggle-2fa")
def toggle_2fa(data: Toggle2FA, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET two_factor_enabled = %s WHERE id = %s", (data.enabled, current_user["id"]))
            conn.commit()
            status_str = "enabled" if data.enabled else "disabled"
            return {"message": f"Two-Factor Authentication has been {status_str}."}
    finally:
        conn.close()

@router.post("/change-password")
def change_password(data: PasswordChange, current_user: dict = Depends(get_current_user)):
    if not re.match(PASSWORD_REGEX, data.new_password):
        raise HTTPException(
            status_code=400,
            detail="New password must be at least 6 characters long, include uppercase, lowercase, numbers, special chars, and no spaces."
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT password_hash FROM users WHERE id = %s", (current_user["id"],))
            user = cursor.fetchone()
            if not verify_password(data.old_password, user["password_hash"]):
                raise HTTPException(status_code=400, detail="Incorrect current password")
            
            new_hashed = hash_password(data.new_password)
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hashed, current_user["id"]))
            conn.commit()
            return {"message": "Password updated successfully!"}
    finally:
        conn.close()
