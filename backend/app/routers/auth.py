from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..dependencies import get_current_key, get_db
from ..models import APIKey
from ..schemas import AuthSessionCreate, AuthSessionResponse, GenericMessage
from ..security import create_session_token, verify_api_key


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/session", response_model=AuthSessionResponse)
def create_session(payload: AuthSessionCreate, request: Request, db: Session = Depends(get_db)):
    active_keys = db.query(APIKey).filter(APIKey.active.is_(True)).all()
    matched_key = None
    for key in active_keys:
        if verify_api_key(payload.api_key, key.key_salt, key.key_hash):
            matched_key = key
            break

    if matched_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    matched_key.last_used_at = datetime.now(timezone.utc)
    db.add(matched_key)
    db.commit()

    token, expires_in = create_session_token(request.app.state.settings, matched_key.id)
    return AuthSessionResponse(
        access_token=token,
        expires_in=expires_in,
        key_id=matched_key.id,
        key_name=matched_key.name,
    )


@router.delete("/session", response_model=GenericMessage)
def delete_session(_current_key: APIKey = Depends(get_current_key)):
    return GenericMessage(message="Session invalidated client-side.")
