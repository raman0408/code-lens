# Dataset tiers

This directory is the canonical registry for Code Lens data partitions.  A
record belongs to exactly one tier, and a learner must never appear in more
than one of training, validation, or final-test.

## Development

`development/` is the integration dataset.  It consists of the existing
synthetic Codex timelines under `data/synthetic_codex/`, including
`cohorts/cohort-seed-42`.  It may be inspected, regenerated, and used while
building the application.  It is not training, validation, or final-test
evidence.

## Training

`training/` will hold independently reviewed, consented learner timelines for
fitting a model.  Do not place synthetic integration records here.

## Validation

`validation/` will hold separate learners for model and feature selection.
It must not be used to fit model parameters.

## Final test

`final-test/` is reserved for the final, untouched evaluation set.  Populate
it only after the training and validation design has been frozen.  Once real
records are added, do not inspect labels, run feature-selection experiments,
or tune against it before the single final evaluation.

Each tier has a `manifest.json` declaring its status and permitted use.  The
placeholder manifests intentionally contain no examples: no independently
reviewed human data is available in this repository yet.
