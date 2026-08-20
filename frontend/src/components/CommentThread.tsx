import { useState, useEffect } from 'react';
import type { Comment } from '../lib/journal-types';
import { fetchComments, createComment, deleteComment } from '../lib/journal-client';
import { JournalClientError } from '../lib/journal-client';
import { useAuth } from '../hooks/use-auth';

interface CommentThreadProps {
  postId: string;
}

export default function CommentThread({ postId }: CommentThreadProps) {
  const { authenticated, userId, signIn } = useAuth();
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchComments(postId)
      .then((data) => {
        if (!cancelled) setComments(data.comments);
      })
      .catch(() => {
        // silent
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [postId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!authenticated) {
      await signIn(`/journal/p/${postId}`);
      return;
    }

    const trimmed = body.trim();
    if (trimmed.length === 0) {
      setError('Comment cannot be empty.');
      return;
    }
    if (trimmed.length > 500) {
      setError('Comment must be 500 characters or fewer.');
      return;
    }

    setSubmitting(true);
    try {
      const comment = await createComment(postId, trimmed);
      setComments((prev) => [...prev, comment]);
      setBody('');
    } catch (err) {
      if (err instanceof JournalClientError) {
        setError(err.message);
      } else {
        setError('Failed to post comment.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (commentId: string) => {
    try {
      await deleteComment(postId, commentId);
      setComments((prev) => prev.filter((c) => c.commentId !== commentId));
    } catch {
      // silent
    }
  };

  return (
    <section className="comment-thread" aria-labelledby="comments-heading">
      <h2 id="comments-heading" className="comment-thread__heading">
        Comments {!loading && comments.length > 0 && `(${comments.length})`}
      </h2>

      {loading ? (
        <p className="comment-thread__loading" aria-live="polite">Loading comments…</p>
      ) : comments.length === 0 ? (
        <p className="comment-thread__empty">No comments yet. Be the first to share your thoughts.</p>
      ) : (
        <ul className="comment-list" aria-label="Comments">
          {comments.map((comment) => (
            <li key={comment.commentId} className="comment-item">
              <div className="comment-item__header">
                <span className="comment-item__author">{comment.author.displayName}</span>
                <time className="comment-item__date" dateTime={comment.createdAt}>
                  {new Date(comment.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </time>
                {authenticated && userId === comment.author.userId && (
                  <button
                    className="comment-item__delete"
                    onClick={() => handleDelete(comment.commentId)}
                    type="button"
                    aria-label={`Delete comment by ${comment.author.displayName}`}
                  >
                    Delete
                  </button>
                )}
              </div>
              <p className="comment-item__body">{comment.body}</p>
            </li>
          ))}
        </ul>
      )}

      <form className="comment-form" onSubmit={handleSubmit} aria-label="Add a comment">
        <label htmlFor="comment-input" className="sr-only">Your comment</label>
        <textarea
          id="comment-input"
          className="comment-form__input"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={authenticated ? 'Add a comment…' : 'Sign in to comment'}
          maxLength={500}
          rows={3}
          disabled={submitting}
        />
        <div className="comment-form__footer">
          <span className="comment-form__count">{body.length}/500</span>
          <button
            className="comment-form__submit"
            type="submit"
            disabled={submitting || body.trim().length === 0}
          >
            {submitting ? 'Posting…' : authenticated ? 'Post comment' : 'Sign in to comment'}
          </button>
        </div>
        {error && <p className="comment-form__error" role="alert">{error}</p>}
      </form>

      <style>{styles}</style>
    </section>
  );
}

const styles = `
.comment-thread {
  margin-top: var(--space-6);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border);
}

.comment-thread__heading {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 var(--space-4);
}

.comment-thread__loading,
.comment-thread__empty {
  font-size: 14px;
  color: var(--color-ink-muted);
  margin-bottom: var(--space-4);
}

.comment-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.comment-item {
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
}

.comment-item__header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.comment-item__author {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}

.comment-item__date {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.comment-item__delete {
  font-size: 12px;
  color: var(--color-danger);
  margin-left: auto;
  min-height: 44px;
  min-width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-input);
}

.comment-item__delete:hover {
  background: var(--color-danger-soft);
}

.comment-item__body {
  font-size: 14px;
  line-height: 20px;
  color: var(--color-ink);
  overflow-wrap: anywhere;
}

.comment-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.comment-form__input {
  width: 100%;
  padding: var(--space-3);
  font-size: 14px;
  line-height: 20px;
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  resize: vertical;
  min-height: 80px;
}

.comment-form__input:focus {
  border-color: var(--color-primary);
}

.comment-form__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.comment-form__count {
  font-size: 12px;
  color: var(--color-ink-muted);
  font-variant-numeric: tabular-nums;
}

.comment-form__submit {
  min-height: 44px;
  padding: var(--space-2) var(--space-4);
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  background: var(--color-primary);
  border-radius: var(--radius-input);
  transition: background var(--duration-fast) ease;
}

.comment-form__submit:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.comment-form__error {
  font-size: 13px;
  color: var(--color-danger);
}
`;
