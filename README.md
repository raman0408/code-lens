# Code Lens

Code Lens is a non-LLM analysis engine for comparing successive versions of Python code. It uses the Python AST to identify changes that plausibly improve runtime behaviour: reduced loop nesting, eliminated repeated work, cheaper membership checks, and lower structural complexity.

This first iteration is terminal-first and dependency-free.

## Handoff: current state and next work

This repository is a working prototype, not a validated predictive system.
It can capture Python attempt histories, compare every consecutive pair, verify
exercise correctness, collect small benchmark measurements, export features,
join reviewer labels, audit static rules, and train a small logistic-regression
ranking model.

### What is complete

- AST rules detect reduced nesting, removed repeated sorting or literal-list
  membership checks, repeated string concatenation, and a conservative
  expand/shrink sliding-window shape.
- A compiler-inspired feature layer also exports AST size, control-flow nodes,
  calls, returns, variable reads/writes, collection allocations, slices,
  comprehensions, and recursive calls. These are ML inputs, not new hard
  verdict rules; every matching function contributes a before/after delta.
- Exercise evaluation runs tests and optional benchmark series in a separate
  process. Multi-size benchmark series produce a log-log growth-exponent
  estimate; this is supporting evidence, not a formal complexity proof.
- `data/synthetic_codex/student-001` contains six reviewed synthetic attempt
  timelines: Palindrome Number, Reverse Integer, Jump Game, Length of Last
  Word, Rotate Array, and Minimum Size Subarray Sum.
- The synthetic dataset has 55 labelled transitions. Its refreshed static-rule
  audit finds all 3 reviewed algorithmic improvements (0 false negatives), but
  still has 4 false positives. See `data/synthetic_codex/static-rule-audit.json`.
- The batch generator recreates a single declared synthetic profile and refuses
  to overwrite an existing one. Run `python scripts/build_synthetic_batch.py
  --help` for its output-root and student-ID options.
- `scripts/build_synthetic_cohort.py` creates profile-authored synthetic
  cohorts. Its default is 27 students: three variants of each documented
  profile. It writes a combined reviewed dataset and audit beside the cohort.
- `python -m unittest discover -s tests -v` currently passes all 14 tests when
  `PYTHONPATH=src` is set.

### Important limits

- Synthetic timelines are only for exercising the pipeline. They are not real
  student behaviour and must not be mixed with human data or used to claim ML
  accuracy.
- `data/datasets/` defines the data-partition contract. The current synthetic
  records are development/integration data only. Training, validation, and
  final-test are separate empty intake tiers until independently reviewed,
  consented learner timelines are available. The final-test tier must remain
  untouched until one final evaluation of the frozen model.
- A new `--student-id` output location is not an independent student profile.
  Do not create a cohort by copying this profile under multiple IDs.
- Rule labels are weak supervision. Train final models only with independently
  reviewed labels, and evaluate on held-out students rather than random
  transitions from the same student.
- The evaluator is not a security sandbox; do not run untrusted code with it.

### Recommended next steps

1. Use the richer feature schema with simple, interpretable ML baselines after
   collecting more independent labelled timelines. Do not add a graph or deep
   model to the current 55-transition dataset.
2. Review the four false positives in the audit and decide whether they should
   be addressed by a stricter eligibility gate, richer ML data, or a narrowly
   justified static rule. Preserve the three true positives and re-run the
   audit after every rule change.
3. Design deliberately varied synthetic profiles (different starting errors,
   approaches, regressions, and true-improvement locations), then add an
   explicit profile/variation mechanism to the generator before producing a
   synthetic cohort.
4. Collect real, consented, independently reviewed timelines. Keep them in a
   separate directory from `data/synthetic_codex`.
5. Once enough independent labelled students exist, add student-level
   train/validation/test splitting and report held-out precision/recall or
   ranking quality. Do not report model performance from the current 55
   synthetic transitions.

### Fast verification for the next agent

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m code_lens.cli audit data/synthetic_codex/reviewed-transitions.jsonl --details --output data/synthetic_codex/static-rule-audit.json
```

Useful starting points are `src/code_lens/model.py` (static rules),
`src/code_lens/evaluation.py` (tests and benchmarks),
`src/code_lens/features.py` (dataset assembly and audit), and
`scripts/build_synthetic_batch.py` (synthetic-profile generation).

## Run

```powershell
python -m pip install -e .
code-lens compare examples/before.py examples/after.py
$env:PYTHONPATH = "src"; python -m unittest discover -s tests -v
```

## Snapshot timelines

Capture source after every compile or submission event. The directory is an
append-only per-student timeline; source snapshots and metadata are retained.

```powershell
code-lens capture .code-lens/student-42 examples/before.py --event compile
code-lens capture .code-lens/student-42 examples/after.py --event submission
code-lens timeline .code-lens/student-42
```

`timeline` analyses every consecutive pair, then identifies the exact transition
where the strongest evidence of a meaningful complexity improvement occurred.

## ML-ready features and one-command demo

The static metrics now become feature vectors for a future non-LLM ranking model.
Each JSONL line represents one consecutive code change and contains structural
features, a weak baseline label, and—when an exercise specification is supplied—
correctness and runtime-change features.

```powershell
# Create a simulated three-version student timeline and its feature dataset.
code-lens demo .code-lens/demo-student

# Export a real student's transitions. The optional spec runs instructor tests
# and small benchmarks in a separate Python process.
code-lens dataset .code-lens/student-42 data/student-42.jsonl --spec examples/exercise_spec.json

# Join generated features to separate human-review labels before training.
code-lens reviewed-dataset data/reviewed-transitions.jsonl data/synthetic_codex/student-001/palindrome-number

# Measure where static rules disagree with human review.
code-lens audit data/reviewed-transitions.jsonl --details --output data/static-rule-audit.json
```

The `baseline_label` is only a transparent rule-based starting label. A transition
is eligible for that label only when its after-version passes every exercise test,
does not pass fewer tests than its before-version, and has a meaningful structural
improvement score. Replace baseline labels with instructor annotations before
training a classifier or learning-to-rank model.
The evaluation harness is for local development; it is not a security sandbox for
untrusted code.

## Train and use the ML model

`code-lens train` trains a binary logistic-regression model and `predict` scores
every timeline transition, highlighting the highest-probability improvement. Add
a human-review `label` to exported JSONL: `1` for the best/meaningful transition
and `0` for the others. Include both labels in the training dataset.

```powershell
code-lens train data/reviewer-labelled-transitions.jsonl models/improvement-model.json
code-lens predict .code-lens/student-42 models/improvement-model.json --spec examples/exercise_spec.json
```

For a runnable demonstration, `examples/reviewer_labelled_transitions.jsonl` is
a deliberately small synthetic labelled dataset. It only proves the workflow;
collect many real, independently instructor-labelled timelines before reporting
model accuracy.

Rule labels can bootstrap a mechanics-only experiment, but are not valid final
training data because the model would simply learn to reproduce the rules. Export
with `--spec`; without exercise tests, transitions are not correctness-verified
and therefore receive no positive baseline label:

```powershell
code-lens train data/bootstrap.jsonl models/bootstrap-model.json --use-baseline-labels
```

The tool reports evidence-backed candidates; it does not claim a measured speed-up. Runtime benchmarking and more languages are planned next steps.

## Layout

- `src/code_lens/model.py` — AST feature extraction and deterministic attribution model.
- `src/code_lens/cli.py` — terminal interface.
- `tests/` — executable specifications.
