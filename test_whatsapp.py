import os
import httpx

def test_twilio():
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    to_number = os.environ.get("WHATSAPP_PHONE")
    
    if not account_sid:
        print("Missing Twilio Secrets!")
        return

    api_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = {
        "From": f"whatsapp:{from_number}",
        "To": f"whatsapp:{to_number}",
        "Body": "?? Beep boop! This is a custom test message from your engine to confirm WhatsApp is wired up correctly! ??"
    }
    
    print("Sending Twilio test...")
    resp = httpx.post(api_url, auth=(account_sid, auth_token), data=data, timeout=10)
    print(resp.status_code, resp.text)
    resp.raise_for_status()

if __name__ == "__main__":
    test_twilio()
