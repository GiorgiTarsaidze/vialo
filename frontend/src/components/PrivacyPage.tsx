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
          <li>
            <strong>Journal accounts:</strong> Publishing to the Journal requires an account.
            Your email address and password are held by AWS Cognito, not by Vialo. Vialo never
            sees your password. The Journal's own storage holds only an opaque account identifier
            and a display name, never your email address.
          </li>
          <li>
            <strong>Journal stories and comments:</strong> What you publish is public, attributed
            to your display name, and stored until you delete it. Unlike shared itineraries, it
            does not expire after 30 days. If you attach an itinerary to a story, a copy of that
            itinerary is stored inside the story so it outlives the 30-day share window.
          </li>
          <li>
            <strong>Cover images:</strong> An uploaded cover image is stored in a private bucket
            and served through Vialo's CDN. Vialo does not strip metadata from your image, so
            remove location data before uploading if you do not want it published.
          </li>
        </ul>
      </section>

      <section>
        <h2>Deleting your content</h2>
        <p>
          You can delete any story or comment you published, from the browser you are signed in
          with. Deletion is immediate and cannot be undone. To remove your account itself, contact
          the maintainer through the GitHub repository linked in the footer.
        </p>
      </section>

      <section>
        <h2>What Vialo does not do</h2>
        <ul>
          <li>Does not require an account to plan a day, or to read the Journal.</li>
          <li>Does not store your email address outside the AWS Cognito user pool.</li>
          <li>Does not use cookies for tracking or advertising.</li>
          <li>Does not sell or share data with third parties beyond the services above.</li>
          <li>Does not log raw prompts, IP addresses, model outputs, or authentication tokens.</li>
        </ul>
      </section>

      <section>
        <h2>Third-party services</h2>
        <p>
          Vialo uses Google Maps Platform (Places API, Routes API, Maps JavaScript API) for place
          and route data, AWS Bedrock (Claude) for AI inference, and AWS Cognito for Journal
          sign-in. These services have their own privacy policies.
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
