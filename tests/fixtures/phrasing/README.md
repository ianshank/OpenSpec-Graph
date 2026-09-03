# Labelled phrasing corpus

Hand-labelled sentences used to measure the accuracy of two matchers:

| File | Rows | Feeds |
|---|---|---|
| `criteria.jsonl` | 86 | `Criterion.is_negative` (rule **G002**) |
| `criteria-ambiguous.jsonl` | 11 | nothing — see below |
| `requirements.jsonl` | 21 | `Requirement.is_normative` (rules **U004**, **S003**) |
| `requirements-modal-variants.jsonl` | 11 | nothing — see below |

Each row is one JSON object: `text` (and `body` for requirements), plus
`label`, and a `note` recording why it was labelled that way.

`label` means the question the rule actually asks, which is not always the
question a reader might assume:

* **criteria** — does this sentence assert a non-success outcome?
* **requirements** — does this requirement use SHALL or MUST as a modal?
  U004's own message says "uses no SHALL/MUST", so that is the contract being
  measured. Requirements that are normative in *spirit* without those words
  ("is required to", "ought to", "Sessions expire after 30 minutes") are a
  genuinely open design question about what should count, and they live in
  `requirements-modal-variants.jsonl` rather than being scored as misses
  against a promise the rule never made. Widening U004 to cover them is a
  change package, not a regex edit.

## Measured

Recorded when the tiering landed, and kept current by
`tools/matcher_accuracy.py`:

| Rule | Precision | Recall | Before |
|---|---|---|---|
| G002 | 0.933 | 0.977 | 0.38 / 0.42 |
| U004 | 0.875 | 1.000 | 0.47 / 0.39 |

U004's one remaining false positive is the interrogative "Shall we keep the
legacy endpoint?" — a question rather than an obligation. Distinguishing the
two needs more than a lexical test, so it is counted against the score rather
than special-cased away.

## Why measure at all

The README's "And what it got wrong" section records four findings that were
the linter's fault. Two of them were this class of defect: a pattern matcher
firing on the wrong thing in natural-language prose. The U004 body-blind bug
alone affected 20 of 34 requirements across four change packages, and it was
found by hand.

One-fixture-per-rule proves a rule *can* fire. It says nothing about how often
it fires on the wrong sentence — and for G002 that is the number that matters,
because the rule asks only whether a spec has **at least one** non-success
criterion. A single false positive anywhere in a document switches it off. The
first measurement here scored precision 0.38: "The block renders below the
header" satisfied G002.

Scored by `tools/matcher_accuracy.py`, gated by
`tests/test_matcher_accuracy.py` against floors in `pyproject.toml`.

## Honest limitations

Read the numbers with these, or they will flatter the matcher:

1. **The set is adversarial.** Roughly half the negative-label-`false`
   sentences were written specifically to contain a trigger word the matcher
   was known to use — "zero-downtime deploy completes", "the failover
   succeeds", "blocked-user list is exported". Precision here is a stress
   test, not a field base rate; the true rate on ordinary spec prose is
   higher. Recall is the more representative of the two figures.
2. **Eleven sentences could not be labelled confidently**, which is why they
   sit in `criteria-ambiguous.jsonl` and are excluded from every score. That
   file asserts nothing. It is kept because 11/97 is the honest floor on how
   much a second labeller would agree with the first, and deleting it would
   hide that.
3. **It is synthetic.** These sentences were composed for this purpose, not
   harvested from real specs. They are a regression net, not a benchmark.

## Adding a row

Label from the sentence alone, before running the matcher against it. A row
added because it makes the number move is not evidence. If you cannot decide,
it belongs in the ambiguous file.
