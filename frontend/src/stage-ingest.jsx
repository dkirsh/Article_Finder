/* Article Finder — Stage 1: INGEST */
const { useState: useStateIngest, useRef: useRefIngest } = React;

function guessKind(text) {
  const t = text.trim();
  if (/^uploaded:/i.test(t) || /\.pdf\b/i.test(t.slice(0, 40))) return 'pdf';
  if (/^10\.\d{4,}\//.test(t)) return 'doi';
  if (t.endsWith('?')) return 'question';
  if (/\(\d{4}\)/.test(t) && /[A-Z][a-z]+,\s*[A-Z]\./.test(t)) return 'citation';
  if (t.length > 240) return 'abstract';
  return 'title';
}

function RawItemCard({ item, onRemove }) {
  const k = window.INPUT_KIND_LABELS[item.kind] || 'Title';
  return (
    <div className="af-raw">
      <span className={`af-kind af-kind--${item.kind}`}>{k}</span>
      <span className="af-raw__text">{item.text}</span>
      <button className="af-raw__rm" title="Remove" onClick={() => onRemove(item.id)}>
        <Icon name="x" size={14} />
      </button>
    </div>
  );
}

function EnrichedCard({ a }) {
  const needsInfo = a.triage.decision === 'NEEDS_MORE_INFO';
  return (
    <div className={`af-enr ${needsInfo ? 'af-enr--warn' : ''}`}>
      <div className="af-enr__top">
        <span className={`af-kind af-kind--${a.inputKind}`}>{window.INPUT_KIND_LABELS[a.inputKind]}</span>
        <Icon name="arrow-right" size={13} style={{ color: 'var(--fg-4)' }} />
        <span className="af-enr__doi af-data">{a.doi || 'no DOI'}</span>
        <span style={{ flex: 1 }} />
        {needsInfo ? <TriageBadge decision="NEEDS_MORE_INFO" /> : (
          <span className="af-enr__ok"><Icon name="check" size={13} /> resolved</span>
        )}
      </div>
      <div className="af-enr__title">{a.title}</div>
      <div className="af-enr__meta af-data">
        {a.authors.join(', ')}{a.year ? ` · ${a.year}` : ''}
      </div>
      {a.abstract
        ? <div className="af-enr__abs">{window.abstractSnippet(a.abstract, 180)}</div>
        : <div className="af-enr__abs af-enr__abs--none"><Icon name="alert-circle" size={13} /> No abstract resolved — flagged for review.</div>}
    </div>
  );
}

function StageIngest() {
  const s = window.useStore();
  const [paste, setPaste] = useStateIngest('');
  const [drag, setDrag] = useStateIngest(false);
  const fileRef = useRefIngest(null);

  const addPaste = () => {
    const blocks = paste.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
    if (!blocks.length) return;
    const items = blocks.map((text, i) => ({ id: 'u' + Date.now() + '_' + i, kind: guessKind(text), text }));
    s.addRawItems(items);
    setPaste('');
  };

  const onFiles = (files) => {
    // Files are illustrative in this mock — they expand into ingest items.
    const arr = Array.from(files || []);
    if (!arr.length) return;
    const items = arr.map((f, i) => ({
      id: 'f' + Date.now() + '_' + i,
      kind: f.name.toLowerCase().endsWith('.zip') ? 'pdf' : guessKind(f.name),
      text: 'uploaded: ' + f.name,
    }));
    s.addRawItems(items);
  };

  const loading = s.enrichState === 'loading';
  const done = s.enrichState === 'done' && s.enriched;

  return (
    <div className="af-stage">
      <div className="af-stage__main">
        {/* Intake */}
        <section className="af-card af-intake">
          <div
            className={`af-drop ${drag ? 'is-drag' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); onFiles(e.dataTransfer.files); }}
            onClick={() => fileRef.current && fileRef.current.click()}
          >
            <input ref={fileRef} type="file" multiple style={{ display: 'none' }} onChange={(e) => onFiles(e.target.files)} />
            <div className="af-drop__icon"><Icon name="upload" size={22} /></div>
            <div className="af-drop__t">Drop files, a <span className="af-data">.zip</span>, or click to browse</div>
            <div className="af-drop__s">Each item may be a citation, research question, abstract, DOI, title, or PDF.</div>
          </div>
          <div className="af-paste">
            <textarea
              value={paste}
              onChange={(e) => setPaste(e.target.value)}
              placeholder={'Or paste here — one item per block, separated by a blank line.\n\ne.g.  10.1086/519146\n      Does a high ceiling make people think more freely?'}
              rows={4}
            />
            <div className="af-paste__foot">
              <span className="af-hint">{guessHint(paste)}</span>
              <Button variant="secondary" size="sm" icon="plus" onClick={addPaste} disabled={!paste.trim()}>Add to queue</Button>
            </div>
          </div>
        </section>

        {/* Queue */}
        <section className="af-card">
          <div className="af-card__head">
            <h3 className="af-card__title">Ingest queue</h3>
            <span className="af-count af-data">{s.rawItems.length} items</span>
          </div>
          <div className="af-rawlist">
            {s.rawItems.length === 0
              ? <EmptyState icon="inbox" title="Nothing queued yet">Drop files or paste inputs above to begin.</EmptyState>
              : s.rawItems.map((it) => <RawItemCard key={it.id} item={it} onRemove={s.removeRawItem} />)}
          </div>
        </section>

        {/* Enriched results */}
        {(loading || done) && (
          <section className="af-card">
            <div className="af-card__head">
              <h3 className="af-card__title">Resolved articles</h3>
              {done ? <span className="af-count af-data">{s.enriched.filter((a) => a.abstract).length} with abstracts · {s.enriched.filter((a) => !a.abstract).length} flagged</span> : null}
            </div>
            {loading ? (
              <div className="af-resolving">
                {s.rawItems.map((it, i) => (
                  <div className="af-skel" key={it.id} style={{ animationDelay: (i * 70) + 'ms' }}>
                    <div className="af-skel__row" style={{ width: '40%' }} />
                    <div className="af-skel__row" style={{ width: '85%' }} />
                    <div className="af-skel__row" style={{ width: '60%' }} />
                  </div>
                ))}
                <div className="af-resolving__label"><Spinner /> Resolving {s.rawItems.length} inputs to APA · abstract · DOI…</div>
              </div>
            ) : (
              <div className="af-enrlist">
                {s.enriched.map((a) => <EnrichedCard key={a.id} a={a} />)}
              </div>
            )}
          </section>
        )}
      </div>

      {/* Action rail */}
      <div className="af-actionbar">
        <div className="af-actionbar__info">
          {done
            ? <span><b className="af-data">{s.enriched.length}</b> resolved · <b className="af-data">{s.enriched.filter((a) => !a.abstract).length}</b> need more info</span>
            : <span>Resolve every input to a structured article before triage.</span>}
        </div>
        <div className="af-actionbar__btns">
          {done && (
            <Button variant="primary" size="md" iconRight="arrow-right" onClick={() => s.setRoute('triage')}>
              Continue to Triage
            </Button>
          )}
          <Button variant={done ? 'secondary' : 'primary'} size="md" icon={loading ? null : 'sparkles'} disabled={loading || !s.rawItems.length} onClick={s.runEnrich}>
            {loading ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><Spinner size={14} /> Enriching…</span> : done ? 'Re-enrich' : `Enrich ${s.rawItems.length} items`}
          </Button>
        </div>
      </div>
    </div>
  );
}

function guessHint(text) {
  const t = text.trim();
  if (!t) return 'Tip: paste a DOI, a full citation, a title, an abstract, or a plain research question.';
  const blocks = t.split(/\n\s*\n/).filter(Boolean);
  const k = window.INPUT_KIND_LABELS[guessKind(blocks[blocks.length - 1])];
  return `${blocks.length} block${blocks.length > 1 ? 's' : ''} · last looks like a ${k}`;
}

Object.assign(window, { StageIngest });
