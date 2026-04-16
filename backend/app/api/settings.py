"""User settings API endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymongo.database import Database

from app.core.database import get_db
from app.api.auth import get_current_user_light, get_org_id_light
from app.services.user_settings import (
    get_document_uploaded_email_disabled,
    set_document_uploaded_email_disabled,
)


router = APIRouter()


class NotificationSettingsResponse(BaseModel):
    """Effective notification settings for the current user and org."""

    document_uploaded_email_enabled: bool


class NotificationSettingsPatch(BaseModel):
    """Patch request for per-pack notification opt-out."""

    document_uploaded_email_enabled: bool


@router.get("/notifications", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db),
):
    clerk_user_id = current_user.get("clerk_user_id")
    disabled = get_document_uploaded_email_disabled(
        org_id=org_id, clerk_user_id=clerk_user_id, db=db
    )
    return NotificationSettingsResponse(
        document_uploaded_email_enabled=not disabled,
    )


@router.patch("/notifications", response_model=NotificationSettingsResponse)
async def patch_notification_settings(
    body: NotificationSettingsPatch,
    current_user: dict = Depends(get_current_user_light),
    org_id: str = Depends(get_org_id_light),
    db: Database = Depends(get_db),
):
    clerk_user_id = current_user.get("clerk_user_id")
    # Store opt-out flag (disabled) but expose enabled boolean in API.
    set_document_uploaded_email_disabled(
        org_id=org_id,
        clerk_user_id=clerk_user_id,
        disabled=not body.document_uploaded_email_enabled,
        db=db,
    )
    return NotificationSettingsResponse(
        document_uploaded_email_enabled=body.document_uploaded_email_enabled,
    )

