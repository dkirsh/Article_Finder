/* Article Finder — Stage 2: IDENTIFY & TRIAGE */
const { useState: useStateTriage, useEffect: useEffectTriage, useRef: useRefTriage } = React;

function TriageStat({ decision, n, active, onClick }) {
  const t = window.TRIAGE[decision];
  return (
    <button className={`af-tstat ${active ? 'is-active' : ''}`} onClick={onClick}>
      <span className="af-tstat__dot" style={{ background: t.color }} />
      <span className="af-tstat__n af-data">{n}</span>
      <span className="af-tstat__l">{t.label}</span>
    </button>
  );
}

function StageTriage() {
  const s = window.useStore();
  const [open, setOpen] = useStateTriage(null);
  const [filter, setFilter] = useStateTriage('all');
  const tbodyRef = useRefTriage(null);

  // auto-run triage on entry if we have enriched articles but no classification yet
  useEffectTriage(() => {
    if (s.enriched && !s.triaged && s.triageState === 'idle') s.runTriage();
  }, [s.enriched, s.triaged, s.triageState]);

  if (!s.enriched) {
    return (
      <div className="af-stage"><div className="af-stage__main">
        <EmptyState icon="list-checks" title="No articles to triage yet"
          action={<Button variant="primary" icon="inbox" onClick={() => s.setRoute('ingest')}>Go to Ingest</Button>}>
          Ingest and enrich some inputs first — triage classifies each resolved article by topic, type, decision and value-of-information.
        </EmptyState>
      </div></div>
    );
  }

  if (s.triageState === 'loading' || !s.triaged) {
    return (
      <div className="af-stage"><div className="af-stage__main">
        <div className="af-card"><div className="af-resolving__label" style={{ padding: 28 }}>
          <Spinner /> Classifying {s.enriched.length} articles — topic · type · triage · VOI…
        </div></div>
      </div></div>
    );
  }

  const rows = s.triaged.filter((a) => filter === 'all' || a.triage.decision === filter);
  const counts = (d) => s.triaged.filter((a) => a.triage.decision === d).length;
  const acceptIds = s.triaged.filter((a) => a.triage.decision === 'ACCEPT').map((a) => a.id);
  const allAcceptSelected = acceptIds.length > 0 && acceptIds.every((id) => s.selectedIds.includes(id));

  const onRowKey = (e, idx, a) => {
    if (e.key === ' ') { e.preventDefault(); s.toggleSelect(a.id); }
    else if (e.key === 'Enter') { e.preventDefault(); setOpen(a); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); focusRow(idx + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); focusRow(idx - 1); }
  };
  const focusRow = (idx) => {
    const body = tbodyRef.current; if (!body) return;
    const r = body.querySelectorAll('tr')[idx];
    if (r) r.focus();
  };

  return (
    <div className="af-stage">
      <div className="af-stage__main af-stage__main--wide">
        {/* triage summary / filters */}
        <div className="af-triagebar">
          <div className="af-tstats">
            <button className={`af-tstat ${filter === 'all' ? 'is-active' : ''}`} onClick={() => setFilter('all')}>
              <span className="af-tstat__n af-data">{s.triaged.length}</span><span className="af-tstat__l">All</span>
            </button>
            {['ACCEPT', 'EDGE_CASE', 'REJECT', 'NEEDS_MORE_INFO'].map((d) => (
              <TriageStat key={d} decision={d} n={counts(d)} active={filter === d} onClick={() => setFilter(filter === d ? 'all' : d)} />
            ))}
          </div>
          <div className="af-triagebar__actions">
            <span className="af-selcount af-data">{s.selectedIds.length} selected</span>
            <Button variant="secondary" size="sm" icon="check" onClick={s.selectAllAccept} disabled={allAcceptSelected}>Select all Accept</Button>
            <Button variant="ghost" size="sm" onClick={s.clearSelect} disabled={!s.selectedIds.length}>Clear</Button>
          </div>
        </div>

        {/* table */}
        <div className="af-tablewrap">
          <table className="af-table">
            <thead>
              <tr>
                <th className="af-th-check">
                  <Check checked={allAcceptSelected} indeterminate={!allAcceptSelected && s.selectedIds.length > 0}
                    onChange={() => (allAcceptSelected ? s.clearSelect() : s.selectAllAccept())} ariaLabel="Select all accepted" />
                </th>
                <th>Article</th>
                <th className="af-th-abs">Abstract</th>
                <th>Topic</th>
                <th>Type</th>
                <th>Triage</th>
                <th className="af-th-voi">VOI</th>
              </tr>
            </thead>
            <tbody ref={tbodyRef}>
              {rows.map((a, idx) => {
                const sel = s.selectedIds.includes(a.id);
                const t = window.TRIAGE[a.triage.decision];
                return (
                  <tr key={a.id} tabIndex={0} className={sel ? 'is-selected' : ''}
                    onClick={() => s.toggleSelect(a.id)}
                    onKeyDown={(e) => onRowKey(e, idx, a)}>
                    <td className="af-td-check" onClick={(e) => e.stopPropagation()}>
                      <Check checked={sel} onChange={() => s.toggleSelect(a.id)} ariaLabel={`Select ${a.title}`} />
                    </td>
                    <td className="af-td-article">
                      <div className="af-art__title" onClick={(e) => { e.stopPropagation(); setOpen(a); }}>{a.title}</div>
                      <div className="af-art__apa af-data">{a.authors[0]}{a.authors.length > 1 ? ' et al.' : ''}{a.year ? ` (${a.year})` : ''} · <span className="af-art__doi">{a.doi || 'no DOI'}</span></div>
                    </td>
                    <td className="af-td-abs">
                      {a.abstract ? <span className="af-abs-snip">{window.abstractSnippet(a.abstract, 130)}</span>
                        : <span className="af-abs-none"><Icon name="alert-circle" size={12} /> no abstract</span>}
                    </td>
                    <td className="af-td-topic">{a.topic && a.topic !== '—' ? <span className="af-topicchip">{a.topic}</span> : <span style={{ color: 'var(--fg-4)' }}>—</span>}</td>
                    <td className="af-td-type"><span className="af-typechip">{window.ARTICLE_TYPE_LABELS[a.articleType] || a.articleType}</span></td>
                    <td className="af-td-triage">
                      <div className="af-triagecell">
                        <TriageBadge decision={a.triage.decision} />
                        <ConfBar value={a.triage.confidence} color={t.color} />
                      </div>
                    </td>
                    <td className="af-td-voi"><VoiChip value={a.voiScore} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="af-tablehint af-data">↑ ↓ move · Space select · Enter open · click a title for details</div>
      </div>

      <div className="af-actionbar">
        <div className="af-actionbar__info">
          {s.selectedIds.length
            ? <span>Retrieving PDFs for <b className="af-data">{s.selectedIds.length}</b> selected article{s.selectedIds.length > 1 ? 's' : ''}.</span>
            : <span>Select the articles to retrieve. <b style={{ color: 'var(--success)' }}>Accept</b> rows are pre-selected.</span>}
        </div>
        <div className="af-actionbar__btns">
          <Button variant="ghost" size="md" icon="inbox" onClick={() => s.setRoute('ingest')}>Back</Button>
          <Button variant="primary" size="md" iconRight="arrow-right" disabled={!s.selectedIds.length}
            onClick={() => s.setRoute('retrieve')}>Retrieve {s.selectedIds.length} selected</Button>
        </div>
      </div>

      {open ? <ArticleDrawer article={open} onClose={() => setOpen(null)} /> : null}
    </div>
  );
}

Object.assign(window, { StageTriage });
