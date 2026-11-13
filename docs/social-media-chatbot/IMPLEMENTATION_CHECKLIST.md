# Social Media Chatbot Production Checklist

## Completed in the repository

- [x] Re-audit prior changes for cross-app effects and trace all `Chatbot`
  consumers. Article Agent has its own article model and does not consume this
  chatbot configuration.
- [x] Keep the chatbot env file separate. App values are read into app-specific
  Django settings and are not injected into `os.environ`; root `.env` and
  Article Agent `LLM_*` values are not changed or used as fallbacks.
- [x] Add encrypted credential fields and additive migrations. Move the
  encrypted field implementation into `apps.agents` so that `apps.agents` no
  longer imports code from the social chatbot app.
- [x] Add owner scoping to chatbot dashboard, CRUD, dashboard menu, QR access,
  and authenticated chat API. Use `PROTECT` on owner deletion to prevent
  silently orphaning Evolution instances.
- [x] Refuse ambiguous ownership assignment for legacy bots during migration;
  the migration only auto-assigns when there is exactly one superuser or one
  account total.
- [x] Implement Evolution API v2.3.7 instance creation with Baileys, unique
  per-instance credentials, QR response handling, connection state, webhook,
  text send, and remote instance deletion.
- [x] Keep the global Evolution API key server-side in the app-specific env.
  Only create/delete calls use it; instance operations use each instance's
  encrypted credential. The dashboard never receives either credential.
- [x] Add owner-only QR pages with no-store response headers and CSRF-protected
  refresh, plus WhatsApp connection-state webhook handling.
- [x] Run focused tests with `--keepdb`: 15 chatbot tests passed, covering
  tenant isolation, CSRF, Evolution auth separation, webhook signature,
  connection events, duplicate inbound delivery, and sanitized API failures.
- [x] Run the complete repository suite with `--keepdb`: all 121 tests passed;
  the existing test database was preserved.
- [x] `manage.py check`, `makemigrations --check --dry-run`, and `compileall`
  passed. The existing test database was preserved; no database was deleted.
- [x] Re-audit Evolution URL validation against both supported deployments:
  loopback HTTP on the host and private Docker service DNS on `evolution-net`;
  public HTTP endpoints remain rejected.

## Remaining production rollout checks

- [ ] Install the app-only requirements listed in
  `apps/social_media_chatbot/requirements.txt`. The active `.venv` currently
  lacks both `cryptography` and `qrcode`; no package was installed by Codex.
- [ ] Configure `.env.social_media_chatbot` on the Django server with the
  stable Fernet key, app LLM settings, Evolution global API key, internal API
  URL, and public HTTPS URL. Do not place these values in the root `.env` or
  browser settings.
- [ ] Back up the Django database and apply migrations. Review the existing
  users first: if legacy chatbot rows exist and there is not exactly one
  superuser (or one total user), assign those legacy records to their intended
  tenant before rerunning migration `agents.0005`.
- [ ] Verify an end-to-end create → QR scan → `open` state → inbound webhook →
  AI reply → outbound WhatsApp message against the running Evolution service.
- [ ] Verify the deployed Django process can reach Evolution without exposing
  port 8080 publicly. On the same host use loopback; in containers use a
  private shared Docker network.
- [ ] Start one Telegram supervisor and a `social_chatbot` Celery worker with
  concurrency 1; check memory under the real number of connected instances.
- [ ] Confirm database backups include the stable encryption key through a
  protected secret-management process and test recovery without exposing it.
- [ ] Review production access logs to redact the per-bot webhook secret path.

## External infrastructure state

- Evolution API is already running as `evoapicloud/evolution-api` version
  2.3.7 on the server, bound to loopback, with its own PostgreSQL, Redis, and
  persistent instance volume. This code does not change or recreate that stack.
- SSH configuration for the supplied host is not available from this Windows
  workspace, so no server files, containers, API key, or production database
  were accessed or modified.
