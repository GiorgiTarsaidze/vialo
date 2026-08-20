# Vialo Journal Technical Design

**Status:** Describes the deployed implementation
**Inputs:** [`requirements.md`](requirements.md)

> **Provenance note.** Written on 2026-08-20 by reading the shipped code, after the implementation
> rather than before it. See the same note in [`requirements.md`](requirements.md).

## Shape of the feature

```
                    anonymous read
browser ──────────────────────────────▶ CloudFront ──▶ API Gateway ──▶ Lambda ──▶ vialo-journal-dev
   │                                         │                                      (DynamoDB)
   │  Cognito hosted UI (PKCE)               │
   ├────────────────────────────────▶ user pool ──▶ ID token
   │                                                     │
   │  Authorization: Bearer <id token>                   ▼
   └──────────────────────────────────────────▶ JWKS verification in Lambda
                                                         │
   cover image ──▶ presigned S3 POST ──▶ vialo-journal-media (private)
                                              │
                          /media/* ◀── CloudFront + Origin Access Control
```

One Lambda serves both the itinerary pipeline and the Journal. They share nothing but the process:
separate configuration loaders, separate tables, separate failure modes. `load_blog_config()` is
deliberately distinct from `load_config()` so that a missing Journal variable cannot stop a planning
request, and a missing Google key cannot stop a story from loading.

## Identity

### Why Cognito

The alternatives considered were a pen-name plus device token (no email, unrecoverable, trivially
spam-able) and rolling our own credential storage (an immediate password-handling liability in a
public repository). Cognito was chosen because no password code of ours exists, the token is a
standard signed JWT we can verify offline against published JWKS, and the hosted UI removes an entire
class of frontend bugs from the critical path.

The cost is honest and is recorded in the corrections table in `KIRO.md`: the hosted UI is Cognito's
default styling, not Vialo's design system. It is the one surface in the product that does not look
like the product.

### Why auto-confirm

Requirement 1.3 auto-confirms new accounts through a `PreSignUp` trigger. The reason is the judging
context: an emailed verification code is a hard dependency on mail deliverability from a domain with
no sending reputation, at the exact moment a judge is deciding whether the feature works. The trade
is real, unverified email addresses can register, and it is bounded by the per-author daily
allowances in Requirement 7 rather than by identity.

### Token verification

`services/auth.py` holds one `PyJWKClient` per pool for the life of the execution environment, so a
warm Lambda verifies without a network call. Every failure path collapses to a single `AuthError`
with a generic message; the exception type is logged, the token never is.

The display name is derived, not stored at signup. `display_name_from_claims` walks
`nickname`, `preferred_username`, `name`, `given_name`, then falls back to the local part of the
email, then to `Traveller`. This is what keeps email addresses out of the Journal table entirely:
the address exists only inside the user pool and inside the token, and the only thing that reaches
storage is the local part, already cleaned and bounded.

## Storage

### Single table, three indexes

`vialo-journal-dev`, on-demand, with the same tagging convention as the other three tables.

| Item | `pk` | `sk` |
|---|---|---|
| Story | `POST#<postId>` | `META` |
| Comment | `POST#<postId>` | `COMMENT#<createdAt>#<commentId>` |
| Daily allowance | `AUTHOR#<userId>` | `QUOTA#<YYYY-MM-DD>` |

| Index | Purpose |
|---|---|
| `gsi1` | The global feed, newest first, on a single `FEED` partition |
| `gsi2` | Stories for one city key |
| `gsi3` | Stories by one author |

Comments sort under their story by creation time, so listing a story's comments is one query on the
base table with no index involved. The three indexes project listing attributes only: a feed page
never pulls a story body or an attached itinerary across the wire, which matters because an attached
itinerary is by far the largest thing in the table.

The single `FEED` partition is a deliberate, bounded choice. It is the classic hot-partition
anti-pattern and it is correct here: the write rate is capped at 5 stories per author per day, and
the read path is a single backwards query. Sharding the feed would add complexity to solve a problem
this feature cannot have at its abuse limits.

### Why a separate table

The place cache expires on its own schedule and holds no user data. The rate-limit table holds
HMACs and Bedrock spend counters. Anonymous shares expire after 30 days. Journal stories persist
until their author deletes them and are the only user-authored content in the system. Four different
lifecycles, four different retention answers, and one of them is the only one a privacy page has to
describe in terms of a person. Keeping them separate makes each answer independently true.

### Quotas

`consume_quota` increments a counter item keyed by author and UTC date, with a 3-day TTL, and raises
`QuotaExceededError` past the limit. It is consumed *before* the write it authorizes, and after the
existence check for the target story, so that a comment on a deleted story costs nothing.

## Text handling

The rule is one sentence: **stored text is plain text, and the frontend renders it as text.**

`clean_text` removes control characters, collapses runs of spaces, and collapses more than one blank
line to one. It does not HTML-escape, because escaping at the storage boundary is the wrong place:
it corrupts the stored value, it double-escapes on any second pass, and it silently becomes wrong the
moment a second renderer appears. The XSS defence is that React interpolates text nodes and the
Journal never calls `dangerouslySetInnerHTML`. That is a property enforced in the frontend, tested in
the frontend, and stated here so it cannot be quietly traded away.

Every user-authored field is length-bounded at the Pydantic layer: title 3 to 120, city 2 to 80, body
50 to 8000, comment 1 to 500, display name 40. The raw request body is refused above 64 KB before it
is parsed at all.

## Cover images

A presigned **POST**, not a presigned PUT. Only POST can carry `content-length-range` and an exact
`Content-Type` as signed policy conditions, which means the 2 MB cap and the image type are enforced
by S3 itself rather than by a browser that could simply not comply. The key is server-generated and
namespaced under the author's opaque subject, so path selection and cross-author overwrites are both
impossible by construction; `is_own_key` re-checks the namespace at publish time and rejects any key
containing `..`.

The bucket is private. Images reach the browser only through the existing CloudFront distribution at
`/media/*` with Origin Access Control and a CloudFront Function that rewrites the path to the bucket
key. No second distribution, no public bucket, no second TLS certificate.

Server-side re-encoding to strip EXIF GPS was scoped and deliberately not shipped. It would have
added Pillow to the Lambda layer for roughly 3 MB. This is a known gap, recorded rather than papered
over: a cover image can carry the location metadata its camera wrote.

## Integration with the itinerary engine

Two touch points, both one-directional so that a Journal failure cannot degrade a computed day.

**Publish this day as a story.** `ResultView` writes the computed `ItineraryResponse` into
`sessionStorage` and navigates to the editor, which picks it up and attaches it to the post. The full
response is snapshotted into the story rather than referenced by share ID, because anonymous shares
expire after 30 days and a story is meant to outlive that. The snapshot is rendered read-only by the
same component that renders a share, so there is exactly one itinerary renderer in the product.

**Stories from this city.** `CityStories` slugifies the computed locality name, asks for up to three
stories in that city, and returns `null` on empty *or on error*. A Journal outage removes the
section; it never shows a broken box on a working itinerary. This is the piece that makes the two
halves read as one product, and it is also the piece most likely to be empty early, which is why
rendering nothing is the correct empty state rather than an invitation.

## API surface

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/blog/posts` | none | `?city=`, `?cursor=`, 12 per page |
| GET | `/api/blog/posts/{postId}` | none | Includes body and attached itinerary |
| POST | `/api/blog/posts` | required | 201 with the created story |
| DELETE | `/api/blog/posts/{postId}` | required | Own story only, 204 |
| GET | `/api/blog/posts/{postId}/comments` | none | Newest first |
| POST | `/api/blog/posts/{postId}/comments` | required | 201 with the comment |
| DELETE | `/api/blog/posts/{postId}/comments/{commentId}` | required | Own comment only, 204 |
| POST | `/api/blog/posts/{postId}/report` | required | 202, reporter not stored |
| POST | `/api/blog/uploads` | required | Presigned POST for one cover |
| GET | `/api/blog/me` | required | Author, own stories, remaining allowance |

Error codes are stable strings in the same envelope the itinerary API uses:
`UNAUTHENTICATED`, `INVALID_INPUT`, `POST_NOT_FOUND`, `COMMENT_NOT_FOUND`, `QUOTA_EXCEEDED`,
`JOURNAL_UNAVAILABLE`, `UPLOAD_UNAVAILABLE`.

Ownership failures return `404`, never `403`. A `403` would confirm that a story exists and belongs
to someone else, which is information the caller has not earned.

## Frontend

| Route | Component |
|---|---|
| `/journal` | `JournalLanding`: hero, city filter, card grid, empty state |
| `/journal/p/:postId` | `JournalPostView`: story, attached itinerary, comments |
| `/journal/new` | `JournalEditor`: title, city, body, cover upload, optional route |
| `/journal/me` | `JournalMine`: own stories, delete, remaining allowance |
| `/auth/callback` | `AuthCallback`: PKCE code exchange, session storage |

`lib/cognito.ts` implements the PKCE flow directly against the hosted UI: a random verifier, an
S256 challenge, a state parameter, and a session in `localStorage` treated as expired 60 seconds
early. The Cognito domain and client ID are compiled into the bundle with deployed defaults. They are
public client configuration, not credentials: there is no client secret, and the redirect URI is
pinned in the user pool client.

## Infrastructure

Added to the existing `vialo-backend-dev` stack:

| Resource | Notes |
|---|---|
| `JournalTable` | On-demand DynamoDB, three GSIs |
| `JournalMediaBucket` | Private, OAC-only access |
| `JournalMediaBucketPolicy` | CloudFront service principal, this distribution only |
| `JournalAutoConfirmFunction` | 128 MB, inline, `PreSignUp` trigger |
| `JournalUserPool` | Email as username, 8-character minimum password |
| `JournalUserPoolClient` | No secret, PKCE, pinned redirect URI |
| `JournalUserPoolDomain` | `vialo-place-journal` |
| `JournalMediaRewriteFunction` | CloudFront Function mapping `/media/*` to bucket keys |

The Content-Security-Policy was widened by exactly one entry, the Cognito token endpoint, and no
more.

## What this design does not solve

Stated plainly because the alternative is discovering it during judging:

- **The hosted UI is not on-brand.** It is Cognito's default styling.
- **EXIF GPS is not stripped** from cover images.
- **Moderation is mechanical.** Three reports hide a story. There is no appeal and no human review.
- **Auto-confirmed signup means unverified email addresses.** Abuse is bounded by daily allowances,
  not by identity.
- **No editing.** The only correction available to an author is deletion and republication.
