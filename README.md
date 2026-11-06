# Rentify — FYP-I Milestone

Rentify is a centralized rental marketplace developed for the FYP-I milestone.
This copy intentionally contains only the FYP-I scope:

- Requirements and API foundation
- MySQL database schema and seed data
- User registration, email verification, login, and JWT authentication
- Email-based two-step verification after password login
- Home/furniture, electronics, car-rental, and event-rental categories
- Listing details, category filtering, text search, and a responsive frontend
- FastAPI REST endpoints with Swagger/OpenAPI documentation

## Deferred to FYP-II

Hostel and short-stay listings, AI recommendations, Rentify Credits wallet
top-ups, booking/payment workflows, refundable-deposit processing, and the
comprehensive administration dashboard are intentionally excluded from this
milestone snapshot. They remain in the full project copy at
`/home/kali/Desktop/rentify-copy`.

## Technology

- Python 3
- FastAPI and Uvicorn
- MySQL with PyMySQL and parameterized SQL
- HTML, CSS, Bootstrap, and JavaScript
- JWT authentication and bcrypt password hashing
- SMTP email verification

## Local setup

1. Install Python 3.12, MySQL Server, and VS Code.
2. Create a Windows or Linux virtual environment:

   ```bash
   python3 -m venv .venv
   ```

3. Install dependencies:

   ```bash
   .venv/bin/python -m pip install -r requirements.txt
   ```

   On Windows, use `.venv\Scripts\python.exe` instead.

4. Copy `.env.example` to `.env` and set the local MySQL credentials,
   database name, a random `SECRET_KEY` of at least 32 characters, and SMTP
   settings for verification email.
5. Execute `sql/schema.sql` in MySQL Workbench or the MySQL client. The script
   creates the `rentify_db` database, four FYP-I categories, and 18 active
   FYP-I listings.
6. Start the server:

   ```bash
   .venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   On Windows, use:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

Open `http://127.0.0.1:8000` for the marketplace and
`http://127.0.0.1:8000/docs` for the API documentation.

## FYP-I demonstration checklist

1. Show the project structure and explain the separation between frontend,
   FastAPI backend, database layer, authentication, and static assets.
2. Register a user and complete email verification.
3. Sign in and show that the protected account endpoint requires a token.
4. Browse the four categories and open listing details.
5. Search for a listing and demonstrate category filtering.
6. Open Swagger UI and explain the listing and authentication endpoints.
7. Show the MySQL tables and seeded FYP-I data in MySQL Workbench.

## Academic integrity

Keep the commit history and project notes truthful. Explain which parts you
implemented, tested, or learned with assistance. Do not claim that a feature
was independently written if it was not. The full FYP-II features are clearly
marked as deferred in this milestone copy.
