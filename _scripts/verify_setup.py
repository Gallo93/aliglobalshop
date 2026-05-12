"""
Verifica che tutte le env vars siano impostate e le API rispondano.
Eseguire prima del go-live: python _scripts/verify_setup.py
"""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

REQUIRED_VARS = [
    "ALIEXPRESS_APP_KEY",
    "ALIEXPRESS_APP_SECRET",
    "ALIEXPRESS_TRACKING_ID",
    "ANTHROPIC_API_KEY",
    "CF_R2_ACCOUNT_ID",
    "CF_R2_ACCESS_KEY_ID",
    "CF_R2_SECRET_ACCESS_KEY",
    "CF_R2_BUCKET_NAME",
    "RESEND_API_KEY",
]

errors = []


def check_env():
    missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
    if missing:
        errors.append(f"[ENV] Variabili mancanti: {', '.join(missing)}")
    else:
        print("[ENV] ✓ tutte le variabili impostate")


def check_anthropic():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        print(f"[ANTHROPIC] ✓ connessione OK ({msg.usage.input_tokens} token)")
    except Exception as e:
        errors.append(f"[ANTHROPIC] ✗ {e}")


def check_r2():
    if not os.getenv("CF_R2_ACCESS_KEY_ID"):
        return
    try:
        import boto3
        from botocore.client import Config
        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{os.getenv('CF_R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
            aws_access_key_id=os.getenv("CF_R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("CF_R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        s3.head_bucket(Bucket=os.getenv("CF_R2_BUCKET_NAME", "aliglobalshop-images"))
        print("[R2] ✓ bucket raggiungibile")
    except Exception as e:
        errors.append(f"[R2] ✗ {e}")


def check_aliexpress():
    app_key = os.getenv("ALIEXPRESS_APP_KEY", "")
    app_secret = os.getenv("ALIEXPRESS_APP_SECRET", "")
    if not app_key or not app_secret:
        return
    try:
        import hashlib
        import hmac
        import time
        import requests

        timestamp = str(int(time.time() * 1000))
        params = {
            "app_key": app_key,
            "timestamp": timestamp,
            "sign_method": "sha256",
            "method": "aliexpress.affiliate.hotproduct.query",
            "keywords": "phone",
            "page_no": "1",
            "page_size": "1",
            "tracking_id": os.getenv("ALIEXPRESS_TRACKING_ID", ""),
        }
        sorted_params = "".join(f"{k}{v}" for k, v in sorted(params.items()))
        sign = hmac.new(
            app_secret.encode(), (sorted_params).encode(), hashlib.sha256
        ).hexdigest().upper()
        params["sign"] = sign

        resp = requests.post(
            "https://api-sg.aliexpress.com/sync",
            data=params,
            timeout=10,
        )
        data = resp.json()
        if "error_response" in data:
            errors.append(f"[ALIEXPRESS] ✗ {data['error_response'].get('msg')}")
        else:
            print("[ALIEXPRESS] ✓ API risponde correttamente")
    except Exception as e:
        errors.append(f"[ALIEXPRESS] ✗ {e}")


def check_resend():
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        return
    try:
        import requests
        resp = requests.get(
            "https://api.resend.com/domains",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            print("[RESEND] ✓ API key valida")
        else:
            errors.append(f"[RESEND] ✗ status {resp.status_code}")
    except Exception as e:
        errors.append(f"[RESEND] ✗ {e}")


if __name__ == "__main__":
    print("=== AliGlobalShop — Setup Verification ===\n")
    check_env()
    check_anthropic()
    check_r2()
    check_aliexpress()
    check_resend()

    print()
    if errors:
        print("ERRORI:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("✓ Setup completo — tutto OK")
