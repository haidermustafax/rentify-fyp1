from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import date
from app.db import get_db_connection
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])

class BookingCreate(BaseModel):
    listing_id: int
    start_date: date
    end_date: date

@router.post("")
def create_booking(booking: BookingCreate, current_user: dict = Depends(get_current_user)):
    if booking.start_date >= booking.end_date or booking.start_date < date.today():
        raise HTTPException(status_code=400, detail="Invalid rental dates selection.")

    conn = get_db_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            # 1. Date Overlap Checking
            overlap_query = """
                SELECT id FROM bookings 
                WHERE listing_id = %s 
                AND status = 'confirmed'
                AND (%s < end_date AND %s > start_date)
            """
            cursor.execute(overlap_query, (booking.listing_id, booking.start_date, booking.end_date))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="This item is already booked for selected dates.")

            # 2. Get Pricing
            cursor.execute("SELECT price_per_day, deposit_amount FROM listings WHERE id = %s", (booking.listing_id,))
            listing = cursor.fetchone()
            if not listing:
                raise HTTPException(status_code=404, detail="Listing not found")

            days = (booking.end_date - booking.start_date).days
            total_rental_cost = float(listing["price_per_day"]) * days
            deposit = float(listing["deposit_amount"])
            total_required = total_rental_cost + deposit

            # 3. Check Wallet Balance
            cursor.execute("SELECT wallet_balance FROM users WHERE id = %s FOR UPDATE", (current_user["id"],))
            user_wallet = float(cursor.fetchone()["wallet_balance"])

            if user_wallet < total_required:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Insufficient Credits. Total needed: ${total_required:.2f} (${total_rental_cost:.2f} Rent + ${deposit:.2f} Security Deposit)"
                )

            # 4. Process Payment
            new_balance = user_wallet - total_required
            cursor.execute("UPDATE users SET wallet_balance = %s WHERE id = %s", (new_balance, current_user["id"]))

            # 5. Insert Booking Record
            cursor.execute(
                """INSERT INTO bookings (user_id, listing_id, start_date, end_date, total_price, deposit_amount, status)
                   VALUES (%s, %s, %s, %s, %s, %s, 'confirmed')""",
                (current_user["id"], booking.listing_id, booking.start_date, booking.end_date, total_rental_cost, deposit)
            )
            
            # 6. Log Wallet Transaction
            cursor.execute(
                """INSERT INTO wallet_transactions (user_id, amount, transaction_type, reference_id)
                   VALUES (%s, %s, 'payment', %s)""",
                (current_user["id"], -total_required, f"Booking Listing #{booking.listing_id}")
            )

            conn.commit()
            return {"message": "Booking successful! Payment deducted from Rentify Credits."}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/my")
def get_my_bookings(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT b.*, l.title, l.location 
                FROM bookings b
                JOIN listings l ON b.listing_id = l.id
                WHERE b.user_id = %s
                ORDER BY b.created_at DESC
            """
            cursor.execute(sql, (current_user["id"],))
            return cursor.fetchall()
    finally:
        conn.close()
