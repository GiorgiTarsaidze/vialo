import { useState } from 'react';
import type { ItineraryResponse } from '../lib/types';
import { useShare } from '../hooks/use-share';

interface ResultActionsProps {
  result: ItineraryResponse;
  readOnly?: boolean;
  shareId?: string;
  onShareDeleted?: () => void;
}

export default function ResultActions({ result, readOnly, shareId, onShareDeleted }: ResultActionsProps) {
  const share = useShare(shareId);
  const [copied, setCopied] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handoff = result.mapsHandoff;
  const hasFullRoute = handoff.fullRouteUrl !== null;
  const hasParts = handoff.browserSafeParts.length > 0;
  const handoffUnavailable = handoff.errorCode === 'HANDOFF_UNAVAILABLE';

  const handleShare = async () => {
    let copiedSuccessfully = false;
    if (share.state === 'created') {
      copiedSuccessfully = await share.copyLink();
    } else {
      const createdUrl = await share.create(result);
      if (createdUrl) {
        try {
          await navigator.clipboard.writeText(createdUrl);
          copiedSuccessfully = true;
        } catch {
          copiedSuccessfully = false;
        }
      }
    }

    if (copiedSuccessfully) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    const deleted = await share.remove();
    setConfirmDelete(false);
    if (deleted) onShareDeleted?.();
  };

  return (
    <section className="result-actions" aria-label="Actions">
      {/* Maps handoff */}
      {hasFullRoute && (
        <a
          href={handoff.fullRouteUrl!}
          target="_blank"
          rel="noopener noreferrer"
          className="action-button action-button--primary"
        >
          Open full route in Google Maps
        </a>
      )}

      {!hasFullRoute && hasParts && (
        <div className="parts-section">
          <p className="parts-note">
            Open route in {handoff.browserSafeParts.length} parts
          </p>
          {handoff.browserSafeParts.map((part) => (
            <a
              key={part.part}
              href={part.url}
              target="_blank"
              rel="noopener noreferrer"
              className="action-button action-button--secondary"
            >
              Part {part.part} of {part.totalParts}
            </a>
          ))}
        </div>
      )}

      {hasFullRoute && hasParts && handoff.warningCode === 'MOBILE_WAYPOINT_LIMIT' && (
        <div className="parts-section">
          <p className="parts-note">
            Mobile browsers support fewer waypoints. Use these parts if the full link doesn't work:
          </p>
          {handoff.browserSafeParts.map((part) => (
            <a
              key={part.part}
              href={part.url}
              target="_blank"
              rel="noopener noreferrer"
              className="action-button action-button--secondary"
            >
              Part {part.part} of {part.totalParts}
            </a>
          ))}
        </div>
      )}

      {handoffUnavailable && (
        <p className="handoff-unavailable">
          Google Maps handoff is unavailable. The timeline and map above remain usable.
        </p>
      )}

      {/* Share actions */}
      {!readOnly && (
        <button
          className="action-button action-button--secondary"
          onClick={handleShare}
          disabled={share.state === 'creating'}
          aria-live="polite"
        >
          {share.state === 'creating'
            ? 'Creating link…'
            : copied
              ? 'Link copied!'
              : share.state === 'created'
                ? 'Copy share link'
                : 'Copy share link'}
        </button>
      )}

      {share.error && (
        <p className="share-error" role="alert">{share.error}</p>
      )}

      {/* Creator-only delete */}
      {share.canDelete && share.state !== 'deleted' && (
        <button
          className="action-button action-button--danger"
          onClick={handleDelete}
          disabled={share.state === 'deleting'}
        >
          {confirmDelete
            ? 'Confirm deletion'
            : share.state === 'deleting'
              ? 'Deleting…'
              : 'Delete shared link'}
        </button>
      )}

      {share.state === 'deleted' && (
        <p className="share-deleted" role="status">Share link deleted.</p>
      )}

      <style>{styles}</style>
    </section>
  );
}

const styles = `
.result-actions {
  margin-top: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-width: 480px;
}

.action-button {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 52px;
  padding: var(--space-3) var(--space-5);
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--radius-input);
  text-decoration: none;
  text-align: center;
  transition: background var(--duration-fast) ease;
}

.action-button--primary {
  color: #ffffff;
  background: var(--color-primary);
}

.action-button--primary:hover {
  background: var(--color-primary-hover);
  color: #ffffff;
}

.action-button--secondary {
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border-strong);
}

.action-button--secondary:hover {
  background: var(--color-surface);
}

.action-button--danger {
  color: var(--color-danger);
  background: var(--color-danger-soft);
  border: 1px solid var(--color-danger);
  font-size: 13px;
  min-height: 44px;
}

.parts-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.parts-note {
  font-size: 13px;
  color: var(--color-ink-muted);
}

.handoff-unavailable {
  font-size: 14px;
  color: var(--color-ink-muted);
  font-style: italic;
}

.share-error {
  font-size: 13px;
  color: var(--color-danger);
}

.share-deleted {
  font-size: 13px;
  color: var(--color-success);
}
`;
