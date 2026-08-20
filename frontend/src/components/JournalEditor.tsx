import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import type { ItineraryResponse } from '../lib/types';
import type { CreatePostPayload } from '../lib/journal-types';
import { createPost, requestUpload, uploadFile, fetchMe } from '../lib/journal-client';
import { JournalClientError } from '../lib/journal-client';
import { useAuth } from '../hooks/use-auth';

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_BYTES = 2 * 1024 * 1024; // 2 MB

export default function JournalEditor() {
  const navigate = useNavigate();
  const location = useLocation();
  const { authenticated, signIn } = useAuth();

  const passedItinerary = (() => {
    const fromState = (location.state as { itinerary?: ItineraryResponse } | null)?.itinerary;
    if (fromState) return fromState;
    try {
      const stored = sessionStorage.getItem('vialo.journal.draft_itinerary');
      if (stored) {
        sessionStorage.removeItem('vialo.journal.draft_itinerary');
        return JSON.parse(stored) as ItineraryResponse;
      }
    } catch { /* ignore */ }
    return null;
  })();

  const [title, setTitle] = useState('');
  const [city, setCity] = useState(passedItinerary?.locality.name ?? '');
  const [body, setBody] = useState('');
  const [attachItinerary, setAttachItinerary] = useState(!!passedItinerary);
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [postsRemaining, setPostsRemaining] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Redirect to sign in if not authenticated
  useEffect(() => {
    if (!authenticated) {
      signIn('/journal/new');
    }
  }, [authenticated, signIn]);

  // Fetch remaining daily allowance
  useEffect(() => {
    if (!authenticated) return;
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) setPostsRemaining(data.postsRemainingToday);
      })
      .catch(() => { /* silent */ });
    return () => { cancelled = true; };
  }, [authenticated]);

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (title.trim().length < 3) errors['title'] = 'Title must be at least 3 characters.';
    if (title.trim().length > 120) errors['title'] = 'Title must be 120 characters or fewer.';
    if (city.trim().length < 2) errors['city'] = 'City must be at least 2 characters.';
    if (city.trim().length > 80) errors['city'] = 'City must be 80 characters or fewer.';
    if (body.trim().length < 50) errors['body'] = 'Story must be at least 50 characters.';
    if (body.trim().length > 8000) errors['body'] = 'Story must be 8000 characters or fewer.';
    if (coverFile) {
      if (!ACCEPTED_TYPES.includes(coverFile.type)) {
        errors['cover'] = 'Image must be JPEG, PNG, or WebP.';
      }
      if (coverFile.size > MAX_IMAGE_BYTES) {
        errors['cover'] = 'Image must be 2 MB or smaller.';
      }
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    if (!file) { setCoverFile(null); setCoverPreview(null); return; }
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setFieldErrors((prev) => ({ ...prev, cover: 'Image must be JPEG, PNG, or WebP.' }));
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setFieldErrors((prev) => ({ ...prev, cover: 'Image must be 2 MB or smaller.' }));
      return;
    }
    setFieldErrors((prev) => { const n = { ...prev }; delete n['cover']; return n; });
    setCoverFile(file);
    const url = URL.createObjectURL(file);
    setCoverPreview(url);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      let imageKey: string | undefined;

      // Upload cover image if present
      if (coverFile) {
        const upload = await requestUpload(coverFile.type);
        await uploadFile(upload.uploadUrl, upload.fields, coverFile);
        imageKey = upload.imageKey;
      }

      const payload: CreatePostPayload = {
        title: title.trim(),
        city: city.trim(),
        body: body.trim(),
      };
      if (imageKey) payload.coverImageKey = imageKey;
      if (attachItinerary && passedItinerary) payload.itinerary = passedItinerary;

      const result = await createPost(payload);
      navigate(`/journal/p/${result.post.postId}`, { replace: true });
    } catch (err) {
      if (err instanceof JournalClientError) {
        if (err.code === 'QUOTA_EXCEEDED') {
          setError('You have reached your daily posting limit. Try again tomorrow.');
        } else {
          setError(err.message);
        }
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!authenticated) {
    return (
      <div className="journal-editor" aria-live="polite">
        <p className="journal-editor__signin">Redirecting to sign in…</p>
        <style>{styles}</style>
      </div>
    );
  }

  return (
    <div className="journal-editor">
      <h1 className="journal-editor__headline">Write a story</h1>
      {postsRemaining !== null && (
        <p className="journal-editor__remaining">
          {postsRemaining} post{postsRemaining === 1 ? '' : 's'} remaining today
        </p>
      )}

      <form className="journal-editor__form" onSubmit={handleSubmit} aria-label="Create a story">
        <div className="journal-editor__field">
          <label htmlFor="editor-title" className="journal-editor__label">Title</label>
          <input
            id="editor-title"
            className="journal-editor__input"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={120}
            disabled={submitting}
            aria-describedby={fieldErrors['title'] ? 'title-error' : undefined}
          />
          {fieldErrors['title'] && <p id="title-error" className="journal-editor__error" role="alert">{fieldErrors['title']}</p>}
        </div>

        <div className="journal-editor__field">
          <label htmlFor="editor-city" className="journal-editor__label">City</label>
          <input
            id="editor-city"
            className="journal-editor__input"
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            maxLength={80}
            disabled={submitting}
            aria-describedby={fieldErrors['city'] ? 'city-error' : undefined}
          />
          {fieldErrors['city'] && <p id="city-error" className="journal-editor__error" role="alert">{fieldErrors['city']}</p>}
        </div>

        <div className="journal-editor__field">
          <label htmlFor="editor-body" className="journal-editor__label">Your story</label>
          <textarea
            id="editor-body"
            className="journal-editor__textarea"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={8000}
            rows={12}
            disabled={submitting}
            aria-describedby={fieldErrors['body'] ? 'body-error' : 'body-count'}
          />
          <span id="body-count" className="journal-editor__count">{body.length}/8000</span>
          {fieldErrors['body'] && <p id="body-error" className="journal-editor__error" role="alert">{fieldErrors['body']}</p>}
        </div>

        <div className="journal-editor__field">
          <label htmlFor="editor-cover" className="journal-editor__label">
            Cover image <span className="journal-editor__optional">(optional)</span>
          </label>
          <input
            ref={fileInputRef}
            id="editor-cover"
            className="journal-editor__file-input"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileChange}
            disabled={submitting}
            aria-describedby={fieldErrors['cover'] ? 'cover-error' : undefined}
          />
          {coverPreview && (
            <div className="journal-editor__preview">
              <img src={coverPreview} alt="Cover preview" className="journal-editor__preview-img" />
              <button
                type="button"
                className="journal-editor__remove-cover"
                onClick={() => {
                  setCoverFile(null);
                  setCoverPreview(null);
                  if (fileInputRef.current) fileInputRef.current.value = '';
                }}
              >
                Remove
              </button>
            </div>
          )}
          {fieldErrors['cover'] && <p id="cover-error" className="journal-editor__error" role="alert">{fieldErrors['cover']}</p>}
        </div>

        {passedItinerary && (
          <div className="journal-editor__attach">
            <label className="journal-editor__attach-label">
              <input
                type="checkbox"
                checked={attachItinerary}
                onChange={(e) => setAttachItinerary(e.target.checked)}
                disabled={submitting}
                className="journal-editor__attach-checkbox"
              />
              <span>Attach this day</span>
            </label>
            <p className="journal-editor__attach-summary">
              {passedItinerary.stops.length} stops · {passedItinerary.locality.name} · {passedItinerary.window.localStart}–{passedItinerary.window.localEnd}
            </p>
          </div>
        )}

        {error && <p className="journal-editor__error journal-editor__error--form" role="alert">{error}</p>}

        <button
          className="journal-editor__submit"
          type="submit"
          disabled={submitting}
        >
          {submitting ? 'Publishing…' : 'Publish story'}
        </button>
      </form>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
.journal-editor {
  padding-top: var(--space-5);
  max-width: 640px;
  margin: 0 auto;
}

.journal-editor__headline {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 500;
  color: var(--color-ink);
  margin: 0 0 var(--space-2);
}

.journal-editor__remaining {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin-bottom: var(--space-5);
}

.journal-editor__signin {
  text-align: center;
  padding: var(--space-7) 0;
  color: var(--color-ink-muted);
}

.journal-editor__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.journal-editor__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.journal-editor__label {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}

.journal-editor__optional {
  font-weight: 400;
  color: var(--color-ink-muted);
}

.journal-editor__input {
  padding: var(--space-3);
  font-size: 15px;
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  min-height: 48px;
}

.journal-editor__input:focus {
  border-color: var(--color-primary);
}

.journal-editor__textarea {
  padding: var(--space-3);
  font-size: 15px;
  line-height: 23px;
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  resize: vertical;
  min-height: 200px;
}

.journal-editor__textarea:focus {
  border-color: var(--color-primary);
}

.journal-editor__count {
  font-size: 12px;
  color: var(--color-ink-muted);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.journal-editor__file-input {
  font-size: 14px;
  min-height: 44px;
}

.journal-editor__preview {
  margin-top: var(--space-2);
  position: relative;
  border-radius: var(--radius-input);
  overflow: hidden;
  max-height: 200px;
}

.journal-editor__preview-img {
  width: 100%;
  max-height: 200px;
  object-fit: cover;
}

.journal-editor__remove-cover {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink);
  background: rgba(255, 255, 255, 0.9);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-pill);
  min-height: 44px;
  min-width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.journal-editor__attach {
  padding: var(--space-3);
  background: var(--color-accent-lilac);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
}

.journal-editor__attach-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  cursor: pointer;
  min-height: 44px;
}

.journal-editor__attach-checkbox {
  width: 20px;
  height: 20px;
  accent-color: var(--color-primary);
}

.journal-editor__attach-summary {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin-top: var(--space-1);
  padding-left: 28px;
  font-variant-numeric: tabular-nums;
}

.journal-editor__error {
  font-size: 13px;
  color: var(--color-danger);
}

.journal-editor__error--form {
  padding: var(--space-3);
  background: var(--color-danger-soft);
  border-radius: var(--radius-input);
}

.journal-editor__submit {
  min-height: 52px;
  padding: var(--space-3) var(--space-6);
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  background: var(--color-primary);
  border-radius: var(--radius-input);
  transition: background var(--duration-fast) ease;
  align-self: flex-start;
}

.journal-editor__submit:hover:not(:disabled) {
  background: var(--color-primary-hover);
}
`;
