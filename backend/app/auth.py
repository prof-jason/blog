import hashlib
import hmac
import secrets
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator

from app.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "session"
Db = Annotated[sqlite3.Connection, Depends(get_db)]


class Credentials(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class User(BaseModel):
    id: int
    email: str


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(digest.hex(), digest_hex)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _start_session(db: sqlite3.Connection, response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO sessions (token_hash, user_id) VALUES (?, ?)", (_hash_token(token), user_id))
    db.commit()
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7)


def current_user(db: Db, session: Annotated[str | None, Cookie()] = None) -> User:
    if session:
        row = db.execute(
            "SELECT users.id, users.email FROM sessions JOIN users ON users.id = sessions.user_id "
            "WHERE sessions.token_hash = ?",
            (_hash_token(session),),
        ).fetchone()
        if row:
            return User(id=row["id"], email=row["email"])
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(creds: Credentials, response: Response, db: Db) -> User:
    try:
        cursor = db.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (creds.email, hash_password(creds.password)),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists")
    _start_session(db, response, cursor.lastrowid)
    return User(id=cursor.lastrowid, email=creds.email)


@router.post("/login")
def login(creds: Credentials, response: Response, db: Db) -> User:
    row = db.execute("SELECT id, password_hash FROM users WHERE email = ?", (creds.email,)).fetchone()
    if not row or not verify_password(creds.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    _start_session(db, response, row["id"])
    return User(id=row["id"], email=creds.email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, db: Db, session: Annotated[str | None, Cookie()] = None) -> None:
    if session:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(session),))
        db.commit()
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me")
def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user
