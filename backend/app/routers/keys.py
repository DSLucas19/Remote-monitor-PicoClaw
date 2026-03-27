from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..dependencies import get_current_key, get_db
from ..models import APIKey
from ..schemas import GenericMessage, KeyCreateRequest, KeyCreateResponse, KeyItem
from ..security import generate_api_key, hash_api_key, key_prefix


router = APIRouter(prefix="/api/keys", tags=["keys"])


@router.get("", response_model=list[KeyItem])
def list_keys(
    _current_key: APIKey = Depends(get_current_key),
    db: Session = Depends(get_db),
):
    keys = db.query(APIKey).order_by(APIKey.created_at.desc()).all()
    return [
        KeyItem(
            id=item.id,
            name=item.name,
            prefix=item.key_prefix,
            created_at=item.created_at,
            last_used_at=item.last_used_at,
            active=item.active,
        )
        for item in keys
    ]


@router.post("", response_model=KeyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_key(
    payload: KeyCreateRequest,
    _current_key: APIKey = Depends(get_current_key),
    db: Session = Depends(get_db),
):
    plain_key = generate_api_key()
    salt, hashed = hash_api_key(plain_key)
    new_item = APIKey(
        name=payload.name.strip(),
        key_prefix=key_prefix(plain_key),
        key_hash=hashed,
        key_salt=salt,
        active=True,
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return KeyCreateResponse(
        id=new_item.id,
        name=new_item.name,
        prefix=new_item.key_prefix,
        api_key=plain_key,
        created_at=new_item.created_at,
    )


@router.post("/{key_id}/revoke", response_model=GenericMessage)
def revoke_key(
    key_id: int,
    current_key: APIKey = Depends(get_current_key),
    db: Session = Depends(get_db),
):
    item = db.query(APIKey).filter(APIKey.id == key_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    if item.id == current_key.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot revoke current session key.")
    item.active = False
    db.add(item)
    db.commit()
    return GenericMessage(message="Key revoked.")

