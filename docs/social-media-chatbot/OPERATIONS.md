# Social Media Chatbot Operations

## App-only environment

Copy `.env.social_media_chatbot.example` to `.env.social_media_chatbot` in the
Django project root. Protect the file as a secret. Fill in:

- `SOCIAL_MEDIA_CHATBOT_ENCRYPTION_KEY`: one stable Fernet key.
- `SOCIAL_MEDIA_CHATBOT_LLM_*`: this app's LLM configuration; it does not read
  the root `.env` `LLM_*` values.
- `SOCIAL_MEDIA_CHATBOT_EVOLUTION_API_KEY`: the Evolution global key, copied by
  the operator from the Evolution server's protected configuration. It is used
  only for administrative create/delete operations and never goes to a browser.
- `SOCIAL_MEDIA_CHATBOT_EVOLUTION_BASE_URL`: use
  `http://127.0.0.1:8080` when Django runs directly on the Evolution host. If
  Django is containerized, use a private address such as
  `http://evolution_api:8080` only after connecting it to `evolution-net`.
  The client permits plain HTTP only to loopback, private IPs, single-label
  Docker service names, and `.internal` / `.local` hosts. Do not expose port
  8080 publicly to make this work.
- `SOCIAL_MEDIA_CHATBOT_PUBLIC_BASE_URL`: the Django application's public HTTPS
  origin, used for inbound Evolution webhooks.

No Evolution global or per-instance key is entered in the dashboard. Each
WhatsApp bot gets a separately generated instance token, which is encrypted in
the Django database and used for its own messages, QR/status requests, and
webhook configuration.

Generate the Fernet key once after installing the chatbot-specific
requirements:

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The project root already pins `cryptography==47.0.0`; QR rendering is isolated
in `apps/social_media_chatbot/requirements.txt` so the shared project
requirements were not expanded. Install that app-only file manually:

```powershell
.\.venv\Scripts\python.exe -m pip install -r apps\social_media_chatbot\requirements.txt
```

Back up the Django database before migrations. Store the Fernet key separately
and securely; encrypted chatbot credentials cannot be recovered without it.

## Evolution API v2.3.7 flow

Creating a WhatsApp bot saves an active bot row, creates a uniquely named
`WHATSAPP-BAILEYS` instance using the server-only global key, configures a
per-instance webhook, and displays the QR on an owner-only page. QR refresh and
connection status use the per-instance token. The QR is rendered locally when
the Evolution response returns its raw pairing string, so pairing data is not
sent to a third-party QR service.

Evolution API v2 documents instance creation and QR generation through
`POST /instance/create` and `GET /instance/connect/{instance}` ([create](https://github.com/evolution-foundation/evolution-docs/blob/main/docs/03-Instance%20contoller/00-create-instance.md),
[connect](https://docs.evoapicloud.com/api-reference/instance-controller/instance-connect)).
Text sends use `POST /message/sendText/{instance}` ([send text](https://github.com/evolution-foundation/evolution-docs/blob/main/docs/05-Endpoints/00-send-plain-text.md));
webhook setup uses `POST /webhook/set/{instance}` ([webhook](https://docs.evoapicloud.com/api-reference/webhook/set)).

Deleting a WhatsApp bot first deletes its Evolution instance with the global
key. If Evolution is unavailable, the Django record is retained so a failed
remote delete cannot silently leave a disconnected ownership record. Disabling
a bot turns off its webhook but preserves the linked WhatsApp session.

## Runtime processes

- Run `python manage.py run_social_chatbots` as one long-running Telegram
  supervisor. Do not run multiple copies; distributed singleton leasing is not
  implemented yet.
- Run a Celery worker subscribed only to `social_chatbot` with concurrency 1,
  for example `celery -A config worker -Q social_chatbot --loglevel=INFO
  --concurrency=1`.
- Keep the web app, Telegram supervisor, and Celery worker on the same
  app-specific environment and encryption key.
- Monitor memory as connected Baileys accounts grow; the reported server has
  about 2 GB total RAM. No extra Evolution containers are created by this app.

The webhook URL includes a per-bot secret. Configure application and reverse
proxy logs to redact that URL path.
