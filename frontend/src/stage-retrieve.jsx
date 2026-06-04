/* Article Finder — Stage 3: RETRIEVE */
const { useState: useStateRetr } = React;

function RetrieveRow({ article, phase, result }) {
  const a = article;
  let statusEl;
  if (result) {
    statusEl = <RetrievalBadge status={result.retrieval.status} />;
  } else if (phase === 'working') {
    statusEl = <span className="af-retr__work"><Spinner size={13} /> fetching…</span>;
  } else if (phase === 'done') {
    statusEl = <span className="af-retr__work" style={{ color: 'var(--success)' }}><Icon name="check" size={13} /> resolved</span>;
  } else {
    statusEl = <span className="af-retr__queued af-data">queued</span>;
  }
  return (
    <div className={`af-retr ${phase === 'working' ? 'is-working' : ''}`}>
      <div className="af-retr__bar"><i className={`af-retr__fill ${phase || 'idle'}`} /></div>
      <div className="af-retr__main">
        <div className="af-retr__title">{a.title}</div>
        <div className="af-retr__meta af-data">{a.doi || 'no DOI'}{result && result.retrieval.discoveredVia ? ` · via ${result.retrieval.discoveredVia}` : ''}</div>
      </div>
      <div className="af-retr__status">{statusEl}</div>
    </div>
  );
}

function StageRetrieve() {
  const s = window.useStore();
  const selected = (s.triaged || []).filter((a) => s.selectedIds.includes(a.id));
  const resultsById = {};
  (s.retrieveResults || []).forEach((r) => (resultsById[r.id] = r));

  if (!selected.length && !s.retrieveResults) {
    return (
      <div className="af-stage"><div className="af-stage__main">
        <EmptyState icon="download" title="Nothing selected to retrieve"
          action={<Button variant="primary" icon="list-checks" onClick={() => s.setRoute('triage')}>Go to Triage</Button>}>
          Select articles in Triage, then return here to attempt PDF retrieval.
        </EmptyState>
      </div></div>
    );
  }

  const done = s.retrieveState === 'done' && s.retrieveResults;
  const loading = s.retrieveState === 'loading';
  const results = s.retrieveResults || [];
  const gotPdf = results.filter((r) => r.retrieval.pdfUrl != null);
  const statusBreak = (st) => results.filter((r) => r.retrieval.status === st).length;

  return (
    <div className="af-stage">
      <div className="af-stage__main">
        {/* success summary */}
        {done && (
          <section className="af-summary-card">
            <div className="af-summary-card__big">
              <span className="af-summary-card__num af-data">{gotPdf.length}</span>
              <span className="af-summary-card__of af-data">of {results.length}</span>
              <span className="af-summary-card__lbl">PDFs retrieved</span>
            </div>
            <div className="af-summary-card__break">
              {['oa_retrieved', 'browser_retrieved', 'oa_blocked', 'paywalled'].map((st) => {
                const n = statusBreak(st); if (!n) return null;
                const r = window.RETRIEVAL[st];
                return (
                  <div className="af-sb" key={st}>
                    <span className="af-sb__dot" style={{ background: r.color }} />
                    <span className="af-sb__n af-data">{n}</span>
                    <span className="af-sb__l">{r.label}</span>
                  </div>
                );
              })}
            </div>
            <p className="af-summary-card__note">
              {gotPdf.length} full text{gotPdf.length === 1 ? '' : 's'} secured. {results.length - gotPdf.length} remain metadata-only — paywalled or publisher-blocked. No retrieval is forced to succeed.
            </p>
          </section>
        )}

        <section className="af-card">
          <div className="af-card__head">
            <h3 className="af-card__title">{done ? 'Retrieval results' : 'Retrieval queue'}</h3>
            <span className="af-count af-data">{selected.length} articles</span>
          </div>
          <div className="af-retrlist">
            {selected.map((a) => (
              <RetrieveRow key={a.id} article={a} phase={s.retrieveProgress[a.id]} result={resultsById[a.id]} />
            ))}
          </div>
        </section>

        {/* retrieved files list */}
        {done && gotPdf.length > 0 && (
          <section className="af-card">
            <div className="af-card__head"><h3 className="af-card__title">Open retrieved files</h3></div>
            <div className="af-filelist">
              {gotPdf.map((r) => (
                <div className="af-file" key={r.id}>
                  <div className="af-file__icon" style={{ color: window.RETRIEVAL[r.retrieval.status].color }}><Icon name="file-text" size={16} /></div>
                  <div className="af-file__main">
                    <div className="af-file__name">{r.retrieval.pdfUrl.split('/').pop()}</div>
                    <div className="af-file__meta af-data">{window.fmtBytes(r.retrieval.bytes)} · {r.retrieval.sha256.replace('sha256:', '').slice(0, 16)}…</div>
                  </div>
                  <RetrievalBadge status={r.retrieval.status} />
                  <Button variant="secondary" size="sm" icon="download">Open</Button>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>

      <div className="af-actionbar">
        <div className="af-actionbar__info">
          {done
            ? <span>Saved to the library. <b className="af-data">{gotPdf.length}</b> with full text, <b className="af-data">{results.length - gotPdf.length}</b> metadata-only.</span>
            : loading ? <span>Attempting open-access, then browser-assisted retrieval…</span>
            : <span>Attempt retrieval for <b className="af-data">{selected.length}</b> selected article{selected.length > 1 ? 's' : ''}. Expect a realistic mix of outcomes.</span>}
        </div>
        <div className="af-actionbar__btns">
          <Button variant="ghost" size="md" icon="list-checks" onClick={() => s.setRoute('triage')}>Back to Triage</Button>
          {done
            ? <Button variant="primary" size="md" icon="database" onClick={() => s.setRoute('library')}>View in Library</Button>
            : <Button variant="primary" size="md" icon={loading ? null : 'download'} disabled={loading} onClick={s.runRetrieve}>
                {loading ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><Spinner size={14} /> Retrieving…</span> : 'Start retrieval'}
              </Button>}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { StageRetrieve });
