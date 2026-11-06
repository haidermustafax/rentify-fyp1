from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_home_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "FYP-I" not in response.text


def test_login_page_loads():
    assert client.get("/login").status_code == 200


def test_fyp1_listing_catalog_is_available():
    response = client.get("/api/listings")
    assert response.status_code == 200
    listings = response.json()
    assert listings
    assert {listing["category_id"] for listing in listings} <= {1, 2, 3, 4}
    assert all(listing["category_name"] != "Hostel & Short Stays" for listing in listings)


def test_listing_search_and_category_filter():
    electronics = client.get("/api/listings", params={"category_id": 2})
    assert electronics.status_code == 200
    assert electronics.json()
    assert all(item["category_id"] == 2 for item in electronics.json())

    search = client.get("/api/listings", params={"search": "PS5"})
    assert search.status_code == 200
    assert any("PS5" in item["title"] for item in search.json())


def test_listing_detail_is_public():
    listing = client.get("/api/listings").json()[0]
    response = client.get(f"/api/listings/{listing['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == listing["id"]
