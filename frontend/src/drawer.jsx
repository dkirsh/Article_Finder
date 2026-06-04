/* Article Finder — shared Article detail drawer */
const { useEffect: useEffectDrawer } = React;

function MetaRow({ label, children, mono }) {
  return (
    <div className="af-mrow">
      <div className="af-mrow__l">{label}</div>
      <div className={`af-mrow__v ${mono ? 'af-data' : ''}`}>{children}</div>
    </div>
  );
}

function ArticleDrawer({ article, onClose }) {
  useEffectDrawer(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!article) return null;
  const a = article;
  const r = window.RETRIEVAL[a.retrieval.status] || window.RETRIEVAL.not_attempted;
  const retrieved = a.retrieval.pdfUrl != null;

  return (
    <div className="af-drawer-scrim" onClick={onClose}>
      <aside className="af-drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Article detail">
        <div className="af-drawer__head">
          <div className="af-drawer__chips">
            <span className={`af-kind af-kind--${a.inputKind}`}>{window.INPUT_KIND_LABELS[a.inputKind]}</span>
            <TriageBadge decision={a.triage.decision} />
            <RetrievalBadge status={a.retrieval.status} />
          </div>
          <button className="af-iconbtn" onClick={onClose} title="Close (Esc)"><Icon name="x" size={18} /></button>
        </div>

        <div className="af-drawer__body">
          <h2 className="af-drawer__title">{a.title}</h2>
          <div className="af-drawer__authors af-data">{a.authors.join(', ')}{a.year ? ` · ${a.year}` : ''}</div>

          <div className="af-drawer__voi">
            <div className="af-mini-stat">
              <div className="af-mini-stat__l">VOI score</div>
              <div className="af-mini-stat__v"><VoiChip value={a.voiScore} size="lg" /></div>
            </div>
            <div className="af-mini-stat">
              <div className="af-mini-stat__l">Triage confidence</div>
              <div className="af-mini-stat__v af-data" style={{ color: (window.TRIAGE[a.triage.decision] || {}).color }}>{Math.round(a.triage.confidence * 100)}%</div>
            </div>
            <div className="af-mini-stat">
              <div className="af-mini-stat__l">Type</div>
              <div className="af-mini-stat__v">{window.ARTICLE_TYPE_LABELS[a.articleType] || a.articleType}</div>
            </div>
          </div>

          <div className="af-drawer__reason">
            <Icon name="info" size={14} style={{ color: (window.TRIAGE[a.triage.decision] || {}).color, flexShrink: 0, marginTop: 2 }} />
            <span>{a.triage.reason}</span>
          </div>

          <div className="af-drawer__section">
            <div className="af-section-eyebrow">Abstract</div>
            {a.abstract
              ? <p className="af-drawer__abs">{a.abstract}</p>
              : <p className="af-drawer__abs af-drawer__abs--none">No abstract is available for this record. Resolve the full text to assess relevance.</p>}
          </div>

          <div className="af-drawer__section">
            <div className="af-section-eyebrow">Citation (APA)</div>
            <div className="af-apa">{a.apaCitation}</div>
          </div>

          <div className="af-drawer__section">
            <div className="af-section-eyebrow">Record</div>
            <MetaRow label="Topic">{a.topic && a.topic !== '—' ? a.topic : <span style={{ color: 'var(--fg-4)' }}>—</span>}</MetaRow>
            <MetaRow label="DOI" mono>
              {a.doi ? <a className="af-link" href={`https://doi.org/${a.doi}`} target="_blank" rel="noreferrer">{a.doi} <Icon name="external-link" size={12} /></a> : <span style={{ color: 'var(--fg-4)' }}>—</span>}
            </MetaRow>
            <MetaRow label="Retrieval">
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <RetrievalBadge status={a.retrieval.status} />
                <span style={{ color: 'var(--fg-3)', fontSize: 12 }}>{r.desc}</span>
              </span>
            </MetaRow>
            {a.retrieval.discoveredVia ? <MetaRow label="Discovered via" mono>{a.retrieval.discoveredVia}</MetaRow> : null}
            {retrieved ? (
              <React.Fragment>
                <MetaRow label="PDF">
                  <a className="af-link" href="#" onClick={(e) => e.preventDefault()}><Icon name="file-text" size={13} /> {a.retrieval.pdfUrl.split('/').pop()}</a>
                  <span className="af-data" style={{ color: 'var(--fg-3)', marginLeft: 8 }}>{window.fmtBytes(a.retrieval.bytes)}</span>
                </MetaRow>
                <MetaRow label="sha256" mono>
                  <span className="af-sha" title={a.retrieval.sha256}>{a.retrieval.sha256.replace('sha256:', '')}</span>
                </MetaRow>
              </React.Fragment>
            ) : null}
          </div>
        </div>

        <div className="af-drawer__foot">
          {retrieved
            ? <Button variant="primary" icon="download">Open PDF</Button>
            : <Button variant="secondary" icon="lock" disabled>No PDF available</Button>}
          <Button variant="ghost" icon="external-link" onClick={() => a.doi && window.open(`https://doi.org/${a.doi}`, '_blank')}>View source</Button>
        </div>
      </aside>
    </div>
  );
}

Object.assign(window, { ArticleDrawer });
