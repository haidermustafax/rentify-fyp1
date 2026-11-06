from fastapi import APIRouter, HTTPException, Depends
from app.db import get_db_connection
from app.dependencies import require_admin

router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(require_admin)])

@router.get("/bookings")
def get_all_bookings():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT b.*, l.title, u.full_name as user_name, u.email as user_email
                FROM bookings b
                JOIN listings l ON b.listing_id = l.id
                JOIN users u ON b.user_id = u.id
                ORDER BY b.created_at DESC
            """)
            return cursor.fetchall()
    finally:
        conn.close()

@router.post("/bookings/{booking_id}/complete")
def complete_booking_and_refund(booking_id: int):
    conn = get_db_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM bookings WHERE id = %s FOR UPDATE", (booking_id,))
            booking = cursor.fetchone()
            if not booking or booking["status"] != "confirmed":
                raise HTTPException(status_code=400, detail="Invalid booking or already completed.")
            
            deposit = float(booking["deposit_amount"])
            user_id = booking["user_id"]
            
            # 1. Update Booking Status
            cursor.execute("UPDATE bookings SET status = 'completed' WHERE id = %s", (booking_id,))
            
            # 2. Refund Deposit to Wallet
            if deposit > 0:
                cursor.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE id = %s", (deposit, user_id))
                cursor.execute(
                    "INSERT INTO wallet_transactions (user_id, amount, transaction_type, reference_id) VALUES (%s, %s, 'refund', %s)",
                    (user_id, deposit, f"Deposit Refund Booking #{booking_id}")
                )
            conn.commit()
            return {"message": f"Booking marked completed! ${deposit} security deposit refunded."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
