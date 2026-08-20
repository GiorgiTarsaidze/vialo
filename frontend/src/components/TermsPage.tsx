export default function TermsPage() {
  return (
    <article className="legal-page" aria-labelledby="terms-heading">
      <h1 id="terms-heading" className="legal-heading">Terms of Use</h1>

      <section>
        <h2>Service description</h2>
        <p>
          Vialo is a free itinerary scheduling tool. It builds day schedules using real place
          data, opening hours, and travel times. Results are estimates and should be verified
          on arrival. Vialo also hosts the Journal, where travellers publish written accounts of
          days they have walked.
        </p>
      </section>

      <section>
        <h2>No warranty</h2>
        <p>
          Vialo is provided as-is. Opening hours, travel times, and place availability may
          change without notice. Vialo is not responsible for closed venues, inaccurate
          directions, or missed appointments resulting from its output.
        </p>
      </section>

      <section>
        <h2>Acceptable use</h2>
        <ul>
          <li>Use Vialo only for planning city sightseeing days.</li>
          <li>Do not submit offensive, illegal, or harmful content.</li>
          <li>Do not attempt to circumvent rate limits or abuse the service.</li>
          <li>Do not use automated tools to make bulk requests.</li>
        </ul>
      </section>

      <section>
        <h2>Rate limits</h2>
        <p>
          Vialo limits requests per IP address to ensure fair access during free use.
          Exceeding the limit results in a temporary cooldown.
        </p>
      </section>

      <section>
        <h2>Shared itineraries</h2>
        <p>
          Shared links are public and expire after 30 days. You can delete a shared
          itinerary from the browser that created it. Once deleted or expired, the data
          cannot be recovered.
        </p>
      </section>

      <section>
        <h2>Journal accounts and content</h2>
        <ul>
          <li>
            Reading the Journal needs no account. Publishing a story, commenting, or reporting
            requires one.
          </li>
          <li>
            You keep ownership of what you write. By publishing, you grant Vialo permission to
            display it publicly on this site for as long as you leave it published.
          </li>
          <li>
            Publish only what is yours. Do not upload images or text you do not have the right to
            share, and do not publish other people's personal information.
          </li>
          <li>
            Stories cannot be edited after publication. You may delete your own stories and
            comments at any time, and deletion is permanent.
          </li>
          <li>
            Each account may publish 5 stories and 20 comments per day. Cover images are limited to
            one per story, 2 MB, in JPEG, PNG, or WebP.
          </li>
          <li>
            A story reported by 3 accounts is hidden from the site automatically. This is a
            mechanical limit, not a judgement, and there is no appeal process.
          </li>
        </ul>
      </section>

      <section>
        <h2>Attribution</h2>
        <p>
          Place data and maps are provided by Google Maps Platform. AI inference uses
          AWS Bedrock. Photo attributions are displayed as required by their respective
          licenses.
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
