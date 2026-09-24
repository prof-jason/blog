from app.auth import hash_password, verify_password

CREDS = {"email": "Student@Example.com", "password": "correct horse"}


def test_password_hashing_round_trip():
    stored = hash_password("s3cret-pass")
    assert stored.startswith("scrypt$")
    assert "s3cret-pass" not in stored
    assert verify_password("s3cret-pass", stored)
    assert not verify_password("wrong-pass", stored)


def test_signup_creates_user_and_signs_in(client):
    response = client.post("/api/auth/signup", json=CREDS)
    assert response.status_code == 201
    assert response.json()["email"] == "student@example.com"
    assert client.get("/api/auth/me").json()["email"] == "student@example.com"


def test_signup_rejects_duplicate_email_case_insensitively(client):
    client.post("/api/auth/signup", json=CREDS)
    response = client.post("/api/auth/signup", json={**CREDS, "email": "STUDENT@example.com"})
    assert response.status_code == 409


def test_signup_validates_input(client):
    assert client.post("/api/auth/signup", json={"email": "nope", "password": "password123"}).status_code == 422
    assert client.post("/api/auth/signup", json={"email": "a@b.co", "password": "short"}).status_code == 422


def test_login_with_correct_and_incorrect_password(client):
    client.post("/api/auth/signup", json=CREDS)
    client.cookies.clear()

    assert client.post("/api/auth/login", json={**CREDS, "password": "wrong password"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401

    response = client.post("/api/auth/login", json=CREDS)
    assert response.status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "student@example.com"


def test_login_unknown_user(client):
    assert client.post("/api/auth/login", json=CREDS).status_code == 401


def test_me_requires_session(client):
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("session", "forged-token")
    assert client.get("/api/auth/me").status_code == 401


def test_logout_ends_session(client):
    client.post("/api/auth/signup", json=CREDS)
    token = client.cookies.get("session")
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("session", token)  # replaying the old token must not work
    assert client.get("/api/auth/me").status_code == 401
