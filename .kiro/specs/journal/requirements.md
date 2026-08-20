# Vialo Journal Requirements

**Status:** Implemented and deployed
**Scope:** Backend, frontend, and infrastructure
**Product cap:** One cover image per story, plain text bodies, flat comments, no editing after publish

> **Provenance note.** Unlike [`../itinerary-engine/`](../itinerary-engine/), this specification was
> written *after* the implementation, on 2026-08-20, by reading the shipped code and recording what
> it actually does. It is an accurate description of the deployed system, not the document the code
> was generated from. The reason is recorded in [`../../../KIRO.md`](../../../KIRO.md); it is the one
> feature in this repository where the spec-before-code discipline was not followed, and saying so
> is cheaper than pretending otherwise.

## Purpose

The Journal is the second surface of Vialo. The itinerary engine answers "what should my day look
like"; the Journal answers "what was this day actually like for the person who walked it". A
traveller publishes a short written account of a day in a city, optionally attaching the itinerary
Vialo computed for them, and other travellers read it, comment on it, and see it surfaced when they
plan a day in that same city.

Reading is anonymous. Publishing, commenting, and reporting require a verified account.

The Journal must never invent a story, an author, a comment, or an attached itinerary, and must never
render user-authored text as markup.

## Non-goals

- Editing a story after it is published
- Threaded comment replies, likes, follows, or notifications
- Inline images inside a story body; only one cover image per story
- Rich text, markdown, or any HTML in user-authored content
- Public author profile pages or any display of an author's email address
- Human moderation queues, appeals, or an admin console

## Terms

- **Story:** One published Journal entry: title, city, body, optional cover image, optional itinerary.
- **Author:** A Cognito user, identified publicly only by an opaque subject and a display name.
- **City key:** A slug derived from the author's free-text city label, used as a partition key.
- **Attached itinerary:** A full `ItineraryResponse` snapshot copied into the story at publish time.
- **Viewer:** The signed-in caller of `GET /api/blog/me`.
- **Daily allowance:** The per-author cap on writes in one UTC day.

## Requirement 1: Identity and authentication

1.1. THE SYSTEM SHALL use an AWS Cognito user pool as the sole identity provider, with email as the
username attribute.

1.2. THE browser SHALL authenticate using the Authorization Code flow with PKCE against the Cognito
hosted UI, with no client secret.

1.3. WHEN a user signs up, THE SYSTEM SHALL auto-confirm the account and auto-verify the email
through a `PreSignUp` Lambda trigger, so that no emailed verification code is required.

1.4. THE backend SHALL verify every write request's Cognito ID token against the user pool's
published JWKS, checking signature, issuer, audience, expiry, and a `token_use` of `id`.

1.5. WHEN a token is absent, malformed, expired, or issued for a different pool or client, THE
SYSTEM SHALL return `401 UNAUTHENTICATED` and SHALL NOT reveal which check failed.

1.6. THE SYSTEM SHALL NOT log ID tokens, and SHALL NOT copy an email address out of a token into the
Journal table or any API response.

1.7. THE public identity of an author SHALL consist only of the opaque Cognito subject and a display
name derived from `nickname`, `preferred_username`, `name`, `given_name`, or the local part of the
email, in that order, falling back to `Traveller`.

1.8. THE display name SHALL be collapsed to a single line, stripped of non-printable characters, and
bounded at 40 characters.

## Requirement 2: Reading the Journal

2.1. THE SYSTEM SHALL serve `GET /api/blog/posts`, `GET /api/blog/posts/{postId}`, and
`GET /api/blog/posts/{postId}/comments` without authentication.

2.2. `GET /api/blog/posts` SHALL return stories newest first, in pages of 12, with an opaque
`nextCursor` that is `null` on the final page.

2.3. WHEN a `city` query parameter is supplied, THE SYSTEM SHALL return only stories whose city key
matches, using a dedicated index rather than a table scan.

2.4. THE listing indexes SHALL project only listing attributes, so that a feed query never reads a
story body or an attached itinerary.

2.5. WHEN a requested story does not exist or has been hidden, THE SYSTEM SHALL return
`404 POST_NOT_FOUND` with a message that does not distinguish the two cases.

2.6. WHEN the Journal store is unavailable, THE SYSTEM SHALL return `503 JOURNAL_UNAVAILABLE` and
SHALL NOT affect the itinerary pipeline.

## Requirement 3: Publishing a story

3.1. `POST /api/blog/posts` SHALL require a verified account.

3.2. A story SHALL carry a title of 3 to 120 characters, a city of 2 to 80 characters, and a body of
50 to 8000 characters, all validated before any write.

3.3. THE body SHALL be stored as plain text. Control characters SHALL be stripped, runs of spaces
collapsed, and runs of more than one blank line collapsed to one, without otherwise altering meaning.

3.4. THE SYSTEM SHALL NOT HTML-escape stored text, and the frontend SHALL render it through JSX text
interpolation only, never through `dangerouslySetInnerHTML` or any equivalent.

3.5. WHEN a request body exceeds 64 KB, THE SYSTEM SHALL reject it before parsing.

3.6. THE SYSTEM SHALL derive a listing excerpt of at most 240 characters from the body, cut on a word
boundary.

3.7. WHEN an itinerary is attached, THE SYSTEM SHALL store a full snapshot of the computed
`ItineraryResponse` inside the story, so that the story survives the 30-day expiry of anonymous
shares.

3.8. THE SYSTEM SHALL record whether a story has an attached itinerary and how many stops it
contains, so that listings can show this without reading the snapshot.

3.9. A story SHALL NOT be editable after publication. The author's only correction is deletion.

## Requirement 4: Cover images

4.1. `POST /api/blog/uploads` SHALL require a verified account and SHALL return a presigned S3 POST
for exactly one image.

4.2. THE SYSTEM SHALL accept only `image/jpeg`, `image/png`, and `image/webp`.

4.3. THE presigned policy SHALL enforce a maximum object size of 2 MB and an exact content type as
signed conditions, so that the browser cannot raise either. A presigned POST SHALL be used rather
than a presigned PUT for this reason.

4.4. THE upload target SHALL expire 300 seconds after issue.

4.5. THE object key SHALL be server-generated as `covers/{userId}/{uuid}.{ext}`, so that a caller
cannot choose a path or overwrite another author's image.

4.6. WHEN a story submits a cover key, THE SYSTEM SHALL verify the key was issued to that author and
SHALL reject any key containing a parent-directory segment.

4.7. THE media bucket SHALL be private, and images SHALL be served only through CloudFront using
Origin Access Control.

## Requirement 5: Comments

5.1. `POST /api/blog/posts/{postId}/comments` SHALL require a verified account.

5.2. A comment SHALL be 1 to 500 characters and SHALL be stored as plain text under the same cleaning
rules as a story body.

5.3. Comments SHALL be flat. THE SYSTEM SHALL NOT support replies to comments.

5.4. WHEN the target story does not exist, THE SYSTEM SHALL return `404 POST_NOT_FOUND` before
consuming any allowance.

5.5. THE SYSTEM SHALL maintain a comment count on the story so that listings do not need to count
comments.

## Requirement 6: Deletion and moderation

6.1. An author SHALL be able to delete their own story and their own comments.

6.2. WHEN a caller attempts to delete a story or comment they do not own, THE SYSTEM SHALL return
`404` rather than `403`, so that ownership is not disclosed.

6.3. `POST /api/blog/posts/{postId}/report` SHALL require a verified account and SHALL return `202`
without confirming any consequence.

6.4. THE SYSTEM SHALL NOT store the reporter's identity.

6.5. WHEN a story accumulates 3 reports, THE SYSTEM SHALL hide it from every listing and from direct
reads.

6.6. WHEN a story is hidden or absent, THE SYSTEM SHALL also refuse to list its comments, so that a
discussion cannot outlive the story it belongs to.

## Requirement 7: Abuse limits

7.1. THE SYSTEM SHALL cap each author at 5 published stories per UTC day.

7.2. THE SYSTEM SHALL cap each author at 20 comments per UTC day.

7.3. WHEN an allowance is exhausted, THE SYSTEM SHALL return `429 QUOTA_EXCEEDED` with a message
stating the limit.

7.4. Allowance counters SHALL expire automatically after 3 days.

7.5. `GET /api/blog/me` SHALL report the caller's remaining story allowance for the current day, so
that the editor can show it before a write is attempted.

## Requirement 8: Storage separation

8.1. Journal data SHALL live in its own DynamoDB table, separate from the place cache, the rate-limit
table, and anonymous shares, because its lifecycle, retention, and access pattern all differ.

8.2. Stories SHALL persist until their author deletes them. THE SYSTEM SHALL NOT apply a TTL to
stories or comments.

8.3. THE difference between Journal retention and the 30-day expiry of anonymous shares SHALL be
stated on the Privacy page.

8.4. Cover images SHALL live in their own S3 bucket, separate from the frontend asset bucket.

## Requirement 9: Integration with the itinerary engine

9.1. WHEN a user has a computed itinerary on screen, THE SYSTEM SHALL offer to publish it as a story
with the itinerary attached.

9.2. WHEN a computed itinerary's city has published stories, THE result view SHALL surface them, so
that the Journal and the engine read as one product rather than two tabs sharing a domain.

9.3. THE Journal SHALL NOT be required for the itinerary pipeline to function. A Journal outage SHALL
degrade the result view's stories section only.

9.4. Attaching an itinerary SHALL be optional. A story with no route is valid.

## Requirement 10: Presentation and accessibility

10.1. THE Journal SHALL use the same design tokens, type scale, and spacing as the itinerary surfaces.

10.2. THE landing page SHALL provide a hero, a city filter, and a card grid, with an explicit empty
state when no stories exist.

10.3. Motion SHALL respect `prefers-reduced-motion`.

10.4. Every interactive control SHALL be reachable and operable by keyboard, with a visible focus
indicator.

10.5. An attached itinerary SHALL be rendered read-only inside the story, reusing the existing share
renderer rather than a second implementation.

10.6. THE Journal SHALL NOT display any model-authored prose, consistent with the product-wide rule.

## Requirement 11: Security

11.1. THE Cognito hosted-UI domain and application client ID are public client configuration and MAY
appear in the browser bundle. No client secret SHALL exist.

11.2. THE Content-Security-Policy SHALL permit the Cognito token endpoint and SHALL NOT be widened
beyond what the flow requires.

11.3. THE Lambda execution role SHALL be scoped to the Journal table, its indexes, and the media
bucket prefix, and SHALL NOT be granted wildcard access.

11.4. No Cognito, AWS, or Google credential SHALL appear in any committed file.
