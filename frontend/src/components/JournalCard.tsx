import { Link } from 'react-router-dom';
import type { PostSummary } from '../lib/journal-types';

interface JournalCardProps {
  post: PostSummary;
  index?: number;
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

export default function JournalCard({ post, index = 0 }: JournalCardProps) {
  return (
    <article
      className="journal-card"
      style={{ '--card-index': index } as React.CSSProperties}
    >
      <Link to={`/journal/p/${post.postId}`} className="journal-card__link">
        {post.coverImageUrl ? (
          <div className="journal-card__image-wrap">
            <img
              src={post.coverImageUrl}
              alt=""
              className="journal-card__image"
              loading="lazy"
            />
          </div>
        ) : (
          <div className="journal-card__image-fallback" aria-hidden="true">
            <span className="journal-card__fallback-initial">
              {post.title.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
        <div className="journal-card__body">
          <h3 className="journal-card__title">{post.title}</h3>
          <p className="journal-card__meta">
            <span>{post.city}</span>
            <span aria-hidden="true">·</span>
            <span>{post.author.displayName}</span>
            <span aria-hidden="true">·</span>
            <time dateTime={post.createdAt}>{relativeDate(post.createdAt)}</time>
          </p>
          <div className="journal-card__footer">
            {post.hasRoute && (
              <span className="journal-card__route-pill">
                Route attached · {post.stopCount} stops
              </span>
            )}
            {post.commentCount > 0 && (
              <span className="journal-card__comments">
                {post.commentCount} comment{post.commentCount === 1 ? '' : 's'}
              </span>
            )}
          </div>
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
  transition: box-shadow var(--duration-fast) ease;
  animation: card-rise var(--duration-section) ease both;
  animation-delay: calc(var(--card-index, 0) * 60ms);
}

@media (prefers-reduced-motion: reduce) {
  .journal-card {
    animation: none;
  }
}

@keyframes card-rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.journal-card:hover {
  box-shadow: 0 4px 16px rgb(43 35 38 / 0.08);
}

.journal-card__link {
  display: block;
  text-decoration: none;
  color: inherit;
}

.journal-card__image-wrap {
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: var(--color-surface);
}

.journal-card__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.journal-card__image-fallback {
  aspect-ratio: 16 / 9;
  background: var(--color-accent-lilac);
  display: flex;
  align-items: center;
  justify-content: center;
}

.journal-card__fallback-initial {
  font-family: var(--font-display);
  font-size: 38px;
  font-weight: 500;
  color: var(--color-primary);
  opacity: 0.5;
}

.journal-card__body {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.journal-card__title {
  font-size: 17px;
  font-weight: 600;
  line-height: 22px;
  color: var(--color-ink);
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.journal-card__meta {
  font-size: 13px;
  color: var(--color-ink-muted);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.journal-card__footer {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

.journal-card__route-pill {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 2px var(--space-2);
  border-radius: var(--radius-pill);
}

.journal-card__comments {
  font-size: 12px;
  color: var(--color-ink-muted);
}
`;
