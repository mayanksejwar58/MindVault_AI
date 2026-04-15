from fastapi import APIRouter, Depends

from .dependencies import get_current_user
from .models import ChangePasswordRequest, LoginRequest, SignupRequest
from .service import auth_service

router = APIRouter()


@router.post("/signup")
def signup(payload: SignupRequest):
    auth_service.create_user(payload.email, payload.password)
    return {"status": "success", "message": "Signup successful"}


@router.post("/login")
def login(payload: LoginRequest):
    return {"access_token": auth_service.login_user(payload.email, payload.password), "token_type": "bearer"}


@router.post("/account/change-password")
def change_password(payload: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    auth_service.change_password(current_user["email"], payload.current_password, payload.new_password)
    return {"status": "success", "message": "Password changed successfully"}
