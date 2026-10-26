# Synthetic Codex dataset

This directory contains synthetic, Codex-assisted attempt timelines. It is for
developing the data pipeline and analysis model; it is not a record of real
student behaviour and must be kept separate from human-submitted data.

Each attempt directory is a `SnapshotStore` compatible timeline:

- `manifest.json` records snapshot order, event type, timestamp, and source hash.
- numbered `.py` files are immutable source snapshots.
- `exercise_spec.json` contains locally authored tests and benchmark inputs.
- `metadata.json` records provenance and the source problem reference.

The problem statement itself is not copied here. Exercise specifications and
tests are authored for this project.
