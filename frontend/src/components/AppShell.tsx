import { Link } from 'react-router-dom';
import SiteFooter from './SiteFooter';

interface AppShellProps {
  children: React.ReactNode;
  onNewDay: () => void;
  showBack: boolean;
}

export default function AppShell({ children, onNewDay, showBack }: AppShellProps) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="app-header container" role="banner">
        {showBack && (
          <button
            className="back-button"
            onClick={onNewDay}
            aria-label="Start a new day"
          >
            ← New day
          </button>
        )}
        <Link to="/" className="wordmark" aria-label="Vialo home">
          vialo.
        </Link>
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

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--space-4);
  padding-bottom: var(--space-4);
  min-height: 56px;
}

.wordmark {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 500;
  color: var(--color-primary);
  text-decoration: none;
  margin-left: auto;
}

.back-button {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-ink-muted);
  min-height: 44px;
  min-width: 44px;
  display: flex;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-input);
  transition: color var(--duration-fast) ease;
}

.back-button:hover {
  color: var(--color-ink);
}

.app-main {
  flex: 1;
  padding-bottom: var(--space-8);
}
`;
