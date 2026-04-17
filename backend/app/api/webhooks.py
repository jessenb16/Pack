"""Clerk webhook endpoints."""
import json
import logging

from fastapi import APIRouter, Request, HTTPException, status
from svix.webhooks import Webhook as SvixWebhook
from svix.exceptions import WebhookVerificationError

from app.core.config import settings
from app.core.clerk_auth import update_clerk_user
from app.core.database import get_db
from app.services.org_settings import get_org_settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/clerk")
async def clerk_webhook(request: Request):
    """
    Handle Clerk webhook events.
    Clerk signs webhooks with Svix; we verify using CLERK_WEBHOOK_SECRET (whsec_...).
    Requests with invalid or missing signature are rejected.
    """
    if not settings.CLERK_WEBHOOK_SECRET:
        logger.error("CLERK_WEBHOOK_SECRET is not set; rejecting webhook")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook signing secret not configured",
        )

    body = await request.body()
    headers = {
        "svix-id": request.headers.get("svix-id", ""),
        "svix-timestamp": request.headers.get("svix-timestamp", ""),
        "svix-signature": request.headers.get("svix-signature", ""),
    }

    try:
        wh = SvixWebhook(settings.CLERK_WEBHOOK_SECRET)
        wh.verify(body, headers)
    except WebhookVerificationError as e:
        logger.warning("Webhook signature verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        ) from e

    try:
        event = json.loads(body.decode("utf-8"))
        event_type = event.get("type")
        data = event.get("data", {})

        logger.info("Received Clerk webhook event: %s", event_type)

        if event_type == "organization.created":
            db = get_db()
            clerk_org_id = data.get("id")
            if clerk_org_id:
                get_org_settings(clerk_org_id, db)
                logger.info("Initialized org_settings for organization: %s", clerk_org_id)

        if event_type in ("user.created", "user.updated"):
            clerk_user_id = data.get("id")
            last_name = (data.get("last_name") or "").strip()
            if clerk_user_id and last_name:
                external_accounts = data.get("external_accounts") or []
                is_google = False
                if isinstance(external_accounts, list):
                    for acct in external_accounts:
                        if not isinstance(acct, dict):
                            continue
                        provider = (acct.get("provider") or acct.get("provider_name") or "").lower()
                        if "google" in provider:
                            is_google = True
                            break

                unsafe_meta = data.get("unsafe_metadata") or {}
                pack_last_name_set = isinstance(unsafe_meta, dict) and unsafe_meta.get("packLastNameSet") is True

                if is_google and not pack_last_name_set:
                    updated = update_clerk_user(clerk_user_id, {"last_name": ""})
                    if updated is not None:
                        logger.info(
                            "Cleared Google-provided last_name for Clerk user %s (webhook: %s)",
                            clerk_user_id,
                            event_type,
                        )
                    else:
                        logger.warning(
                            "Failed clearing last_name for Clerk user %s (webhook: %s)",
                            clerk_user_id,
                            event_type,
                        )

        return {"received": True}
    except Exception as e:
        logger.error("Error processing Clerk webhook: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook",
        ) from e

