# CodeSpace SMS Hub

A compliant, customer-facing inbound SMS platform starter.

## Scope
- Customer accounts and tenant-scoped inbox foundations
- Country catalogue for US, UK, Canada, and Italy
- Provider-neutral number provisioning interface
- Signed-webhook integration point for a licensed SMS provider
- Inbound message storage and health endpoint
- No public/shared OTP pool, third-party account verification bypass, or social-media account farming

**Important:** Carrier inventory, number purchase, SMS delivery, and country eligibility depend on the selected provider, account approval, local regulations, and permitted use case. The starter runs in mock mode until a provider adapter is configured.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000 and http://localhost:8000/docs.

## Environment
- `DATABASE_URL`: PostgreSQL URL; defaults to local SQLite for development
- `APP_ENV`: development or production
- `WEBHOOK_SECRET`: required to authenticate provider webhook requests in production
- `SMS_PROVIDER`: mock until a vetted provider adapter is implemented

## Next steps
1. Select a provider that explicitly supports your business use case and all target countries.
2. Complete provider business/KYC review and confirm number types and inbound SMS capability.
3. Implement that provider's inventory, purchase, release, and webhook adapter.
4. Add customer authentication, billing, retention controls, and operational monitoring before public launch.

Do not advertise TikTok, Facebook, Instagram, or other third-party OTP compatibility unless the platform and carrier explicitly permit the number type and use case.
