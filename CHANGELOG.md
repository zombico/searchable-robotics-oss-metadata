# Changes

## Unreleased

- Pick task v0 (`tasks/pick/`): x/z carriage + example gripper scene built from `example.json`/`task.json`; `PickEnv` with Gymnasium-style API; per-episode randomization of box size, mass (with consistent inertia), friction and position; outcome and quarantine rules; scripted demonstrator on policy observations only; generator with contract validation, split-leakage check, per-transition diagnostics (object pose, pad force, actuator force, mechanical power) and `--replay`. Samples and a 1,000-episode summary committed.
- Episode validator generalized to multi-axis actions (per-axis bounds) and declared observation channels (`channel_dims`, `channel_units`); the legacy jaw contract still applies when they are absent.
- `engine_check.py` writes hashed engine evidence for the example gripper (forward-simulated episode; engine, replay/continuation and convergence reports; `engine_checked` release). Measured: stop overshoot 0.05 mm, coupling 0.03 mm, peak speed 0.094 m/s, exact same-process replay and continuation, first-order timestep convergence (observed order 1.00). CI regenerates it on its runner and replays the committed episode; a stdlib test fails on stale evidence.
- Gripper MJCF drive is now a linear force-speed line (DC-motor back-EMF form): the ideal force actuator reached 1.34 m/s against the declared 0.1 m/s.
- Added `electronics/` as a separate concern: 16 swappable-slot interfaces with per-field compatibility rules, swap consequences and solver mappings; 34 components (servos, drivers, sensors, buses, MCUs, power, e-stop standards) with per-value source, quote and verification level; raw research files and a normalizing build script.
- Added `electronics/swap.py`: candidate ranking, single-swap reports, `--audit` of bound parts and a static worst-case `--budget` per supply rail. Missing or conflicting data yields `undetermined`, never a pass; voltage-dependent ratings are used only at the slot's supply voltage.
- Added SO-101 follower bindings (5 V default and 12 V option) and 27 electronics tests.
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
