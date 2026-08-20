import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import type { Post } from '../lib/journal-types';
import { fetchPost, deletePost, reportPost } from '../lib/journal-client';
import { JournalClientError } from '../lib/journal-client';
import { useAuth } from '../hooks/use-auth';
import ResultView from './ResultView';
import CommentThread from './CommentThread';

type ViewState = 'loading' | 'ready' | 'not_found' | 'error';

export default function JournalPostView() {
  const { postId } = useParams<{ postId: string }>();
  const navigate = useNavigate();
  const { authenticated, userId } = useAuth();
  const [state, setState] = useState<ViewState>('loading');
  const [post, setPost] = useState<Post | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmReport, setConfirmReport] = useState(false);
  const [reported, setReported] = useState(false);

  useEffect(() => {
    if (!postId) { setState('not_found'); return; }
    let cancelled = false;
    setState('loading');
    fetchPost(postId)
      .then((data) => {
        if (!cancelled) { setPost(data); setState('ready'); }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof JournalClientError && err.code === 'POST_NOT_FOUND') {
          setState('not_found');
        } else {
          setState('error');
        }
      });
    return () => { cancelled = true; };
  }, [postId]);

  const isAuthor = authenticated && userId === post?.author.userId;

  const handleDelete = async () => {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    if (!postId) return;
    try {
      await deletePost(postId);
      navigate('/journal', { replace: true });
    } catch {
      // stay on page
    }
  };

  const handleReport = async () => {
    if (!confirmReport) { setConfirmReport(true); return; }
    if (!postId) return;
    try {
      await reportPost(postId);
      setReported(true);
      setConfirmReport(false);
    } catch {
      // silent
    }
  };

  if (state === 'loading') {
    return (
      <div className="journal-post-view" aria-live="polite">
        <p className="journal-post-loading">Loading story…</p>
        <style>{styles}</style>
      </div>
    );
  }

  if (state === 'not_found') {
    return (
      <div className="journal-post-view">
        <h1 className="journal-post-not-found">Story not found</h1>
        <Link to="/journal" className="journal-post-back">Back to Journal</Link>
        <style>{styles}</style>
      </div>
    );
  }

  if (state === 'error' || !post) {
    return (
      <div className="journal-post-view">
        <p className="journal-post-error" role="alert">Something went wrong loading this story.</p>
        <Link to="/journal" className="journal-post-back">Back to Journal</Link>
        <style>{styles}</style>
      </div>
    );
  }

  const paragraphs = post.body.split(/\n\s*\n/).filter((p) => p.trim().length > 0);

  return (
    <article className="journal-post-view" aria-labelledby="post-title">
      <header className="journal-post-header">
        <Link to="/journal" className="journal-post-back">
          <span aria-hidden="true">←</span> Journal
        </Link>
        <p className="journal-post-city">{post.city}</p>
        <h1 id="post-title" className="journal-post-title">{post.title}</h1>
        <div className="journal-post-meta">
          <span className="journal-post-avatar" aria-hidden="true">
            {post.author.displayName.charAt(0).toUpperCase()}
          </span>
          <span className="journal-post-author">{post.author.displayName}</span>
          <span className="journal-post-sep" aria-hidden="true">·</span>
          <time dateTime={post.createdAt}>
            {new Date(post.createdAt).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
          </time>
          {post.itinerary && (
            <>
              <span className="journal-post-sep" aria-hidden="true">·</span>
              <span className="journal-post-stops">{post.itinerary.stops.length} stops walked</span>
            </>
          )}
        </div>
      </header>

      {post.coverImageUrl && (
        <div className="journal-post-cover">
          <img src={post.coverImageUrl} alt="" className="journal-post-cover__img" />
        </div>
      )}

      <div className="journal-post-body">
        {paragraphs.map((para, i) => (
          <p key={i}>{para}</p>
        ))}
      </div>

      {post.itinerary && (
        <section className="journal-post-itinerary" aria-label="Attached itinerary">
          <h2 className="journal-post-itinerary__heading">The day they walked</h2>
          <p className="journal-post-itinerary__note">
            Computed by Vialo and saved with this story, so it stays readable after the
            30-day share window closes.
          </p>
          <ResultView result={post.itinerary} readOnly />
        </section>
      )}

      <CommentThread postId={post.postId} />

      <div className="journal-post-actions">
        {isAuthor && (
          <button
            className="journal-post-action journal-post-action--delete"
            onClick={handleDelete}
            type="button"
          >
            {confirmDelete ? 'Confirm delete' : 'Delete story'}
          </button>
        )}
        {authenticated && !isAuthor && !reported && (
          <button
            className="journal-post-action journal-post-action--report"
            onClick={handleReport}
            type="button"
          >
            {confirmReport ? 'Confirm report' : 'Report'}
          </button>
        )}
        {reported && (
          <p className="journal-post-reported" role="status">Report received.</p>
        )}
      </div>

      <style>{styles}</style>
    </article>
  );
}

const styles = `
.journal-post-view {
  padding-top: var(--space-5);
  max-width: 720px;
  margin: 0 auto;
}

.journal-post-loading,
.journal-post-error {
  text-align: center;
  padding: var(--space-7) 0;
  color: var(--color-ink-muted);
}

.journal-post-not-found {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 500;
  text-align: center;
  padding-top: var(--space-7);
  color: var(--color-ink);
}

.journal-post-back {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink-muted);
  text-decoration: none;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.journal-post-back:hover {
  color: var(--color-primary);
}

.journal-post-header {
  margin-bottom: var(--space-6);
}

.journal-post-city {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin: var(--space-4) 0 var(--space-2);
}

.journal-post-title {
  font-family: var(--font-display);
  font-size: 32px;
  line-height: 38px;
  font-weight: 500;
  letter-spacing: -0.015em;
  color: var(--color-ink);
  margin: 0 0 var(--space-4);
  text-wrap: balance;
}

@media (min-width: 640px) {
  .journal-post-title {
    font-size: 46px;
    line-height: 52px;
  }
}

.journal-post-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  font-size: 14px;
  color: var(--color-ink-muted);
}

.journal-post-avatar {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-pill);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.journal-post-author {
  font-weight: 600;
  color: var(--color-ink);
}

.journal-post-sep {
  color: var(--color-border-strong);
}

.journal-post-stops {
  font-weight: 500;
  color: var(--color-primary);
}

.journal-post-cover {
  margin-bottom: var(--space-6);
  border-radius: var(--radius-card);
  overflow: hidden;
  border: 1px solid var(--color-border);
}

.journal-post-cover__img {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}

/* Reading measure: wider leading and a larger size than UI body copy, because
   this is the one surface in the product meant to be read rather than scanned. */
.journal-post-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  font-size: 18px;
  line-height: 30px;
  color: var(--color-ink);
}

.journal-post-body p {
  margin: 0;
}

.journal-post-body p:first-child::first-letter {
  font-family: var(--font-display);
  font-size: 56px;
  line-height: 44px;
  font-weight: 500;
  float: left;
  padding: 4px var(--space-3) 0 0;
  color: var(--color-primary);
}

/* The attached day carries maps and a timeline, so it breaks out of the
   reading measure on wide screens instead of being squeezed into it. */
.journal-post-itinerary {
  margin-top: var(--space-8);
  padding-top: var(--space-6);
  border-top: 1px solid var(--color-border);
}

@media (min-width: 1080px) {
  .journal-post-itinerary {
    width: calc(100vw - var(--space-6) * 2);
    max-width: 1140px;
    margin-left: 50%;
    transform: translateX(-50%);
  }
}

.journal-post-itinerary__heading {
  font-family: var(--font-display);
  font-size: 24px;
  line-height: 30px;
  font-weight: 500;
  color: var(--color-ink);
  margin: 0 0 var(--space-2);
}

.journal-post-itinerary__note {
  font-size: 14px;
  color: var(--color-ink-muted);
  margin: 0 0 var(--space-5);
}

.journal-post-actions {
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.journal-post-action {
  font-size: 13px;
  font-weight: 600;
  min-height: 44px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-pill);
  display: inline-flex;
  align-items: center;
  transition: background var(--duration-fast) ease;
}

.journal-post-action--delete {
  color: var(--color-danger);
  background: var(--color-danger-soft);
  border: 1px solid var(--color-danger);
}

.journal-post-action--report {
  color: var(--color-ink-muted);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}

.journal-post-reported {
  font-size: 13px;
  color: var(--color-ink-muted);
}
`;
