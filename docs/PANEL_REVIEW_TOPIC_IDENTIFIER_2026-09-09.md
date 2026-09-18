# Panel review — topic/field identifier v1 (and typer v1 finalization)

*2026-09-09, Fable, before the corpus-wide run David commissioned ("if something is
pure neuroscience put it in a different bucket"). Six-voice panel per the lab's
method; each concern states what changed in the build as a result.*

**Methodologist.** The blind-50 protocol must survive this run: the corpus-wide pass
may not overwrite or expose the sealed blind-50 machine verdicts, and the 50's human
round stays authoritative for κ. *Incorporated:* the corpus run writes to its own
output dir; blind-50 files untouched. Also: v1 must show its calibration receipt
before scaling — it is scored against David's final gold-20 rulings first, and the
run proceeds only if it matches or beats the pilot's 14/14 family agreement.

**Computational linguist.** Lexical field-scoring is brittle three ways: OCR noise,
reference-section contamination (a bibliography full of "cortex" is not a
neuroscience paper), and language (at least one corpus paper is Spanish).
*Incorporated:* all signals are computed on the pre-references body (references
located and stripped); title+abstract hits weighted 5x body hits; a crude
non-English detector routes foreign-language papers to the HARD tier rather than
mislabeling them; densities are per-10k-chars so long documents don't win by bulk.

**Neuroscientist.** The pure-neuroscience bucket must not swallow neuroarchitecture.
An fMRI study of ceiling height is OUR paper; a rat recognition-memory study is not.
The test is therefore NOT "contains neuro terms" but "neuro-dense AND
environment-silent." *Incorporated:* bucket rule = neuro density above threshold
AND environmental density below threshold; papers dense in both are in-field
(neuro-architecture); the known case PDF-0267 (ROCs in rats) is the calibration
anchor for the bucket, PDF-0595 (ceiling-height fMRI) the anchor for in-field.

**Environmental psychologist / architect.** The field lexicon must span the corpus's
actual breadth — not just "architecture" but landscape, urban design, acoustic
comfort, lighting, thermal environment, wayfinding, restorative environments,
workplace and classroom settings — or half the field lands in "out of field."
*Incorporated:* the environmental lexicon covers built/urban/landscape/ambient
domains (~60 terms); "borderline" is a real output, not a failure state, and goes
to the GREY tier for human eyes.

**Information scientist.** Don't ignore priors the system already owns: 883 papers
carry kg_topic_membership rows, 745 carry Article_Finder topic classifications via
the AE match. A fresh lexical score that contradicts an existing topic assignment is
itself a flag. *Incorporated:* existing topic coverage is recorded per paper as
provenance (has_kg_topics / af_topic when joinable); disagreement between lexical
field-call and existing topic data lowers confidence and can demote to GREY. Full
reconciliation is future work, stated as such.

**Corpus engineer.** Every output row needs receipts, a version stamp, and a
machine-readable tier so downstream automation (scheduler, registry amendment) can
consume it without re-deriving. *Incorporated:* per-paper JSON carries matched
spans for every fired signal, `typer_version` and `field_version` stamps, tier
(CLEAN/GREY/HARD), and the field bucket (in_field / pure_neuroscience /
out_of_field_candidate / borderline).

**Residual risks the panel accepts, stated plainly:** thresholds are calibrated on
few anchors and one afternoon; the LLM adjudication layer is NOT in this scripted
v1 (the pilot showed the mechanical layers alone abstain or misfire on roughly a
third of papers — those land in GREY/HARD by design rather than being guessed);
field buckets are candidates for David's hand review, never deletions.
