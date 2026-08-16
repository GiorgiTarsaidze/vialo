import { Link } from 'react-router-dom';

export default function SiteFooter() {
  return (
    <footer className="site-footer container" role="contentinfo">
      <nav aria-label="Footer navigation" className="footer-links">
        <Link to="/privacy">Privacy</Link>
        <Link to="/terms">Terms</Link>
        <a
          href="https://github.com/GiorgiTarsaidze/vialo"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
      </nav>
      <style>{styles}</style>
    </footer>
  );
}

const styles = `
.site-footer {
  padding-top: var(--space-6);
  padding-bottom: var(--space-5);
  border-top: 1px solid var(--color-border);
  margin-top: auto;
}

.footer-links {
  display: flex;
  gap: var(--space-5);
  flex-wrap: wrap;
}

.footer-links a {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-ink-muted);
  text-decoration: none;
  min-height: 44px;
  display: flex;
  align-items: center;
}

.footer-links a:hover {
  color: var(--color-primary);
  text-decoration: underline;
}
`;
