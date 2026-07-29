import os
import sys
import httpx

account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
from_number = os.environ.get("TWILIO_FROM_NUMBER")
to_number = os.environ.get("WHATSAPP_PHONE")

print("--- TWILIO DIAGNOSTIC CHECK ---")
print(f"TWILIO_ACCOUNT_SID present: {bool(account_sid)}")
print(f"TWILIO_AUTH_TOKEN present: {bool(auth_token)}")
print(f"TWILIO_FROM_NUMBER present: {bool(from_number)} (Value: {from_number})")
print(f"WHATSAPP_PHONE present: {bool(to_number)} (Value: {to_number})")

if not all([account_sid, auth_token, from_number, to_number]):
    print("❌ FAILED: One or more Twilio secrets are missing from GitHub Repository Secrets!")
    sys.exit(1)

api_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
data = {
    "From": f"whatsapp:{from_number}" if not from_number.startswith("whatsapp:") else from_number,
    "To": f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number,
    "Body": "🚀 Internship Engine Test Alert: Twilio WhatsApp integration is working!"
}

try:
    resp = httpx.post(api_url, auth=(account_sid, auth_token), data=data, timeout=10)
    print(f"Twilio API Response Code: {resp.status_code}")
    print(f"Twilio API Response Body: {resp.text}")
    resp.raise_for_status()
    print("✅ SUCCESS: Test WhatsApp message delivered to Twilio!")
except Exception as exc:
    print(f"❌ FAILED: Twilio API request failed: {exc}")
    sys.exit(1)

