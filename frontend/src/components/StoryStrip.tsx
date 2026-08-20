import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { PostSummary } from '../lib/journal-types';
import { fetchPosts } from '../lib/journal-client';

/**
 * A continuously drifting band of recent Journal stories, shown under the hero
 * on the home page. It is what makes the planner and the Journal read as one
 * product rather than two tabs sharing a domain.
 *
 * Motion rules this respects:
 *  - It is a marquee, not a carousel. Nothing is hidden and then swapped in on a
 *    timer, so no content ever changes under the reader.
 *  - It pauses on hover and on keyboard focus.
 *  - Under `prefers-reduced-motion` the track does not move at all and becomes
 *    an ordinary horizontally scrollable row.
 *  - The duplicated half of the track is `aria-hidden`, so assistive technology
 *    and the tab order see each story exactly once.
 *  - It only drifts once there are enough distinct stories to fill a lane
 *    without repetition doing the work. Below that it is a static row.
 *
 * Renders nothing at all when the Journal is empty or unreachable: an empty
 * band under the hero would be worse than no band.
 */

const MAX_STORIES = 8;
/**
 * Below this many distinct stories the band does not drift. Repeating one or two
 * stories across a full-width lane reads as filler, and "nothing simulated" is a
 * product rule, not just a data rule.
 */
const MIN_FOR_DRIFT = 4;

interface StoryStripProps {
  /** Injected in tests to avoid a network call. */
  posts?: PostSummary[];
}

export default function StoryStrip({ posts: injected }: StoryStripProps) {
  const [posts, setPosts] = useState<PostSummary[]>(injected ?? []);

  useEffect(() => {
    if (injected) return;
    let cancelled = false;
    fetchPosts()
      .then((data) => {
        if (!cancelled) setPosts(data.posts.slice(0, MAX_STORIES));
      })
      .catch(() => {
        /* The home page must not degrade because the Journal is unreachable. */
      });
    return () => {
      cancelled = true;
    };
  }, [injected]);

  if (posts.length === 0) return null;

  // Drifting requires a track wider than the viewport, which means repeating the
  // source list. Repeating two stories into a lane of six makes a thin Journal
  // look busy, which is padding rather than content, so below this threshold the
  // band renders as a plain static row of exactly what exists.
  const drifting = posts.length >= MIN_FOR_DRIFT;

  const minTiles = 8;
  const repeats = drifting ? Math.max(1, Math.ceil(minTiles / posts.length)) : 1;
  const lane = Array.from({ length: repeats }, () => posts).flat();

  const tile = (post: PostSummary, key: string, duplicate: boolean) => (
    <Link
      key={key}
      to={`/journal/p/${post.postId}`}
      className="story-strip__tile"
      tabIndex={duplicate ? -1 : undefined}
    >
      <span className="story-strip__thumb" aria-hidden="true">
        {post.coverImageUrl ? (
          <img src={post.coverImageUrl} alt="" loading="lazy" />
        ) : (
          <span className="story-strip__thumb-letter">
            {post.title.charAt(0).toUpperCase()}
          </span>
        )}
      </span>
      <span className="story-strip__text">
        <span className="story-strip__city">{post.city}</span>
        <span className="story-strip__title">{post.title}</span>
        <span className="story-strip__by">
          {post.author.displayName}
          {post.hasRoute ? ` · ${post.stopCount} stops` : ''}
        </span>
      </span>
    </Link>
  );

  return (
    <section className="story-strip" aria-labelledby="story-strip-heading">
      <div className="story-strip__head">
        <h2 id="story-strip-heading" className="story-strip__heading">
          Days people actually walked
        </h2>
        <Link to="/journal" className="story-strip__all">
          All stories
          <span aria-hidden="true"> →</span>
        </Link>
      </div>

      <div className={`story-strip__viewport${drifting ? '' : ' story-strip__viewport--static'}`}>
        <div className={`story-strip__track${drifting ? '' : ' story-strip__track--static'}`}>
          <div className="story-strip__lane">
            {lane.map((post, i) => tile(post, `a-${post.postId}-${i}`, false))}
          </div>
          {drifting && (
            <div className="story-strip__lane" aria-hidden="true">
              {lane.map((post, i) => tile(post, `b-${post.postId}-${i}`, true))}
            </div>
          )}
        </div>
      </div>

      <style>{styles}</style>
    </section>
  );
}

const styles = `
.story-strip {
  margin-top: var(--space-8);
  padding-top: var(--space-6);
  border-top: 1px solid var(--color-border);
}

.story-strip__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.story-strip__heading {
  font-family: var(--font-display);
  font-size: 22px;
  line-height: 28px;
  font-weight: 500;
  color: var(--color-ink);
  margin: 0;
}

.story-strip__all {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
  text-decoration: none;
  white-space: nowrap;
  padding: var(--space-2) 0;
}

.story-strip__all:hover {
  text-decoration: underline;
}

/* Full-bleed viewport so tiles run off both edges rather than stopping at the
   container gutter, which is what makes the band feel like it is moving
   through the page instead of inside a box. */
.story-strip__viewport {
  position: relative;
  margin-left: calc(var(--space-4) * -1);
  margin-right: calc(var(--space-4) * -1);
  padding-left: var(--space-4);
  padding-right: var(--space-4);
  overflow: hidden;
  /* Soften both edges so tiles enter and leave rather than being cut off. */
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent);
  mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent);
}

@media (min-width: 640px) {
  .story-strip__viewport {
    margin-left: calc(var(--space-5) * -1);
    margin-right: calc(var(--space-5) * -1);
    padding-left: var(--space-5);
    padding-right: var(--space-5);
  }
}

.story-strip__track {
  display: flex;
  width: max-content;
  animation: story-drift 68s linear infinite;
}

/* Too few stories to loop honestly: no motion, no duplicate lane, no mask. */
.story-strip__viewport--static {
  overflow-x: auto;
  -webkit-mask-image: none;
  mask-image: none;
}

.story-strip__track--static {
  animation: none;
  width: auto;
}

.story-strip__viewport:hover .story-strip__track,
.story-strip__track:focus-within {
  animation-play-state: paused;
}

@keyframes story-drift {
  from { transform: translate3d(0, 0, 0); }
  to { transform: translate3d(-50%, 0, 0); }
}

.story-strip__lane {
  display: flex;
  gap: var(--space-3);
  padding-right: var(--space-3);
}

.story-strip__tile {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 286px;
  flex-shrink: 0;
  padding: var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  text-decoration: none;
  color: inherit;
  transition: border-color var(--duration-fast) ease, transform var(--duration-fast) ease;
}

.story-strip__tile:hover {
  border-color: var(--color-border-strong);
  transform: translateY(-2px);
}

.story-strip__thumb {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  border-radius: 12px;
  overflow: hidden;
  background: var(--color-accent-lilac);
  display: flex;
  align-items: center;
  justify-content: center;
}

.story-strip__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.story-strip__thumb-letter {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 500;
  color: var(--color-primary);
  opacity: 0.55;
}

.story-strip__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.story-strip__city {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-primary);
}

.story-strip__title {
  font-size: 15px;
  font-weight: 600;
  line-height: 20px;
  color: var(--color-ink);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.story-strip__by {
  font-size: 12px;
  color: var(--color-ink-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* No motion at all, and the band becomes an ordinary scrollable row. */
@media (prefers-reduced-motion: reduce) {
  .story-strip__viewport {
    overflow-x: auto;
    -webkit-mask-image: none;
    mask-image: none;
  }

  .story-strip__track {
    animation: none;
    width: auto;
  }

  .story-strip__lane[aria-hidden='true'] {
    display: none;
  }
}
`;
