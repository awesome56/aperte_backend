---
name: analytics-aware
description: Use when creating or modifying pages, views, components, features, endpoints, API routes, or tracking-related code in this application. Ensure every new user-facing surface is wired into the Aperte analytics system (page views, events, conversions, performance, property analytics).
---

# Analytics-Aware Development

This application has a full visitor/page/property analytics system. Every new
page or feature should be tracked so the admin analytics dashboard stays
useful. Follow this checklist when creating or changing user-facing code.

## Where the analytics system lives

- **Frontend tracker**: `src/analytics/tracker.ts` (frontend repo) — buffered,
  batched, beacon-based. Auto-tracks page views via `router.afterEach`, time on
  page, performance metrics (TTFB/FCP/LCP/CLS), JS errors, sessions, visitors,
  UTM params, device info.
- **Ingestion**: `POST /api/v1/tracking/batch` (`src/tracking.py` in the
  backend repo) — one batched write; sessions upserted, traffic sources /
  device / browser / OS / country classified server-side.
- **Data model**: `AnalyticsEvent` and `VisitorSession` in
  `src/database.py`; `Property.views` counter increments on detail GET.
- **Reports**: `src/admin_analytics.py` (overview/traffic/content/properties/
  audience/performance/events/realtime/export/prune), gated by the
  `stats.view` permission. Admin UI lives in `AdminAnalytics.vue`
  (frontend repo), reachable at `/admin/analytics`.

## Checklist when creating a page or feature

1. **Page views**: plain routes are tracked automatically by the router hook —
   no extra code needed. If the route carries an entity id (e.g. a new
   `/rooms/:id`-style detail page), ensure it is exposed to the tracker so
   property/content analytics can associate it (`router.afterEach` in
   `src/router/index.ts` passes `property_id` for `/properties/:id`).
2. **User actions**: any meaningful interaction (buttons, form submits,
   filters, downloads, CTA clicks) should fire
   `tracker.trackEvent(name, category, properties)`. Follow existing
   conventions: fire-and-forget via
   `import('@/analytics/tracker').then((m) => m.default.trackEvent(...))`
   so the UI is never blocked.
3. **Conversions**: registrations, logins, bookings, contact submissions —
   use `category: 'conversion'` so they surface in the Conversions KPI.
4. **Search**: internal search usage must be tracked with
   `category: 'search'` and the query as `properties.term` (powers the
   "Search Terms" report).
5. **Backend changes**: if a new endpoint or model is added, consider what
   analytics it produces. New event types flow through
   `ingest_batch()` in `src/tracking.py` — no new table needed for most
   events (use `AnalyticsEvent` fields; add columns only when a new metric
   is genuinely required). Add DB changes via a flask-migrate revision in
   `migrations/versions/`.
6. **Property features**: anything tied to a property should include the
   `property_id` in tracked events/page views so per-property analytics
   (views, visitors, sessions, sources, devices) work.
7. **Admin reports**: new reporting surfaces go in `AdminAnalytics.vue`
   (or `src/admin_analytics.py` for new endpoints), use `adminApi.analytics*`,
   and are protected by the existing `stats.view` permission — never expose
   analytics to normal users.

## Rules

- **Keep tracking lightweight**: never block the request lifecycle. Use the
  buffered tracker / beacon; do not add per-interaction network calls.
- **Privacy**: never record passwords, form field values, or PII in event
  properties. Anonymous visitor/session IDs only. No cookies or
  fingerprinting.
- **No duplicates**: page views come from the router hook — do not also call
  `pageview()` manually in components (double counting).
- **Verify after building**: confirm the new page/event appears in
  `/admin/analytics` (Overview → Events tab / Content tab) for the current
  date range before considering the feature done.
