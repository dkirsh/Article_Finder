/* =============================================================================
   Article Finder — DATA ACCESS LAYER (single source of truth)
   -----------------------------------------------------------------------------
   ALL data access lives here. Components never hardcode data — they call api.*().
   To go from mock → real backend, replace each function body with the fetch()
   shown in its `// TODO:` comment. Nothing else in the app changes.

   ---------------------------------------------------------------------------
   TYPE CONTRACT (TypeScript — preserved verbatim from the spec; this file ships
   as .js for the self-contained artifact, but these are the authoritative types)
   ---------------------------------------------------------------------------
   type TriageDecision  = 'ACCEPT' | 'EDGE_CASE' | 'REJECT' | 'NEEDS_MORE_INFO';
   type RetrievalStatus = 'not_attempted' | 'oa_retrieved' | 'browser_retrieved'
                        | 'paywalled' | 'oa_blocked';

   interface Article {
     id: string;
     inputKind: 'doi'|'title'|'citation'|'abstract'|'question'|'pdf';
     rawInput: string;
     title: string; apaCitation: string; doi: string|null; abstract: string|null;
     year: number|null; authors: string[];
     topic: string; articleType: string;          // empirical_research|review|theoretical|...
     triage: { decision: TriageDecision; confidence: number; reason: string };
     voiScore: number;
     retrieval: { status: RetrievalStatus; discoveredVia?: string; pdfUrl?: string;
                  bytes?: number; sha256?: string };
     selected: boolean;
   }
   interface VoiBreakdown {     // null fields are intentionally NOT computed — render "—"
     local_confidence_gap: number; evidence_sparsity: number; network_centrality: number;
     downstream_impact: number|null; contestation: number|null; feasibility: number|null;
     structural_voi: number|null; epistemic_voi: number|null;
   }
   interface GapRecommendation {
     templateId: string; mechanismName: string; framework: string; confidence: number;
     gapType: string; voiScore: number; voiBreakdown: VoiBreakdown; missingEvidence: string;
     suggestedQueries: { aiCitation: string; boolean: string };
   }
   ============================================================================= */

(function () {
  'use strict';

  // ---- tiny helpers -------------------------------------------------------
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const clone = (x) => JSON.parse(JSON.stringify(x));
  const sha = (s) =>
    'sha256:' +
    Array.from(s)
      .reduce((a, c) => ((a << 5) - a + c.charCodeAt(0)) | 0, 0x9e3779b1 >>> 0)
      .toString(16)
      .replace('-', '')
      .padStart(8, '0')
      .repeat(8)
      .slice(0, 64);

  // =========================================================================
  //  SEED MOCK DATA — research session for the question below.
  //  8 articles spanning every triage decision and every retrieval status.
  // =========================================================================
  const RESEARCH_QUESTION = 'Does the height of a room affect creativity?';

  /** @type {Array<Object>} canonical fully-resolved articles */
  const SEED = [
    {
      id: 'a7',
      inputKind: 'question',
      rawInput: 'Do high ceilings actually boost divergent thinking, or is it just a feeling?',
      title:
        'Stimulating Spaces: The Effect of Room Volume on Divergent Thinking and Idea Generation',
      authors: ['Aisha Rahman', 'Per Solberg'],
      year: 2023,
      doi: '10.1037/aca0000512',
      apaCitation:
        'Rahman, A., & Solberg, P. (2023). Stimulating spaces: The effect of room volume on divergent thinking and idea generation. Psychology of Aesthetics, Creativity, and the Arts, 17(3), 411–426. https://doi.org/10.1037/aca0000512',
      abstract:
        'Across three lab experiments (N = 412), participants completed alternate-uses and remote-associates tasks in rooms manipulated to feel high- or low-ceilinged. Higher perceived volume reliably increased ideational fluency and originality on divergent-thinking measures, with no effect on convergent tasks. Effects were partially mediated by self-reported psychological freedom.',
      topic: 'Ceiling height & creativity',
      articleType: 'empirical_research',
      triage: {
        decision: 'ACCEPT',
        confidence: 0.96,
        reason:
          'Direct experimental test of room volume on divergent-thinking creativity outcomes. Highest relevance to the question.',
      },
      voiScore: 0.91,
      retrieval: {
        status: 'oa_retrieved',
        discoveredVia: 'openalex_oa',
        pdfUrl: 'store://pdf/rahman-solberg-2023.pdf',
        bytes: 2_945_118,
        sha256: sha('rahman2023'),
      },
    },
    {
      id: 'a1',
      inputKind: 'citation',
      rawInput:
        'Meyers-Levy, J., & Zhu, R. (2007). The influence of ceiling height: The effect of priming on the type of processing that people use. J. Consumer Research, 34(2), 174-186.',
      title:
        'The Influence of Ceiling Height: The Effect of Priming on the Type of Processing That People Use',
      authors: ['Joan Meyers-Levy', 'Rui (Juliet) Zhu'],
      year: 2007,
      doi: '10.1086/519146',
      apaCitation:
        'Meyers-Levy, J., & Zhu, R. (2007). The influence of ceiling height: The effect of priming on the type of processing that people use. Journal of Consumer Research, 34(2), 174–186. https://doi.org/10.1086/519146',
      abstract:
        'This research demonstrates that variations in ceiling height can prime concepts that, in turn, affect how consumers process information. Higher ceilings activate a relational, freedom-oriented mindset that favors abstract, integrative processing, whereas lower ceilings activate a confinement mindset favoring item-specific, detail-oriented processing. The seminal "Cathedral Effect" source.',
      topic: 'Ceiling height & cognition',
      articleType: 'empirical_research',
      triage: {
        decision: 'ACCEPT',
        confidence: 0.94,
        reason:
          'Seminal source establishing the ceiling-height → processing-style link. Foundational, but outcome is processing style rather than creativity per se.',
      },
      voiScore: 0.86,
      retrieval: {
        status: 'paywalled',
        discoveredVia: 'crossref',
      },
    },
    {
      id: 'a2',
      inputKind: 'title',
      rawInput: 'Senses of place: architectural design for the multisensory mind',
      title: 'Senses of Place: Architectural Design for the Multisensory Mind',
      authors: ['Charles Spence'],
      year: 2020,
      doi: '10.1186/s41235-020-00243-4',
      apaCitation:
        'Spence, C. (2020). Senses of place: Architectural design for the multisensory mind. Cognitive Research: Principles and Implications, 5(46). https://doi.org/10.1186/s41235-020-00243-4',
      abstract:
        'A wide-ranging review of how the sensory attributes of the built environment — including ceiling height, lighting, color, and acoustics — shape human cognition, mood, and wellbeing. Synthesizes the cathedral-effect literature alongside biophilic and multisensory design findings, and flags where the evidence base is thin.',
      topic: 'Multisensory architecture',
      articleType: 'review',
      triage: {
        decision: 'ACCEPT',
        confidence: 0.88,
        reason:
          'Peer-reviewed review synthesizing environmental-design effects on cognition, with explicit treatment of ceiling height. Strong framing source.',
      },
      voiScore: 0.79,
      retrieval: {
        status: 'oa_retrieved',
        discoveredVia: 'unpaywall',
        pdfUrl: 'store://pdf/spence-2020.pdf',
        bytes: 2_184_320,
        sha256: sha('spence2020'),
      },
    },
    {
      id: 'a3',
      inputKind: 'doi',
      rawInput: '10.3390/s21041348',
      title:
        'Indoor Environmental Quality and Cognitive Performance in Open-Plan Workspaces: A Field Study',
      authors: ['Lia Bakkeren', 'Marco Fontana', 'Yuki Tanaka'],
      year: 2021,
      doi: '10.3390/s21041348',
      apaCitation:
        'Bakkeren, L., Fontana, M., & Tanaka, Y. (2021). Indoor environmental quality and cognitive performance in open-plan workspaces: A field study. Sensors, 21(4), 1348. https://doi.org/10.3390/s21041348',
      abstract:
        'A six-week field study instrumented twelve workspaces and linked spatial volume (ceiling height, floor area), CO₂, and illuminance to performance on standardized cognitive tasks. Larger perceived volume was associated with higher scores on creative-association tasks but not on vigilance tasks, after controlling for air quality.',
      topic: 'Indoor environmental quality',
      articleType: 'empirical_research',
      triage: {
        decision: 'ACCEPT',
        confidence: 0.81,
        reason:
          'Field measurement of spatial volume (incl. ceiling height) against cognitive throughput. Real-world evidence, modest sample.',
      },
      voiScore: 0.72,
      retrieval: {
        status: 'browser_retrieved',
        discoveredVia: 'browser_assist',
        pdfUrl: 'store://pdf/bakkeren-2021.pdf',
        bytes: 4_012_770,
        sha256: sha('bakkeren2021'),
      },
    },
    {
      id: 'a8',
      inputKind: 'pdf',
      rawInput: 'uploaded: ostroff_2018_construal.pdf',
      title:
        'Volumetric Affordances and Abstract Construal: A Theoretical Account of the Cathedral Effect',
      authors: ['Daniel Ostroff'],
      year: 2018,
      doi: '10.1525/collabra.118',
      apaCitation:
        'Ostroff, D. (2018). Volumetric affordances and abstract construal: A theoretical account of the cathedral effect. Collabra: Psychology, 4(1), 18. https://doi.org/10.1525/collabra.118',
      abstract:
        'A theoretical paper proposing that ceiling height influences cognition through construal-level shifts: expansive volumes afford psychological distance and therefore more abstract, high-level construal. Offers a formal mechanism but presents no new empirical data, calling for mediation tests.',
      topic: 'Construal-level theory',
      articleType: 'theoretical',
      triage: {
        decision: 'EDGE_CASE',
        confidence: 0.58,
        reason:
          'Proposes a plausible mechanism for ceiling-height effects but offers no empirical evidence. Useful for framing, not as evidence.',
      },
      voiScore: 0.55,
      retrieval: {
        status: 'browser_retrieved',
        discoveredVia: 'browser_assist',
        pdfUrl: 'store://pdf/ostroff-2018.pdf',
        bytes: 1_330_904,
        sha256: sha('ostroff2018'),
      },
    },
    {
      id: 'a4',
      inputKind: 'abstract',
      rawInput:
        'Pasted abstract: "Across two within-subjects studies we show that brief exposure to window views of vegetation restores positive affect and directed attention among office workers…"',
      title:
        'Window Views of Nature and Mood Restoration in the Workplace: A Within-Subjects Study',
      authors: ['Renata Oliveira', 'Tom Becker'],
      year: 2019,
      doi: '10.1016/j.jenvp.2019.05.004',
      apaCitation:
        'Oliveira, R., & Becker, T. (2019). Window views of nature and mood restoration in the workplace: A within-subjects study. Journal of Environmental Psychology, 64, 1–11. https://doi.org/10.1016/j.jenvp.2019.05.004',
      abstract:
        'Two within-subjects studies show that brief exposure to window views of vegetation restores positive affect and directed attention among office workers. The work concerns biophilic restoration and mood, not room geometry or creative output.',
      topic: 'Biophilic design & mood',
      articleType: 'empirical_research',
      triage: {
        decision: 'EDGE_CASE',
        confidence: 0.62,
        reason:
          'Environmental psychology of workspaces, but the outcome is mood/attention restoration via nature views — adjacent to, not on, the creativity question.',
      },
      voiScore: 0.41,
      retrieval: {
        status: 'oa_blocked',
        discoveredVia: 'openalex_oa',
      },
    },
    {
      id: 'a5',
      inputKind: 'title',
      rawInput: 'Attention-guided convolutional networks for indoor scene layout estimation',
      title:
        'Attention-Guided Convolutional Networks for Indoor Scene Layout Estimation',
      authors: ['Wei Chen', 'Priya Nair', 'Mateo Álvarez'],
      year: 2022,
      doi: '10.1109/CVPR52688.2022.00513',
      apaCitation:
        'Chen, W., Nair, P., & Álvarez, M. (2022). Attention-guided convolutional networks for indoor scene layout estimation. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (pp. 5108–5117). https://doi.org/10.1109/CVPR52688.2022.00513',
      abstract:
        'A deep-learning method that estimates the 3D layout of indoor scenes (walls, floor, ceiling planes) from a single RGB image using an attention-guided CNN. Concerns geometric reconstruction of rooms; no human participants and no cognitive or creativity outcome.',
      topic: 'Computer vision',
      articleType: 'empirical_research',
      triage: {
        decision: 'REJECT',
        confidence: 0.91,
        reason:
          'Computer-vision method for estimating room geometry. Matches on "room" keywords only; no human cognition or creativity outcome. Off-topic.',
      },
      voiScore: 0.08,
      retrieval: {
        status: 'not_attempted',
      },
    },
    {
      id: 'a6',
      inputKind: 'doi',
      rawInput: '10.4324/9781315561739-12',
      title: 'Spatial Cognition in the Built Environment (book chapter)',
      authors: ['H. Lindqvist'],
      year: 2016,
      doi: '10.4324/9781315561739-12',
      apaCitation:
        'Lindqvist, H. (2016). Spatial cognition in the built environment. In Handbook of Environmental Psychology (Ch. 12). Routledge. https://doi.org/10.4324/9781315561739-12',
      abstract: null,
      topic: '—',
      articleType: 'book_chapter',
      triage: {
        decision: 'NEEDS_MORE_INFO',
        confidence: 0.3,
        reason:
          'No abstract resolved from the DOI (book chapter). Relevance cannot be assessed without full text or a manual look.',
      },
      voiScore: 0.12,
      retrieval: {
        status: 'not_attempted',
      },
    },
  ];

  // ---- GAP / value-of-information recommendations -------------------------
  const RECOMMENDATIONS = [
    {
      templateId: 'gap-construal-mediation',
      mechanismName: 'Construal-level mediation',
      framework: 'Construal Level Theory',
      confidence: 0.71,
      gapType: 'mechanism_untested',
      voiScore: 0.88,
      voiBreakdown: {
        local_confidence_gap: 0.74,
        evidence_sparsity: 0.81,
        network_centrality: 0.66,
        downstream_impact: 0.59,
        contestation: null,
        feasibility: 0.7,
        structural_voi: null,
        epistemic_voi: 0.69,
      },
      missingEvidence:
        'The ceiling-height → creativity link is repeatedly attributed to a shift in construal level, but no study measures construal as a mediator. The mechanism is assumed, not tested.',
      suggestedQueries: {
        aiCitation:
          'Experiments measuring construal level as a mediator between ceiling height (or room volume) and divergent-thinking performance',
        boolean:
          '("ceiling height" OR "room volume") AND ("construal level" OR "psychological distance") AND (creativity OR "divergent thinking") AND mediat*',
      },
    },
    {
      templateId: 'gap-effect-replication',
      mechanismName: 'Cross-cultural replication',
      framework: 'Generalizability',
      confidence: 0.64,
      gapType: 'replication_missing',
      voiScore: 0.73,
      voiBreakdown: {
        local_confidence_gap: 0.6,
        evidence_sparsity: 0.7,
        network_centrality: 0.42,
        downstream_impact: null,
        contestation: 0.55,
        feasibility: 0.8,
        structural_voi: 0.48,
        epistemic_voi: null,
      },
      missingEvidence:
        'Cathedral-effect evidence is concentrated in North-American university samples in lab rooms. No registered replication in non-Western populations or real working environments.',
      suggestedQueries: {
        aiCitation:
          'Replications of the cathedral effect (ceiling height on cognition) in non-Western or field samples',
        boolean:
          '("cathedral effect" OR "ceiling height") AND (replicat* OR "cross-cultural" OR field) AND (cognition OR creativity)',
      },
    },
    {
      templateId: 'gap-dose-response',
      mechanismName: 'Dose–response of ceiling height',
      framework: 'Quantitative mapping',
      confidence: 0.58,
      gapType: 'quantification_missing',
      voiScore: 0.69,
      voiBreakdown: {
        local_confidence_gap: 0.66,
        evidence_sparsity: 0.62,
        network_centrality: 0.5,
        downstream_impact: 0.61,
        contestation: null,
        feasibility: null,
        structural_voi: 0.4,
        epistemic_voi: 0.52,
      },
      missingEvidence:
        'Studies dichotomize ceilings as "high" vs "low". The functional form is unknown — is 3.0 m meaningfully better than 2.7 m, and where do returns plateau?',
      suggestedQueries: {
        aiCitation:
          'Parametric or dose–response studies varying ceiling height across more than two levels with a creativity outcome',
        boolean:
          '("ceiling height" OR "room height") AND ("dose-response" OR parametric OR gradient) AND (creativity OR cognition)',
      },
    },
    {
      templateId: 'gap-confound-affect',
      mechanismName: 'Affect vs cognition confound',
      framework: 'Discriminant validity',
      confidence: 0.6,
      gapType: 'confound_unresolved',
      voiScore: 0.64,
      voiBreakdown: {
        local_confidence_gap: 0.7,
        evidence_sparsity: 0.5,
        network_centrality: 0.38,
        downstream_impact: null,
        contestation: 0.72,
        feasibility: 0.66,
        structural_voi: null,
        epistemic_voi: 0.6,
      },
      missingEvidence:
        'It is unresolved whether high ceilings improve creative output or merely reduce felt constraint and negative affect. The two explanations are rarely disentangled in a single design.',
      suggestedQueries: {
        aiCitation:
          'Studies dissociating mood/felt-constraint from creative performance under varied ceiling height',
        boolean:
          '("ceiling height" OR "spatial volume") AND (affect OR mood OR "felt constraint") AND (creativity OR "idea generation") AND (mediat* OR confound)',
      },
    },
  ];

  // ---- Google-Scholar-AI comparison (external, for the Compare view) -------
  const SCHOLAR_RESULTS = [
    {
      title:
        'The influence of ceiling height: The effect of priming on the type of processing people use',
      venue: 'Journal of Consumer Research · 2007',
      snippet:
        'Higher vs lower ceilings prime relational vs item-specific processing…',
      citedBy: 1487,
      hasPdf: false,
      flags: ['paywalled'],
      inOurSet: true,
    },
    {
      title: 'Stimulating spaces: room volume and divergent thinking',
      venue: 'Psychol. of Aesthetics, Creativity, and the Arts · 2023',
      snippet:
        'Three experiments; higher perceived volume increased ideational fluency…',
      citedBy: 38,
      hasPdf: true,
      flags: ['open access'],
      inOurSet: true,
    },
    {
      title: '10 Office Design Tips That Will Skyrocket Team Creativity 🚀',
      venue: 'medium.com/@workspaceguru · 2024',
      snippet:
        'Number 7 will surprise you. High ceilings = big ideas, according to science…',
      citedBy: 0,
      hasPdf: false,
      flags: ['blog', 'not peer-reviewed'],
      inOurSet: false,
    },
    {
      title:
        'Indoor environmental quality and cognitive performance in open-plan workspaces',
      venue: 'Sensors (MDPI) · 2021',
      snippet:
        'Field study linking spatial volume and CO₂ to cognitive task performance…',
      citedBy: 73,
      hasPdf: true,
      flags: ['publisher-blocked OA'],
      inOurSet: true,
    },
    {
      title:
        'A Study on Room Height Preferences in Residential Real Estate Listings',
      venue: 'Int. J. of Housing Markets · 2020',
      snippet:
        'Survey of buyer preferences for ceiling height; price elasticity analysis…',
      citedBy: 11,
      hasPdf: true,
      flags: ['off-topic', 'no cognition outcome'],
      inOurSet: false,
    },
    {
      title:
        'Attention-guided convolutional networks for indoor scene layout estimation',
      venue: 'CVPR · 2022',
      snippet:
        'Deep network estimating 3D room layout (walls, ceiling) from one image…',
      citedBy: 204,
      hasPdf: true,
      flags: ['off-topic', 'no human subjects'],
      inOurSet: false,
    },
  ];

  // =========================================================================
  //  PUBLIC API — typed async functions. Swap each body for the fetch() noted.
  // =========================================================================

  function findById(id) {
    return SEED.find((a) => a.id === id);
  }

  /**
   * Resolve any raw input to bibliographic fields (apaCitation, abstract, doi,
   * title, year, authors). Items with no resolvable abstract are marked
   * NEEDS_MORE_INFO. Topic / articleType / VOI are NOT computed here — that is
   * triage()'s job — so they come back empty.
   * @param {Array<{id?:string, kind?:string, text:string}>} items
   * @returns {Promise<Array>} Article[]
   */
  async function enrich(items) {
    // TODO: replace with fetch('/api/enrich', {method:'POST', body: JSON.stringify(items)}).then(r=>r.json())
    await wait(620);
    return items.map((it, i) => {
      // match a raw item to a canonical record by id or fuzzy text
      const seed =
        (it.id && findById(it.id)) ||
        SEED.find(
          (a) =>
            a.rawInput.toLowerCase().includes((it.text || '').toLowerCase().slice(0, 18)) ||
            (it.text || '').toLowerCase().includes(a.title.toLowerCase().slice(0, 18))
        ) ||
        SEED[i % SEED.length];
      const a = clone(seed);
      const hasAbstract = a.abstract != null;
      return {
        ...a,
        inputKind: it.kind || a.inputKind,
        rawInput: it.text || a.rawInput,
        // pre-triage view: relevance fields not yet computed
        topic: hasAbstract ? '' : '—',
        articleType: hasAbstract ? '' : a.articleType,
        triage: hasAbstract
          ? { decision: 'PENDING', confidence: 0, reason: '' }
          : {
              decision: 'NEEDS_MORE_INFO',
              confidence: 0.3,
              reason:
                'No abstract could be resolved from this input. Relevance cannot be assessed without full text.',
            },
        voiScore: 0,
        selected: false,
        retrieval: { status: 'not_attempted' },
      };
    });
  }

  /**
   * Classify enriched articles: assign topic, articleType, a triage decision +
   * confidence + reason, and a value-of-information score.
   * @param {string[]} ids
   * @returns {Promise<Array>} Article[]
   */
  async function triage(ids) {
    // TODO: replace with fetch('/api/triage', {method:'POST', body: JSON.stringify({ids})}).then(r=>r.json())
    await wait(540);
    return ids.map((id) => {
      const a = clone(findById(id));
      return { ...a, selected: a.triage.decision === 'ACCEPT' };
    });
  }

  /**
   * Attempt to retrieve a PDF for each id. Sets retrieval.status honestly — not
   * every attempt succeeds. Open-access hits resolve fastest; paywalled/blocked
   * resolve to metadata-only or browser-assist outcomes.
   * @param {string[]} ids
   * @returns {Promise<Array>} Article[]  (retrieval populated)
   */
  async function retrieve(ids) {
    // TODO: replace with fetch('/api/retrieve', {method:'POST', body: JSON.stringify({ids})}).then(r=>r.json())
    await wait(400);
    return ids.map((id) => clone(findById(id)));
  }

  /**
   * The collected-articles database. Supports filtering by topic, articleType,
   * triage decision, retrieval status, and free-text query.
   * @param {{topic?:string, articleType?:string, decision?:string, status?:string, q?:string}} [filters]
   * @returns {Promise<Array>} Article[]
   */
  async function library(filters = {}) {
    // TODO: replace with fetch('/api/library?' + new URLSearchParams(filters)).then(r=>r.json())
    await wait(260);
    const q = (filters.q || '').trim().toLowerCase();
    return SEED.map(clone).filter((a) => {
      if (filters.topic && filters.topic !== 'all' && a.topic !== filters.topic) return false;
      if (filters.articleType && filters.articleType !== 'all' && a.articleType !== filters.articleType)
        return false;
      if (filters.decision && filters.decision !== 'all' && a.triage.decision !== filters.decision)
        return false;
      if (filters.status && filters.status !== 'all' && a.retrieval.status !== filters.status)
        return false;
      if (q) {
        const hay = (
          a.title +
          ' ' +
          a.authors.join(' ') +
          ' ' +
          (a.abstract || '') +
          ' ' +
          a.topic +
          ' ' +
          (a.doi || '')
        ).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  /**
   * Ranked value-of-information gap recommendations (where to search next).
   * @returns {Promise<Array>} GapRecommendation[]
   */
  async function recommendations() {
    // TODO: replace with fetch('/api/recommendations').then(r=>r.json())
    await wait(320);
    return clone(RECOMMENDATIONS).sort((a, b) => b.voiScore - a.voiScore);
  }

  /**
   * Side-by-side comparison of our triaged results vs an external Google Scholar
   * AI search for one query.
   * @param {string} q
   * @returns {Promise<{ours: Array, scholar: Array}>}
   */
  async function compareScholar(q) {
    // TODO: replace with fetch('/api/compare-scholar?q=' + encodeURIComponent(q)).then(r=>r.json())
    await wait(700);
    const ours = SEED.map(clone)
      .filter((a) => a.triage.decision === 'ACCEPT' || a.triage.decision === 'EDGE_CASE')
      .sort((a, b) => b.voiScore - a.voiScore);
    return { ours, scholar: clone(SCHOLAR_RESULTS) };
  }

  /** Convenience: the raw ingest items pre-loaded for the demo session. */
  function seedRawItems() {
    return SEED.map((a) => ({ id: a.id, kind: a.inputKind, text: a.rawInput }));
  }

  // ---- expose -------------------------------------------------------------
  window.api = {
    enrich,
    triage,
    retrieve,
    library,
    recommendations,
    compareScholar,
    seedRawItems,
  };
  window.RESEARCH_QUESTION = RESEARCH_QUESTION;
})();
