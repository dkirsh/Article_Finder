/* Article Finder — global session store (carries state across all stages) */
const { createContext, useContext, useState, useCallback, useEffect, useRef } = React;

const StoreContext = createContext(null);

const DEFAULT_TWEAKS = {
  theme: 'dark', // 'dark' | 'light'
  density: 'comfortable', // 'comfortable' | 'compact'
  accent: 'amber', // 'amber' | 'blue' | 'green'
  badgeStyle: 'pill', // 'pill' | 'dot' | 'text'
};

const ACCENTS = {
  amber: { accent: '#F29A4B', hover: '#FFAE62', press: '#D87E32', soft: 'rgba(242,154,75,0.12)', ring: 'rgba(242,154,75,0.30)', on: '#2b1400' },
  blue: { accent: '#57A8D9', hover: '#7DBEE4', press: '#3E8FC2', soft: 'rgba(87,168,217,0.12)', ring: 'rgba(87,168,217,0.32)', on: '#04121d' },
  green: { accent: '#4ADE80', hover: '#6BE89A', press: '#37BE68', soft: 'rgba(74,222,128,0.12)', ring: 'rgba(74,222,128,0.30)', on: '#04200f' },
};

function loadTweaks() {
  try {
    const raw = localStorage.getItem('af.tweaks');
    if (raw) return { ...DEFAULT_TWEAKS, ...JSON.parse(raw) };
  } catch (e) {}
  return { ...DEFAULT_TWEAKS };
}

function StoreProvider({ children }) {
  const [route, setRoute] = useState('ingest');
  const [rawItems, setRawItems] = useState(() => window.api.seedRawItems());

  const [enriched, setEnriched] = useState(null);
  const [enrichState, setEnrichState] = useState('idle'); // idle|loading|done

  const [triaged, setTriaged] = useState(null);
  const [triageState, setTriageState] = useState('idle');

  const [selectedIds, setSelectedIds] = useState([]);

  const [retrieveResults, setRetrieveResults] = useState(null);
  const [retrieveState, setRetrieveState] = useState('idle');
  const [retrieveProgress, setRetrieveProgress] = useState({}); // id -> queued|working|done

  const [tweaks, setTweaks] = useState(loadTweaks);

  // ---- tweak persistence + application ----
  useEffect(() => {
    try { localStorage.setItem('af.tweaks', JSON.stringify(tweaks)); } catch (e) {}
    const root = document.documentElement;
    root.classList.toggle('light', tweaks.theme === 'light');
    const a = ACCENTS[tweaks.accent] || ACCENTS.amber;
    root.style.setProperty('--accent', a.accent);
    root.style.setProperty('--accent-hover', a.hover);
    root.style.setProperty('--accent-press', a.press);
    root.style.setProperty('--accent-soft', a.soft);
    root.style.setProperty('--accent-ring', a.ring);
    root.style.setProperty('--accent-on', a.on);
    root.setAttribute('data-density', tweaks.density);
    root.setAttribute('data-badge', tweaks.badgeStyle);
  }, [tweaks]);

  const setTweak = useCallback((k, v) => setTweaks((t) => ({ ...t, [k]: v })), []);

  // ---- actions ----
  const addRawItems = useCallback((items) => {
    setRawItems((cur) => [...cur, ...items]);
  }, []);
  const removeRawItem = useCallback((id) => {
    setRawItems((cur) => cur.filter((x) => x.id !== id));
  }, []);

  const runEnrich = useCallback(async () => {
    setEnrichState('loading');
    setEnriched(null);
    const res = await window.api.enrich(rawItems);
    setEnriched(res);
    setEnrichState('done');
    // a new enrich invalidates downstream stages
    setTriaged(null);
    setTriageState('idle');
    setRetrieveResults(null);
    setRetrieveState('idle');
    setRetrieveProgress({});
    setSelectedIds([]);
  }, [rawItems]);

  const runTriage = useCallback(async () => {
    if (!enriched) return;
    setTriageState('loading');
    const ids = enriched.map((a) => a.id);
    const res = await window.api.triage(ids);
    setTriaged(res);
    setTriageState('done');
    setSelectedIds(res.filter((a) => a.triage.decision === 'ACCEPT').map((a) => a.id));
  }, [enriched]);

  const toggleSelect = useCallback((id) => {
    setSelectedIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }, []);
  const selectAllAccept = useCallback(() => {
    if (!triaged) return;
    setSelectedIds(triaged.filter((a) => a.triage.decision === 'ACCEPT').map((a) => a.id));
  }, [triaged]);
  const setSelection = useCallback((ids) => setSelectedIds(ids), []);
  const clearSelect = useCallback(() => setSelectedIds([]), []);

  const runRetrieve = useCallback(async () => {
    if (!selectedIds.length) return;
    setRetrieveState('loading');
    setRetrieveResults(null);
    // stage progress per item
    const init = {};
    selectedIds.forEach((id) => (init[id] = 'queued'));
    setRetrieveProgress(init);
    const results = await window.api.retrieve(selectedIds);
    // animate sequential resolution
    for (let i = 0; i < selectedIds.length; i++) {
      const id = selectedIds[i];
      setRetrieveProgress((p) => ({ ...p, [id]: 'working' }));
      await new Promise((r) => setTimeout(r, 360 + Math.random() * 320));
      setRetrieveProgress((p) => ({ ...p, [id]: 'done' }));
    }
    setRetrieveResults(results);
    setRetrieveState('done');
  }, [selectedIds]);

  const resetSession = useCallback(() => {
    setRawItems(window.api.seedRawItems());
    setEnriched(null); setEnrichState('idle');
    setTriaged(null); setTriageState('idle');
    setSelectedIds([]);
    setRetrieveResults(null); setRetrieveState('idle'); setRetrieveProgress({});
    setRoute('ingest');
  }, []);

  const value = {
    route, setRoute,
    topic: window.RESEARCH_QUESTION,
    rawItems, addRawItems, removeRawItem, setRawItems,
    enriched, enrichState, runEnrich,
    triaged, triageState, runTriage,
    selectedIds, toggleSelect, selectAllAccept, setSelection, clearSelect,
    retrieveResults, retrieveState, retrieveProgress, runRetrieve,
    tweaks, setTweak, resetSession,
  };
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

function useStore() {
  return useContext(StoreContext);
}

Object.assign(window, { StoreProvider, useStore, ACCENTS });
