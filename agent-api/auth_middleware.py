"""Firebase auth middleware for FastAPI.

Validates Firebase ID token from Authorization header and returns FirebaseUser.
"""

from fastapi import Depends, HTTPException, Request

from commons.firebase_auth import verify_token
from commons.types import FirebaseUser


async def get_current_user(request: Request) -> FirebaseUser:
    """FastAPI dependency: extract and validate Firebase token from request.

    Usage:
        @app.post("/chat")
        async def chat(user: FirebaseUser = Depends(get_current_user)):
            ...
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split("Bearer ")[1]

    try:
        user = verify_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {e}")

    return user
