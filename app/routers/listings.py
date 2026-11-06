from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel
from app.db import get_db_connection
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/listings", tags=["Listings"])

class ListingCreate(BaseModel):
    category_id: int
    title: str
    description: str
    price_per_day: float
    deposit_amount: float
    location: str

@router.get("")
def get_listings(category_id: Optional[int] = None, search: Optional[str] = None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT l.*, c.name as category_name 
                FROM listings l
                JOIN categories c ON l.category_id = c.id
                WHERE l.is_available = TRUE
            """
            params = []
            if category_id:
                sql += " AND l.category_id = %s"
                params.append(category_id)
            if search:
                sql += " AND (l.title LIKE %s OR l.description LIKE %s)"
                params.extend([f"%{search}%", f"%{search}%"])
            
            sql += " ORDER BY l.created_at DESC"
            cursor.execute(sql, params)
            return cursor.fetchall()
    finally:
        conn.close()

# NEW: Fetch a single item by ID
@router.get("/{listing_id}")
def get_single_listing(listing_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT l.*, c.name as category_name 
                FROM listings l
                JOIN categories c ON l.category_id = c.id
                WHERE l.id = %s
            """, (listing_id,))
            item = cursor.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="Item not found")
            return item
    finally:
        conn.close()

@router.post("")
def create_listing(item: ListingCreate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO listings (category_id, title, description, price_per_day, deposit_amount, location)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (item.category_id, item.title, item.description, item.price_per_day, item.deposit_amount, item.location)
            )
            conn.commit()
            return {"message": "Listing created successfully!"}
    finally:
        conn.close()
