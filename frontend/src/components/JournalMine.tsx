import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import type { PostSummary } from '../lib/journal-types';
import { fetchMe, deletePost } from '../lib/journal-client';
import { useAuth } from '../hooks/use-auth';
import JournalCard from './JournalCard';

export default function JournalMine() {
  const { authenticated, signIn } = useAuth();
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    if (!authenticated) {
      signIn('/journal/me');
      return;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) setPosts(data.posts);
      })
      .catch(() => { /* silent */ })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [authenticated, signIn]);

  const handleDelete = async (postId: string) => {
    setDeletingId(postId);
    try {
      await deletePost(postId);
      setPosts((prev) => prev.filter((p) => p.postId !== postId));
    } catch {
      // silent
    } finally {
      setDeletingId(null);
    }
  };

  if (!authenticated) {
    return (
      <div className="journal-mine" aria-live="polite">
        <p className="journal-mine__signin">Redirecting to sign in…</p>
        <style>{styles}</style>
      </div>
    );
  }

  return (
    <div className="journal-mine">
      <h1 className="journal-mine__headline">My stories</h1>

      {loading ? (
        <p className="journal-mine__loading" aria-live="polite">Loading your stories…</p>
      ) : posts.length === 0 ? (
        <div className="journal-mine__empty">
          <p className="journal-mine__empty-text">You haven't written any stories yet.</p>
          <Link to="/journal/new" className="journal-mine__write-btn">Write your first story</Link>
        </div>
      ) : (
        <div className="journal-mine__grid">
          {posts.map((post, i) => (
            <div key={post.postId} className="journal-mine__card-wrap">
              <JournalCard post={post} index={i} />
              <button
                className="journal-mine__delete-btn"
                onClick={() => handleDelete(post.postId)}
                disabled={deletingId === post.postId}
                type="button"
                aria-label={`Delete "${post.title}"`}
              >
                {deletingId === post.postId ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          ))}
        </div>
      )}

      <style>{styles}</style>
    </div>
  );
}

const styles = `
.journal-mine {
  padding-top: var(--space-5);
}

.journal-mine__headline {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 500;
  color: var(--color-ink);
  margin: 0 0 var(--space-5);
}

.journal-mine__loading,
.journal-mine__signin {
  text-align: center;
  padding: var(--space-7) 0;
  color: var(--color-ink-muted);
}

.journal-mine__empty {
  text-align: center;
  padding: var(--space-8) 0;
}

.journal-mine__empty-text {
  font-size: 15px;
  color: var(--color-ink-muted);
  margin-bottom: var(--space-4);
}

.journal-mine__write-btn {
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
  text-decoration: none;
}

.journal-mine__grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-5);
}

@media (min-width: 640px) {
  .journal-mine__grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.journal-mine__card-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.journal-mine__delete-btn {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-danger);
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-input);
  align-self: flex-start;
}

.journal-mine__delete-btn:hover:not(:disabled) {
  background: var(--color-danger-soft);
}
`;
