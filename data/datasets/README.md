# Dataset tiers

This directory is the canonical registry for Code Lens data partitions.  A
record belongs to exactly one tier, and a learner must never appear in more
than one of training, validation, or final-test.

## Development

`development/` is the integration dataset. It contains its own generated,
synthetic cohort and may be inspected, regenerated, and used while building
the application. It is not training, validation, or final-test evidence.

## Training

`training/` contains a distinct synthetic cohort used only for fitting model
parameters in this synthetic-only project version.

## Validation

`validation/` contains separate synthetic learners for model and feature
selection. It must not be used to fit model parameters.

## Final test

`final-test/` is reserved for the final, untouched evaluation set.  Populate
it only after the training and validation design has been frozen.  Once real
records are added, do not inspect labels, run feature-selection experiments,
or tune against it before the single final evaluation.

Each tier has a `manifest.json` declaring its status and permitted use. These
cohorts are synthetic-only and demonstrate the complete pipeline; they cannot
support claims about real student behaviour or production model performance.
