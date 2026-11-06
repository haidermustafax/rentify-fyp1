import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from app.db import get_db_connection

def get_ai_recommendations(user_id: int, top_n: int = 3):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Fetch all active listings
            cursor.execute("""
                SELECT l.id, l.title, l.description, l.price_per_day, l.location, c.name as category_name 
                FROM listings l 
                JOIN categories c ON l.category_id = c.id 
                WHERE l.is_available = TRUE
            """)
            listings = cursor.fetchall()

            if not listings or len(listings) < 2:
                return listings  # Not enough items to compute similarity

            # 2. Load into Pandas DataFrame
            df = pd.DataFrame(listings)
            # Combine text features for the AI to analyze
            df['content'] = df['title'] + " " + df['description'] + " " + df['category_name']

            # 3. Compute TF-IDF Matrix (Extracting keywords)
            tfidf = TfidfVectorizer(stop_words='english')
            tfidf_matrix = tfidf.fit_transform(df['content'])

            # 4. Fetch the user's past bookings
            cursor.execute("SELECT listing_id FROM bookings WHERE user_id = %s", (user_id,))
            user_bookings = cursor.fetchall()

            if not user_bookings:
                # If user is new and has no history, return the latest items
                return listings[:top_n]

            booked_ids = [b["listing_id"] for b in user_bookings]
            
            # 5. Find the row indices of the items the user booked
            booked_indices = df[df['id'].isin(booked_ids)].index.tolist()

            if not booked_indices:
                return listings[:top_n]

            # 6. Calculate Cosine Similarity (How similar is every item to the booked items?)
            cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)
            
            # Get average similarity score across all items the user previously booked
            sim_scores = cosine_sim[booked_indices].mean(axis=0)

            df['similarity'] = sim_scores
            
            # 7. Filter out items they already booked, sort by highest similarity
            recs = df[~df['id'].isin(booked_ids)].sort_values(by='similarity', ascending=False)

            # Return the top N recommendations as a dictionary for FastAPI
            return recs.head(top_n).drop(columns=['content', 'similarity']).to_dict(orient='records')
    finally:
        conn.close()
