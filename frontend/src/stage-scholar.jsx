/* Article Finder — Stage 6: SCHOLAR COMPARE (external comparison) */
const { useState: useStateSch, useEffect: useEffectSch } = React;

function OursCard({ a }) {
  return (
    <div className="af-cmp-item">
      <div className="af-cmp-item__title">{a.title}</div>
      <div className="af-cmp-item__meta af-data">{a.authors[0]}{a.authors.length > 1 ? ' et al.' : ''}{a.year ? ` · ${a.year}` : ''}</div>
      <div className="af-cmp-item__row">
        <TriageBadge decision={a.triage.decision} />
        <RetrievalBadge status={a.retrieval.status} />
        <span style={{ flex: 1 }} />
        <VoiChip value={a.voiScore} />
      </div>
    </div>
  );
}

const FLAG_TONE = {
  'open access': 'good', 'paywalled': 'mute', 'publisher-blocked OA': 'warn',
  'blog': 'bad', 'not peer-reviewed': 'bad', 'off-topic': 'bad',
  'no cognition outcome': 'bad', 'no human subjects': 'bad', 'preprint': 'warn',
};

function ScholarCard({ r }) {
  return (
    <div className={`af-cmp-item af-cmp-item--scholar ${r.inOurSet ? '' : 'is-noise'}`}>
      <div className="af-cmp-item__title">{r.title}</div>
      <div className="af-cmp-item__meta af-data">{r.venue} · cited by {r.citedBy}</div>
      <div className="af-cmp-item__snip">{r.snippet}</div>
      <div className="af-cmp-item__flags">
        {r.flags.map((f) => <span key={f} className={`af-flag af-flag--${FLAG_TONE[f] || 'mute'}`}>{f}</span>)}
        {r.inOurSet
          ? <span className="af-flag af-flag--match"><Icon name="check" size={11} /> in our set</span>
          : <span className="af-flag af-flag--filtered"><Icon name="x" size={11} /> we filtered out</span>}
      </div>
    </div>
  );
}

function StageScholar() {
  const s = window.useStore();
  const [data, setData] = useStateSch(null);
  const [loading, setLoading] = useStateSch(true);

  const run = () => {
    setLoading(true);
    window.api.compareScholar(s.topic).then((d) => { setData(d); setLoading(false); });
  };
  useEffectSch(() => { run(); }, []);

  const noiseFiltered = data ? data.scholar.filter((r) => !r.inOurSet).length : 0;

  return (
    <div className="af-stage">
      <div className="af-stage__main af-stage__main--wide">
        <div className="af-cmp-querybar">
          <div className="af-cmp-querybar__q">
            <Icon name="search" size={15} style={{ color: 'var(--fg-3)' }} />
            <span className="af-cmp-querybar__text">{s.topic}</span>
          </div>
          <Button variant="secondary" size="sm" icon="rotate-cw" onClick={run} disabled={loading}>Re-run</Button>
        </div>

        <div className="af-cmp-banner">
          <Icon name="info" size={15} style={{ color: 'var(--cool)', flexShrink: 0 }} />
          <span>External comparison. The right column shows raw <b>Google Scholar AI</b> results for the same query, presented as-is. Article Finder adds triage, value-of-information and verified retrieval — and removes off-topic noise.</span>
        </div>

        {loading ? (
          <div className="af-resolving__label" style={{ padding: 28 }}><Spinner /> Running both searches…</div>
        ) : (
          <div className="af-cmp-grid">
            <section className="af-cmp-col af-cmp-col--ours">
              <div className="af-cmp-col__head">
                <div className="af-cmp-col__brand"><span className="af-cmp-logo">AF</span> Article Finder</div>
                <div className="af-cmp-col__count af-data">{data.ours.length} triaged · {data.ours.filter((a) => a.retrieval.pdfUrl).length} with PDF</div>
              </div>
              <div className="af-cmp-col__body">
                {data.ours.map((a) => <OursCard key={a.id} a={a} />)}
              </div>
            </section>

            <section className="af-cmp-col af-cmp-col--scholar">
              <div className="af-cmp-col__head">
                <div className="af-cmp-col__brand af-cmp-col__brand--ext"><Icon name="globe" size={16} /> Google Scholar AI</div>
                <div className="af-cmp-col__count af-data">{data.scholar.length} results · {noiseFiltered} off-topic</div>
              </div>
              <div className="af-cmp-col__body">
                {data.scholar.map((r, i) => <ScholarCard key={i} r={r} />)}
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { StageScholar });
