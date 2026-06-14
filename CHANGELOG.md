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
