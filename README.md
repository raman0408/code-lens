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
- Fresh profile-authored synthetic cohorts are partitioned under
  `data/datasets/`: development (1 student), training (3), validation (2),
  and sealed final-test (2). Every learner attempts the same five questions:
  Reverse Integer, Jump Game, Length of Last Word, Rotate Array, and Minimum
  Size Subarray Sum. They exercise the complete synthetic-only
  workflow without mixing learner identities between tiers.
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
python -m code_lens.cli audit data/datasets/training/cohort-seed-202/reviewed-transitions.jsonl --details
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
code-lens reviewed-dataset data/reviewed-transitions.jsonl data/datasets/training/cohort-seed-202/train-001/minimum-size-subarray-sum

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

For the synthetic-only project workflow, generate all uniform tiers and then
train and validate without reading the sealed final-test tier:

```powershell
$env:PYTHONPATH = "src"
python scripts/build_uniform_synthetic_datasets.py
python scripts/evaluate_synthetic_ranker.py data/datasets/training/uniform-five-problem-seed-202/reviewed-transitions.jsonl data/datasets/validation/uniform-five-problem-seed-303 models/synthetic-ml-ranker.json reports/synthetic-validation.json
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

## Final decision contract

For a completed student attempt, Code Lens first rejects a transition unless its
after-version passes every defined test, does not regress versus its predecessor,
and has either a recognised algorithmic signal or a material benchmark-growth
reduction. The logistic-regression model is then the ranking authority: it
selects the highest-probability transition from the eligible candidates. The
static and benchmark evidence remain in the result so the teacher can inspect
why the ML-selected transition was allowed to compete.

`code_lens.engine.analyze_attempt()` is the application-facing API. It returns
a stable report payload containing the selected version pair (or no result),
ML probability, eligibility evidence, and a human-readable conclusion.

## Layout

- `src/code_lens/model.py` — AST feature extraction and deterministic attribution model.
- `src/code_lens/cli.py` — terminal interface.
- `tests/` — executable specifications.
