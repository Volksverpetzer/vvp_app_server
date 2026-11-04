# vvp_app_server

Django backend server for the Volksverpetzer and Mimikama mobile apps.

## Project Structure

| App | Responsibility |
|-----|----------------|
| **factApi** | `/googleFact` — Google Fact Check API proxy |
| **contact** | `/contact` — generic contact requests (feedback, fake reports, other), posted to the Asana board |
| **reportFake** | Legacy fake-report submissions and status polling (old app versions) |
| **notifications** | Device registration, push notification scheduling (Django-Q), and webhooks for new posts |
| **payment** | Stripe payment intents |
| **proxycache** | Social-media feed proxies (Instagram, Bluesky, TikTok, YouTube) and Plausible analytics proxy; caches responses |
| **info** | Simple informational page |
| **vvp_app_server** | Core settings, URL routing, and shared utilities |

### API Endpoints

| Method | Path | App | Description |
|--------|------|-----|-------------|
| `POST` | `/googleFact` | factApi | Google Fact Check search |
| `POST` | `/contact` | contact | Submit a contact request (creates an Asana task) |
| `POST` | `/reportFake` | reportFake | Submit a fake-report (legacy, old app versions) |
| `GET` | `/statusFake/<uuid>` | reportFake | Check report status |
| `POST` | `/register` | notifications | Register device for push notifications |
| `POST` | `/webhook_new_post` | notifications | Trigger push notifications for a new post |
| `POST` | `/notification_stats` | notifications | Push notification delivery stats |
| `GET` | `/task_monitor` | notifications | Django-Q task queue status |
| `GET` | `/receipts_monitor` | notifications | Push receipt monitoring |
| `POST` | `/paymentIntent` | payment | Create Stripe payment intent |
| `GET` | `/proxy/instaFeed` | proxycache | Instagram feed (`?account=volksverpetzer\|pruefpunkt\|mimikama_org`) |
| `GET` | `/proxy/instaById/<id>` | proxycache | Single Instagram post |
| `GET` | `/proxy/blueskyFeed` | proxycache | Bluesky feed (`?account=volksverpetzer\|pruefpunkt\|bot`) |
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
| `EXPO_PUSH_ACCESS_TOKEN` | Expo access token for the push API (enhanced push security) |
| `NOTIFICATION_BEARER` | Bearer token to authenticate incoming webhook calls |
| `GOOGLE_FACT` | Google Fact Check API key |
| `STRIPE_SECRET_KEY` | Stripe live secret key |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram Graph API token (volksverpetzer account) |
| `INSTAGRAM_ACCESS_TOKEN_PRUEFPUNKT` | Instagram Graph API token (pruefpunkt account) |
| `INSTAGRAM_ACCESS_TOKEN_MIMIKAMA` | Instagram Graph API token (mimikama_org account) |
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
| `ASANA_TOKEN` | Asana personal access token (contact requests & fake reports) |
| `ASANA_PROJECT_GID` | Asana project (board) gid that contact tasks are added to |
| `ASANA_SECTION_REPORT_FAKE` | Board section gid for fake reports (optional) |
| `ASANA_SECTION_APP_FEEDBACK` | Board section gid for app feedback (optional) |
| `ASANA_SECTION_OTHER` | Board section gid for other requests (optional) |
| `PLAUSIBLE_TOKEN` | Plausible Analytics API token |

## Local Development

**Prerequisites:** Python 3.12, PostgreSQL, [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install dependencies (creates .venv and installs the dev dependency
#    group too; add --no-dev to skip it)
uv sync

# 2. Activate the virtual environment
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 3. Configure environment
cp .env.sample .env
# Edit .env and fill in the values

# 4. Set up the database
python manage.py migrate
python manage.py createcachetable

# 5. Start the development server
python manage.py runserver
# or use the helper script: ./scripts/dev_startup.sh
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

## Hosting & CDN

| Hostname | Served by | Origin |
|----------|-----------|--------|
| `volksverpetzer-app.de` | Bunny pull zone `vvp-app-api` | `vvpappserver` Scaleway container |
| `mimikama.volksverpetzer-app.de` | Bunny pull zone `mimikama-app-api` | `mimikamaappserver` Scaleway container |
| `staging.volksverpetzer-app.de` | Scaleway directly (DNS CNAME) | `vvpappserverstaging` container |

DNS for `volksverpetzer-app.de` is hosted in Bunny DNS; the apex and `mimikama` are `PZ` (pull zone) records.

### Bunny pull zones `vvp-app-api` and `mimikama-app-api`

Both zones are set up the same way; `mimikama-app-api` sends `mimikama.volksverpetzer-app.de` as its `X-Forwarded-Host` and has no CORS rule, since there is no Mimikama web app.


- **Origin URL** is the container's own `*.functions.fnc.fr-par.scw.cloud` URL, with **Forward Host Header off**. Scaleway then routes by its own hostname, so the container needs no Scaleway custom domain for `volksverpetzer-app.de`.
- **Edge rule "Origin: send public host as X-Forwarded-Host"** sets `X-Forwarded-Host: volksverpetzer-app.de` on every request. Django reads it via `USE_X_FORWARDED_HOST` for `ALLOWED_HOSTS`, CSRF and absolute URLs (e.g. the `media_url` links in the Instagram feed). Without it every request is a `400`.
- **Edge rule "CORS: add headers for web.volksverpetzer.de on cached responses"** sets `Access-Control-Allow-Origin: https://web.volksverpetzer.de` and `Access-Control-Allow-Credentials: true` when the request's `Origin` is the web app. Bunny does not honour `Vary: Origin`, so a copy cached for the native app (no `Origin`) would otherwise reach the web app without CORS headers.
- **Caching** respects the origin's `Cache-Control` (set by `EdgeCacheControlMiddleware`) and keeps the query string in the cache key.
- **TLS** for the public hostname is Bunny's free certificate, with Force SSL on.

### Don't put a Scaleway custom domain behind Bunny

A Scaleway custom domain only renews its certificate while the hostname's DNS points at the container. Once DNS points at Bunny, renewal fails, Scaleway drops the hostname from its routing and every request returns an empty `404`. This took `volksverpetzer-app.de` down in October 2026. So either point DNS straight at the container and keep the Scaleway custom domain (as staging does), or put the hostname behind a pull zone set up like `vvp-app-api` and delete its Scaleway custom domain.

## CI/CD

One GitHub Actions workflow is defined in `.github/workflows/`:

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `test-and-deploy.yml` | Push to any branch | Runs the Django test suite; on `main` also deploys the image to the production **and Mimikama** Scaleway containers (needs the `SCALEWAY_MIMIKAMA_SERVICE_ID` secret), on `prerelease` to staging |
