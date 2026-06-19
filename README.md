# vvp_app_server

Django backend server for the Volksverpetzer and Mimikama mobile apps.

## Project Structure

| App | Responsibility |
|-----|----------------|
| **factApi** | `/googleFact` — Google Fact Check API proxy |
| **reportFake** | Fake-report submissions, triage, archiving, and Bluesky bot feed |
| **notifications** | Device registration, push notification scheduling (Django-Q), and webhooks for new posts |
| **payment** | Stripe payment intents |
| **proxycache** | Social-media feed proxies (Instagram, Bluesky, TikTok, YouTube) and Plausible analytics proxy; caches responses |
| **info** | Simple informational page |
| **vvp_app_server** | Core settings, URL routing, and shared utilities |

### API Endpoints

| Method | Path | App | Description |
|--------|------|-----|-------------|
| `POST` | `/googleFact` | factApi | Google Fact Check search |
| `POST` | `/reportFake` | reportFake | Submit a fake-report |
| `POST` | `/triageFake` | reportFake | Triage a report |
| `POST` | `/archiveFake` | reportFake | Archive a report |
| `POST` | `/assign-bluesky` | reportFake | Assign Bluesky post to report |
| `GET` | `/statusFake/<uuid>` | reportFake | Check report status |
| `POST` | `/register` | notifications | Register device for push notifications |
| `POST` | `/webhook_new_post` | notifications | Trigger push notifications for a new post |
| `POST` | `/notification_stats` | notifications | Push notification delivery stats |
| `GET` | `/task_monitor` | notifications | Django-Q task queue status |
| `GET` | `/receipts_monitor` | notifications | Push receipt monitoring |
| `POST` | `/paymentIntent` | payment | Create Stripe payment intent |
| `GET` | `/proxy/instaFeed` | proxycache | Instagram feed (`?account=volksverpetzer\|pruefpunkt`) |
| `GET` | `/proxy/instaById/<id>` | proxycache | Single Instagram post |
| `GET` | `/proxy/blueskyFeed` | proxycache | Bluesky feed (`?account=volksverpetzer\|pruefpunkt`) |
| `GET` | `/proxy/tiktokFeed` | proxycache | TikTok feed |
| `GET` | `/proxy/ytAPI` | proxycache | YouTube feed |
| `GET` | `/proxy/media_url` | proxycache | Resolve and proxy external media |
| `GET` | `/proxy/shares[/<path>]` | proxycache | Article share counts |
| `GET` | `/proxy/links/<path>/` | proxycache | Link analytics |
| `GET` | `/proxy/map` | proxycache | Geographic analytics map |
| `GET` | `/proxy/stats/<path>/` | proxycache | Plausible stats proxy |
| `GET` | `/proxy/favs/<path>/` | proxycache | Plausible favourites proxy |
| `GET` | `/proxy/regions` | proxycache | Plausible regions proxy |
| `GET` | `/info` | info | App info page |

## Required Environment Variables

Copy `.env.sample` to `.env` and fill in the values.

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | Set to `enabled` to activate debug mode |
| `DATABASE_URL` | PostgreSQL connection string (e.g. `postgres://user:pass@host:5432/db`) |
| `DB_SSLMODE` | SSL mode for DB connection (`require`, `disable`, …) |
| `DB_SSLROOTCERT` | Path to SSL root certificate |
| `EXPO_TOKEN` | Expo push notification server token |
| `NOTIFICATION_BEARER` | Bearer token to authenticate incoming webhook calls |
| `GOOGLE_FACT` | Google Fact Check API key |
| `STRIPE_SECRET_KEY` | Stripe live secret key |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram Graph API token (volksverpetzer account) |
| `INSTAGRAM_ACCESS_TOKEN_PRUEFPUNKT` | Instagram Graph API token (pruefpunkt account) |
| `BSKY_HANDLE` | Bluesky handle for feed fetching (volksverpetzer) |
| `BSKY_PWD` | Bluesky password for feed fetching (volksverpetzer) |
| `BSKY_HANDLE_PRUEFPUNKT` | Bluesky handle for feed fetching (pruefpunkt, optional) |
| `BSKY_PWD_PRUEFPUNKT` | Bluesky password for feed fetching (pruefpunkt, optional) |
| `BSKY_BOT_HANDLE` | Bluesky bot account handle (fact-check replies) |
| `BSKY_BOT_PWD` | Bluesky bot account password |
| `TIKTOK_CLIENT_KEY` | TikTok API client key |
| `TIKTOK_CLIENT_SECRET` | TikTok API client secret |
| `TIKTOK_REFRESH_TOKEN` | TikTok OAuth refresh token (fallback when no DB token exists) |
| `YT_ACCESS_TOKEN` | YouTube Data API v3 key |
| `MAILGUN_DOMAIN` | Mailgun domain for sending report emails |
| `MAILGUN_TOKEN` | Mailgun API token |
| `MAILGUN_RECEIVER` | Email address to receive fake-report notifications |
| `PLAUSIBLE_TOKEN` | Plausible Analytics API token |

## Local Development

**Prerequisites:** Python 3.12, PostgreSQL.

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 3. Configure environment
cp .env.sample .env
# Edit .env and fill in the values

# 4. Set up the database
python manage.py migrate
python manage.py createcachetable

# 5. Start the development server
python manage.py runserver
# or use the helper script: ./dev_startup.sh
```

### Background Worker

Push notifications and scheduled tasks are processed by a **Django-Q** cluster. Run it in a separate terminal alongside the dev server:

```bash
python manage.py qcluster
```

## Connecting the Mobile App to the Local Server

The app's `apiUrl` is set in `config/volksverpetzer.config.ts` (or `mimikama.config.ts`) and typed as `HttpsUrl`, so a cast is required for a plain HTTP local address.

**iOS Simulator** — localhost is reachable directly:

```ts
apiUrl: "http://localhost:8000" as any,
```

**Android Emulator** — use the special loopback alias for the host machine:

```ts
apiUrl: "http://10.0.2.2:8000" as any,
```

Android blocks cleartext HTTP by default. Add this to the `android` section of `app.config.ts` while developing locally:

```ts
usesCleartextTraffic: true,
```

**Alternative: HTTPS tunnel (avoids both workarounds)**

Tools like `ngrok` or `cloudflared` expose the local server over HTTPS, so no type cast or cleartext flag is needed:

```bash
ngrok http 8000
# → use the printed https://... URL as apiUrl
```

## Docker

Build the image and run the container:

```bash
docker build -t vvp_app_server .
docker run --env-file .env -p 8080:8080 vvp_app_server
```

The container starts both `gunicorn` (port 8080) and `qcluster` via the `CMD` in the `dockerfile`.

## CI/CD

Two GitHub Actions workflows are defined in `.github/workflows/`:

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `test-and-release.yml` | Push to any branch | Runs the Django test suite against a PostgreSQL service container |
| `build-mimikama.yml` | Push to `mimikama` branch | Builds and deploys the app to Azure App Service (`mimikamaserver`) |
