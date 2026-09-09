# HITL paper judgment — onboarding for Stephan

*2026-09-09. David Kirsh's lab. Written by Fable under the ATLAS
science-communication norms; process designed with David in chat, 2026-09-09.*

Welcome. Your job in this workflow is to be the human judge of how our corpus
papers are classified — what kind of paper each one is, and whether it belongs in
our corpus at all. Machines propose; you decide. Nothing you do here needs
programming, and mistakes are recoverable: every judgment can be reopened and
changed before export.

## Why your judgment matters

We are building a typed, topic-mapped corpus of environmental-cognition research.
An automatic typer reads each paper and proposes labels, but a machine's label is
a *measurement*, not a truth — the audit that motivated this workflow found that
half of one certified 20-paper set carried a wrong label of one kind or another.
Your rulings are the standard the machine is corrected against. And the passages
you mark as decisive teach the machine *where to look*, which over time is worth
more than the verdicts themselves.

## The one rule about context

The few words that ultimately decide a classification are almost never enough
context to trust. So the viewer always gives you the **whole paper**, scrollable,
and you should feel free to roam it. In assisted batches the machine's key passage
is highlighted amber as an *anchor* — a suggestion of where to look first, never a
boundary on what to read. In blind batches nothing is highlighted, on purpose:
those batches measure the machine against you, so you must not see its opinion
before forming your own.

## Getting started (one-time)

1. Get the working folder from David — either a shared Drive folder or a copy of
   `Article_Finder_v3_2_3/data/topic_comparison/<batch-name>/` containing
   `hitl_viewer.html`, `tasks.json`, and a `papers/` directory of text files.
2. Open Terminal, `cd` into that folder, and run: `python3 -m http.server 8765`
   (leave that window open while you work).
3. In your browser, go to `http://localhost:8765/hitl_viewer.html`.
4. You should see the paper list on the left with a progress count. Click any
   paper; its full text loads in the middle pane, the judgment form on the right.
5. Your work saves in the browser (per batch, per paper) every time you press
   **Save judgment** — you can close and return any time on the same computer and
   browser.

## Judging one paper (the loop)

6. Read the title and abstract, then skim the paper — especially any methods and
   results material. Scroll as much as you need; the highlighted passage (if any)
   is a starting point, not the evidence in full.
7. Answer **METHOD**: how was the knowledge produced? Quantitative empirical work
   collects data and reports numbers or statistical tests. Qualitative empirical
   work collects data through interviews, observation, or thematic analysis.
   Reviews synthesize other papers' findings (systematic ones describe a database
   search and inclusion criteria; narrative ones don't). A paper is *theoretical*
   only if it constructs or defends a theory — David's criterion, worth memorizing:
   a paper offering pointers and associations but no theory is a review.
8. Answer **FORM**: most papers are journal articles; watch for responses/
   commentaries ("Reply to…", "Response to…"), book chapters, and edited
   collections.
9. Answer **FIELD**: does this paper belong in an environmental-cognition /
   architecture-and-behavior corpus? Papers can be well-executed and still out of
   field (a rat-memory study, an educational-technology experiment). `borderline`
   is an honest answer; say why in the notes.
10. **Mark your decisive passages.** When you hit the sentence or table caption
    that settles the question for you, select it with the mouse and click *Mark
    selected passage as decisive*. Mark one to three per paper. This is the most
    valuable thing you produce — it is how the machine learns where decisions
    live in papers.
11. If you are genuinely unsure, choose *unsure*, write a sentence in the notes,
    and move on. An honest "unsure" is worth more than a guessed label.
12. Tick **"David should also evaluate this decision"** only when you want his
    eyes on it — a judgment call you don't feel you own, a paper that seems
    important to the corpus, a possible systematic problem. Untick papers you
    later resolve yourself. David sees only what you escalate.
13. Press **Save judgment**. The paper gets a ✓ in the list (⚑ if escalated).

## Finishing a batch

14. When the progress count reaches the full batch, press **Export all judgments
    (JSON)** — the browser downloads a `hitl_judgments_<date>.json` file.
15. Send that file to David (or drop it in the batch's Drive folder). That file —
    not the browser's memory — is the durable record, so export before switching
    computers.
16. Anything you noticed that the form couldn't capture (a recurring OCR problem,
    a label the vocabulary lacks, papers that feel like a new category) goes in
    an email alongside the export. Process observations are wanted, not noise.

## Practical notes

- The paper texts are machine-extracted (OCR) and imperfect — garbled equations
  and broken tables are normal. Judge through the noise; if the text is too
  damaged to judge, mark *unsure* and note it.
- Expect roughly 5–10 minutes per paper at first, faster once the categories
  settle in.
- Questions about the workflow go to David; he may route them onward.
