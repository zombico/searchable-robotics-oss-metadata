# Changes

## Unreleased

- First executed MuJoCo runs (3.15.0): `smoke_sim.py` and new `tests/test_engine.py` (full-effort stop/coupling checks, timestep halving, in-process repeatability).
- Fixed soft joint limits/coupling in the exported MJCF: jaws overshot their stops by ~10 mm at the 5 N limit with MuJoCo defaults; `constraint_timeconst_s` (0.002 s) now bounds this below 1 mm.
- Added `requirements-sim.txt`, an `engine` CI job (with a regenerate-and-diff check on exported models) and a README quickstart.

## 0.2.0 — 2026-10-08

- Added 20 training-focused findings from 16 primary sources, in JSON and a searchable table.
- Added training fidelity/task/release profiles to all 53 catalog records.
- Replaced the solution roadmap with a calibration-and-evidence pipeline, beginning with primitive motion/contact tests.
- Defined separate state playback and action replay, sensor clocks, action semantics, privilege separation and grouped dataset splits.
- Added a limited episode schema, hand-authored fixtures, evidence/declaration validator and 13 contract tests.
- Added a portable GitHub Actions contract workflow; no engine or exporter integration is claimed.
- Preserved the original mechanism report as MECHANISM-RESEARCH.md.

## 0.1.0

Initial mechanism/component catalog and illustrative fixed-gripper URDF/MJCF exporter. No engine execution or physical calibration.
