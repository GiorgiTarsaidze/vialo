import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { exchangeCode } from '../lib/cognito';

type CallbackState = 'exchanging' | 'success' | 'error';

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [state, setState] = useState<CallbackState>('exchanging');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get('code');
    const stateParam = searchParams.get('state');

    if (!code || !stateParam) {
      setState('error');
      setError('Missing authorization code or state. Please try signing in again.');
      return;
    }

    let cancelled = false;
    exchangeCode(code, stateParam).then((result) => {
      if (cancelled) return;
      if (result.success) {
        setState('success');
        navigate(result.returnPath ?? '/journal', { replace: true });
      } else {
        setState('error');
        setError(result.error ?? 'Sign-in failed.');
      }
    });

    return () => { cancelled = true; };
  }, [searchParams, navigate]);

  if (state === 'error') {
    return (
      <div className="auth-callback">
        <p className="auth-error" role="alert">{error}</p>
        <Link to="/journal" className="auth-retry">Return to Journal</Link>
        <style>{styles}</style>
      </div>
    );
  }

  return (
    <div className="auth-callback" aria-live="polite">
      <p className="auth-exchanging">Signing you in…</p>
      <style>{styles}</style>
    </div>
  );
}

const styles = `
.auth-callback {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-top: var(--space-9);
  gap: var(--space-4);
  text-align: center;
}

.auth-exchanging {
  font-size: 15px;
  color: var(--color-ink-muted);
}

.auth-error {
  font-size: 15px;
  color: var(--color-danger);
  max-width: 360px;
}

.auth-retry {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary);
  min-height: 44px;
  display: inline-flex;
  align-items: center;
}
`;
