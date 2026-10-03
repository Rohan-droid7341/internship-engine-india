"""Send a one-time apology email to subscribers."""

from __future__ import annotations

import os
import time
from html import escape

import httpx

from intern_engine import config, mailer

_APOLOGY_SUBJECT = "Please ignore our last email alert — our apologies!"

_APOLOGY_HTML = """<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:580px;margin:0 auto;padding:24px 16px;color:#222;line-height:1.6">
  <h2 style="margin:0 0 16px 0;font-size:20px;color:#111">Please ignore our last email alert — our apologies!</h2>
  
  <p>Hi everyone,</p>

  <p>If you received our recent email alert about new internship openings, please ignore it.</p>

  <p>A few non-tech roles accidentally slipped into that update. We have already corrected the issue and removed them from the tracker.</p>

  <p>We are very sorry for the clutter and confusion in your inbox. Going forward, you will only receive genuine tech and software engineering internships, as always.</p>

  <p>Thank you for your understanding!</p>

  <p style="margin-top:24px;font-weight:500">
    Best regards,<br>
    <strong>Internship Engine India Team</strong>
  </p>

  <hr style="border:none;border-top:1px solid #eee;margin:32px 0 16px 0">
  <p style="color:#999;font-size:12px;margin:0">
    You received this because you are subscribed to new-internship alerts.
    <a href="{{UNSUB_URL}}" style="color:#999">Unsubscribe</a> anytime.
  </p>
</div>
"""


def send_apology() -> int:
    api_key = os.environ.get("BREVO_API_KEY")
    base_url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    sender = mailer._sender()

    if not api_key:
        print("ERROR: BREVO_API_KEY missing.")
        return 0
    if not base_url or not service_key:
        print("ERROR: SUPABASE credentials missing.")
        return 0
    if not sender:
        print("ERROR: MAIL_FROM missing or invalid.")
        return 0

    subscribers = mailer._subscribers(base_url, service_key)
    if not subscribers:
        print("No subscribers found.")
        return 0

    print(f"Found {len(subscribers)} subscribers. Starting delivery...")
    unsub_base = f"{config.pages_base()}/unsubscribe.html"
    sent = 0

    with httpx.Client(timeout=20) as client:
        for sub in subscribers:
            address = (sub.get("email") or "").strip()
            token = sub.get("unsub_token") or ""
            if not address or not token:
                continue

            html = _APOLOGY_HTML.replace("{{UNSUB_URL}}", f"{unsub_base}?t={token}")
            try:
                resp = client.post(
                    mailer._BREVO_URL,
                    headers={"api-key": api_key, "Content-Type": "application/json"},
                    json={
                        "sender": sender,
                        "to": [{"email": address}],
                        "subject": _APOLOGY_SUBJECT,
                        "htmlContent": html,
                    },
                )
                resp.raise_for_status()
                sent += 1
                print(f"[{sent}/{len(subscribers)}] Sent to {address}")
            except Exception as e:
                print(f"Failed to send to {address}: {e}")
                continue
            time.sleep(0.12)

    print(f"Done. Sent apology to {sent} subscribers.")
    return sent


if __name__ == "__main__":
    send_apology()
