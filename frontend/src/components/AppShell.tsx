import { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import SiteFooter from './SiteFooter';
import { useAuth } from '../hooks/use-auth';

interface AppShellProps {
  children: React.ReactNode;
  onNewDay: () => void;
  showBack: boolean;
}

/**
 * Header identity control.
 *
 * Signed out it is a single sign-in action. Signed in it names the account, so
 * the viewer can always tell who they are about to publish as. The name comes
 * from the ID token and is never an email address.
 */
function AccountMenu() {
  const { authenticated, displayName, signIn, signOutUser } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => setOpen(false), [location.pathname]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!authenticated) {
    return (
      <button
        type="button"
        className="account-signin"
        onClick={() => void signIn(location.pathname)}
      >
        Sign in
      </button>
    );
  }

  const name = displayName ?? 'Traveller';

  return (
    <div className="account" ref={wrapRef}>
      <button
        type="button"
        className="account-chip"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <span className="account-avatar" aria-hidden="true">
          {name.charAt(0).toUpperCase()}
        </span>
        <span className="account-name">{name}</span>
        <svg
          className={`account-caret${open ? ' account-caret--open' : ''}`}
          width="10"
          height="6"
          viewBox="0 0 10 6"
          aria-hidden="true"
        >
          <path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <span className="sr-only">Signed in as {name}. Account menu.</span>
      </button>

      {open && (
        <div className="account-menu" role="menu">
          <p className="account-menu__who">
            <span className="account-menu__who-label">Signed in as</span>
            <span className="account-menu__who-name">{name}</span>
          </p>
          <Link to="/journal/me" className="account-menu__item" role="menuitem">
            My stories
          </Link>
          <Link to="/journal/new" className="account-menu__item" role="menuitem">
            Write a story
          </Link>
          <button
            type="button"
            className="account-menu__item account-menu__item--quiet"
            role="menuitem"
            onClick={signOutUser}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export default function AppShell({ children, onNewDay, showBack }: AppShellProps) {
  const location = useLocation();
  const [lifted, setLifted] = useState(false);
  const onJournal = location.pathname.startsWith('/journal');

  useEffect(() => {
    const onScroll = () => setLifted(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>

      <header className={`app-header${lifted ? ' app-header--lifted' : ''}`} role="banner">
        <div className="app-header__inner container">
          <div className="app-header__left">
            <Link to="/" className="wordmark" aria-label="Vialo home">
              <img src="/logo.png" alt="" className="wordmark-logo" width="36" height="36" />
              <span className="wordmark-text">vialo.</span>
            </Link>
            {showBack && (
              <button className="back-button" onClick={onNewDay} type="button">
                <span aria-hidden="true">←</span> New day
              </button>
            )}
          </div>

          <nav className="app-header__nav" aria-label="Primary">
            <Link
              to="/"
              className={`header-nav-link${!onJournal ? ' header-nav-link--current' : ''}`}
              aria-current={!onJournal ? 'page' : undefined}
            >
              Plan a day
            </Link>
            <Link
              to="/journal"
              className={`header-nav-link${onJournal ? ' header-nav-link--current' : ''}`}
              aria-current={onJournal ? 'page' : undefined}
            >
              Journal
            </Link>
            <AccountMenu />
          </nav>
        </div>
      </header>

      <main id="main-content" className="app-main container" role="main" tabIndex={-1}>
        {children}
      </main>
      <SiteFooter />
      <style>{styles}</style>
    </div>
  );
}

const styles = `
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.skip-link {
  position: fixed;
  top: var(--space-2);
  left: var(--space-2);
  z-index: 1000;
  padding: var(--space-3) var(--space-4);
  color: #ffffff;
  background: var(--color-primary);
  border-radius: var(--radius-input);
  transform: translateY(-160%);
  transition: transform var(--duration-fast) ease;
}

.skip-link:focus-visible {
  color: #ffffff;
  transform: translateY(0);
}

/* Sticky header. A solid canvas fill rather than a blurred panel: the design
   system rules out glassmorphism, and a hairline on scroll reads as structure. */
.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: var(--color-canvas);
  border-bottom: 1px solid transparent;
  transition: border-color var(--duration-fast) ease, box-shadow var(--duration-fast) ease;
}

.app-header--lifted {
  border-bottom-color: var(--color-border);
  box-shadow: 0 1px 12px rgb(43 35 38 / 0.04);
}

.app-header__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-height: 64px;
  padding-top: var(--space-3);
  padding-bottom: var(--space-3);
}

.app-header__left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.wordmark {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  text-decoration: none;
  min-height: 44px;
  flex-shrink: 0;
}

.wordmark-logo {
  width: 34px;
  height: 34px;
  border-radius: 9px;
}

.wordmark-text {
  font-family: var(--font-display);
  font-size: 23px;
  line-height: 1;
  font-weight: 500;
  color: var(--color-primary);
  letter-spacing: -0.01em;
  /* Optical alignment: the serif sits slightly high against the mark. */
  transform: translateY(1px);
}

.back-button {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink-muted);
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-3);
  border-radius: var(--radius-pill);
  border: 1px solid var(--color-border);
  background: var(--color-surface-strong);
  transition: color var(--duration-fast) ease, border-color var(--duration-fast) ease;
  white-space: nowrap;
}

.back-button:hover {
  color: var(--color-ink);
  border-color: var(--color-border-strong);
}

.app-header__nav {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
}

.header-nav-link {
  position: relative;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink-muted);
  text-decoration: none;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  padding: 0 var(--space-3);
  border-radius: var(--radius-pill);
  transition: color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.header-nav-link:hover {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.header-nav-link--current {
  color: var(--color-ink);
  font-weight: 600;
}

/* The current page is marked by a rule as well as weight, never colour alone. */
.header-nav-link--current::after {
  content: '';
  position: absolute;
  left: var(--space-3);
  right: var(--space-3);
  bottom: 8px;
  height: 2px;
  border-radius: 2px;
  background: var(--color-primary);
}

.account {
  position: relative;
  margin-left: var(--space-2);
}

.account-signin {
  min-height: 40px;
  padding: 0 var(--space-4);
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  background: var(--color-primary);
  border-radius: var(--radius-pill);
  transition: background var(--duration-fast) ease;
}

.account-signin:hover {
  background: var(--color-primary-hover);
}

.account-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 40px;
  padding: 3px var(--space-3) 3px 3px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: var(--color-surface-strong);
  color: var(--color-ink);
  transition: border-color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.account-chip:hover {
  border-color: var(--color-border-strong);
  background: var(--color-surface);
}

.account-avatar {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-pill);
  background: var(--color-primary);
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.account-name {
  font-size: 14px;
  font-weight: 500;
  max-width: 12ch;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-caret {
  color: var(--color-ink-muted);
  transition: transform var(--duration-fast) ease;
  flex-shrink: 0;
}

.account-caret--open {
  transform: rotate(180deg);
}

.account-menu {
  position: absolute;
  top: calc(100% + var(--space-2));
  right: 0;
  min-width: 208px;
  padding: var(--space-2);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-floating);
  z-index: 60;
  animation: account-menu-in var(--duration-fast) ease both;
}

@keyframes account-menu-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .account-menu { animation: none; }
}

.account-menu__who {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) var(--space-3) var(--space-3);
  border-bottom: 1px solid var(--color-border);
  margin-bottom: var(--space-2);
}

.account-menu__who-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-ink-muted);
}

.account-menu__who-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-menu__item {
  display: block;
  width: 100%;
  text-align: left;
  padding: var(--space-3);
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
  text-decoration: none;
  border-radius: 10px;
  min-height: 44px;
  transition: background var(--duration-fast) ease;
}

.account-menu__item:hover {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.account-menu__item--quiet {
  color: var(--color-ink-muted);
}

.app-main {
  flex: 1;
  padding-bottom: var(--space-8);
}

/* Below 560 px the wordmark text and the "Plan a day" link give up their space
   before the account control does: knowing who you are signed in as matters
   more than the label next to a mark that is already visible. */
@media (max-width: 560px) {
  .app-header__inner {
    gap: var(--space-2);
    min-height: 56px;
  }

  .wordmark-text {
    display: none;
  }

  .header-nav-link {
    padding: 0 var(--space-2);
  }

  .header-nav-link--current::after {
    left: var(--space-2);
    right: var(--space-2);
  }

  .account-name {
    display: none;
  }

  .account-chip {
    padding: 3px;
  }

  .back-button {
    padding: 0 var(--space-2);
  }
}
`;
