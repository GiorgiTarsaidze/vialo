export default function PrivacyPage() {
  return (
    <article className="legal-page" aria-labelledby="privacy-heading">
      <h1 id="privacy-heading" className="legal-heading">Privacy</h1>

      <section>
        <h2>What Vialo processes</h2>
        <p>
          Vialo processes your natural-language day description to build a scheduled itinerary.
          Your prompt is sent to a server, used to query Google Places and Routes APIs, and
          processed through a language model to identify candidate stops. Prompts are processed
          in memory and are not stored after the request completes.
        </p>
      </section>

      <section>
        <h2>What Vialo stores</h2>
        <ul>
          <li>
            <strong>Place data cache:</strong> Google Places results are cached server-side
            with automatic expiry to reduce API calls. No user data is in the cache.
          </li>
          <li>
            <strong>Rate limiting:</strong> A cryptographic hash of your IP address is used
            to enforce request limits. Your raw IP address is never stored or logged.
          </li>
          <li>
            <strong>Shared itineraries:</strong> If you choose to share a result, the computed
            itinerary is stored for 30 days. Shared links are public to anyone with the URL.
            No account or personal information is attached.
          </li>
        </ul>
      </section>

      <section>
        <h2>What Vialo does not do</h2>
        <ul>
          <li>Does not create accounts or collect personal information.</li>
          <li>Does not use cookies for tracking or advertising.</li>
          <li>Does not sell or share data with third parties beyond the services above.</li>
          <li>Does not log raw prompts, IP addresses, or model outputs.</li>
        </ul>
      </section>

      <section>
        <h2>Third-party services</h2>
        <p>
          Vialo uses Google Maps Platform (Places API, Routes API, Maps JavaScript API) and
          AWS Bedrock (Claude) for AI inference. These services have their own privacy policies.
        </p>
      </section>

      <section>
        <h2>Do not enter sensitive information</h2>
        <p>
          The input field is for describing a sightseeing day (city, times, interests).
          Do not enter personal, financial, medical, or other sensitive information.
        </p>
      </section>

      <style>{styles}</style>
    </article>
  );
}

const styles = `
.legal-page {
  max-width: 640px;
  margin: 0 auto;
  padding-top: var(--space-7);
}

.legal-heading {
  font-family: var(--font-display);
  font-size: 38px;
  line-height: 42px;
  font-weight: 500;
  color: var(--color-ink);
  margin-bottom: var(--space-6);
}

.legal-page h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin-top: var(--space-6);
  margin-bottom: var(--space-3);
}

.legal-page p,
.legal-page li {
  font-size: 15px;
  line-height: 23px;
  color: var(--color-ink);
  margin-bottom: var(--space-3);
}

.legal-page ul {
  padding-left: var(--space-5);
}
`;
