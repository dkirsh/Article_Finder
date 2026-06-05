/* Article Finder — app shell, sidebar nav, display settings, routing */
const { useState: useStateApp } = React;

const STAGES = [
  { id: 'ingest',   n: 1, group: 'pipeline', icon: 'inbox',       label: 'Ingest',          title: 'Ingest',            desc: 'Accept files, a .zip, or pasted text — then resolve each input to a structured article.' },
  { id: 'triage',   n: 2, group: 'pipeline', icon: 'list-checks', label: 'Identify & Triage', title: 'Identify & Triage', desc: 'Topic, type, a triage decision and value-of-information for every resolved article.' },
  { id: 'retrieve', n: 3, group: 'pipeline', icon: 'download',    label: 'Retrieve',        title: 'Retrieve',          desc: 'Attempt PDFs for the selected articles. Outcomes are reported honestly.' },
  { id: 'library',  group: 'explore', icon: 'database', label: 'Library',         title: 'Library',           desc: 'Every collected article. Filter by topic, type, decision and retrieval status.' },
  { id: 'voi',      group: 'explore', icon: 'target',   label: 'VOI',             title: 'Recommended areas to search', desc: 'Knowledge gaps ranked by value of information, with suggested queries.' },
  { id: 'compare',  group: 'explore', icon: 'compare',  label: 'Scholar Compare', title: 'Scholar Compare',   desc: 'Article Finder vs Google Scholar AI for the same query — an external comparison.' },
];

function Segmented({ value, onChange, options }) {
  return (
    <div className="af-seg" role="group">
      {options.map((o) => (
        <button key={o.v} className={`af-seg__btn ${value === o.v ? 'is-on' : ''}`} onClick={() => onChange(o.v)}>{o.label}</button>
      ))}
    </div>
  );
}

function DisplayPanel({ onClose }) {
  const s = window.useStore();
  const t = s.tweaks;
  return (
    <React.Fragment>
      <div className="af-pop-scrim" onClick={onClose} />
      <div className="af-pop" role="dialog" aria-label="Display settings">
        <div className="af-pop__head"><span>Display</span><button className="af-iconbtn" onClick={onClose}><Icon name="x" size={16} /></button></div>
        <div className="af-pop__field">
          <div className="af-pop__l">Theme</div>
          <Segmented value={t.theme} onChange={(v) => s.setTweak('theme', v)} options={[{ v: 'dark', label: 'Dark' }, { v: 'light', label: 'Light' }]} />
        </div>
        <div className="af-pop__field">
          <div className="af-pop__l">Table density</div>
          <Segmented value={t.density} onChange={(v) => s.setTweak('density', v)} options={[{ v: 'comfortable', label: 'Comfortable' }, { v: 'compact', label: 'Compact' }]} />
        </div>
        <div className="af-pop__field">
          <div className="af-pop__l">Accent</div>
          <div className="af-swatches">
            {[['amber', '#F29A4B'], ['blue', '#57A8D9'], ['green', '#4ADE80']].map(([k, c]) => (
              <button key={k} className={`af-swatch ${t.accent === k ? 'is-on' : ''}`} style={{ '--sw': c }} onClick={() => s.setTweak('accent', k)} title={k}>
                <span style={{ background: c }} />
              </button>
            ))}
          </div>
        </div>
        <div className="af-pop__field">
          <div className="af-pop__l">Status badges</div>
          <Segmented value={t.badgeStyle} onChange={(v) => s.setTweak('badgeStyle', v)} options={[{ v: 'pill', label: 'Pill' }, { v: 'dot', label: 'Dot' }, { v: 'text', label: 'Text' }]} />
        </div>
      </div>
    </React.Fragment>
  );
}

function NavItem({ stage, active, state, onClick }) {
  return (
    <button className={`af-nav ${active ? 'is-active' : ''}`} onClick={onClick}>
      <span className="af-nav__icon"><Icon name={stage.icon} size={17} /></span>
      <span className="af-nav__label">{stage.label}</span>
      {stage.n ? <span className={`af-nav__step ${state}`}>{state === 'done' ? <Icon name="check" size={11} strokeWidth={2.6} /> : stage.n}</span> : null}
    </button>
  );
}

function Sidebar() {
  const s = window.useStore();
  const pipeState = (id) => {
    if (id === 'ingest') return s.enrichState === 'done' ? 'done' : (s.route === 'ingest' ? 'active' : 'idle');
    if (id === 'triage') return s.triaged ? 'done' : (s.route === 'triage' ? 'active' : 'idle');
    if (id === 'retrieve') return s.retrieveResults ? 'done' : (s.route === 'retrieve' ? 'active' : 'idle');
    return 'idle';
  };
  return (
    <aside className="af-sidebar">
      <div className="af-brand">
        <span className="af-brand__mark"><Icon name="search" size={15} strokeWidth={2} /></span>
        <span className="af-brand__name">Article Finder</span>
      </div>

      <div className="af-session">
        <div className="af-session__eyebrow">Research question</div>
        <div className="af-session__q">{s.topic}</div>
      </div>

      <nav className="af-navgroup">
        <div className="af-navgroup__label">Pipeline</div>
        {STAGES.filter((x) => x.group === 'pipeline').map((st) => (
          <NavItem key={st.id} stage={st} active={s.route === st.id} state={pipeState(st.id)} onClick={() => s.setRoute(st.id)} />
        ))}
      </nav>
      <nav className="af-navgroup">
        <div className="af-navgroup__label">Explore</div>
        {STAGES.filter((x) => x.group === 'explore').map((st) => (
          <NavItem key={st.id} stage={st} active={s.route === st.id} state="idle" onClick={() => s.setRoute(st.id)} />
        ))}
      </nav>

      <div className="af-sidebar__spacer" />
      <button className="af-reset" onClick={s.resetSession}><Icon name="rotate-cw" size={14} /> Reset session</button>
    </aside>
  );
}

function StageHost() {
  const s = window.useStore();
  switch (s.route) {
    case 'ingest': return <StageIngest />;
    case 'triage': return <StageTriage />;
    case 'retrieve': return <StageRetrieve />;
    case 'library': return <StageLibrary />;
    case 'voi': return <StageVoi />;
    case 'compare': return <StageScholar />;
    default: return <StageIngest />;
  }
}

function App() {
  const s = window.useStore();
  const [showDisplay, setShowDisplay] = useStateApp(false);
  const stage = STAGES.find((x) => x.id === s.route) || STAGES[0];

  return (
    <div className="af-app">
      <Sidebar />
      <div className="af-content">
        <header className="af-header">
          <div className="af-header__titles">
            {stage.n ? <span className="af-header__step af-data">Step {stage.n} / 3</span> : <span className="af-header__step af-data" style={{ color: 'var(--cool)' }}>Explore</span>}
            <h1 className="af-header__title">{stage.title}</h1>
            <p className="af-header__desc">{stage.desc}</p>
          </div>
          <div className="af-header__actions">
            <Button variant="ghost" size="sm" icon="book-open">Methodology</Button>
            <div style={{ position: 'relative' }}>
              <Button variant="secondary" size="sm" icon="sliders-horizontal" onClick={() => setShowDisplay((v) => !v)}>Display</Button>
              {showDisplay ? <DisplayPanel onClose={() => setShowDisplay(false)} /> : null}
            </div>
          </div>
        </header>
        <div className="af-scroll" key={s.route}>
          <StageHost />
        </div>
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<StoreProvider><App /></StoreProvider>);
