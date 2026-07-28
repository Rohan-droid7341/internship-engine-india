"""Discord webhook alerts for newly spotted roles (optional, best-effort).

Set the DISCORD_WEBHOOK_URL secret and every run posts the roles it just found
to that channel. Unset = silent no-op, like every optional integration here.
Failures are swallowed: alerting must never break the data pipeline.
"""

from __future__ import annotations

import os

import httpx

from . import config, sponsorship

_MAX_EMBEDS = 10  # Discord's cap per message

# One color per configured cycle, in order (green, orange, purple, blue);
# anything else gets Discord blurple.
_PALETTE = (0x2ECC71, 0xE67E22, 0x9B59B6, 0x3498DB)


def _cycle_colors() -> dict[str, int]:
    labels = config.cycles(config.load_config())
    return {label: _PALETTE[i % len(_PALETTE)] for i, label in enumerate(labels)}


def _embed(record: dict, colors: dict[str, int]) -> dict:
    flag = sponsorship.flag(record.get("sponsorship"))
    title = f"{record.get('company', '')} — {record.get('title', '')}"
    bits = [record.get("season") or "", record.get("location") or ""]
    if record.get("salary"):
        bits.append(record["salary"])
    if flag:
        bits.append(flag)
    return {
        "title": title[:256],
        "url": record.get("url") or None,
        "description": " · ".join(b for b in bits if b)[:2048],
        "color": colors.get(record.get("season", ""), 0x5865F2),
    }


def _send_whatsapp(records: list[dict]) -> bool:
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    to_number = os.environ.get("WHATSAPP_PHONE")
    
    if not all([account_sid, auth_token, from_number, to_number]):
        return False
        
    text = f"*{len(records)} new internship{'s' if len(records) != 1 else ''} spotted!*\n\n"
    for r in records[:_MAX_EMBEDS]:
        title = f"{r.get('company', '')} — {r.get('title', '')}"
        url = r.get("url") or ""
        text += f"🏢 {title}\n🔗 {url}\n\n"
        
    extra = len(records) - _MAX_EMBEDS
    if extra > 0:
        text += f"(+{extra} more on the dashboard)\n"
        
    api_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = {
        "From": f"whatsapp:{from_number}",
        "To": f"whatsapp:{to_number}",
        "Body": text
    }
    
    try:
        httpx.post(api_url, auth=(account_sid, auth_token), data=data, timeout=10).raise_for_status()
        return True
    except Exception:
        return False


def _send_discord(records: list[dict]) -> bool:
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        return False

    extra = len(records) - _MAX_EMBEDS
    content = f"**{len(records)} new internship{'s' if len(records) != 1 else ''} spotted**"
    if extra > 0:
        content += f" (showing {_MAX_EMBEDS}, +{extra} more on the list)"

    colors = _cycle_colors()
    try:
        httpx.post(
            webhook,
            json={"content": content, "embeds": [_embed(r, colors) for r in records[:_MAX_EMBEDS]]},
            timeout=10,
        ).raise_for_status()
        return True
    except Exception:  # noqa: BLE001 — alerting is a side channel, never fatal
        return False


def send_new_roles(store_data: dict, new_ids: list[str]) -> bool:
    """Post this run's new roles to Discord and WhatsApp. Returns True if any sent."""
    if not new_ids:
        return False

    records = [store_data[jid] for jid in new_ids if jid in store_data]
    records = [r for r in records if r.get("is_open")]
    if not records:
        return False

    sent_discord = _send_discord(records)
    sent_whatsapp = _send_whatsapp(records)
    return sent_discord or sent_whatsapp
