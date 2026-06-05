/* Article Finder — Stage 5: VOI (recommended areas to search) */
const { useState: useStateVoi, useEffect: useEffectVoi } = React;

const VOI_FACTOR_LABELS = {
  local_confidence_gap: 'Confidence gap',
  evidence_sparsity: 'Evidence sparsity',
  network_centrality: 'Network centrality',
  downstream_impact: 'Downstream impact',
  contestation: 'Contestation',
  feasibility: 'Feasibility',
  structural_voi: 'Structural VOI',
  epistemic_voi: 'Epistemic VOI',
};

const GAP_TYPE_LABELS = {
  mechanism_untested: 'Mechanism untested',
  replication_missing: 'Replication missing',
  quantification_missing: 'Quantification missing',
  confound_unresolved: 'Confound unresolved',
};

function Factor({ name, value }) {
  if (value == null) {
    return (
      <div className="af-factor af-factor--null">
        <span className="af-factor__l">{VOI_FACTOR_LABELS[name]}</span>
        <Tip text="Not computed for this gap — the model declined to estimate this factor." side="top">
          <span className="af-factor__dash af-data">—</span>
        </Tip>
      </div>
    );
  }
  return (
    <div className="af-factor">
      <span className="af-factor__l">{VOI_FACTOR_LABELS[name]}</span>
      <span className="af-factor__bar"><i style={{ width: Math.round(value * 100) + '%', background: window.climateForScore(value) }} /></span>
      <span className="af-factor__v af-data">{value.toFixed(2)}</span>
    </div>
  );
}

function CopyBtn({ text }) {
  const [done, setDone] = useStateVoi(false);
  return (
    <button className="af-copy" onClick={() => {
      try { navigator.clipboard.writeText(text); } catch (e) {}
      setDone(true); setTimeout(() => setDone(false), 1400);
    }} title="Copy query">
      <Icon name={done ? 'check' : 'copy'} size={13} /> {done ? 'Copied' : 'Copy'}
    </button>
  );
}

function GapCard({ gap, rank }) {
  const s = window.useStore();
  const order = ['local_confidence_gap', 'evidence_sparsity', 'network_centrality', 'downstream_impact', 'contestation', 'feasibility', 'structural_voi', 'epistemic_voi'];
  const computed = order.filter((k) => gap.voiBreakdown[k] != null).length;
  return (
    <article className="af-gap">
      <div className="af-gap__rail" style={{ background: window.climateForScore(gap.voiScore) }} />
      <div className="af-gap__head">
        <div className="af-gap__rank af-data">#{rank}</div>
        <div className="af-gap__heading">
          <div className="af-gap__mech">{gap.mechanismName}</div>
          <div className="af-gap__sub af-data">{gap.framework} · {GAP_TYPE_LABELS[gap.gapType] || gap.gapType}</div>
        </div>
        <div className="af-gap__score">
          <div className="af-gap__score-num af-data" style={{ color: window.climateForScore(gap.voiScore) }}>{gap.voiScore.toFixed(2)}</div>
          <div className="af-gap__score-l">VOI</div>
        </div>
      </div>

      <p className="af-gap__missing">{gap.missingEvidence}</p>

      <div className="af-gap__breakdown">
        <div className="af-section-eyebrow">VOI breakdown <span style={{ color: 'var(--fg-4)', textTransform: 'none', letterSpacing: 0 }}>· {computed}/8 computed</span></div>
        <div className="af-factors">
          {order.map((k) => <Factor key={k} name={k} value={gap.voiBreakdown[k]} />)}
        </div>
      </div>

      <div className="af-gap__queries">
        <div className="af-query">
          <div className="af-query__head"><span className="af-query__tag"><Icon name="sparkles" size={12} /> AI citation search</span><CopyBtn text={gap.suggestedQueries.aiCitation} /></div>
          <div className="af-query__body">{gap.suggestedQueries.aiCitation}</div>
        </div>
        <div className="af-query">
          <div className="af-query__head"><span className="af-query__tag"><Icon name="hash" size={12} /> Boolean</span><CopyBtn text={gap.suggestedQueries.boolean} /></div>
          <div className="af-query__body af-data af-query__body--mono">{gap.suggestedQueries.boolean}</div>
        </div>
      </div>

      <div className="af-gap__foot">
        <div className="af-gap__conf af-data">model confidence <b style={{ color: 'var(--fg-1)' }}>{Math.round(gap.confidence * 100)}%</b></div>
        <Button variant="primary" size="sm" icon="search" onClick={() => s.setRoute('compare')}>Search this</Button>
      </div>
    </article>
  );
}

function StageVoi() {
  const s = window.useStore();
  const [gaps, setGaps] = useStateVoi(null);
  useEffectVoi(() => { window.api.recommendations().then(setGaps); }, []);

  return (
    <div className="af-stage">
      <div className="af-stage__main af-stage__main--wide">
        <div className="af-voi-intro">
          <p className="af-voi-intro__lead">Ranked by <span className="af-serif">value of information</span> — where new evidence would most reduce uncertainty about the question. Some factors are left uncomputed and shown as <span className="af-data">—</span>; that is deliberate, not missing.</p>
        </div>
        {gaps == null ? (
          <div className="af-resolving__label" style={{ padding: 28 }}><Spinner /> Ranking knowledge gaps by value of information…</div>
        ) : (
          <div className="af-gaplist">
            {gaps.map((g, i) => <GapCard key={g.templateId} gap={g} rank={i + 1} />)}
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { StageVoi });
