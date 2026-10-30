# Synthetic Codex dataset

This directory contains synthetic, Codex-assisted attempt timelines. It is for
developing the data pipeline and analysis model; it is not a record of real
student behaviour and must be kept separate from human-submitted data.

Each attempt directory is a `SnapshotStore` compatible timeline:

- `manifest.json` records snapshot order, event type, timestamp, and source hash.
- numbered `.py` files are immutable source snapshots.
- `exercise_spec.json` contains locally authored tests and benchmark inputs.
- `metadata.json` records provenance and the source problem reference.
- `gold_labels.jsonl` contains reviewed transition labels and rationales. It is
  deliberately separate from generated `transitions.jsonl` baseline labels so
  heuristic output can be compared with human judgement.

The problem statement itself is not copied here. Exercise specifications and
tests are authored for this project.

Generated cohorts now live under `data/datasets/`, whose tier manifests define
their permitted use. This directory retains only the source generators and
their documentation. The single-profile batch can be reproduced here for
development experiments with:

```powershell
$env:PYTHONPATH = "src"
python scripts/build_synthetic_batch.py --output-root data/synthetic_codex --student-id student-001
```

It refuses to overwrite an existing timeline. Supplying another student ID only
chooses an output location; it does not make a copied profile independent
training data. Additional students need deliberately authored variation and
separate review labels.

## Profile-driven synthetic cohorts

`scripts/build_synthetic_cohort.py` creates deliberately different learner
profiles. The default generates three variants of each of these nine profiles
(27 students): gradual trial and error,
no clue to a mediocre answer, correct then optimized, brute force to optimal,
frequent delete and retry, optimal with edge-case errors, syntax struggles,
average-case logic struggles, and perfect improver.

```powershell
$env:PYTHONPATH = "src"
python scripts/build_synthetic_cohort.py --seed 42 --variants-per-profile 3
```

The output root is configurable; the active cohorts use the corresponding
directory below `data/datasets/`. Each cohort includes attempts, a combined
`reviewed-transitions.jsonl`, and a `static-rule-audit.json`. The generator
refuses to overwrite an existing cohort. This data remains synthetic and is
unsuitable for reporting real-world model accuracy.
