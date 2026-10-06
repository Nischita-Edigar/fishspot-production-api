# Fish Spot Malpe Production API

FastAPI backend for the Fish Spot Malpe customer app.

## Current production endpoints

- `GET /` - API status
- `GET /health` - API + PostgreSQL health check
- `GET /products/` - active products
- `POST /auth/send-otp` - send Twilio Verify SMS OTP
- `POST /auth/verify-otp` - verify OTP
- `GET /location/search?q=...` - Google Places autocomplete

## Local run

1. Create `.env` from `.env.example` and fill in real values.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Render deployment

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set the secret environment variables in Render. Do not upload `.env` or commit secrets.

After deployment test:

- `/health`
- `/products/`
- `/docs`

## Important

`seed_products.py` is a development/data-loading script. Do not execute it automatically during deployment.
