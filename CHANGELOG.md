# [1.2.0](https://github.com/Volksverpetzer/vvp_app_server/compare/v1.1.0...v1.2.0) (2026-06-24)


### Features

* **Bluesky** — support multiple accounts in the bluesky proxy via `?account=` (mirrors the Instagram multi-account support); removed the unused `botFeed` endpoint ([#2](https://github.com/Volksverpetzer/vvp_app_server/issues/2))
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
