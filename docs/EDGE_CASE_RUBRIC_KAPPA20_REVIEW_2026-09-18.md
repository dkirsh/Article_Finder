# Edge-case rubric — the 20-paper extraction review

*For Stephan, September 2026. David Kirsh's lab. This is the written-down
version of the judgments the tool already asks of you; nothing here is a new
task. Read it once before your first sitting, then keep it open for the hard
calls. Everything below is drawn from the field definitions built into the
tool (the **i** button on every field) and from what a QA pass over the wider
corpus turned up this week.*

## What you are actually doing

The machine has already read each of the twenty papers and written down, for
each, a set of facts: the citation, the kind of paper it is, who was studied,
what was manipulated, what was measured, what was found, at what effect size
and *p* value. Your job is to check one of those facts at a time against the
paper itself, and to say whether the machine got it right, got it wrong (and
what the right answer is), or reported something the paper does not actually
establish. The tool decides the order and stops asking about a field once your
rulings have pinned down its error rate, so the count falls as you go.

Two rules stand behind all the specific ones. First, judge against the paper,
not against plausibility: a claim that reads as reasonable is still wrong if
the paper in front of you does not support it. Second, mark the passages that
carried you to your answer — all of them, not only the single sentence you
would cite if forced to pick one. The trail of passages is the most valuable
thing the review produces, because it teaches the system where in a paper the
evidence for each field actually lives.

## The habit that matters most

When you settle a field, select the text that got you there and mark it. If
three sentences and a table caption together convinced you, mark all four,
even if in the end one of them would have been sufficient on its own. A field
you answer without a marked passage is a verdict with its reasoning thrown
away; a field you answer with the whole trail is a verdict the machine can
learn from. This is worth the extra seconds every time.

## When more than one label is true

Papers do not always fall into one box, and you should not force them. Record
the best single label in the verdict or correction, and put any other labels
that genuinely apply in **Also applies**. A study that is mostly a controlled
experiment but carries a substantial interview component is
`empirical_quantitative` with `mixed_methods` noted alongside, not a coin
toss between the two.

## When you are not sure

An honest *unsure* is worth more than a confident guess, and it is a real
answer, not a failure to answer. Use it when the paper itself is genuinely
ambiguous, or when the extracted text is too damaged to judge, and write one
sentence saying which. Reserve **Not established in the paper** for the
different case where you have read enough of the paper to be confident it
makes no such claim — an absence judgment you can defend, not a place you
stopped looking.

## The two fields to slow down on

A QA pass over the wider corpus this week found the errors clustering in two
places, and both are among the fields you will see. The run puts the
hardest cases — where our two extraction methods disagree — in front of you
first, so this is where your time is best spent.

**Effect direction.** There is a small but real rate of sign errors: the
machine occasionally reports an effect running the wrong way. Direction is
cheap to get backwards and expensive to leave wrong downstream, so check the
sign against the *sentence that states the result*, not against the size of
the effect or against what you would expect the result to be. If a paper says
higher illuminance went with *lower* reported comfort, that is `negative`,
however counterintuitive, and however large the coefficient.

**The finding itself (main conclusion).** In the wider corpus the extractor
sometimes hands over an OCR fragment dressed as a finding — a truncated line,
a bare figure label like "F7," a scrap of an author affiliation. If one of
those turns up in your twenty it is not a borderline call and not a
badly-worded finding; it simply is not a claim. Mark it wrong and, where the
tool lets you, say why. (The upstream check meant to catch these has been
tightened; it had been over-flagging genuinely short findings, which was its
own lesson — a three-word finding backed by a statistic is a finding, not
corruption.)

One field you will *not* see, in case you have heard it mentioned: the
mechanism field, where the machine collapsed many papers onto a generic
"fluency" mechanism that is not in their text, is being cleaned upstream and
is not part of this review. You need not think about it.

## The thirteen fields, and where each one trips

**article_type** — what kind of paper it is, judged by *how its knowledge was
produced*, not by its topic. The genuine categories are: `empirical_quantitative`
(collects data, reports numbers or statistical tests); `empirical_qualitative`
(collects data through interviews, observation, or thematic analysis, with no
statistical test at its core); `mixed_methods` (substantial quantitative *and*
qualitative components in one study); `narrative_review` (synthesizes other
papers without a systematic search); `systematic_review` (a review that
describes its database search and inclusion criteria); `meta_analysis`
(statistically combines results from prior studies); `theoretical` (builds or
defends a theory); and `methodology` (the paper's primary contribution is a
method, instrument, protocol, or analysis approach others could use).

The criterion worth memorizing is mine, for the line reviewers cross most
often: a paper that offers pointers and associations but no actual theory is a
*review*, not a `theoretical` paper. "Theoretical" requires a theory being
constructed or defended, not a literature tour with a thesis-shaped title.

The machine also emits older, looser labels; read them as follows and correct
to the specific category. `qualitative` → `empirical_qualitative`.
`quantitative` → `empirical_quantitative`. `methods` → `methodology`.
`commentary` → a response or commentary on another publication.
`empirical_research` is the machine declining to commit — decide for yourself
whether the study is quantitative, qualitative, or mixed, and correct it to
the specific one.

**apa_citation** — the full APA reference for *this* paper: authors, year,
title, journal or venue, volume and pages, DOI where printed. Judge it against
the paper's own front matter — its title page and printed citation block —
never from memory or from what a search returns. (A handful of citation items
have already been resolved by lookup and will not reach you.)

**main_conclusion** — the paper's central finding, in one sentence, as its
authors would state it. Not a side result, not a limitation, not the aim
restated. This is the field where OCR fragments masquerade as findings; see
above.

**independent_variables** — what the *main* study manipulated or used as
predictors (lighting level, ceiling height, sound condition). Empty is the
*correct* answer for reviews and theory papers; do not invent variables to
fill the box.

**dependent_variables** — the outcomes the main study measured (comfort
rating, task accuracy, heart rate).

**construct_pair** — the central exposure-to-outcome pairing at the construct
level, written X → Y (for example, `daylight exposure → mood`). One pair, the
paper's main axis — not every relation the paper touches.

**direction** — the sign of that main relation, as the paper reports it.
`positive` (more IV, more DV); `negative` (more IV, less DV); `mixed` (the
paper's own results point both ways across conditions or outcomes); `no_effect`
(the paper reports no reliable effect); `not_applicable` (the paper makes no
directional claim — reviews, theory, methods papers). Two machine labels to
correct: `differential` usually means the effect differs by subgroup and is
better recorded as `mixed` with the split named; `unclear` means the machine
could not decide, so judge whether the *paper* is genuinely unclear or the
machine simply missed it. This is the first of the two slow-down fields.

**sample_n** — total human participants in the main study; the primary study
if several are reported. Null is correct when there is no human sample (a
review, a simulation, a theory paper).

**p_value** — the *p* attached to the main finding, exactly as printed
("p < .001"). Null is correct if the paper reports none.

**effect_size** — the main finding's effect size as printed (d, r, η², odds
ratio, and so on). Null is correct if none is reported. A number that could
not possibly be an effect size — `d = 57462037` — is wrong on its face and
should be marked so.

**stimulus_description** — what participants were actually exposed to: the
rooms, images, sounds, VR scenes, or light settings, in a sentence or two.

**methods_surface_summary** — design, procedure, and analysis in brief: what
kind of study this was and how it was run.

**measurement_inventory** — the named instruments and measures used (PANAS,
EEG alpha power, a seven-point comfort scale). Judge the list against what the
methods section actually names; a missing instrument counts against the
extraction as much as an invented one does.

## When the task itself feels wrong

The most useful thing I got out of my own round of this kind of judging was
not the verdicts but the distinctions — noticing, for instance, that a paper
can be pure neuroscience, pure psychology, or pure methodology rather than
being forced into a bare in-or-out call. So if a category feels missing, or a
question feels wrong, or the vocabulary lacks a label a paper plainly needs,
write it down and send it to me. That is a contribution to the design, not a
complaint about it, and it is exactly what I want from a second pair of hands
on this.

— David
