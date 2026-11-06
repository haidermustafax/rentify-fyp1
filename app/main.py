import random
from typing import Optional
from datetime import datetime, date, timedelta, timezone
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from app.email_utils import generate_otp, send_otp_email

from app.dependencies import (
    get_db,
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user
)

app = FastAPI(title="Rentify API", version="1.0.0")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files & Jinja2 Template rendering
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# -------------------------------------------------------------------
# PYDANTIC REQUEST SCHEMAS
# -------------------------------------------------------------------

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

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str
    new_password: str

class BookingRequest(BaseModel):
    listing_id: int
    start_date: str
    end_date: str

class TopupRequest(BaseModel):
    amount: float

class ListingCreateRequest(BaseModel):
    category_id: int
    title: str
    description: str
    price_per_day: float
    deposit_amount: float = 0
    location: str
    image_url: Optional[str] = None

class Toggle2FARequest(BaseModel):
    enabled: bool

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

def otp_is_expired(value) -> bool:
    if not value:
        return True
    expires_at = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)

# -------------------------------------------------------------------
# HTML PAGE ROUTES
# -------------------------------------------------------------------

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
    return templates.TemplateResponse(request=request, name="item_detail.html", context={"item_id": item_id})

# -------------------------------------------------------------------
# AUTHENTICATION & PASSWORD RESET ROUTES
# -------------------------------------------------------------------

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (req.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered.")

        otp_code = generate_otp()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        hashed_pwd = get_password_hash(req.password)

        cursor.execute(
            """INSERT INTO users (full_name, email, password_hash, is_verified, otp_code, otp_expires_at)
               VALUES (%s, %s, %s, FALSE, %s, %s)""",
            (req.full_name, req.email, hashed_pwd, otp_code, expires_at)
        )
        send_otp_email(req.email, otp_code, "Sign-Up Verification")
        db.commit()
        return {"email": req.email, "message": "Verification code sent to your email."}
    finally:
        cursor.close()

@app.post("/api/auth/verify-signup-otp")
def verify_signup_otp(req: OTPVerifyRequest):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, otp_code, otp_expires_at FROM users WHERE email = %s", (req.email,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="User not found.")

        otp_in_db = user["otp_code"] if isinstance(user, dict) else user[1]
        user_id = user["id"] if isinstance(user, dict) else user[0]
        otp_expires_at = user["otp_expires_at"] if isinstance(user, dict) else user[2]

        if otp_in_db != req.otp_code or otp_is_expired(otp_expires_at):
            raise HTTPException(status_code=400, detail="Invalid or expired OTP code.")

        cursor.execute("UPDATE users SET is_verified = TRUE, otp_code = NULL, otp_expires_at = NULL WHERE id = %s", (user_id,))
        db.commit()

        access_token = create_access_token(data={"sub": req.email})
        return {"access_token": access_token, "token_type": "bearer", "message": "Account verified successfully!"}
    finally:
        cursor.close()

@app.post("/api/auth/login")
def login(req: LoginRequest):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, full_name, email, password_hash, is_verified, two_factor_enabled FROM users WHERE email = %s", (req.email,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="Invalid email or password")

        pwd_hash = user["password_hash"] if isinstance(user, dict) else user[3]
        is_ver = user["is_verified"] if isinstance(user, dict) else user[4]
        two_fa = user["two_factor_enabled"] if isinstance(user, dict) else user[5]

        if not verify_password(req.password, pwd_hash):
            raise HTTPException(status_code=400, detail="Invalid email or password")

        if not is_ver:
            otp_code = generate_otp()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            cursor.execute("UPDATE users SET otp_code = %s, otp_expires_at = %s WHERE email = %s", (otp_code, expires_at, req.email))
            db.commit()
            send_otp_email(req.email, otp_code, "Sign-Up Verification")
            return {"requires_signup_otp": True, "email": req.email, "message": "Check your email (or the development server output) for your verification code."}

        if two_fa:
            otp_code = generate_otp()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            cursor.execute("UPDATE users SET otp_code = %s, otp_expires_at = %s WHERE email = %s", (otp_code, expires_at, req.email))
            db.commit()
            send_otp_email(req.email, otp_code, "2FA Login Verification")
            return {"requires_2fa": True, "email": req.email, "message": "Check your email (or the development server output) for your 2FA code."}

        access_token = create_access_token(data={"sub": req.email})
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        cursor.close()

@app.post("/api/auth/verify-2fa-otp")
def verify_2fa_otp(req: OTPVerifyRequest):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, otp_code, otp_expires_at FROM users WHERE email = %s", (req.email,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="User not found.")

        otp_in_db = user["otp_code"] if isinstance(user, dict) else user[1]
        otp_expires_at = user["otp_expires_at"] if isinstance(user, dict) else user[2]

        if otp_in_db != req.otp_code or otp_is_expired(otp_expires_at):
            raise HTTPException(status_code=400, detail="Invalid or expired 2FA code.")

        cursor.execute("UPDATE users SET otp_code = NULL, otp_expires_at = NULL WHERE email = %s", (req.email,))
        db.commit()

        access_token = create_access_token(data={"sub": req.email})
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        cursor.close()

@app.post("/api/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (req.email,))
        user = cursor.fetchone()

        if not user:
            return {"message": "If an account exists with this email, a 6-digit OTP has been sent."}

        otp_code = generate_otp()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        cursor.execute("UPDATE users SET otp_code = %s, otp_expires_at = %s WHERE email = %s", (otp_code, expires_at, req.email))
        db.commit()
        send_otp_email(req.email, otp_code, "Password Reset")
        return {"message": "A 6-digit password reset code has been sent. Check your email (or the development server output)."}
    finally:
        cursor.close()

@app.post("/api/auth/reset-password")
def reset_password(req: ResetPasswordRequest):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, otp_code, otp_expires_at FROM users WHERE email = %s", (req.email,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="Invalid request.")

        otp_in_db = user["otp_code"] if isinstance(user, dict) else user[1]
        otp_expires_at = user["otp_expires_at"] if isinstance(user, dict) else user[2]

        if not otp_in_db or otp_in_db != req.otp_code or otp_is_expired(otp_expires_at):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP verification code."
            )

        if len(req.new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long."
            )

        hashed_password = get_password_hash(req.new_password)
        cursor.execute(
            "UPDATE users SET password_hash = %s, otp_code = NULL, otp_expires_at = NULL WHERE email = %s",
            (hashed_password, req.email)
        )
        db.commit()

        return {"message": "Password reset successful! You can now sign in with your new password."}
    finally:
        cursor.close()

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@app.post("/api/auth/toggle-2fa")
def toggle_2fa(req: Toggle2FARequest, current_user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE users SET two_factor_enabled = %s WHERE id = %s",
            (req.enabled, current_user["id"]),
        )
        db.commit()
        return {"message": f"Two-factor authentication {'enabled' if req.enabled else 'disabled'}."}
    finally:
        cursor.close()

@app.post("/api/auth/change-password")
def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters long.")
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (current_user["id"],))
        row = cursor.fetchone()
        stored_hash = row["password_hash"] if isinstance(row, dict) else row[0]
        if not verify_password(req.old_password, stored_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (get_password_hash(req.new_password), current_user["id"]),
        )
        db.commit()
        return {"message": "Password updated successfully."}
    finally:
        cursor.close()

# -------------------------------------------------------------------
# MARKETPLACE LISTINGS & CATEGORIES
# -------------------------------------------------------------------

@app.get("/api/listings")
def get_listings(category_id: Optional[int] = None, search: Optional[str] = None):
    db = get_db()
    cursor = db.cursor()
    try:
        # Changed to LEFT JOIN so items never disappear if a category goes missing
        query = """
            SELECT l.id, l.title, l.description, l.price_per_day, l.deposit_amount, 
                   l.location, l.image_url, c.name as category_name, l.category_id
            FROM listings l
            LEFT JOIN categories c ON l.category_id = c.id
            WHERE l.is_available = TRUE
        """
        params = []

        if category_id:
            query += " AND l.category_id = %s"
            params.append(category_id)

        if search:
            query += " AND (l.title LIKE %s OR l.description LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY l.id DESC"
        cursor.execute(query, tuple(params))
        
        rows = cursor.fetchall()
        result = []
        for r in rows:
            if isinstance(r, dict):
                r["category_name"] = r.get("category_name") or "Uncategorized"
                result.append(r)
            else:
                result.append({
                    "id": r[0], 
                    "title": r[1], 
                    "description": r[2],
                    "price_per_day": float(r[3] or 0), 
                    "deposit_amount": float(r[4] or 0),
                    "location": r[5], 
                    "image_url": r[6], 
                    "category_name": r[7] or "Uncategorized", 
                    "category_id": r[8]
                })
        return result
    finally:
        cursor.close()
@app.get("/api/listings/{listing_id}")
def get_listing_detail(listing_id: int):
    db = get_db()
    cursor = db.cursor()
    try:
        query = """
            SELECT l.id, l.title, l.description, l.price_per_day, l.deposit_amount, 
                   l.location, l.image_url, c.name as category_name, l.category_id
            FROM listings l
            LEFT JOIN categories c ON l.category_id = c.id
            WHERE l.id = %s
        """
        cursor.execute(query, (listing_id,))
        r = cursor.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Listing not found.")

        if isinstance(r, dict):
            r["category_name"] = r.get("category_name") or "Uncategorized"
            return r
        return {
            "id": r[0], 
            "title": r[1], 
            "description": r[2],
            "price_per_day": float(r[3] or 0), 
            "deposit_amount": float(r[4] or 0),
            "location": r[5], 
            "image_url": r[6], 
            "category_name": r[7] or "Uncategorized", 
            "category_id": r[8]
        }
    finally:
        cursor.close()

@app.post("/api/listings", status_code=201)
def create_listing(req: ListingCreateRequest, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required.")
    if not req.title.strip() or not req.description.strip() or not req.location.strip():
        raise HTTPException(status_code=400, detail="Title, description, and location are required.")
    if req.category_id not in {1, 2, 3, 4}:
        raise HTTPException(status_code=400, detail="Choose a valid listing category.")
    if req.price_per_day <= 0 or req.deposit_amount < 0:
        raise HTTPException(status_code=400, detail="Price must be positive and deposit cannot be negative.")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """INSERT INTO listings
               (category_id, title, description, price_per_day, deposit_amount, location, image_url, is_available)
               VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)""",
            (
                req.category_id,
                req.title.strip(),
                req.description.strip(),
                req.price_per_day,
                req.deposit_amount,
                req.location.strip(),
                req.image_url,
            ),
        )
        listing_id = cursor.lastrowid
        db.commit()
        return {"id": listing_id, "message": "Listing added to the marketplace."}
    finally:
        cursor.close()

@app.delete("/api/listings/{listing_id}")
def delete_listing(listing_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required.")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE listings SET is_available = FALSE WHERE id = %s", (listing_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Listing not found.")
        db.commit()
        return {"message": "Listing removed from the active marketplace."}
    finally:
        cursor.close()

# -------------------------------------------------------------------
# BOOKINGS & WALLET (BUG FIXES APPLIED)
# -------------------------------------------------------------------

@app.post("/api/bookings")
def create_booking(req: BookingRequest, current_user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.cursor()
    try:
        user_id = current_user["id"]

        # FIX 1: Strict date validation and calculation
        try:
            start_dt = datetime.strptime(req.start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(req.end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

        if start_dt > end_dt:
            raise HTTPException(status_code=400, detail="Start date cannot be after end date.")
        
        if start_dt < date.today():
            raise HTTPException(status_code=400, detail="Cannot book dates in the past.")

        # FIX 2: HARD OVERLAP BLOCKER
        overlap_query = """
            SELECT id FROM bookings 
            WHERE listing_id = %s 
              AND status = 'confirmed'
              AND start_date <= %s 
              AND end_date >= %s
        """
        cursor.execute(overlap_query, (req.listing_id, end_dt, start_dt))
        if cursor.fetchone():
            raise HTTPException(
                status_code=400, 
                detail="Booking failed: This item is already reserved for the selected dates."
            )

        cursor.execute(
            "SELECT price_per_day, deposit_amount, is_available FROM listings WHERE id = %s",
            (req.listing_id,),
        )
        listing = cursor.fetchone()
        if not listing:
            raise HTTPException(status_code=404, detail="Item not found.")

        # FIX 3: Actual dynamic pricing calculation based on dates selected
        price_per_day = float(listing["price_per_day"] if isinstance(listing, dict) else listing[0])
        deposit_amount = float(listing["deposit_amount"] if isinstance(listing, dict) else listing[1])
        is_available = listing["is_available"] if isinstance(listing, dict) else listing[2]
        if not is_available:
            raise HTTPException(status_code=400, detail="This listing is no longer available.")
        rental_days = (end_dt - start_dt).days + 1
        total_price = price_per_day * rental_days
        amount_due = total_price + deposit_amount

        user_balance = float(current_user.get("wallet_balance", 0.0))
        if user_balance < amount_due:
            raise HTTPException(status_code=400, detail=f"Insufficient wallet credits. Required: Rs. {amount_due:,.2f} including the refundable deposit.")

        new_balance = user_balance - amount_due
        cursor.execute("UPDATE users SET wallet_balance = %s WHERE id = %s", (new_balance, user_id))

        # Insert booking and retrieve exact Booking ID to prevent duplicate ID bugs
        cursor.execute(
            """INSERT INTO bookings
               (user_id, listing_id, start_date, end_date, total_price, deposit_amount, status)
               VALUES (%s, %s, %s, %s, %s, %s, 'confirmed')""",
            (user_id, req.listing_id, req.start_date, req.end_date, total_price, deposit_amount)
        )
        booking_id = cursor.lastrowid

        # FIX 4: Bind transaction strictly to specific booking_id (not listing_id)
        cursor.execute(
            """INSERT INTO wallet_transactions (user_id, amount, transaction_type, reference_id)
               VALUES (%s, %s, 'BOOKING_PAYMENT', %s)""",
            (user_id, -amount_due, f"BOOKING-{booking_id}")
        )
        db.commit()

        return {
            "message": "Booking confirmed. Rental cost and refundable deposit were deducted from Rentify Credits.",
            "total_price": total_price,
            "deposit_amount": deposit_amount,
            "amount_paid": amount_due,
            "wallet_balance": new_balance,
        }
    finally:
        cursor.close()

@app.get("/api/bookings/my")
def get_my_bookings(current_user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.cursor()
    try:
        user_id = current_user["id"]
        cursor.execute("""
            SELECT b.id, b.listing_id, l.title, b.start_date, b.end_date, b.total_price, b.deposit_amount, b.status
            FROM bookings b
            JOIN listings l ON b.listing_id = l.id
            WHERE b.user_id = %s
            ORDER BY b.id DESC
        """, (user_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            if isinstance(r, dict):
                result.append(r)
            else:
                result.append({
                    "id": r[0], "listing_id": r[1], "title": r[2],
                    "start_date": str(r[3]), "end_date": str(r[4]),
                    "total_price": float(r[5]), "deposit_amount": float(r[6]), "status": r[7]
                })
        return result
    finally:
        cursor.close()

@app.post("/api/wallet/topup")
def wallet_topup(req: TopupRequest, current_user: dict = Depends(get_current_user)):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid top-up amount.")

    db = get_db()
    cursor = db.cursor()
    try:
        user_id = current_user["id"]
        current_bal = float(current_user.get("wallet_balance", 0.0))
        new_balance = current_bal + req.amount

        cursor.execute("UPDATE users SET wallet_balance = %s WHERE id = %s", (new_balance, user_id))
        cursor.execute(
            """INSERT INTO wallet_transactions (user_id, amount, transaction_type, reference_id)
               VALUES (%s, %s, 'TOPUP', %s)""",
            (user_id, req.amount, f"TOPUP-{random.randint(100000, 999999)}")
        )
        db.commit()

        return {
            "message": f"Added Rs. {req.amount:,.2f} in simulated demo credits. No real payment was charged.",
            "new_balance": new_balance,
        }
    finally:
        cursor.close()

@app.get("/api/wallet/transactions")
def get_wallet_transactions(current_user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.cursor()
    try:
        user_id = current_user["id"]
        cursor.execute("""
            SELECT id, amount, transaction_type, reference_id, created_at
            FROM wallet_transactions
            WHERE user_id = %s
            ORDER BY id DESC
        """, (user_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            if isinstance(r, dict):
                result.append(r)
            else:
                result.append({
                    "id": r[0], "amount": float(r[1]),
                    "transaction_type": r[2], "reference_id": r[3],
                    "created_at": str(r[4])
                })
        return result
    finally:
        cursor.close()

# -------------------------------------------------------------------
# ADMIN PANEL (SORTING & LOGIC FIXES)
# -------------------------------------------------------------------

@app.get("/api/admin/users")
def get_admin_users(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required.")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, full_name, email, role, wallet_balance, is_verified FROM users ORDER BY id DESC")
        rows = cursor.fetchall()
        result = []
        for r in rows:
            if isinstance(r, dict):
                result.append(r)
            else:
                result.append({
                    "id": r[0],
                    "full_name": r[1],
                    "email": r[2],
                    "role": r[3],
                    "wallet_balance": float(r[4]),
                    "is_verified": bool(r[5])
                })
        return result
    finally:
        cursor.close()

@app.get("/api/admin/transactions")
def get_admin_transactions(
    tx_type: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required.")

    db = get_db()
    cursor = db.cursor()
    try:
        query = """
            SELECT t.id, t.user_id, u.full_name, u.email, t.amount, t.transaction_type, t.reference_id, t.created_at
            FROM wallet_transactions t
            JOIN users u ON t.user_id = u.id
            WHERE 1=1
        """
        params = []

        if tx_type and tx_type != "ALL":
            query += " AND t.transaction_type = %s"
            params.append(tx_type)

        if search:
            query += " AND (t.reference_id LIKE %s OR u.email LIKE %s OR u.full_name LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        # FIX 5: Strictly sorting chronologically for proper Admin Panel logic
        query += " ORDER BY t.id DESC LIMIT 150"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        result = []
        for r in rows:
            if isinstance(r, dict):
                result.append(r)
            else:
                result.append({
                    "id": r[0], "user_id": r[1], "full_name": r[2], "email": r[3],
                    "amount": float(r[4]), "transaction_type": r[5],
                    "reference_id": r[6], "created_at": str(r[7])
                })
        return result
    finally:
        cursor.close()

@app.get("/api/admin/transactions/{tx_id}")
def get_admin_transaction_detail(tx_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required.")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("""
            SELECT t.id, t.user_id, u.full_name, u.email, u.wallet_balance,
                   t.amount, t.transaction_type, t.reference_id, t.created_at
            FROM wallet_transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = %s
        """, (tx_id,))
        tx = cursor.fetchone()
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction record not found.")

        tx_dict = tx if isinstance(tx, dict) else {
            "id": tx[0], "user_id": tx[1], "full_name": tx[2], "email": tx[3],
            "user_balance": float(tx[4]), "amount": float(tx[5]),
            "transaction_type": tx[6], "reference_id": tx[7], "created_at": str(tx[8])
        }

        # FIX 6: Connect inspector accurately using the exact Booking ID
        booking_info = None
        ref_id = tx_dict["reference_id"]
        if ref_id.startswith("BOOKING-"):
            try:
                booking_id = int(ref_id.replace("BOOKING-", ""))
                cursor.execute("""
                    SELECT b.id, b.start_date, b.end_date, b.total_price, b.status, l.title, l.location
                    FROM bookings b
                    JOIN listings l ON b.listing_id = l.id
                    WHERE b.id = %s
                """, (booking_id,))
                b_row = cursor.fetchone()
                if b_row:
                    booking_info = b_row if isinstance(b_row, dict) else {
                        "booking_id": b_row[0], "start_date": str(b_row[1]),
                        "end_date": str(b_row[2]), "total_price": float(b_row[3]),
                        "status": b_row[4], "listing_title": b_row[5], "location": b_row[6]
                    }
            except Exception:
                pass

        return {"transaction": tx_dict, "booking_info": booking_info}
    finally:
        cursor.close()

@app.post("/api/admin/transactions/{tx_id}/refund")
def refund_transaction(tx_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required.")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT user_id, amount, transaction_type, reference_id FROM wallet_transactions WHERE id = %s", (tx_id,))
        tx = cursor.fetchone()
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction record not found.")

        u_id = tx["user_id"] if isinstance(tx, dict) else tx[0]
        amt = float(tx["amount"] if isinstance(tx, dict) else tx[1])
        tx_type = tx["transaction_type"] if isinstance(tx, dict) else tx[2]
        ref_id = tx["reference_id"] if isinstance(tx, dict) else tx[3]

        if tx_type == "REFUND" or amt >= 0:
            raise HTTPException(status_code=400, detail="Only negative booking debit transactions can be reversed/refunded.")
        cursor.execute(
            "SELECT id FROM wallet_transactions WHERE transaction_type = 'REFUND' AND reference_id = %s",
            (f"REFUND-TX-{tx_id}",),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="This booking payment has already been refunded.")

        refund_amt = abs(amt)

        cursor.execute("SELECT wallet_balance FROM users WHERE id = %s", (u_id,))
        u_row = cursor.fetchone()
        cur_bal = float(u_row["wallet_balance"] if isinstance(u_row, dict) else u_row[0])
        new_bal = cur_bal + refund_amt

        cursor.execute("UPDATE users SET wallet_balance = %s WHERE id = %s", (new_bal, u_id))
        
        cursor.execute("""
            INSERT INTO wallet_transactions (user_id, amount, transaction_type, reference_id)
            VALUES (%s, %s, 'REFUND', %s)
        """, (u_id, refund_amt, f"REFUND-TX-{tx_id}"))

        # FIX 7: Refund correctly targets and cancels the specific booking by its ID
        if ref_id.startswith("BOOKING-"):
            try:
                booking_id = int(ref_id.replace("BOOKING-", ""))
                cursor.execute(
                    "UPDATE bookings SET status = 'cancelled' WHERE id = %s",
                    (booking_id,)
                )
            except Exception:
                pass

        db.commit()
        return {"message": f"Successfully refunded Rs. {refund_amt:,.2f} to user's wallet balance.", "new_balance": new_bal}
    finally:
        cursor.close()

@app.get("/api/admin/bookings")
def get_admin_bookings(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required.")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("""
            SELECT b.id, b.listing_id, u.full_name, u.email, l.title, b.start_date, b.end_date, b.total_price, b.status, b.created_at
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN listings l ON b.listing_id = l.id
            ORDER BY b.id DESC
        """)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            if isinstance(r, dict):
                result.append(r)
            else:
                result.append({
                    "id": r[0], "listing_id": r[1], "full_name": r[2], "email": r[3], "title": r[4],
                    "start_date": str(r[5]), "end_date": str(r[6]),
                    "total_price": float(r[7]), "status": r[8], "created_at": str(r[9])
                })
        return result
    finally:
        cursor.close()
