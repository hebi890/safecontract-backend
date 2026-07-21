import json
import os
from dataclasses import dataclass
from typing import Optional

import firebase_admin
from fastapi import Header, HTTPException
from firebase_admin import auth, credentials


def init_firebase() -> None:
    if firebase_admin._apps:
        return

    raw_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    file_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE")

    if raw_json:
        cred = credentials.Certificate(json.loads(raw_json))
    elif file_path:
        cred = credentials.Certificate(file_path)
    else:
        raise RuntimeError(
            "Missing Firebase Admin credentials. "
            "Set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_FILE."
        )

    firebase_admin.initialize_app(cred)


def is_anonymous_uid(uid: str) -> bool:
    """Return True only when Firebase confirms that the UID is anonymous."""
    uid = (uid or "").strip()
    if not uid:
        return False

    try:
        user = auth.get_user(uid)
    except Exception:
        # If Firebase cannot confirm the account type, do not allow a transfer.
        return False

    return not user.email and not list(user.provider_data or [])


def delete_firebase_user(uid: str) -> None:
    auth.delete_user(uid)


@dataclass
class CurrentUser:
    uid: str
    email: Optional[str]
    name: Optional[str]
    provider: Optional[str]
    is_anonymous: bool


def is_google_user(current_user: CurrentUser) -> bool:
    return (
        not current_user.is_anonymous
        and current_user.provider == "google.com"
        and bool((current_user.email or "").strip())
    )


def get_current_user(authorization: Optional[str] = Header(default=None)) -> CurrentUser:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    try:
        decoded = auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    firebase_data = decoded.get("firebase", {}) or {}
    sign_in_provider = firebase_data.get("sign_in_provider")
    identities = firebase_data.get("identities", {}) or {}
    # Match Flutter's providerData check: an account linked with Google is a
    # Google account even if Firebase refreshed the token through another
    # linked sign-in method.
    provider = "google.com" if identities.get("google.com") else sign_in_provider

    return CurrentUser(
        uid=decoded["uid"],
        email=decoded.get("email"),
        name=decoded.get("name"),
        provider=provider,
        is_anonymous=(sign_in_provider == "anonymous"),
    )
