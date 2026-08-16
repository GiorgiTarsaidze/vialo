# Vialo frontend

React and Vite implement Vialo's mobile-first input, route comparison, scheduled timeline, Google Maps handoff, and anonymous share screens. Production uses same-origin `/api/*` requests through CloudFront; no server credential is included in the bundle.

## Local checks

```bash
npm ci
npm run generate:contracts
npm run lint
npm run typecheck
npm test
VITE_GOOGLE_MAPS_BROWSER_KEY=replace-with-referrer-restricted-key npm run build
```

`VITE_GOOGLE_MAPS_BROWSER_KEY` is the browser-only Maps JavaScript API key. Browser keys are visible to visitors by design, so restrict it to the production `https://vialo.place/*` referrer (and explicitly approved local development origins when needed) and enable only the Maps JavaScript API. Never use the Google server key here.

The committed `src/lib/itinerary-response.schema.json` is generated from the backend Pydantic model. Backend and frontend tests fail if it drifts.

## Deployment

The repository-level `scripts/deploy-frontend.sh` builds with the browser key supplied by the environment, uploads hashed assets with immutable caching, uploads `index.html` without caching, and invalidates the CloudFront entry points. The S3 bucket is private and can be read only through CloudFront Origin Access Control.

## Fonts

The production bundle self-hosts the Latin subsets of:

- **Inter**, Copyright 2020 The Inter Project Authors, licensed under the SIL Open Font License 1.1.
- **Newsreader**, Copyright 2020 The Newsreader Project Authors, licensed under the SIL Open Font License 1.1.

Font files and metadata are provided by the pinned `@fontsource/inter` and `@fontsource/newsreader` packages. Their license texts are available as `OFL-1.1` metadata in those packages and at <https://openfontlicense.org/>. No production font request is made to a third-party font service.
