"""
Export Service

Provides helper utilities for emailing summaries and generating PDF download
placeholders. In production this should integrate with AWS SES/S3.
"""

import base64
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    import boto3  # type: ignore
    from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
except ImportError:  # pragma: no cover - boto3 optional in dev
    boto3 = None  # type: ignore
    BotoCoreError = ClientError = Exception  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class SummaryPayload:
    meeting_id: str
    persona: str
    summary: str
    topics: List[str]
    actions: List[str]


def _format_email_body(payload: SummaryPayload, recipient: str) -> str:
    topic_lines = "\n".join(f"- {topic}" for topic in payload.topics) or "Inga ämnen registrerade."
    action_lines = (
        "\n".join(f"- {action}" for action in payload.actions) or "Inga åtgärdspunkter registrerade."
    )
    return (
        f"Hej {recipient},\n\n"
        f"Här är sammanfattningen för mötet {payload.meeting_id} ur {payload.persona}-perspektiv:\n\n"
        f"{payload.summary}\n\n"
        f"Ämnen:\n{topic_lines}\n\n"
        f"Åtgärdspunkter:\n{action_lines}\n\n"
        "Skickat automatiskt av Meetmind."
    )


def _send_with_ses(subject: str, body: str, to_email: str) -> bool:
    if not boto3:
        logger.warning("boto3 not installed; skipping SES email send.")
        return False

    sender = os.getenv("SES_FROM_ADDRESS")
    region = os.getenv("AWS_REGION", "us-west-2")

    if not sender:
        logger.warning("SES_FROM_ADDRESS not configured; skipping SES email send.")
        return False

    try:
        client = boto3.client("ses", region_name=region)
        client.send_email(
            Source=sender,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        return True
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover - external service
        logger.error("Failed to send SES email: %s", exc)
        return False


def send_summary_email(payload: SummaryPayload, to_email: str, subject: Optional[str] = None) -> Dict[str, str]:
    """
    Send meeting summary via email. Falls back to logging in local development.
    """
    subject_line = subject or f"Meetmind sammanfattning – {payload.meeting_id} ({payload.persona})"
    body = _format_email_body(payload, to_email)

    delivered = _send_with_ses(subject_line, body, to_email)

    if not delivered:
        # Log for local development and treat as success for demo purposes
        logger.info("[DEV] Email (simulated) to %s\nSubject: %s\nBody:\n%s", to_email, subject_line, body)

    return {
        "success": True,
        "delivery_mode": "ses" if delivered else "simulated",
    }


def generate_summary_pdf(payload: SummaryPayload) -> Dict[str, str]:
    """
    Generate a lightweight PDF placeholder encoded as data URL.
    In production this should upload to S3 and return a presigned URL.
    """
    lines = [
        f"Meetmind summary for {payload.meeting_id}",
        f"Persona: {payload.persona}",
        "",
        "Summary:",
        payload.summary,
        "",
        "Topics:",
    ]
    lines.extend(f"- {topic}" for topic in payload.topics)
    lines.append("")
    lines.append("Action Items:")
    lines.extend(f"- {action}" for action in payload.actions)

    text = "\n".join(lines)
    # Encode as simple text-based PDF placeholder
    pdf_bytes = text.encode("utf-8")
    b64_pdf = base64.b64encode(pdf_bytes).decode("ascii")

    url = f"data:application/pdf;base64,{b64_pdf}"
    expires_at = (datetime.utcnow() + timedelta(minutes=15)).isoformat() + "Z"

    logger.info("Generated simulated PDF data URL for %s (%s)", payload.meeting_id, payload.persona)

    return {
        "url": url,
        "filename": f"{payload.meeting_id}_{payload.persona}_summary.pdf",
        "expires_at": expires_at,
    }
