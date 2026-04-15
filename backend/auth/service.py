import json
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException
from jwt import InvalidTokenError


class AuthService:
    def __init__(self):
        self.users_db_path = ""
        self.jwt_secret = ""
        self.jwt_algorithm = "HS256"
        self.expire_minutes = 30

    def configure(self, users_db_path: str, jwt_secret_key: str, jwt_algorithm: str = "HS256", access_token_expire_minutes: int = 30):
        self.users_db_path = users_db_path
        self.jwt_secret = jwt_secret_key
        self.jwt_algorithm = jwt_algorithm
        self.expire_minutes = access_token_expire_minutes

    def normalize_email(self, email: str) -> str:
        return email.strip().lower()

    def _read_users(self) -> dict:
        try:
            with open(self.users_db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"users": []}

    def _write_users(self, data: dict):
        with open(self.users_db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_user(self, email: str, password: str):
        email = self.normalize_email(email)
        password = password.strip()
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

        db = self._read_users()
        users = db.setdefault("users", [])
        if any(u.get("email") == email for u in users):
            raise HTTPException(status_code=409, detail="User already exists")

        users.append(
            {
                "email": email,
                "password_hash": bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._write_users(db)

    def login_user(self, email: str, password: str) -> str:
        email = self.normalize_email(email)
        users = self._read_users().get("users", [])
        user = next((u for u in users if u.get("email") == email), None)

        password_hash = (user or {}).get("password_hash", "")
        try:
            ok = bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception:
            ok = False

        if not user or not ok:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": email,
                "iat": now,
                "exp": now + timedelta(minutes=self.expire_minutes),
            },
            self.jwt_secret,
            algorithm=self.jwt_algorithm,
        )
        return token

    def get_current_user_from_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
        except InvalidTokenError as e:
            raise HTTPException(status_code=401, detail="Invalid or expired token") from e

        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        email = self.normalize_email(email)
        users = self._read_users().get("users", [])
        user = next((u for u in users if u.get("email") == email), None)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    def change_password(self, email: str, current_password: str, new_password: str):
        email = self.normalize_email(email)
        current_password = current_password.strip()
        new_password = new_password.strip()

        if len(new_password) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
        if current_password == new_password:
            raise HTTPException(status_code=400, detail="New password must be different from current password")

        db = self._read_users()
        users = db.get("users", [])

        for user in users:
            if user.get("email") != email:
                continue

            try:
                ok = bcrypt.checkpw(current_password.encode("utf-8"), user.get("password_hash", "").encode("utf-8"))
            except Exception:
                ok = False

            if not ok:
                raise HTTPException(status_code=401, detail="Current password is incorrect")

            user["password_hash"] = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            user["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_users(db)
            return

        raise HTTPException(status_code=404, detail="User not found")

    def delete_user_by_email(self, email: str) -> bool:
        email = self.normalize_email(email)
        db = self._read_users()
        users = db.get("users", [])
        filtered = [u for u in users if u.get("email") != email]

        if len(filtered) == len(users):
            return False

        db["users"] = filtered
        self._write_users(db)
        return True


auth_service = AuthService()
