import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
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
    } catch {
      // Silent — empty state is inviting
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadPosts(cityFilter || undefined).finally(() => setLoading(false));
  }, [cityFilter, loadPosts]);

  // Extract unique cities from loaded posts
  useEffect(() => {
    const uniqueCities = Array.from(new Set(posts.map((p) => p.city))).sort();
    setCities(uniqueCities);
  }, [posts]);

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

  return (
    <div className="journal-landing">
      <section className="journal-hero" aria-labelledby="journal-heading">
        <h1 id="journal-heading" className="journal-hero__headline">
          Vialo Journal
        </h1>
        <p className="journal-hero__sub">
          Days that actually happened, written by the people who walked them.
        </p>
        <button
          className="journal-hero__cta"
          onClick={handleWrite}
          type="button"
        >
          Write a story
        </button>
      </section>

      {cities.length > 0 && (
        <nav className="journal-filters" aria-label="Filter by city">
          <button
            className={`journal-filter-btn${!cityFilter ? ' journal-filter-btn--active' : ''}`}
            onClick={() => setCityFilter('')}
            type="button"
          >
            All cities
          </button>
          {cities.map((city) => (
            <button
              key={city}
              className={`journal-filter-btn${cityFilter === city ? ' journal-filter-btn--active' : ''}`}
              onClick={() => setCityFilter(city)}
              type="button"
            >
              {city}
            </button>
          ))}
        </nav>
      )}

      {loading ? (
        <p className="journal-loading" aria-live="polite">Loading stories…</p>
      ) : posts.length === 0 ? (
        <div className="journal-empty" aria-live="polite">
          <p className="journal-empty__headline">No stories yet</p>
          <p className="journal-empty__sub">
            Be the first to share a day you walked. Your route, your words.
          </p>
        </div>
      ) : (
        <>
          <div className="journal-grid" role="feed" aria-label="Journal stories">
            {posts.map((post, i) => (
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
                {loadingMore ? 'Loading…' : 'Load more'}
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
  padding-top: var(--space-5);
}

.journal-hero {
  text-align: center;
  padding: var(--space-7) 0 var(--space-6);
}

.journal-hero__headline {
  font-family: var(--font-display);
  font-size: 38px;
  line-height: 42px;
  font-weight: 500;
  color: var(--color-ink);
  margin: 0 0 var(--space-3);
}

@media (min-width: 640px) {
  .journal-hero__headline {
    font-size: 48px;
    line-height: 52px;
  }
}

.journal-hero__sub {
  font-size: 17px;
  line-height: 27px;
  color: var(--color-ink-muted);
  margin: 0 0 var(--space-5);
  max-width: 480px;
  margin-left: auto;
  margin-right: auto;
}

.journal-hero__cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 52px;
  padding: var(--space-3) var(--space-6);
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  background: var(--color-primary);
  border-radius: var(--radius-input);
  transition: background var(--duration-fast) ease;
}

.journal-hero__cta:hover {
  background: var(--color-primary-hover);
}

.journal-filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-border);
}

.journal-filter-btn {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-ink-muted);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-pill);
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  transition: background var(--duration-fast) ease, color var(--duration-fast) ease;
}

.journal-filter-btn:hover {
  background: var(--color-surface);
  color: var(--color-ink);
}

.journal-filter-btn--active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 600;
}

.journal-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-5);
}

@media (min-width: 640px) {
  .journal-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1024px) {
  .journal-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

.journal-loading {
  text-align: center;
  padding: var(--space-7) 0;
  color: var(--color-ink-muted);
}

.journal-empty {
  text-align: center;
  padding: var(--space-8) 0;
}

.journal-empty__headline {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 500;
  color: var(--color-ink);
  margin: 0 0 var(--space-2);
}

.journal-empty__sub {
  font-size: 15px;
  color: var(--color-ink-muted);
  max-width: 360px;
  margin: 0 auto;
}

.journal-load-more {
  display: flex;
  justify-content: center;
  padding: var(--space-6) 0;
}

.journal-load-more__btn {
  min-height: 52px;
  padding: var(--space-3) var(--space-6);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-input);
  transition: background var(--duration-fast) ease;
}

.journal-load-more__btn:hover {
  background: var(--color-surface);
}
`;
