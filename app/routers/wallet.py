from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.db import get_db_connection
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/wallet", tags=["Wallet"])

class TopupRequest(BaseModel):
    amount: float

@router.post("/topup")
def topup_wallet(data: TopupRequest, current_user: dict = Depends(get_current_user)):
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Update user wallet balance
            cursor.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE id = %s", (data.amount, current_user["id"]))
            # Log transaction
            cursor.execute(
                "INSERT INTO wallet_transactions (user_id, amount, transaction_type, reference_id) VALUES (%s, %s, 'topup', 'SANDBOX_TOPUP')",
                (current_user["id"], data.amount)
            )
            conn.commit()
            return {"message": f"Successfully added ${data.amount:.2f} to your Rentify Credits."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/transactions")
def get_wallet_history(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM wallet_transactions WHERE user_id = %s ORDER BY created_at DESC",
                (current_user["id"],)
            )
            return cursor.fetchall()
    finally:
        conn.close()
