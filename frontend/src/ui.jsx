/* Article Finder — UI primitives + canonical status maps */
const { useState: useStateUI, useRef: useRefUI } = React;

// ---------------------------------------------------------------------------
// Canonical maps — the single place triage + retrieval semantics get colors.
// ---------------------------------------------------------------------------
const TRIAGE = {
  ACCEPT:          { label: 'Accept',     color: 'var(--success)', soft: 'var(--success-soft)', icon: 'check-circle' },
  EDGE_CASE:       { label: 'Edge case',  color: 'var(--warn)',    soft: 'var(--warn-soft)',    icon: 'help-circle' },
  REJECT:          { label: 'Reject',     color: 'var(--danger)',  soft: 'var(--danger-soft)',  icon: 'x-circle' },
  NEEDS_MORE_INFO: { label: 'Needs info', color: 'var(--cool)',    soft: 'var(--cool-soft)',    icon: 'file-question' },
  PENDING:         { label: 'Pending',    color: 'var(--fg-3)',    soft: 'rgba(255,255,255,0.05)', icon: 'loader' },
};

const RETRIEVAL = {
  oa_retrieved:      { label: 'OA retrieved',      short: 'OA',       color: 'var(--success)', soft: 'var(--success-soft)', icon: 'unlock',  desc: 'Open-access PDF downloaded.' },
  browser_retrieved: { label: 'Browser retrieved', short: 'Browser',  color: 'var(--cool)',    soft: 'var(--cool-soft)',    icon: 'globe',   desc: 'Publisher-blocked OA, fetched via assisted browser.' },
  paywalled:         { label: 'Paywalled',         short: 'Paywall',  color: 'var(--fg-3)',    soft: 'rgba(255,255,255,0.05)', icon: 'lock', desc: 'Metadata only — no PDF (paywalled).' },
  oa_blocked:        { label: 'OA blocked',        short: 'Blocked',  color: 'var(--warn)',    soft: 'var(--warn-soft)',    icon: 'shield',  desc: 'Open access but publisher-blocked; needs browser-assist.' },
  not_attempted:     { label: 'Not attempted',     short: 'Idle',     color: 'var(--fg-4)',    soft: 'rgba(255,255,255,0.04)', icon: 'minus', desc: 'Retrieval has not been attempted yet.' },
};

const ARTICLE_TYPE_LABELS = {
  empirical_research: 'Empirical',
  review: 'Review',
  theoretical: 'Theoretical',
  meta_analysis: 'Meta-analysis',
  book_chapter: 'Book chapter',
  '': '—',
};

const INPUT_KIND_LABELS = {
  doi: 'DOI', title: 'Title', citation: 'Citation',
  abstract: 'Abstract', question: 'Question', pdf: 'PDF',
};

// ---------------------------------------------------------------------------
// Badge — respects the badgeStyle tweak (pill / dot / text)
// ---------------------------------------------------------------------------
function Badge({ color, soft, icon, label, title }) {
  const style = (window.useStore && window.useStore().tweaks.badgeStyle) || 'pill';
  if (style === 'text') {
    return (
      <span className="af-badge af-badge--text" style={{ color }} title={title}>
        {label}
      </span>
    );
  }
  if (style === 'dot') {
    return (
      <span className="af-badge af-badge--dot" title={title}>
        <span className="af-dot" style={{ background: color }} />
        <span style={{ color: 'var(--fg-2)' }}>{label}</span>
      </span>
    );
  }
  return (
    <span className="af-badge af-badge--pill" style={{ color, background: soft, borderColor: 'transparent' }} title={title}>
      {icon ? <Icon name={icon} size={12} /> : null}
      {label}
    </span>
  );
}

function TriageBadge({ decision }) {
  const t = TRIAGE[decision] || TRIAGE.PENDING;
  return <Badge color={t.color} soft={t.soft} icon={t.icon} label={t.label} />;
}

function RetrievalBadge({ status }) {
  const r = RETRIEVAL[status] || RETRIEVAL.not_attempted;
  return <Badge color={r.color} soft={r.soft} icon={r.icon} label={r.label} title={r.desc} />;
}

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------
function Button({ variant = 'secondary', size = 'md', icon, iconRight, children, disabled, onClick, style, title }) {
  return (
    <button
      className={`af-btn af-btn--${variant} af-btn--${size}`}
      disabled={disabled}
      onClick={onClick}
      style={style}
      title={title}
    >
      {icon ? <Icon name={icon} size={size === 'sm' ? 13 : 15} /> : null}
      {children ? <span>{children}</span> : null}
      {iconRight ? <Icon name={iconRight} size={size === 'sm' ? 13 : 15} /> : null}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Checkbox
// ---------------------------------------------------------------------------
function Check({ checked, indeterminate, onChange, ariaLabel }) {
  return (
    <button
      role="checkbox"
      aria-checked={checked}
      aria-label={ariaLabel || 'Select'}
      className={`af-check ${checked ? 'is-on' : ''} ${indeterminate ? 'is-mixed' : ''}`}
      onClick={(e) => { e.stopPropagation(); onChange && onChange(!checked); }}
    >
      {checked ? <Icon name="check" size={12} strokeWidth={2.4} /> : indeterminate ? <Icon name="minus" size={12} strokeWidth={2.4} /> : null}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Tooltip (hover / focus)
// ---------------------------------------------------------------------------
function Tip({ text, children, side = 'top' }) {
  return (
    <span className={`af-tip af-tip--${side}`} tabIndex={0}>
      {children}
      <span className="af-tip__pop" role="tooltip">{text}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Confidence bar (0..1)
// ---------------------------------------------------------------------------
function ConfBar({ value, color = 'var(--fg-2)', width = 44 }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <span className="af-confbar" style={{ width }} title={`${pct}% confidence`}>
      <i style={{ width: pct + '%', background: color }} />
    </span>
  );
}

// ---------------------------------------------------------------------------
// VOI score chip — mono, climate-tinted
// ---------------------------------------------------------------------------
function climateForScore(v) {
  // higher VOI = warmer (more worth knowing)
  const stops = ['#57A8D9', '#9FD0E8', '#F1E9D2', '#F5C77E', '#F29A4B', '#E66A2C'];
  return stops[Math.min(stops.length - 1, Math.max(0, Math.floor((v || 0) * stops.length)))];
}
function VoiChip({ value, size = 'md' }) {
  if (value == null) return <span className="af-data" style={{ color: 'var(--fg-4)' }}>—</span>;
  const c = climateForScore(value);
  return (
    <span className={`af-voi af-voi--${size}`} title={`Value-of-information score: ${value.toFixed(2)}`}>
      <span className="af-voi__bead" style={{ background: c }} />
      <span className="af-data">{value.toFixed(2)}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Empty / loading states
// ---------------------------------------------------------------------------
function EmptyState({ icon = 'inbox', title, children, action }) {
  return (
    <div className="af-empty">
      <div className="af-empty__icon"><Icon name={icon} size={26} /></div>
      <div className="af-empty__title">{title}</div>
      {children ? <div className="af-empty__body">{children}</div> : null}
      {action ? <div style={{ marginTop: 16 }}>{action}</div> : null}
    </div>
  );
}

function Spinner({ size = 16 }) {
  return <span className="af-spin" style={{ width: size, height: size }}><Icon name="loader" size={size} /></span>;
}

// ---------------------------------------------------------------------------
// Misc helpers
// ---------------------------------------------------------------------------
function fmtBytes(b) {
  if (b == null) return '—';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(0) + ' KB';
  return (b / 1048576).toFixed(1) + ' MB';
}
function abstractSnippet(a, n = 120) {
  if (!a) return null;
  return a.length > n ? a.slice(0, n).trim() + '…' : a;
}
function SciTitle({ children }) {
  return <span className="af-sci">{children}</span>;
}

Object.assign(window, {
  TRIAGE, RETRIEVAL, ARTICLE_TYPE_LABELS, INPUT_KIND_LABELS,
  Badge, TriageBadge, RetrievalBadge, Button, Check, Tip, ConfBar,
  VoiChip, climateForScore, EmptyState, Spinner,
  fmtBytes, abstractSnippet, SciTitle,
});
