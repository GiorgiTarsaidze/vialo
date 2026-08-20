import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchPosts } from '../lib/journal-client';
import { slugifyCity } from '../lib/journal-types';
import type { PostSummary } from '../lib/journal-types';
import { useAuth } from '../hooks/use-auth';
import JournalCard from './JournalCard';

export default function JournalLanding() {
  const navigate = useNavigate();
  const { authenticated, signIn } = useAuth();
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [cityFilter, setCityFilter] = useState<string>('');

  // Cities come from the unfiltered feed and are captured once. Deriving them
  // from the visible posts collapsed the filter row to a single city as soon as
  // a filter was applied, leaving no way back except "All cities".
  const [cities, setCities] = useState<string[]>([]);

  const loadPosts = useCallback(async (city?: string, cursor?: string) => {
    try {
      const slug = city ? slugifyCity(city) : undefined;
      const data = await fetchPosts(slug, cursor);
      if (cursor) {
        setPosts((prev) => [...prev, ...data.posts]);
      } else {
        setPosts(data.posts);
      }
      setNextCursor(data.nextCursor);
      if (!city && !cursor) {
        setCities(Array.from(new Set(data.posts.map((p) => p.city))).sort());
      }
    } catch {
      /* The empty state is the honest fallback. */
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadPosts(cityFilter || undefined).finally(() => setLoading(false));
  }, [cityFilter, loadPosts]);

  const handleLoadMore = async () => {
    if (!nextCursor) return;
    setLoadingMore(true);
    await loadPosts(cityFilter || undefined, nextCursor);
    setLoadingMore(false);
  };

  const handleWrite = async () => {
    if (authenticated) {
      navigate('/journal/new');
    } else {
      await signIn('/journal/new');
    }
  };

  const [lead, ...rest] = posts;
  // The lead plate only earns its width when there is a grid beneath it.
  const showLead = !cityFilter && posts.length >= 3;

  return (
    <div className="journal-landing">
      <section className="journal-hero" aria-labelledby="journal-heading">
        <p className="journal-hero__eyebrow">The Vialo Journal</p>
        <h1 id="journal-heading" className="journal-hero__headline">
          Days that actually happened
        </h1>
        <p className="journal-hero__sub">
          Written by the people who walked them, with the route attached.
        </p>
        <div className="journal-hero__actions">
          <button className="journal-hero__cta" onClick={handleWrite} type="button">
            Write a story
          </button>
          <Link to="/" className="journal-hero__secondary">
            Plan a day first
            <span aria-hidden="true"> →</span>
          </Link>
        </div>
      </section>

      {cities.length > 1 && (
        <nav className="journal-filters" aria-label="Filter by city">
          <button
            className={`journal-filter-btn${!cityFilter ? ' journal-filter-btn--active' : ''}`}
            onClick={() => setCityFilter('')}
            type="button"
            aria-pressed={!cityFilter}
          >
            All cities
          </button>
          {cities.map((city) => (
            <button
              key={city}
              className={`journal-filter-btn${cityFilter === city ? ' journal-filter-btn--active' : ''}`}
              onClick={() => setCityFilter(city)}
              type="button"
              aria-pressed={cityFilter === city}
            >
              {city}
            </button>
          ))}
        </nav>
      )}

      {loading ? (
        <div className="journal-skeletons" aria-live="polite" aria-busy="true">
          <span className="sr-only">Loading stories</span>
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="journal-skeleton" aria-hidden="true">
              <div className="journal-skeleton__media" />
              <div className="journal-skeleton__line journal-skeleton__line--title" />
              <div className="journal-skeleton__line" />
              <div className="journal-skeleton__line journal-skeleton__line--short" />
            </div>
          ))}
        </div>
      ) : posts.length === 0 ? (
        <div className="journal-empty" aria-live="polite">
          <div className="journal-empty__plate" aria-hidden="true">
            <svg viewBox="0 0 120 80" className="journal-empty__art">
              <path
                d="M12 62 Q34 22 58 44 T108 26"
                fill="none"
                stroke="var(--color-primary)"
                strokeWidth="2"
                strokeLinecap="round"
                strokeDasharray="5 7"
                opacity="0.5"
              />
              <circle cx="12" cy="62" r="4" fill="var(--color-primary)" />
              <circle cx="58" cy="44" r="4" fill="var(--color-primary)" opacity="0.65" />
              <circle cx="108" cy="26" r="4" fill="var(--color-accent-sun)" />
            </svg>
          </div>
          <p className="journal-empty__headline">
            {cityFilter ? `No stories from ${cityFilter} yet` : 'No stories yet'}
          </p>
          <p className="journal-empty__sub">
            {cityFilter
              ? 'Be the first to write one, or browse every city.'
              : 'Be the first to share a day you walked. Your route, your words.'}
          </p>
          <div className="journal-empty__actions">
            <button className="journal-hero__cta" onClick={handleWrite} type="button">
              Write the first one
            </button>
            {cityFilter && (
              <button
                className="journal-hero__secondary journal-hero__secondary--button"
                onClick={() => setCityFilter('')}
                type="button"
              >
                All cities
              </button>
            )}
          </div>
        </div>
      ) : (
        <>
          {showLead && lead && (
            <div className="journal-lead">
              <JournalCard post={lead} index={0} featured />
            </div>
          )}
          <div
            className={`journal-grid${(showLead ? rest : posts).length < 3 ? ' journal-grid--sparse' : ''}`}
            role="feed"
            aria-label="Journal stories"
          >
            {(showLead ? rest : posts).map((post, i) => (
              <JournalCard key={post.postId} post={post} index={i} />
            ))}
          </div>
          {nextCursor && (
            <div className="journal-load-more">
              <button
                className="journal-load-more__btn"
                onClick={handleLoadMore}
                disabled={loadingMore}
                type="button"
              >
                {loadingMore ? 'Loading…' : 'Load more stories'}
              </button>
            </div>
          )}
        </>
      )}

      <style>{styles}</style>
    </div>
  );
}

const styles = `
.journal-landing {
  padding-top: var(--space-4);
}

.journal-hero {
  text-align: center;
  padding: var(--space-7) 0 var(--space-6);
  max-width: 720px;
  margin: 0 auto;
}

.journal-hero__eyebrow {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin: 0 0 var(--space-3);
}

.journal-hero__headline {
  font-family: var(--font-display);
  font-size: 38px;
  line-height: 42px;
  font-weight: 500;
  letter-spacing: -0.015em;
  color: var(--color-ink);
  margin: 0 0 var(--space-3);
  text-wrap: balance;
}

@media (min-width: 640px) {
  .journal-hero__headline {
    font-size: 52px;
    line-height: 56px;
  }
}

.journal-hero__sub {
  font-size: 17px;
  line-height: 27px;
  color: var(--color-ink-muted);
  margin: 0 auto var(--space-5);
  max-width: 460px;
  text-wrap: balance;
}

/* One row, centred, both controls on the same optical baseline. The previous
   version stacked a filled button with no counterpart, which read as unaligned. */
.journal-hero__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--space-3) var(--space-5);
}

.journal-hero__cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 50px;
  padding: 0 var(--space-6);
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  background: var(--color-primary);
  border-radius: var(--radius-pill);
  transition: background var(--duration-fast) ease, transform var(--duration-fast) ease;
}

.journal-hero__cta:hover {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
}

.journal-hero__secondary {
  display: inline-flex;
  align-items: center;
  min-height: 50px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary);
  text-decoration: none;
  padding: 0 var(--space-2);
}

.journal-hero__secondary:hover {
  text-decoration: underline;
}

.journal-hero__secondary--button {
  background: none;
}

.journal-filters {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-2);
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-border);
}

.journal-filter-btn {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-ink-muted);
  padding: 0 var(--space-4);
  border: 1px solid var(--color-border);
  background: var(--color-surface-strong);
  border-radius: var(--radius-pill);
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  transition:
    background var(--duration-fast) ease,
    color var(--duration-fast) ease,
    border-color var(--duration-fast) ease;
}

.journal-filter-btn:hover {
  color: var(--color-ink);
  border-color: var(--color-border-strong);
}

.journal-filter-btn--active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #ffffff;
  font-weight: 600;
}

.journal-lead {
  margin-bottom: var(--space-5);
}

.journal-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-5);
  align-items: stretch;
}

/* One or two stories in a three-column grid leaves a dead column that reads as
   a loading failure. Centre them at a readable width instead of stretching one
   card across the page.

   Compound selector on purpose: the responsive .journal-grid rules below have
   the same specificity and come later, so a single class would lose to them. */
.journal-grid.journal-grid--sparse {
  justify-content: center;
}

@media (min-width: 620px) {
  .journal-grid.journal-grid--sparse {
    grid-template-columns: repeat(auto-fit, minmax(280px, 360px));
  }
}

@media (min-width: 620px) {
  .journal-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1000px) {
  .journal-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* Loading skeletons match the eventual card layout so nothing jumps. */
.journal-skeletons {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-5);
}

@media (min-width: 620px) {
  .journal-skeletons { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1000px) {
  .journal-skeletons { grid-template-columns: repeat(3, 1fr); }
}

.journal-skeleton {
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 0 0 var(--space-4);
  overflow: hidden;
}

.journal-skeleton__media {
  aspect-ratio: 3 / 2;
  background: var(--color-surface);
}

.journal-skeleton__line {
  height: 12px;
  margin: var(--space-3) var(--space-4) 0;
  border-radius: 6px;
  background: var(--color-surface);
}

.journal-skeleton__line--title {
  height: 20px;
  width: 70%;
}

.journal-skeleton__line--short {
  width: 45%;
}

.journal-skeleton__media,
.journal-skeleton__line {
  animation: skeleton-breathe 1.6s ease-in-out infinite;
}

@keyframes skeleton-breathe {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

@media (prefers-reduced-motion: reduce) {
  .journal-skeleton__media,
  .journal-skeleton__line {
    animation: none;
  }
}

.journal-empty {
  text-align: center;
  padding: var(--space-7) var(--space-4) var(--space-8);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.journal-empty__plate {
  width: 120px;
  margin: 0 auto var(--space-4);
}

.journal-empty__art {
  width: 100%;
  height: auto;
}

.journal-empty__headline {
  font-family: var(--font-display);
  font-size: 26px;
  line-height: 32px;
  font-weight: 500;
  color: var(--color-ink);
  margin: 0 0 var(--space-2);
}

.journal-empty__sub {
  font-size: 15px;
  line-height: 23px;
  color: var(--color-ink-muted);
  max-width: 380px;
  margin: 0 auto var(--space-5);
}

.journal-empty__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--space-3) var(--space-5);
}

.journal-load-more {
  display: flex;
  justify-content: center;
  padding: var(--space-7) 0 var(--space-4);
}

.journal-load-more__btn {
  min-height: 50px;
  padding: 0 var(--space-6);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-pill);
  transition: background var(--duration-fast) ease;
}

.journal-load-more__btn:hover {
  background: var(--color-surface);
}
`;
