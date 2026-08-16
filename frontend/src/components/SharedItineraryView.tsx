import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import type { ItineraryResponse } from '../lib/types';
import { getShare, ApiClientError } from '../lib/api-client';
import ResultView from './ResultView';

type ShareState = 'loading' | 'ready' | 'not_found';

export default function SharedItineraryView() {
  const { shareId } = useParams<{ shareId: string }>();
  const [state, setState] = useState<ShareState>('loading');
  const [itinerary, setItinerary] = useState<ItineraryResponse | null>(null);

  useEffect(() => {
    if (!shareId) {
      setState('not_found');
      return;
    }

    let cancelled = false;
    getShare(shareId)
      .then((data) => {
        if (!cancelled) {
          setItinerary(data);
          setState('ready');
        }
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ApiClientError && err.code === 'SHARE_NOT_FOUND') {
            setState('not_found');
          } else {
            setState('not_found');
          }
        }
      });

    return () => { cancelled = true; };
  }, [shareId]);

  if (state === 'loading') {
    return (
      <div className="share-loading" aria-live="polite">
        <p>Loading shared itinerary…</p>
        <style>{styles}</style>
      </div>
    );
  }

  if (state === 'not_found') {
    return (
      <div className="share-not-found">
        <h1 className="not-found-headline">This itinerary is no longer available</h1>
        <p className="not-found-text">
          Shared itineraries expire after 30 days and cannot be recovered.
        </p>
        <Link to="/" className="action-button action-button--primary">
          Build a new day
        </Link>
        <style>{styles}</style>
      </div>
    );
  }

  return (
    <div className="shared-view">
      <p className="shared-banner">
        Shared itinerary · This link is public to anyone who has it.
      </p>
      {itinerary && (
        <ResultView
          result={itinerary}
          readOnly
          shareId={shareId}
          onShareDeleted={() => {
            setItinerary(null);
            setState('not_found');
          }}
        />
      )}
      <div className="shared-footer-actions">
        <Link to="/" className="action-button action-button--secondary">
          Build your own day
        </Link>
      </div>
      <style>{styles}</style>
    </div>
  );
}

const styles = `
.share-loading {
  padding-top: var(--space-8);
  text-align: center;
  color: var(--color-ink-muted);
}

.share-not-found {
  padding-top: var(--space-8);
  text-align: center;
  max-width: 480px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
}

.not-found-headline {
  font-family: var(--font-display);
  font-size: 28px;
  line-height: 34px;
  font-weight: 500;
  color: var(--color-ink);
}

.not-found-text {
  font-size: 15px;
  color: var(--color-ink-muted);
}

.shared-banner {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-ink-muted);
  background: var(--color-accent-lilac);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-pill);
  margin-bottom: var(--space-4);
  text-align: center;
}

.shared-footer-actions {
  margin-top: var(--space-6);
  display: flex;
  justify-content: center;
}

.shared-view .action-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 52px;
  padding: var(--space-3) var(--space-5);
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--radius-input);
  text-decoration: none;
  text-align: center;
}

.shared-view .action-button--primary {
  color: #ffffff;
  background: var(--color-primary);
}

.shared-view .action-button--secondary {
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border-strong);
}
`;
