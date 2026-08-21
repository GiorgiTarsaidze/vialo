import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import type { ItineraryResponse } from '../lib/types';
import type { CreatePostPayload } from '../lib/journal-types';
import { createPost, requestUpload, uploadFile, fetchMe } from '../lib/journal-client';
import { JournalClientError } from '../lib/journal-client';
import { useAuth } from '../hooks/use-auth';

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_BYTES = 2 * 1024 * 1024; // 2 MB
const BODY_MAX = 8000;
const BODY_MIN = 50;

export default function JournalEditor() {
  const navigate = useNavigate();
  const location = useLocation();
  const { authenticated, displayName, signIn } = useAuth();

  /**
   * The day handed over by "Publish this day as a story".
   *
   * Held in state with a lazy initialiser so it is read exactly once. As a plain
   * expression in the render body it consumed the sessionStorage entry on the
   * first render and then evaluated to null on every render after it, so the
   * attached route silently disappeared the moment anything re-rendered, which
   * the daily-allowance fetch does immediately. No story ever carried a route.
   */
  const [passedItinerary] = useState<ItineraryResponse | null>(() => {
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
  });

  const [title, setTitle] = useState('');
  const [city, setCity] = useState(passedItinerary?.locality.name ?? '');
  const [body, setBody] = useState('');
  const [attachItinerary, setAttachItinerary] = useState(!!passedItinerary);
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
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

  // Release the object URL when the preview changes or the editor unmounts.
  useEffect(() => {
    if (!coverPreview) return;
    return () => URL.revokeObjectURL(coverPreview);
  }, [coverPreview]);

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (title.trim().length < 3) errors['title'] = 'Title must be at least 3 characters.';
    if (title.trim().length > 120) errors['title'] = 'Title must be 120 characters or fewer.';
    if (city.trim().length < 2) errors['city'] = 'City must be at least 2 characters.';
    if (city.trim().length > 80) errors['city'] = 'City must be 80 characters or fewer.';
    if (body.trim().length < BODY_MIN) errors['body'] = 'Story must be at least 50 characters.';
    if (body.trim().length > BODY_MAX) errors['body'] = 'Story must be 8000 characters or fewer.';
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

  const acceptFile = (file: File | null) => {
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
    setCoverPreview(URL.createObjectURL(file));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    acceptFile(e.target.files?.[0] ?? null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (submitting) return;
    acceptFile(e.dataTransfer.files?.[0] ?? null);
  };

  const clearCover = () => {
    setCoverFile(null);
    setCoverPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      let imageKey: string | undefined;

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
        <p className="journal-editor__signin">Taking you to sign in…</p>
        <style>{styles}</style>
      </div>
    );
  }

  const bodyChars = body.trim().length;
  const bodyProgress = Math.min(100, (bodyChars / BODY_MIN) * 100);
  const bodyReady = bodyChars >= BODY_MIN;

  return (
    <div className="journal-editor">
      <header className="journal-editor__head">
        <div>
          <p className="journal-editor__eyebrow">New story</p>
          <h1 className="journal-editor__headline">Write the day down</h1>
        </div>
        <div className="journal-editor__head-meta">
          {displayName && (
            <span className="journal-editor__as">
              <span className="journal-editor__as-avatar" aria-hidden="true">
                {displayName.charAt(0).toUpperCase()}
              </span>
              Publishing as <strong>{displayName}</strong>
            </span>
          )}
          {postsRemaining !== null && (
            <span className="journal-editor__remaining">
              {postsRemaining} left today
            </span>
          )}
        </div>
      </header>

      <form className="journal-editor__form" onSubmit={handleSubmit} aria-label="Create a story">
        <div className="journal-editor__main">
          <div className="journal-editor__field">
            <label htmlFor="editor-title" className="journal-editor__label">Title</label>
            <input
              id="editor-title"
              className="journal-editor__title-input"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={120}
              disabled={submitting}
              placeholder="What was the day?"
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
              placeholder="Naples"
              aria-describedby={fieldErrors['city'] ? 'city-error' : undefined}
            />
            {fieldErrors['city'] && <p id="city-error" className="journal-editor__error" role="alert">{fieldErrors['city']}</p>}
          </div>

          <div className="journal-editor__field">
            <div className="journal-editor__label-row">
              <label htmlFor="editor-body" className="journal-editor__label">Your story</label>
              <span
                id="body-count"
                className={`journal-editor__count${bodyChars > BODY_MAX ? ' journal-editor__count--over' : ''}`}
              >
                {body.length}/{BODY_MAX}
              </span>
            </div>
            <textarea
              id="editor-body"
              className="journal-editor__textarea"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              maxLength={BODY_MAX}
              rows={16}
              disabled={submitting}
              placeholder={
                'What did the day feel like? Where did you actually end up?\n\n' +
                'Plain text. Blank lines start a new paragraph.'
              }
              aria-describedby={fieldErrors['body'] ? 'body-error' : 'body-count body-progress'}
            />
            <div className="journal-editor__progress" id="body-progress">
              <div className="journal-editor__progress-track" aria-hidden="true">
                <div
                  className={`journal-editor__progress-fill${bodyReady ? ' journal-editor__progress-fill--ready' : ''}`}
                  style={{ width: `${bodyProgress}%` }}
                />
              </div>
              <span className="journal-editor__progress-text">
                {bodyReady
                  ? 'Long enough to publish'
                  : `${BODY_MIN - bodyChars} more characters to publish`}
              </span>
            </div>
            {fieldErrors['body'] && <p id="body-error" className="journal-editor__error" role="alert">{fieldErrors['body']}</p>}
          </div>
        </div>

        <aside className="journal-editor__side">
          <div className="journal-editor__panel">
            <label htmlFor="editor-cover" className="journal-editor__label">
              Cover image <span className="journal-editor__optional">(optional)</span>
            </label>

            {coverPreview ? (
              <div className="journal-editor__preview">
                <img src={coverPreview} alt="Cover preview" className="journal-editor__preview-img" />
                <button
                  type="button"
                  className="journal-editor__remove-cover"
                  onClick={clearCover}
                  disabled={submitting}
                >
                  Remove
                </button>
              </div>
            ) : (
              <label
                htmlFor="editor-cover"
                className={`journal-editor__drop${dragging ? ' journal-editor__drop--active' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
              >
                <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true" className="journal-editor__drop-icon">
                  <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M4 16v2.5A1.5 1.5 0 005.5 20h13a1.5 1.5 0 001.5-1.5V16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
                <span className="journal-editor__drop-title">Drop an image or browse</span>
                <span className="journal-editor__drop-hint">JPEG, PNG or WebP, up to 2 MB</span>
              </label>
            )}

            <input
              ref={fileInputRef}
              id="editor-cover"
              className="journal-editor__file-input sr-only"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleFileChange}
              disabled={submitting}
              aria-describedby={fieldErrors['cover'] ? 'cover-error' : 'cover-hint'}
            />
            <p id="cover-hint" className="journal-editor__hint">
              Vialo does not strip metadata from your image.
            </p>
            {fieldErrors['cover'] && <p id="cover-error" className="journal-editor__error" role="alert">{fieldErrors['cover']}</p>}
          </div>

          {passedItinerary && (
            <div className="journal-editor__panel journal-editor__panel--route">
              <span className="journal-editor__label">Your computed day</span>
              <p className="journal-editor__attach-summary">
                <strong>{passedItinerary.locality.name}</strong>
                <span>
                  {passedItinerary.stops.length} stops · {passedItinerary.window.localStart} to{' '}
                  {passedItinerary.window.localEnd}
                </span>
              </p>
              <label className="journal-editor__attach-label">
                <input
                  type="checkbox"
                  checked={attachItinerary}
                  onChange={(e) => setAttachItinerary(e.target.checked)}
                  disabled={submitting}
                  className="journal-editor__attach-checkbox"
                />
                <span>Attach this day to the story</span>
              </label>
            </div>
          )}

          <div className="journal-editor__actions">
            {error && <p className="journal-editor__error journal-editor__error--form" role="alert">{error}</p>}
            <button className="journal-editor__submit" type="submit" disabled={submitting}>
              {submitting ? 'Publishing…' : 'Publish story'}
            </button>
            <p className="journal-editor__note">
              Published stories are public and cannot be edited afterwards. You can delete yours at
              any time.
            </p>
          </div>
        </aside>
      </form>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
.journal-editor {
  padding-top: var(--space-5);
  padding-bottom: var(--space-8);
  max-width: 1080px;
  margin: 0 auto;
}

.journal-editor__signin {
  text-align: center;
  padding: var(--space-8) 0;
  color: var(--color-ink-muted);
}

.journal-editor__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  padding-bottom: var(--space-5);
  margin-bottom: var(--space-6);
  border-bottom: 1px solid var(--color-border);
}

.journal-editor__eyebrow {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin: 0 0 var(--space-2);
}

.journal-editor__headline {
  font-family: var(--font-display);
  font-size: 34px;
  line-height: 40px;
  font-weight: 500;
  letter-spacing: -0.015em;
  color: var(--color-ink);
  margin: 0;
}

.journal-editor__head-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.journal-editor__as {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  color: var(--color-ink-muted);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  padding: 5px var(--space-3) 5px 5px;
}

.journal-editor__as strong {
  color: var(--color-ink);
  font-weight: 600;
}

.journal-editor__as-avatar {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-pill);
  background: var(--color-primary);
  color: #ffffff;
  font-size: 11px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.journal-editor__remaining {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-radius: var(--radius-pill);
  padding: 6px var(--space-3);
}

.journal-editor__form {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-6);
  align-items: start;
}

@media (min-width: 900px) {
  .journal-editor__form {
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: var(--space-7);
  }
}

.journal-editor__main {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  min-width: 0;
}

.journal-editor__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.journal-editor__label-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}

.journal-editor__label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

.journal-editor__optional {
  text-transform: none;
  letter-spacing: 0;
  font-weight: 500;
  opacity: 0.8;
}

/* The title behaves like the headline it becomes, not like a form field. */
.journal-editor__title-input {
  font-family: var(--font-display);
  font-size: 28px;
  line-height: 36px;
  font-weight: 500;
  letter-spacing: -0.01em;
  color: var(--color-ink);
  background: transparent;
  border: none;
  border-bottom: 2px solid var(--color-border);
  border-radius: 0;
  padding: var(--space-2) 0;
  width: 100%;
  transition: border-color var(--duration-fast) ease;
}

.journal-editor__title-input::placeholder {
  color: var(--color-border-strong);
  font-style: italic;
}

.journal-editor__title-input:focus {
  outline: none;
  border-bottom-color: var(--color-primary);
}

.journal-editor__title-input:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 4px;
}

@media (min-width: 640px) {
  .journal-editor__title-input {
    font-size: 34px;
    line-height: 42px;
  }
}

.journal-editor__input,
.journal-editor__textarea {
  width: 100%;
  font-family: var(--font-ui);
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  padding: var(--space-3) var(--space-4);
  transition: border-color var(--duration-fast) ease, box-shadow var(--duration-fast) ease;
}

.journal-editor__input {
  font-size: 15px;
  min-height: 50px;
}

.journal-editor__textarea {
  font-size: 16px;
  line-height: 27px;
  resize: vertical;
  min-height: 320px;
  padding: var(--space-4);
}

.journal-editor__input:focus,
.journal-editor__textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.journal-editor__input:focus-visible,
.journal-editor__textarea:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.journal-editor__input::placeholder,
.journal-editor__textarea::placeholder {
  color: var(--color-border-strong);
}

.journal-editor__count {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--color-ink-muted);
}

.journal-editor__count--over {
  color: var(--color-danger);
  font-weight: 600;
}

.journal-editor__progress {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.journal-editor__progress-track {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: var(--color-border);
  overflow: hidden;
}

.journal-editor__progress-fill {
  height: 100%;
  background: var(--color-accent-sun);
  border-radius: 2px;
  transition: width var(--duration-fast) ease, background var(--duration-fast) ease;
}

.journal-editor__progress-fill--ready {
  background: var(--color-success);
}

.journal-editor__progress-text {
  font-size: 12px;
  color: var(--color-ink-muted);
  white-space: nowrap;
}

.journal-editor__side {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

@media (min-width: 900px) {
  .journal-editor__side {
    position: sticky;
    top: 88px;
  }
}

.journal-editor__panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.journal-editor__panel--route {
  background: var(--color-primary-soft);
  border-color: transparent;
}

.journal-editor__drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-6) var(--space-4);
  text-align: center;
  background: var(--color-surface-strong);
  border: 1.5px dashed var(--color-border-strong);
  border-radius: var(--radius-input);
  cursor: pointer;
  transition: border-color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.journal-editor__drop:hover,
.journal-editor__drop--active {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.journal-editor__file-input:focus-visible + .journal-editor__drop,
.journal-editor__drop:focus-within {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.journal-editor__drop-icon {
  color: var(--color-primary);
}

.journal-editor__drop-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}

.journal-editor__drop-hint {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.journal-editor__hint {
  font-size: 12px;
  line-height: 18px;
  color: var(--color-ink-muted);
  margin: 0;
}

.journal-editor__preview {
  position: relative;
  border-radius: var(--radius-input);
  overflow: hidden;
  border: 1px solid var(--color-border);
}

.journal-editor__preview-img {
  width: 100%;
  aspect-ratio: 3 / 2;
  object-fit: cover;
}

.journal-editor__remove-cover {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  min-height: 34px;
  padding: 0 var(--space-3);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
}

.journal-editor__remove-cover:hover {
  background: var(--color-surface);
}

.journal-editor__attach-summary {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 13px;
  color: var(--color-primary);
  margin: 0;
}

.journal-editor__attach-summary strong {
  font-size: 15px;
  color: var(--color-ink);
}

.journal-editor__attach-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
  cursor: pointer;
  min-height: 44px;
}

.journal-editor__attach-checkbox {
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary);
  flex-shrink: 0;
}

.journal-editor__actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.journal-editor__submit {
  width: 100%;
  min-height: 52px;
  padding: 0 var(--space-5);
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  background: var(--color-primary);
  border-radius: var(--radius-pill);
  transition: background var(--duration-fast) ease, transform var(--duration-fast) ease;
}

.journal-editor__submit:hover:not(:disabled) {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
}

.journal-editor__note {
  font-size: 12px;
  line-height: 18px;
  color: var(--color-ink-muted);
  margin: 0;
}

.journal-editor__error {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-danger);
  margin: 0;
}

.journal-editor__error--form {
  padding: var(--space-3);
  background: var(--color-danger-soft);
  border-radius: var(--radius-input);
}
`;
