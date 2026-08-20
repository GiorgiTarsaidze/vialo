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
        <Link to="/journal" className="journal-post-back">← Journal</Link>
        <h1 id="post-title" className="journal-post-title">{post.title}</h1>
        <p className="journal-post-meta">
          <span>{post.city}</span>
          <span aria-hidden="true">·</span>
          <span>{post.author.displayName}</span>
          <span aria-hidden="true">·</span>
          <time dateTime={post.createdAt}>
            {new Date(post.createdAt).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
          </time>
        </p>
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
          <h2 className="journal-post-itinerary__heading">Attached route</h2>
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
  font-weight: 500;
  color: var(--color-ink-muted);
  text-decoration: none;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
}

.journal-post-back:hover {
  color: var(--color-primary);
}

.journal-post-header {
  margin-bottom: var(--space-5);
}

.journal-post-title {
  font-family: var(--font-display);
  font-size: 28px;
  line-height: 34px;
  font-weight: 500;
  color: var(--color-ink);
  margin: var(--space-3) 0 var(--space-2);
}

@media (min-width: 640px) {
  .journal-post-title {
    font-size: 38px;
    line-height: 42px;
  }
}

.journal-post-meta {
  font-size: 14px;
  color: var(--color-ink-muted);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.journal-post-cover {
  margin-bottom: var(--space-5);
  border-radius: var(--radius-card);
  overflow: hidden;
  max-height: 360px;
}

.journal-post-cover__img {
  width: 100%;
  height: 100%;
  max-height: 360px;
  object-fit: cover;
}

.journal-post-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  font-size: 15px;
  line-height: 23px;
  color: var(--color-ink);
}

.journal-post-itinerary {
  margin-top: var(--space-6);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border);
}

.journal-post-itinerary__heading {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 var(--space-4);
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
  font-weight: 500;
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-input);
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
