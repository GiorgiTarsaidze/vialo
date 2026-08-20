import { Link } from 'react-router-dom';
import type { PostSummary } from '../lib/journal-types';

interface JournalCardProps {
  post: PostSummary;
  index?: number;
  /** The lead story on the Journal landing page, laid out wide on desktop. */
  featured?: boolean;
}

function relativeDate(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} month${months === 1 ? '' : 's'} ago`;
  const years = Math.floor(months / 12);
  return `${years} year${years === 1 ? '' : 's'} ago`;
}

/**
 * One story in a listing.
 *
 * The cover is treated as evidence rather than decoration: it sits behind a
 * fixed aspect ratio so a missing image cannot change row height, and the
 * fallback is a quiet pastel plate with the story's initial rather than a
 * stock placeholder.
 */
export default function JournalCard({ post, index = 0, featured = false }: JournalCardProps) {
  const cover = post.coverImageUrl ? (
    <img src={post.coverImageUrl} alt="" className="journal-card__image" loading="lazy" />
  ) : (
    <span className="journal-card__fallback-initial" aria-hidden="true">
      {post.title.charAt(0).toUpperCase()}
    </span>
  );

  return (
    <article
      className={`journal-card${featured ? ' journal-card--featured' : ''}`}
      style={{ '--card-index': index } as React.CSSProperties}
    >
      <Link to={`/journal/p/${post.postId}`} className="journal-card__link">
        <div className={`journal-card__media${post.coverImageUrl ? '' : ' journal-card__media--empty'}`}>
          {cover}
          <span className="journal-card__city">{post.city}</span>
        </div>

        <div className="journal-card__body">
          <h3 className="journal-card__title">{post.title}</h3>
          {post.excerpt && <p className="journal-card__excerpt">{post.excerpt}</p>}

          <div className="journal-card__footer">
            <span className="journal-card__byline">
              <span className="journal-card__avatar" aria-hidden="true">
                {post.author.displayName.charAt(0).toUpperCase()}
              </span>
              <span className="journal-card__author">{post.author.displayName}</span>
            </span>
            <span className="journal-card__dot" aria-hidden="true">·</span>
            <time className="journal-card__time" dateTime={post.createdAt}>
              {relativeDate(post.createdAt)}
            </time>
          </div>

          {(post.hasRoute || post.commentCount > 0) && (
            <div className="journal-card__tags">
              {post.hasRoute && (
                <span className="journal-card__route-pill">
                  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                    <path
                      d="M2 9c3 0 1-6 4-6s1 5 4 5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.4"
                      strokeLinecap="round"
                    />
                    <circle cx="2" cy="9" r="1.5" fill="currentColor" />
                    <circle cx="10" cy="8" r="1.5" fill="currentColor" />
                  </svg>
                  {post.stopCount} stops
                </span>
              )}
              {post.commentCount > 0 && (
                <span className="journal-card__comments">
                  {post.commentCount} comment{post.commentCount === 1 ? '' : 's'}
                </span>
              )}
            </div>
          )}
        </div>
      </Link>
      <style>{styles}</style>
    </article>
  );
}

const styles = `
.journal-card {
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  overflow: hidden;
  transition:
    box-shadow var(--duration-fast) ease,
    border-color var(--duration-fast) ease,
    transform var(--duration-fast) ease;
  animation: card-rise var(--duration-section) ease both;
  animation-delay: calc(var(--card-index, 0) * 55ms);
}

@media (prefers-reduced-motion: reduce) {
  .journal-card {
    animation: none;
  }
}

@keyframes card-rise {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}

.journal-card:hover {
  border-color: var(--color-border-strong);
  box-shadow: 0 10px 28px rgb(43 35 38 / 0.09);
  transform: translateY(-3px);
}

.journal-card:focus-within {
  border-color: var(--color-border-strong);
}

.journal-card__link {
  display: flex;
  flex-direction: column;
  height: 100%;
  text-decoration: none;
  color: inherit;
}

.journal-card__media {
  position: relative;
  aspect-ratio: 3 / 2;
  overflow: hidden;
  background: var(--color-surface);
  flex-shrink: 0;
}

.journal-card__media--empty {
  background: var(--color-accent-lilac);
  display: flex;
  align-items: center;
  justify-content: center;
}

.journal-card__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 400ms ease;
}

.journal-card:hover .journal-card__image {
  transform: scale(1.035);
}

@media (prefers-reduced-motion: reduce) {
  .journal-card__image,
  .journal-card:hover .journal-card__image {
    transition: none;
    transform: none;
  }
}

.journal-card__fallback-initial {
  font-family: var(--font-display);
  font-size: 56px;
  font-weight: 500;
  color: var(--color-primary);
  opacity: 0.4;
  line-height: 1;
}

.journal-card__city {
  position: absolute;
  left: var(--space-3);
  bottom: var(--space-3);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-primary);
  background: var(--color-surface-strong);
  border-radius: var(--radius-pill);
  padding: 5px var(--space-3);
  box-shadow: 0 2px 8px rgb(43 35 38 / 0.12);
}

.journal-card__body {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  flex: 1;
}

.journal-card__title {
  font-family: var(--font-display);
  font-size: 21px;
  font-weight: 500;
  line-height: 27px;
  color: var(--color-ink);
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.journal-card__excerpt {
  font-size: 14px;
  line-height: 22px;
  color: var(--color-ink-muted);
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.journal-card__footer {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: auto;
  padding-top: var(--space-2);
  font-size: 13px;
  color: var(--color-ink-muted);
}

.journal-card__byline {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.journal-card__avatar {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  border-radius: var(--radius-pill);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 11px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.journal-card__author {
  font-weight: 500;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.journal-card__dot {
  color: var(--color-border-strong);
}

.journal-card__time {
  white-space: nowrap;
}

.journal-card__tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.journal-card__route-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 4px var(--space-3);
  border-radius: var(--radius-pill);
}

.journal-card__comments {
  font-size: 12px;
  color: var(--color-ink-muted);
}

/* Featured lead story: a wide two-column plate on desktop only. */
@media (min-width: 900px) {
  .journal-card--featured .journal-card__link {
    flex-direction: row;
    align-items: stretch;
  }

  .journal-card--featured .journal-card__media {
    width: 54%;
    aspect-ratio: auto;
    min-height: 340px;
  }

  .journal-card--featured .journal-card__body {
    width: 46%;
    padding: var(--space-6);
    justify-content: center;
    gap: var(--space-3);
  }

  .journal-card--featured .journal-card__title {
    font-size: 32px;
    line-height: 38px;
    -webkit-line-clamp: 3;
  }

  .journal-card--featured .journal-card__excerpt {
    font-size: 15px;
    line-height: 24px;
    -webkit-line-clamp: 4;
  }

  .journal-card--featured .journal-card__footer {
    margin-top: var(--space-2);
  }

  .journal-card--featured .journal-card__fallback-initial {
    font-size: 96px;
  }
}
`;
