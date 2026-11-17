# WhatsApp AI Sales Closer

A deployable Express service that receives signed WhatsApp Cloud API webhooks, uses Gemini 2.5 Flash as a multilingual digital-agency sales closer, sends replies through Meta Graph API v20.0, and stores leads plus the last conversation turns in Supabase.

## What is included

- Meta `GET /webhook` verification and `POST /webhook` event handling
- Immediate webhook acknowledgement, batched-payload support, and per-phone processing order
- SHA-256 webhook signature verification with `META_APP_SECRET`
- Duplicate-event protection using WhatsApp message IDs
- Durable eight-message context in Supabase (English, Urdu, and Roman Urdu)
- A short, ethical sales-closer prompt for web/app development, UI/UX, SEO/marketing, and AI automation
- Gemini failure fallback, Meta/Supabase error reporting, health endpoint, and automated unit tests

## Folder structure

```text
whatsapp-ai-sales-closer/
├── server.js                 # Express entry point and webhook orchestration
├── src/
│   ├── ai.js                 # Gemini sales closer
│   ├── config.js             # Environment validation
│   ├── store.js              # Supabase leads, history, and deduplication
│   ├── webhook.js            # Meta payload and signature helpers
│   └── whatsapp.js           # Graph API sender
├── test/                     # Node test runner tests
├── supabase.sql              # Database schema
├── package.json
├── .env.example
└── .gitignore
```

## 1. Local setup

Requirements: Node.js 20 or 22, a Meta developer app with WhatsApp configured, a Gemini API key, and a Supabase project.

```bash
cd whatsapp-ai-sales-closer
npm install
cp .env.example .env
```

On PowerShell, use `Copy-Item .env.example .env`. Fill every required value in `.env`, then run:

```bash
npm test
npm start
```

Check `http://localhost:3000/health`. For local Meta testing, expose port 3000 through an HTTPS tunnel and use its public `/webhook` URL. Never commit `.env` or expose the Supabase service-role key.

## 2. Supabase setup

Open **Supabase Dashboard → SQL Editor**, paste [supabase.sql](./supabase.sql), and run it. It creates:

- `leads`: one current CRM row per phone number; new rows receive `lead_status = 'New'`.
- `conversation_messages`: durable user/model turns used for the latest eight-message context.
- `processed_messages`: WhatsApp message IDs used to ignore Meta retries.

Copy the project URL and **service role** key from **Project Settings → API** into `.env`. Row Level Security is enabled; the backend service-role key bypasses it and must remain server-only.

## 3. Meta WhatsApp Cloud API setup

1. In Meta for Developers, create/select a Business app and add **WhatsApp**.
2. Collect the WhatsApp phone number ID and create a permanent system-user token with the required WhatsApp permissions. Put them in `PHONE_NUMBER_ID` and `WHATSAPP_TOKEN`.
3. Choose a long random `VERIFY_TOKEN`; the same exact value is entered in Meta and `.env`.
4. Copy the Meta app secret into `META_APP_SECRET`. Production startup refuses to run without it, because it is used to validate `X-Hub-Signature-256`.
5. Under **WhatsApp → Configuration**, set the callback URL to `https://YOUR-DOMAIN/webhook`, enter the verify token, verify it, and subscribe to the `messages` field.
6. Add recipient test numbers while the app is in development mode. Move through Meta App Review/business verification as required before serving real customers.

The bot can freely reply within WhatsApp's customer-service window after a user messages it. Business-initiated messages outside that window require an approved template; this service intentionally handles inbound conversations only.

## 4. Gemini and sales configuration

Create a key in Google AI Studio and set `GEMINI_API_KEY`. The default model is `gemini-2.5-flash`; change `GEMINI_MODEL` only if the model is available to your account. Set:

```dotenv
AGENCY_NAME=Acme Digital
DISCOVERY_CALL_URL=https://cal.com/acme/15min
```

The prompt replies in the language/script used by the lead, limits output to 2–3 short sentences, asks one qualifying question at a time, avoids fabricated claims, and advances qualified prospects toward a quote or discovery call.

## 5. Render.com 24/7 deployment

1. Push the repository to GitHub/GitLab/Bitbucket. Do not push `.env`.
2. In Render, choose **New → Web Service** and connect the repository.
3. Use these settings:
   - **Root Directory:** `whatsapp-ai-sales-closer`
   - **Runtime:** Node
   - **Build Command:** `npm ci`
   - **Start Command:** `npm start`
   - **Health Check Path:** `/health`
4. Add all values from `.env.example` under **Environment**, with `NODE_ENV=production`. Use Render secrets for all tokens and keys.
5. Deploy, then configure Meta's callback as `https://YOUR-SERVICE.onrender.com/webhook`.
6. Send a test WhatsApp message and confirm the Render logs show `accepted`, `processing`, and `reply sent`; confirm rows appear in all three Supabase tables.

Use a paid Render instance for true 24/7 operation; free instances may sleep or have platform limits. Rotate any secret that appears in logs or source control.

## Operations and troubleshooting

- **Webhook verification returns 403:** Meta's verify token does not exactly match `VERIFY_TOKEN`.
- **Webhook POST returns 401:** `META_APP_SECRET` is wrong, or an intermediary altered the request body.
- **Meta send fails:** inspect the logged Graph API error; check token expiry/permissions, phone number ID, recipient eligibility, and the customer-service window.
- **Gemini fallback is sent:** verify the key, model availability, quota, and billing. The original lead is still handled with a safe generic reply.
- **Supabase errors:** run `supabase.sql`, use the service-role rather than anon key, and verify the project URL.
- **Duplicate messages:** are expected when Meta retries and are ignored by `processed_messages`.

Logs deliberately identify phone numbers for operational debugging as requested. In regulated environments, redact them and configure log retention. Add a privacy notice, human handoff path, data-retention job, monitoring/alerts, and backups appropriate to your jurisdiction before processing production customer data.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Basic liveness response |
| `GET` | `/health` | Render health check |
| `GET` | `/webhook` | Meta verification challenge |
| `POST` | `/webhook` | Signed WhatsApp notifications |
