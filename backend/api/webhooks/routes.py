# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Webhook receiver endpoints.

Receives incoming webhooks from external services and triggers
workflow executions based on configured webhook triggers.

Features:
- HMAC signature verification (optional)
- IP whitelist filtering (optional)
- Payload transformation
- Execution logging
"""

import hashlib
import hmac
import ipaddress
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session

from db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def verify_signature(payload: bytes, secret: str, signature: str) -> bool:
    """
    Verify HMAC-SHA256 webhook signature.

    Supports common signature formats:
    - sha256=<hex>
    - <hex>
    """
    if not signature or not secret:
        return False

    # Handle "sha256=" prefix
    if signature.startswith("sha256="):
        signature = signature[7:]

    # Calculate expected signature
    expected = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(expected.lower(), signature.lower())


def check_ip_whitelist(client_ip: str, allowed_ips: list) -> bool:
    """
    Check if client IP is in the allowed list.

    Supports:
    - Individual IPs: "192.168.1.100"
    - CIDR ranges: "192.168.1.0/24"
    - "any" to allow all
    """
    if not allowed_ips or "any" in allowed_ips:
        return True

    try:
        client = ipaddress.ip_address(client_ip)

        for allowed in allowed_ips:
            try:
                if "/" in allowed:
                    # CIDR range
                    network = ipaddress.ip_network(allowed, strict=False)
                    if client in network:
                        return True
                else:
                    # Single IP
                    if client == ipaddress.ip_address(allowed):
                        return True
            except ValueError:
                continue

        return False
    except ValueError:
        logger.warning(f"Invalid client IP: {client_ip}")
        return False


@router.post("/trigger/{trigger_id}")
async def receive_webhook(
    trigger_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive and process an incoming webhook.

    This endpoint is called by external services to trigger workflow execution.
    Each trigger has its own URL: /api/webhooks/trigger/{trigger_id}

    Security:
    - Optional HMAC signature verification (X-Webhook-Signature header)
    - Optional IP whitelist
    """
    from models.workflow_trigger import WorkflowTrigger, TriggerLog, TriggerType, TriggerStatus
    from core.task_queue import task_queue, TaskPriority

    # Load trigger
    trigger = db.query(WorkflowTrigger).filter(
        WorkflowTrigger.id == trigger_id,
        WorkflowTrigger.trigger_type == TriggerType.WEBHOOK.value
    ).first()

    if not trigger:
        logger.warning(f"Webhook received for unknown trigger: {trigger_id}")
        raise HTTPException(status_code=404, detail="Trigger not found")

    if not trigger.enabled:
        logger.info(f"Webhook received for disabled trigger: {trigger_id}")
        raise HTTPException(status_code=403, detail="Trigger is disabled")

    config = trigger.config or {}

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    # Check IP whitelist
    allowed_ips = config.get("allowed_ips", [])
    if allowed_ips and not check_ip_whitelist(client_ip, allowed_ips):
        logger.warning(f"Webhook rejected: IP {client_ip} not in whitelist for trigger {trigger_id}")
        raise HTTPException(status_code=403, detail="IP not allowed")

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature if required
    if config.get("require_signature", False) and trigger.webhook_secret:
        signature = (
            request.headers.get("X-Webhook-Signature") or
            request.headers.get("X-Hub-Signature-256") or  # GitHub
            request.headers.get("X-Signature-256") or
            request.headers.get("Stripe-Signature")  # Stripe (partial support)
        )

        if not signature:
            logger.warning(f"Webhook rejected: Missing signature for trigger {trigger_id}")
            raise HTTPException(status_code=401, detail="Missing signature")

        if not verify_signature(body, trigger.webhook_secret, signature):
            logger.warning(f"Webhook rejected: Invalid signature for trigger {trigger_id}")
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        if body:
            payload = await request.json()
        else:
            payload = {}
    except Exception:
        # Handle non-JSON payloads
        payload = {"raw": body.decode('utf-8', errors='replace')}

    logger.info(f"Webhook received for trigger {trigger_id} from {client_ip}")

    # Create trigger log
    trigger_log = TriggerLog(
        trigger_id=trigger.id,
        triggered_at=datetime.now(timezone.utc),
        status=TriggerStatus.PENDING.value,
        trigger_source=client_ip,
        trigger_payload=payload
    )
    db.add(trigger_log)
    db.flush()

    # Build input data
    input_data = build_input_from_webhook(payload, config)

    try:
        # Enqueue workflow execution
        task_id = await task_queue.enqueue(
            "execute_triggered_workflow",
            {
                "trigger_id": trigger.id,
                "trigger_log_id": trigger_log.id,
                "workflow_id": trigger.workflow_id,
                "trigger_type": "webhook",
                "input_data": input_data,
                "trigger_source": client_ip,
            },
            priority=TaskPriority.NORMAL
        )

        # Update trigger log
        trigger_log.task_id = task_id

        # Update trigger stats
        trigger.last_triggered_at = datetime.now(timezone.utc)
        trigger.trigger_count = (trigger.trigger_count or 0) + 1

        db.commit()

        logger.info(f"Webhook trigger {trigger_id} queued workflow execution (task: {task_id})")

        return {
            "status": "accepted",
            "trigger_id": trigger_id,
            "task_id": task_id,
            "trigger_log_id": trigger_log.id
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing webhook for trigger {trigger_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process webhook")


def build_input_from_webhook(payload: dict, config: dict) -> dict:
    """
    Build workflow input data from webhook payload.

    Uses input_mapping from config to transform payload fields
    into workflow input structure.
    """
    input_mapping = config.get("input_mapping", {})

    if not input_mapping:
        # Default: pass entire payload as context
        return {
            "task": "Process webhook data",
            "context": {
                "source": "webhook",
                "payload": payload
            }
        }

    input_data = {}

    for target_key, source_path in input_mapping.items():
        # Handle JSONPath-like syntax (simplified)
        value = extract_value(payload, source_path)

        # Handle nested target keys
        parts = target_key.split(".")
        target = input_data
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value

    return input_data


def extract_value(data: dict, path: str) -> any:
    """
    Extract value from nested dict using simple path syntax.

    Supports:
    - "$.field" or "field" - top level field
    - "$.field.nested" - nested field
    - Literal strings without $ prefix
    """
    if not path.startswith("$"):
        # Literal value
        return path

    # Remove "$." prefix
    path = path.lstrip("$.")

    parts = path.split(".")
    current = data

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current


@router.get("/trigger/{trigger_id}/test")
async def test_webhook_endpoint(
    trigger_id: int,
    db: Session = Depends(get_db)
):
    """
    Test that a webhook trigger exists and is configured.

    Returns the webhook URL and configuration (without secrets).
    Useful for testing connectivity.
    """
    from models.workflow_trigger import WorkflowTrigger, TriggerType

    trigger = db.query(WorkflowTrigger).filter(
        WorkflowTrigger.id == trigger_id,
        WorkflowTrigger.trigger_type == TriggerType.WEBHOOK.value
    ).first()

    if not trigger:
        raise HTTPException(status_code=404, detail="Webhook trigger not found")

    config = trigger.config or {}

    return {
        "status": "ok",
        "trigger_id": trigger.id,
        "workflow_id": trigger.workflow_id,
        "enabled": trigger.enabled,
        "requires_signature": config.get("require_signature", False),
        "has_ip_whitelist": bool(config.get("allowed_ips")),
        "trigger_count": trigger.trigger_count,
        "last_triggered_at": trigger.last_triggered_at.isoformat() if trigger.last_triggered_at else None
    }
