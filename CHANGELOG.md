# [1.5.0](https://github.com/Volksverpetzer/vvp_app_server/compare/v1.4.0...v1.5.0) (2026-09-07)


### Bug Fixes

* **Instagram proxy** — retry expired Instagram media URLs before giving up. Some media get noticeably shorter-lived signed CDN URLs than others in the same batch, so a `media_url` embedded on the WordPress side could already be expired even though our cache entry was still fresh; the proxy now does one retry, re-fetching that single post directly from the Instagram Graph API for a freshly signed URL before failing. Backward compatible with links generated before this deploy ([#41](https://github.com/Volksverpetzer/vvp_app_server/pull/41))
* **Podcast** — parse the podcast feed XML with `defusedxml` instead of `ElementTree.fromstring` to avoid XXE risk on network-fetched content ([#43](https://github.com/Volksverpetzer/vvp_app_server/pull/43))
* **Deploy** — stop passing the registry-endpoint image ref through a job output; GitHub Actions silently drops job outputs containing secrets, which was leaving the sha-tagged image ref blank for the deploy step. The ref is now reconstructed inline wherever it's used ([#39](https://github.com/Volksverpetzer/vvp_app_server/pull/39))
* **Deploy** — add a concurrency group to the deploy job, keyed by branch, so an older run's deploy can no longer finish after a newer one's and move the container backwards ([#40](https://github.com/Volksverpetzer/vvp_app_server/pull/40))


### Chores

* **CI** — rename `test-and-release.yml` to `test-and-deploy.yml` and deploy by PATCHing the container's `registry_image` to the sha-tagged image instead of POSTing a bare `/deploy` trigger against a static `:latest`/`:staging` tag, so a concurrent push to the other branch can't get deployed to the wrong service; switch the Docker base to `python:3.12-slim` and loosen `.python-version` to `3.12` so it stays in sync with the floating base image ([#38](https://github.com/Volksverpetzer/vvp_app_server/pull/38))
* **CI** — align GitHub Actions workflow step/job naming style with `vvp_app` (icon-prefixed names, no logic changes) ([#36](https://github.com/Volksverpetzer/vvp_app_server/pull/36))
* **Scripts** — replace `add_ip_to_scaleway_allowlist.sh` with the shared `@volksverpetzer/whitelist-ip` CLI published from `vvp_tools`; `make allowlist` now delegates to `npx @volksverpetzer/whitelist-ip` ([#37](https://github.com/Volksverpetzer/vvp_app_server/pull/37))
* **Dependabot** — add `cooldown.default-days` to all ecosystems that were missing it (mainly `github-actions`), matching the pattern already used for npm/uv ([#42](https://github.com/Volksverpetzer/vvp_app_server/pull/42))


# [1.4.0](https://github.com/Volksverpetzer/vvp_app_server/compare/v1.3.1...v1.4.0) (2026-07-23)


### Bug Fixes

* **Startup** — stop the Django-Q worker gracefully on shutdown. The container startup no longer `exec`s Gunicorn as PID 1 (which left the `qcluster` worker to be force-killed); it now runs both as child processes, forwards `SIGTERM`/`SIGINT` to each, and waits for Gunicorn to finish draining before exiting ([#26](https://github.com/Volksverpetzer/vvp_app_server/issues/26))
* **ytAPI** — filter the YouTube feed to regular videos by actual duration (YouTube's own <=3min Shorts threshold) instead of the unreliable `"#shorts"` description-tag check, which let genuine Shorts through ([#31](https://github.com/Volksverpetzer/vvp_app_server/pull/31))


### Features

* **Podcast** — new `/proxy/podcastFeed` endpoint that fetches the podcast RSS feed (the Volksverpetzer Podigee feed by default, configurable via the `PODCAST_FEED_URL` env var) and serves parsed episodes as JSON for the app's new podcast home-feed section. Cached for 30 minutes under a constant cache key (query strings cannot bypass or evict the cache), returns a controlled `502` on upstream or parse failures, normalizes naive `pubDate` timezones to UTC, and validates `itunes:duration` values ([#27](https://github.com/Volksverpetzer/vvp_app_server/pull/27))
* **Rate limiting** — add a `RATELIMIT_ENABLE` env toggle to disable API rate limits for local development/testing; defaults to enabled. Parsing is strict: only explicit true/false values are accepted and anything else raises at startup, so a typo can never silently disable rate limiting ([#26](https://github.com/Volksverpetzer/vvp_app_server/issues/26))
* **YouTube channel** — add a `YT_CHANNEL_ID` env var (mirrors `PODCAST_FEED_URL`) so the `ytAPI` endpoint's source channel is configurable per deployment (e.g. Mimikama) without a code change; both it and `PODCAST_FEED_URL` now fall back to the default instead of passing a whitespace-only value downstream ([#29](https://github.com/Volksverpetzer/vvp_app_server/pull/29))


### Chores

* **Scripts** — consolidate shell scripts under `scripts/` (merge the `run_add_ip.sh` wrapper into `add_ip_to_scaleway_allowlist.sh`, move `startup.sh`/`dev_startup.sh`), make them runnable from any directory, and have the Docker `CMD` call `scripts/startup.sh`; update the Makefile, README, and `.env.sample` accordingly ([#26](https://github.com/Volksverpetzer/vvp_app_server/issues/26))
* **ALLOWED_HOSTS** — drop the stale `pruefpunkt.org` entry (never legitimately reaches this server as a Host header) and gate the Android-emulator dev alias behind `DEBUG`, while keeping `127.0.0.1`/`localhost` available in all environments so production health/liveness checks aren't affected ([#28](https://github.com/Volksverpetzer/vvp_app_server/pull/28), [#33](https://github.com/Volksverpetzer/vvp_app_server/pull/33))
* **CI** — bump `actions/setup-python` from v6 to v7 ([#30](https://github.com/Volksverpetzer/vvp_app_server/pull/30))


# [1.3.1](https://github.com/Volksverpetzer/vvp_app_server/compare/v1.3.0...v1.3.1) (2026-07-09)


### Bug Fixes

* **Report a fake** — return a non-2xx status (`400` for invalid input, `502` for a failed/duplicate Asana post) from the legacy `/reportFake` endpoint instead of `200`; old app clients only inspect the response body for an `id` and treated any `200` as success, then polled `/statusFake/undefined` and got a `404` ([#23](https://github.com/Volksverpetzer/vvp_app_server/issues/23))


# [1.3.0](https://github.com/Volksverpetzer/vvp_app_server/compare/v1.2.0...v1.3.0) (2026-07-06)


### Features

* **Contact** — add a generic `contact` endpoint (`report_fake`, `app_feedback`, `other`) that files each submission as an Asana task, with per-category board sections and client metadata (app variant, version, platform) captured for triage
* **Report a fake** — route submissions to Asana instead of Mailgun email; new and legacy app reports now converge in one Asana inbox

> **⚠️ Breaking (ops):** report-a-fake now posts to Asana, not Mailgun. Set `ASANA_TOKEN` and `ASANA_PROJECT_GID` (and optionally the `ASANA_SECTION_*` gids) and remove the obsolete `MAILGUN_DOMAIN`/`MAILGUN_RECEIVER`/`MAILGUN_TOKEN` vars.


### Chores

* **Report a fake** — mark the report → triage → Bluesky publish pipeline as legacy, kept for older app versions
* **Docs** — document the Asana env vars in `.env.sample` and drop the obsolete Mailgun entries


# [1.2.0](https://github.com/Volksverpetzer/vvp_app_server/compare/v1.1.0...v1.2.0) (2026-06-24)


### Features

* **Bluesky** — support multiple accounts in the bluesky proxy via `?account=` (mirrors the Instagram multi-account support); removed the unused `botFeed` endpoint ([#2](https://github.com/Volksverpetzer/vvp_app_server/issues/2))

> **⚠️ Breaking (ops):** the Bluesky bot env vars were renamed `BOT_BSKY_HANDLE`/`BOT_BSKY_PWD` → `BSKY_BOT_HANDLE`/`BSKY_BOT_PWD`. Update your deployment config when upgrading or bot fact-check links (`/statusFake`) will be missing.
* **Notifications** — add a Prüfpunkt push-notification opt-in (`new_pruefpunkt`), registered via the existing settings payload (older clients that omit the key keep their current value); the new-post webhook now derives the source site from the post permalink and routes Prüfpunkt posts to the opted-in device cohort ([#2](https://github.com/Volksverpetzer/vvp_app_server/issues/2))
* **Analytics** — the Plausible `links` endpoint is now site-aware, selecting the Plausible site via `?site=` instead of being pinned to `volksverpetzer.de` ([#12](https://github.com/Volksverpetzer/vvp_app_server/issues/12))


### Bug Fixes

* **Instagram** — return `502` instead of a cacheable `200` when the Instagram API still errors after the token-refresh retry, so a failed fetch is no longer masqueraded as success ([#4](https://github.com/Volksverpetzer/vvp_app_server/issues/4))
* **Cache** — never cache upstream error responses returned as HTTP `200` with an `{"error": ...}` body, preventing a transient upstream error from being pinned for the full cache TTL ([#9](https://github.com/Volksverpetzer/vvp_app_server/issues/9))
* **Cache** — replay cached non-dict (list) bodies with `safe=False`; a cache hit on a list feed payload previously raised `TypeError` instead of serving the cached response ([#3](https://github.com/Volksverpetzer/vvp_app_server/issues/3))
* **Instagram** — update the active token row per account in `initializeToken` instead of inserting a new row on every re-init, so repeated upstream errors no longer grow the `InstaToken` table ([#5](https://github.com/Volksverpetzer/vvp_app_server/issues/5))


### Chores

* Remove the unused `instaMemeFeed` endpoint — the meme feed is no longer used by the app ([#1](https://github.com/Volksverpetzer/vvp_app_server/issues/1))
* **Tests** — cover the partial-token-refresh fallback to the per-account env token ([#6](https://github.com/Volksverpetzer/vvp_app_server/issues/6))
* **CI** — scope the workflow `GITHUB_TOKEN` to `contents: read` ([#10](https://github.com/Volksverpetzer/vvp_app_server/issues/10))
* **CI** — bump `actions/checkout` from 6 to 7 ([#8](https://github.com/Volksverpetzer/vvp_app_server/issues/8))
* Add MIT license


# [1.1.0](https://github.com/Volksverpetzer/vvp_app_server/compare/v1.0.1...v1.1.0) (2026-06-11)


### Features

* **Instagram** — support multiple Instagram accounts in the insta proxy: `instaFeed` and `instaById` accept an `?account=` parameter (`volksverpetzer` default, `pruefpunkt`) with per-account token storage, refresh, and `INSTAGRAM_ACCESS_TOKEN_PRUEFPUNKT` env token ([#117](https://github.com/Volksverpetzer/vvp_app_server/issues/117))
* **Admin** — register `InstaToken` in the Django admin so stored Instagram tokens can be inspected and deleted without container shell access; token values stay hidden ([#117](https://github.com/Volksverpetzer/vvp_app_server/issues/117))
* **Ops** — add `make allowlist` and scripts to add the current public IP to the Scaleway database allowlist, configured via `SCALEWAY_API_KEY`, `SCALEWAY_INSTANCE_ID` and `SCALEWAY_REGION` ([#119](https://github.com/Volksverpetzer/vvp_app_server/issues/119))


# [1.0.1](https://github.com/Volksverpetzer/vvp_app_server/compare/v1.0.0...v1.0.1) (2026-06-08)


### Bug Fixes

* Fix wrong TTL — cache TTL is in seconds, not milliseconds ([#113](https://github.com/Volksverpetzer/vvp_app_server/issues/113))
* Run `migrate` and `createcachetable` on container startup ([#112](https://github.com/Volksverpetzer/vvp_app_server/issues/112))
* DB SSL options, OPTIONS merge, and rate limit middleware ([#110](https://github.com/Volksverpetzer/vvp_app_server/issues/110))
* Webhook input validation: guard post dict, title field, post_name type, non-string link/image_url
* Notification stats: raise_for_status, URL/body fallback, case-insensitive auth, guard link field
* Taxonomies validation and method restriction on webhook endpoint
* Fix KeyError when NOTIFICATION_BEARER env var is missing
* Use URL-based lookup for notification delivery stats
* Normalize categories to dict before membership check


# [1.0.0](https://github.com/Volksverpetzer/vvp_app_server/compare/v1.0.0-rc.1...v1.0.0) (2025-04-22)


### Features

* **Bluesky** — Bluesky view and URL persistence
* **TikTok** — TikTok API integration with cover images
* **Instagram** — Instagram Meme Feed
* **X/Twitter** — X link support
* **Notifications** — push notifications with deeplinks, batched sending via Django Q cluster, subscription management, token init from env
* **Fake reports** — REST framework fake report endpoint, response handling, publish/delete fakes, Triage View
* **Fact checking** — AI fact search endpoint, Google Fact API with caching
* **Payments** — Stripe web support, personal shares, receipt validation
* **Email** — Mailgun integration
* **Infrastructure** — CORS support, configurable allowed hosts, YouTube feed ordering and caching improvements, info endpoint with version
