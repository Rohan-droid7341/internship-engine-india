import os
import sys

from src.intern_engine import notify

sample_job = {
    "company": "Stripe (Test Alert)",
    "title": "Software Engineering Intern - Summer 2027",
    "season": "Summer 2027",
    "location": "Bengaluru, India",
    "url": "https://github.com/Rohan-droid7341/internship-engine-india"
}

print("Testing WhatsApp alert via Twilio on GitHub Actions runner...")
sent = notify.send_whatsapp_digest([sample_job])
if sent:
    print("✅ SUCCESS: WhatsApp test message delivered to Twilio API!")
else:
    print("❌ FAILED: Could not send WhatsApp test message. Please verify your Twilio GitHub secrets.")
    sys.exit(1)
