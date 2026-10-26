# Code Lens

Code Lens is a non-LLM analysis engine for comparing successive versions of Python code. It uses the Python AST to identify changes that plausibly improve runtime behaviour: reduced loop nesting, eliminated repeated work, cheaper membership checks, and lower structural complexity.

This first iteration is terminal-first and dependency-free.

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
```

The `baseline_label` is only a transparent rule-based starting label. Replace it
with instructor annotations before training a classifier or learning-to-rank model.
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
training data because the model would simply learn to reproduce the rules:

```powershell
code-lens train data/bootstrap.jsonl models/bootstrap-model.json --use-baseline-labels
```

The tool reports evidence-backed candidates; it does not claim a measured speed-up. Runtime benchmarking and more languages are planned next steps.

## Layout

- `src/code_lens/model.py` — AST feature extraction and deterministic attribution model.
- `src/code_lens/cli.py` — terminal interface.
- `tests/` — executable specifications.
