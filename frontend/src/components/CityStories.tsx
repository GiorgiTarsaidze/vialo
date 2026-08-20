import { useState, useEffect } from 'react';
import type { PostSummary } from '../lib/journal-types';
import { fetchPosts } from '../lib/journal-client';
import { slugifyCity } from '../lib/journal-types';

interface CityStoriesProps {
  cityName: string;
}

export default function CityStories({ cityName }: CityStoriesProps) {
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const slug = slugifyCity(cityName);
    if (!slug) { setLoaded(true); return; }
    let cancelled = false;
    fetchPosts(slug)
      .then((data) => {
        if (!cancelled) setPosts(data.posts.slice(0, 3));
      })
      .catch(() => { /* render nothing on failure */ })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => { cancelled = true; };
  }, [cityName]);

  if (!loaded || posts.length === 0) return null;

  return (
    <section className="city-stories" aria-labelledby="city-stories-heading">
      <h3 id="city-stories-heading" className="city-stories__heading">
        Stories from {cityName}
      </h3>
      <div className="city-stories__list">
        {posts.map((post) => (
          <a
            key={post.postId}
            href={`/journal/p/${post.postId}`}
            className="city-stories__card"
          >
            <span className="city-stories__card-title">{post.title}</span>
            <span className="city-stories__card-meta">
              {post.author.displayName} · {post.stopCount} stops
            </span>
          </a>
        ))}
      </div>
      <style>{styles}</style>
    </section>
  );
}

const styles = `
.city-stories {
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.city-stories__heading {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 var(--space-3);
}

.city-stories__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.city-stories__card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  text-decoration: none;
  transition: border-color var(--duration-fast) ease;
  min-height: 44px;
  justify-content: center;
}

.city-stories__card:hover {
  border-color: var(--color-primary);
}

.city-stories__card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.city-stories__card-meta {
  font-size: 12px;
  color: var(--color-ink-muted);
}
`;
