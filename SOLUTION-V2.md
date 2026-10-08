# Synthetic robotics training solution v0.2

Research date: 2026-10-08. Objective: reproducible synthetic sensorimotor data, with task-bounded physics validation. Repository: `zombico/searchable-robotics-oss-metadata`.

## What changed after the second research pass

The initial package catalogs mechanisms and interfaces. Version 0.2 adds an explicit path from a researched mechanism to a qualified training asset. It retains 53 catalog records and adds 20 sourced findings from 16 primary sources. `training_findings.json` separates source facts from proposed decisions; its source IDs R01–R16 identify the URLs behind this document.

The important correction is to stop treating a successfully loaded robot model, a plausible animation, and a calibrated dynamics model as interchangeable. Each has a different acceptance test. Contact modeling research documents consequential differences between simulator assumptions (R02); measured impact comparisons show limitations that depend on the interaction (R03). Those results do not rank one engine as universally accurate.

**Current implemented scope:** research catalogs, an illustrative box-gripper exporter, metadata contracts, a dependency-free fixture validator, negative contract tests, and a standard-library CI workflow. No actual training episodes, engine-run evidence, calibration measurements, image dataset, trained policy or transfer result is included.

## Architecture and authoritative state

| Layer | Responsibility | Output |
|---|---|---|
| Mechanism catalog | Functional retrieval, sources, component interfaces | Existing 53-row catalog plus training profiles |
| Compiler | Generate geometry and physical assembly graph from a recipe | Visual/collision assets, native physics model, manifest |
| Physics adapter | Simulate actuators, contacts, constraints and environment | Authoritative state sequence and engine diagnostics |
| Task/controller adapter | Define observations, commands, limits, rewards and resets | Versioned task/control contract |
| Sensor/render adapter | Produce observations at declared capture and release times | RGB/depth/proprioception with calibration metadata |
| Recorder | Align transitions and retain full-state checkpoints | Canonical episodes and provenance sidecars |
| Export adapters | Map canonical records to training tools | LeRobot or robomimic-compatible datasets |
| Qualification | Check contracts, calibrate, validate, evaluate transfer | Scoped error report and release level |

Mojulo should own the mechanism recipe, assembly depiction, attachment semantics and visual asset generation. A selected simulator owns physical state evolution. Rendered frames must refer to those states and the recorded sensor clock. A depiction renderer alone should not be advertised as a calibrated camera sensor: intrinsics, visibility, depth, distortion, exposure and latency require separate validation.

Adapters should declare unsupported features and approximation losses. URDF mimic metadata cannot be presumed to enforce coupling in every importer. Neither converting XML nor importing USD establishes equivalent contacts, actuators or solver behavior. This proposal does not establish compatibility with a particular Mojulo API.

## Engine selection: proposed decision

Begin with **one pinned CPU MuJoCo runtime** for inspectable rigid-body primitive tests. Keep native MJCF as the authoritative executable artifact for that adapter; use URDF for tooling/interoperability and GLB/HTML for review. MuJoCo's current source contains a system-identification toolbox; some API details remain provisional (R01). Select and test an exact release/commit before adopting those APIs.

Use **Isaac Lab as a later adapter**, where vectorized environments, camera workflows and actuator models justify its additional runtime requirements. ManiSkill and robosuite are useful references/adapters for manipulation tasks, controllers and demonstrations (R05–R07). Do not build a first release around simultaneous support for all stacks. Simulator capabilities and deployment dependencies must be audited for the chosen versions; this research does not declare the entire selected stack unrestricted OSS.

Use Menagerie models as **comparison baselines**, retaining exact model-specific licenses and parameter provenance. Its proposed grading distinguishes parameter sources, but its README does not guarantee every model has an assigned grade (R04). Mark missing grades unknown. An available model does not make our composed assembly calibrated. Prefer comparison against a native existing arm/gripper before independently rebuilding every robot.

Cross-engine trajectory comparisons can expose dependence on solver/contact choices (R13). Agreement between two simulators is diagnostic, not independent proof of reality.

## Qualification levels

These are proposed release labels, not claims about current assets.

| Level | Permitted claim | Required evidence |
|---|---|---|
| L0 `synthetic_only` | Generated/contract-checked synthetic artifacts | Parameter assumptions and provenance; no accuracy implication |
| L1 `engine_checked` | Executable within declared engine/test envelope | Native compile, finite bounded trajectories, constraint/limit checks, replay and timestep sensitivity |
| L2 `calibrated_envelope` | Specified errors within a named physical operating envelope | Physical measurements, fitted parameters, held-out residuals, uncertainty and approved tolerances |
| L3 `transfer_tested` | Policy transfer results on the named real robot/tasks | Real evaluation protocol, trials, success/failure and confidence intervals, deployment observation/action parity |

L3 does not imply that every underlying physical variable is accurately estimated. Behavioral success and model-error evidence must be reported independently. Requalify when geometry, materials, controller, engine or solver settings change materially.

`verify_release.py` checks declarations, evidence hashes and metric thresholds. It does not authenticate experiments, inspect scientific methodology or independently establish physical accuracy. A green metadata check cannot substitute for evidence review.

## First implementation sequence

The original proposal jumped to pick-and-place. First isolate mechanisms:

| Milestone | Experiment/task | What it resolves | Deliverable |
|---|---|---|---|
| M0 | Native load, dimensions, frame and inertia checks | Structural correctness | Pinned model, manifest and compile report |
| M1 | Unloaded single-axis sweep/step response | Controller, saturation, lag, joint friction | Timed action/state logs and held-out motion errors |
| M2 | Passive sliding and low-speed impact | Contact friction and damping sensitivity | Measured versus simulated slip/impact curves |
| M3 | Fixed gripper squeeze/slip/release | Pad behavior, force, grasp loss | Force/slip tests over declared materials and loads |
| M4 | Gripper on a Cartesian carriage, simple lift/place | Coupled actuation, contact and perception | Proposed first manipulation environment and episodes |
| M5 | Train a small policy and test held-out conditions | Dataset learning value | Baseline metrics and ablations |
| M6 | Real-hardware transfer evaluation | Deployment utility | Trial report and qualified operating envelope |

The current box gripper has a fixed base and cannot perform pick-and-place by itself. M4 requires a new carriage or arm, actuators, objects, sensors and reset logic; those are not implemented. Start with a simple Cartesian carriage to avoid conflating arm kinematics with gripper contact failures. A specific SO-101 hardware variant is an alternative if actual calibration hardware is available.

Do not invent universal tolerance numbers. Define task tolerances before fitting, based on physical measurement uncertainty and deployment needs. Record units and whether metrics represent worst-case, mean, percentile or a confidence bound.

## Calibration and identification

Fit against one set of experiments; evaluate against separately collected trajectories and contact conditions. Vary excitation/load enough to expose the parameters being identified. Mass, motor gain, friction, latency and controller gains can be confounded; low residuals alone do not establish unique physical parameters.

R01 supports bounded fitting of physical and measurement parameters. Our proposed workflow adds experiment design, held-out evaluation, sensitivity checks and a parameter uncertainty report. Record raw data, sensor calibration, fitting code/version, bounds, optimized values and residual definition.

| Property | Candidate evidence | Evaluation metric |
|---|---|---|
| Joint dynamics | No-load/load sweeps, measured commands and positions | Position/velocity prediction error and phase lag |
| Drive saturation | Current/torque-speed and sustained-load measurements | Torque/current residual; saturation events |
| Contact friction | Controlled sliding/tilt or slip tests | Slip threshold and travel error |
| Impact/compliance | Declared drop/impact conditions | Impulse/rebound or trajectory error; measurement bandwidth |
| Grasp reliability | Known object/pad/load combinations | Slip events, force error and outcome agreement |
| Camera observation | Calibration target and depth reference | Reprojection/depth errors, frame timing |

Contact impulses and forces are engine/model-dependent quantities; do not treat instantaneous solver forces as sensor-equivalent measurements without aggregation, bandwidth and calibration definitions.

## Time, action and observation contract

The canonical transition is `(observation_t, commanded_action_t, next_observation_t_plus_dt, outcome)`. Record the action application interval and the realized low-level signal separately when different. Controller type, command frame, unit, absolute/delta convention, action normalization, saturation, hold/interpolation and control period are part of the task identity (R06).

Physics, controller and sensors run on independent clocks (R14). The fixture uses a **proposed** 1 ms physics step, 20-step controller decimation and 50 Hz action rate. Those values are not established deployment requirements or accuracy-optimal settings.

Every sensor channel needs capture and release times; a policy may only see data released by its decision time. Rendered RGB, depth and labels share camera calibration and a documented state/exposure interval. A camera can have a different rate from control; do not silently duplicate frames as fresh captures. Specify rolling shutter or instantaneous approximation where applicable.

Distinguish privileged simulator truth/teacher inputs from deployable policy observations. True object poses, material parameters, contact impulses and future states may be diagnostic labels, but should not silently enter the deployed student's input space.

## Replay and rendering

ManiSkill explicitly supports saved-state playback and action replay (R07). Use saved-state playback for visual inspection and observation regeneration. Use forward action replay for dynamics/closed-loop checks. Restoring every recorded state can produce perfectly aligned imagery while hiding an incorrect dynamics model.

For continuation, save the engine-supported full integration state, controller history, actuator hidden state, RNG state and sensor histories. MuJoCo documents warmstart considerations for exact numerical continuation (R15). State the runtime/hardware scope and numeric tolerance; do not promise cross-platform bitwise reproducibility from a seed.

## Randomization and coverage

Maintain a nominal calibration model and bounded variations. Separate physical uncertainty, object/task variation and appearance variation. Store both the sampled parameters and distribution definition for every episode.

Physical coupling rules are our engineering constraints, supported by the need to keep mass/inertia consistent in R12:

- At fixed geometry and mass multiplier a, inertia about the same COM scales by a.
- For uniform geometry scaling s at constant density, mass scales by s³ and inertia by s⁵. Attachments/collision geometry must scale consistently; standardized parts should not be arbitrarily scaled.
- Changing COM requires a declared inertia reference and correct translation/rotation handling; arbitrary independent COM/inertia sampling can produce impossible bodies.
- Material/pad friction ranges should be tied to experiments. Randomization is not a substitute for a missing nominal model.

Train/validation/test splits are by source demonstration, object family, layout, calibration condition and/or robot variant as relevant. Descendant trajectories from one demonstration should remain in the same leakage group. Normalize using training data only. Report per-stratum performance and coverage, not just total frame counts. DROID motivates attention to environment diversity (R11); our split rules are proposed safeguards rather than a claim about its protocol.

## Episode generation and export

Track generator type (`scripted`, `planner`, `teleoperation`, `policy`, `demo_adaptation`), revision, source demonstrations, task phases, attempts and outcome categories. MimicGen demonstrates source-demo adaptation (R10); use it as a candidate strategy, not an assumption that arbitrary tasks can be automatically solved.

Retain valid success, slip, miss, collision and recovery episodes with appropriate labels. Keep physically invalid or corrupted episodes quarantined with diagnostic reasons. Do not treat penetration/exploding states as valid task failures. Report attempted/generated/valid/success counts separately, including rejection reasons.

The first canonical store can be inspectable JSON/JSONL for metadata plus suitable arrays/video; production storage is an implementation decision. LeRobot and robomimic exporters are planned (R08–R09), not present. Their file containers cannot fix incompatible action meanings (R16). A real adapter needs import/export round-trip tests for timestamps, modalities, units, actions and outcomes. RL needs a resettable executable environment in addition to logged transitions.

## Evaluation and release

Compare learning on: nominal synthetic data; constrained randomized synthetic data; any available real-data baseline; and a mixed-data condition at stated data budgets. Hold policy architecture and evaluation conditions fixed for meaningful comparisons. Report task success with uncertainty, physical model errors, grasp/slip failure modes, throughput, storage and hardware requirements separately.

Maintain solver timestep/convergence checks and a measured-error report. Engine load success, video quality and metadata validation are prerequisites with limited scope. A release claimed as calibrated must name the exact robot, task, objects/materials, speeds/load ranges, calibration data and held-out metrics.

## Repository implementation backlog

1. Pin a simulator version and asset revision; resolve source-specific licenses.
2. Implement a native primitive test harness and scoped runtime CI. Add full schema validation with a pinned dependency.
3. Implement real episode recording, replay, action/controller contracts and diagnostics.
4. Implement physical calibration acquisition/fitting and held-out evaluation.
5. Add the Cartesian-gripper manipulation environment, bounded randomization and sensor timing.
6. Implement one training exporter and round-trip tests; then a baseline policy.
7. Add a second engine or renderer only for a demonstrated need.

The package seeds `zombico/searchable-robotics-oss-metadata`, with implemented versus proposed scope documented. Repository licensing for newly authored material remains an owner decision before a public release; third-party model/data licenses remain independent.
