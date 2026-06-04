/* Article Finder — Stage 4: LIBRARY (database viewer) */
const { useState: useStateLib, useEffect: useEffectLib, useRef: useRefLib } = React;

function Select({ label, value, onChange, options }) {
  return (
    <label className="af-select">
      <span className="af-select__l">{label}</span>
      <span className="af-select__wrap">
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          {options.map((o) => <option key={o.v} value={o.v}>{o.label}</option>)}
        </select>
        <Icon name="chevron-down" size={14} className="af-select__chev" />
      </span>
    </label>
  );
}

function StageLibrary() {
  const s = window.useStore();
  const [filters, setFilters] = useStateLib({ q: '', topic: 'all', articleType: 'all', decision: 'all', status: 'all' });
  const [rows, setRows] = useStateLib(null);
  const [open, setOpen] = useStateLib(null);
  const allRef = useRefLib(null);

  // distinct option sets (computed once from a full fetch)
  const [opts, setOpts] = useStateLib(null);
  useEffectLib(() => {
    window.api.library({}).then((all) => {
      allRef.current = all;
      const distinct = (key, get) => [{ v: 'all', label: 'All ' + key }].concat(
        Array.from(new Set(all.map(get))).filter((x) => x && x !== '—').sort().map((x) => ({ v: x, label: window.ARTICLE_TYPE_LABELS[x] || x }))
      );
      setOpts({
        topic: distinct('topics', (a) => a.topic),
        type: distinct('types', (a) => a.articleType),
      });
    });
  }, []);

  useEffectLib(() => {
    setRows(null);
    let cancelled = false;
    window.api.library(filters).then((r) => { if (!cancelled) setRows(r); });
    return () => { cancelled = true; };
  }, [filters]);

  const set = (k, v) => setFilters((f) => ({ ...f, [k]: v }));
  const activeFilters = Object.entries(filters).filter(([k, v]) => v && v !== 'all' && v !== '').length;

  const decisionOpts = [{ v: 'all', label: 'All decisions' }, ...['ACCEPT', 'EDGE_CASE', 'REJECT', 'NEEDS_MORE_INFO'].map((d) => ({ v: d, label: window.TRIAGE[d].label }))];
  const statusOpts = [{ v: 'all', label: 'All retrieval' }, ...Object.keys(window.RETRIEVAL).map((st) => ({ v: st, label: window.RETRIEVAL[st].label }))];

  return (
    <div className="af-stage">
      <div className="af-stage__main af-stage__main--wide">
        {/* filter bar */}
        <div className="af-filterbar">
          <div className="af-searchbox">
            <Icon name="search" size={15} style={{ color: 'var(--fg-3)' }} />
            <input value={filters.q} onChange={(e) => set('q', e.target.value)} placeholder="Search title, author, abstract, DOI…" />
            {filters.q ? <button className="af-searchbox__clr" onClick={() => set('q', '')}><Icon name="x" size={13} /></button> : null}
          </div>
          {opts && <Select label="Topic" value={filters.topic} onChange={(v) => set('topic', v)} options={opts.topic} />}
          {opts && <Select label="Type" value={filters.articleType} onChange={(v) => set('articleType', v)} options={opts.type} />}
          <Select label="Triage" value={filters.decision} onChange={(v) => set('decision', v)} options={decisionOpts} />
          <Select label="Retrieval" value={filters.status} onChange={(v) => set('status', v)} options={statusOpts} />
          {activeFilters > 0 ? <Button variant="ghost" size="sm" icon="x" onClick={() => setFilters({ q: '', topic: 'all', articleType: 'all', decision: 'all', status: 'all' })}>Reset</Button> : null}
        </div>

        <div className="af-libcount af-data">
          {rows == null ? 'Loading…' : `${rows.length} article${rows.length === 1 ? '' : 's'}`}
          {rows && rows.length > 0 ? <span style={{ color: 'var(--fg-4)' }}> · {rows.filter((a) => a.retrieval.pdfUrl).length} with PDF</span> : null}
        </div>

        {/* table */}
        <div className="af-tablewrap">
          {rows == null ? (
            <div className="af-resolving__label" style={{ padding: 28 }}><Spinner /> Querying library…</div>
          ) : rows.length === 0 ? (
            <EmptyState icon="search" title="No articles match these filters">Try clearing a filter or broadening your search.</EmptyState>
          ) : (
            <table className="af-table af-table--lib">
              <thead>
                <tr>
                  <th>Article</th>
                  <th>Topic</th>
                  <th>Type</th>
                  <th>Triage</th>
                  <th>Retrieval</th>
                  <th className="af-th-voi">VOI</th>
                  <th className="af-th-open"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id} tabIndex={0} onClick={() => setOpen(a)}
                    onKeyDown={(e) => { if (e.key === 'Enter') setOpen(a); }}>
                    <td className="af-td-article">
                      <div className="af-art__title">{a.title}</div>
                      <div className="af-art__apa af-data">{a.authors[0]}{a.authors.length > 1 ? ' et al.' : ''}{a.year ? ` (${a.year})` : ''} · <span className="af-art__doi">{a.doi || 'no DOI'}</span></div>
                    </td>
                    <td className="af-td-topic">{a.topic && a.topic !== '—' ? <span className="af-topicchip">{a.topic}</span> : <span style={{ color: 'var(--fg-4)' }}>—</span>}</td>
                    <td className="af-td-type"><span className="af-typechip">{window.ARTICLE_TYPE_LABELS[a.articleType] || a.articleType}</span></td>
                    <td><TriageBadge decision={a.triage.decision} /></td>
                    <td><RetrievalBadge status={a.retrieval.status} /></td>
                    <td className="af-td-voi"><VoiChip value={a.voiScore} /></td>
                    <td className="af-td-open"><span className="af-openhint"><Icon name="chevron-right" size={16} /></span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {open ? <ArticleDrawer article={open} onClose={() => setOpen(null)} /> : null}
    </div>
  );
}

Object.assign(window, { StageLibrary });
