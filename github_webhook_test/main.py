from fastapi import FastAPI, Request
import hmac
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# for right now, we have to manually setup a webhook on github but will be able to automate this using an API call to github hooks within the user's repo
# we will have to use a request payload for push events

@app.post("/github/webhook")
async def github_webhook(request: Request):
    """
    Test route — prints the payload when GitHub pushes code
    """
    body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256", "")

    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode()

    # verify signature if secret exists
    if secret and signature_header:
        digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
        expected = f"sha256={digest}"
        if not hmac.compare_digest(expected, signature_header):
            return {"message": "Invalid signature"}

    payload = await request.json()
    print("Webhook received!")
    print(payload)

    return {"message": "Webhook received successfully!"}