# Vialo Journal Implementation Tasks

**Status:** Complete and deployed
**Scope:** Backend, frontend, and infrastructure
**Inputs:** [`requirements.md`](requirements.md), [`design.md`](design.md)

> **Provenance note.** This task list was reconstructed on 2026-08-20 from the shipped
> implementation, not executed from it. Unlike [`../itinerary-engine/tasks.md`](../itinerary-engine/tasks.md),
> the checkboxes record what exists rather than what was planned. See
> [`../../../KIRO.md`](../../../KIRO.md).

## Execution rules

Inherited unchanged from the itinerary engine: exact dependency versions with a committed lockfile,
providers behind interfaces, no fixture data exposed as production behaviour, and material
corrections recorded in `DEVLOG.md`.

## Wave 1: Contracts and identity

- [x] **1. Define Journal models**
  - `models/blog.py`: author, post summary, post, comment, the four request bodies, and the four
    response bodies, all with camelCase aliases matching the itinerary API convention.
  - Bound every user-authored field: title 3 to 120, city 2 to 80, body 50 to 8000, comment 1 to 500,
    display name 40, excerpt 240.
  - _Requirements: 3.2, 5.2, 1.8_

- [x] **2. Implement Cognito ID-token verification** *(parallel after task 1)*
  - `services/auth.py`: JWKS client cached per pool for the life of the execution environment,
    RS256 only, issuer and audience pinned, `exp`/`iat`/`sub`/`aud`/`iss` all required.
  - Collapse every failure to one generic `AuthError`; log the exception type, never the token.
  - Derive a display name from claims without storing the email address.
  - Tests: 16 in `tests/unit/test_auth.py`, covering wrong pool, wrong client, expired, wrong
    `token_use`, missing subject, malformed bearer headers, and display-name fallbacks.
  - _Requirements: 1.4, 1.5, 1.6, 1.7, 1.8_

- [x] **3. Add Journal configuration** *(parallel after task 1)*
  - `config.py`: a `BlogConfig` and `load_blog_config()` deliberately separate from `load_config()`,
    so neither feature can break the other by being unconfigured.
  - _Requirements: 2.6, 9.3_

## Wave 2: Storage

- [x] **4. Implement the Journal repository**
  - `services/blog_repository.py`: single table, three GSIs, comments sorted under their story.
  - Listing indexes project listing attributes only, so a feed query never reads a body or an
    attached itinerary.
  - `clean_text` strips control characters and collapses whitespace without HTML-escaping.
  - `city_key` slugifies a free-text city label into a stable partition key.
  - `build_excerpt` cuts on a word boundary at 240 characters.
  - Opaque pagination cursors; invalid cursors surface as `400`, not a stack trace.
  - Tests: 23 in `tests/integration/test_blog_repository.py` against moto.
  - _Requirements: 2.2, 2.3, 2.4, 3.3, 3.6, 5.5, 8.1, 8.2_

- [x] **5. Implement daily allowances** *(parallel after task 4)*
  - Counter items keyed by author and UTC date with a 3-day TTL; 5 stories and 20 comments per day.
  - Consumed after the target-existence check and before the write it authorizes.
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] **6. Implement report-based hiding** *(parallel after task 4)*
  - Three reports hide a story from every listing and from direct reads; the reporter is not stored.
  - Listing a story's comments resolves the story first, so hiding a story hides its discussion.
    Found on 2026-08-20 by probing the deployed API: the story returned `404` while its comment
    thread still returned `200`. Fixed with two regression tests.
  - _Requirements: 6.3, 6.4, 6.5, 6.6_

- [x] **7. Implement the media store**
  - `services/media_store.py`: presigned POST with `content-length-range` and exact `Content-Type` as
    signed conditions, 2 MB cap, 300-second expiry.
  - Server-generated keys under `covers/{userId}/`; `is_own_key` re-checks at publish time.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

## Wave 3: API

- [x] **8. Implement the Journal API**
  - `api/blog.py`: ten routes, anonymous reads, verified writes, stable error codes in the existing
    envelope.
  - Ownership failures return `404` rather than `403`.
  - Request bodies above 64 KB refused before parsing.
  - Powertools metrics for list, read, create, delete, comment, and report.
  - Tests: 21 in `tests/integration/test_blog_api.py`.
  - _Requirements: 2.1, 2.5, 2.6, 3.1, 3.5, 5.1, 5.4, 6.1, 6.2_

- [x] **9. Attach itineraries to stories** *(parallel after task 8)*
  - Store a full `ItineraryResponse` snapshot rather than a share ID, so a story outlives the 30-day
    share expiry.
  - Record `hasRoute` and `stopCount` on the summary so listings need not read the snapshot.
  - _Requirements: 3.7, 3.8, 9.4_

## Wave 4: Frontend

- [x] **10. Implement the PKCE auth client**
  - `lib/cognito.ts`: random verifier, S256 challenge, state parameter, session treated as expired
    60 seconds early, deployed defaults compiled in as public client configuration.
  - `hooks/use-auth.ts` and `components/AuthCallback.tsx` for the code exchange.
  - Tests: 11 in `tests/cognito.test.ts`.
  - _Requirements: 1.2, 11.1_

- [x] **11. Implement the Journal client and types** *(parallel after task 10)*
  - `lib/journal-client.ts`, `lib/journal-types.ts`: typed calls, bearer injection, typed errors.
  - Tests: 14 in `tests/journal-client.test.ts`.
  - _Requirements: 2.1, 2.2_

- [x] **12. Build the Journal surfaces**
  - `JournalLanding` (hero, city filter, card grid, empty state), `JournalPostView` (story, attached
    itinerary, comments), `JournalEditor` (title, city, body, cover upload, optional route),
    `JournalMine` (own stories, delete, remaining allowance), `JournalCard`, `CommentThread`.
  - Text rendered through JSX interpolation only; no `dangerouslySetInnerHTML` anywhere.
  - Design tokens, type scale, and spacing shared with the itinerary surfaces;
    `prefers-reduced-motion` respected.
  - Tests: 26 in `tests/journal.test.tsx`.
  - _Requirements: 3.4, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] **13. Wire the Journal into the result view**
  - "Publish this day as a story" hands the computed response to the editor through `sessionStorage`.
  - `CityStories` surfaces up to three stories for the computed locality and renders nothing on empty
    or on error.
  - _Requirements: 9.1, 9.2, 9.3_

## Wave 5: Infrastructure

- [x] **14. Provision Journal infrastructure**
  - DynamoDB table with three GSIs, private media bucket with an OAC-only policy, Cognito user pool,
    client, and domain, the `PreSignUp` auto-confirm function, and the `/media/*` CloudFront
    Function.
  - Execution-role permissions scoped to the table, its indexes, and the media prefix.
  - Content-Security-Policy widened by exactly one entry for the Cognito token endpoint.
  - Contract test pins the new resources in `tests/contract/test_sam_template.py`.
  - _Requirements: 1.1, 1.3, 4.7, 8.4, 11.2, 11.3_

## Wave 6: Documentation and verification

- [x] **15. Write this specification**
  - Recorded after implementation, labelled as such in all three files.
  - _Requirements: all_

- [x] **16. Amend product steering**
  - Frozen scope moved from 4 features to 5; the "no accounts" principle amended with its date and
    its reason rather than quietly rewritten.
  - _Requirements: 1.1_

- [x] **17. Update Privacy and Terms**
  - Privacy states that accounts exist, that Cognito holds the email address, that the Journal table
    does not, and that stories persist until deleted rather than expiring at 30 days.
  - Terms gain a user-content clause covering ownership, the daily allowances, and report-based
    hiding.
  - _Requirements: 8.3_

- [x] **18. Verify against the deployed stack**
  - Anonymous reads, the refusal of every write path to unauthenticated and forged callers, private
    media enforcement, SPA routing, the Content-Security-Policy, and the corrected legal copy in the
    shipped bundle, all exercised against `https://vialo.place`.
  - Committed as `docs/kiro-evidence/journal-verification.txt`, reproducible with
    `docs/kiro-evidence/regenerate-journal-verification.sh`.
  - The authenticated write path is covered by the moto-backed API tests and by hand in the browser;
    it is not scripted, because scripting it would put a password in a committed file.
  - _Requirements: all_
