# Composed pick gripper: report

Feasible means feasible in MuJoCo under the stated assumptions and catalog values. Release level: synthetic_only.

## Requirements (derived from tasks/pick/task.json)

- **pad_normal_force_N**: 8.857 — `SF * m_max * (g + a_lift) / (2 * mu_min)`
- **jaw_drive_force_N**: 17.71 — `twin racks: total rack force = 2 * pad normal force`
- **jaw_opening_m**: 0.05 — `w_max + 2 * 2.5 mm` (available 0.06)
- **per_jaw_travel_m**: 0.025 — `example.json jaw_travel_mm`
- **max_close_time_s**: 0.6 — `proposed requirement`
- **z_payload_N**: 10.39 — `(carriage + gripper + servo + m_max) * (g + a_lift)` (limit 30)

Assumptions: safety_factor=1.5, lift_accel_m_s2=2.0, rack_pinion_efficiency=0.9, pinion_module_mm=1.0, min_teeth_without_profile_shift=17, max_full_stroke_close_s=0.6, rail_voltage_V=12.0, supply=E72, torque_current_model=current proportional to torque between zero and the published stall point (assumption).

## Screening

| Design | Servo | Status | Failed or unknown checks | Warnings |
|---|---|---|---|---|
| baseline_example_drive | example.json linear drive (5 N, 0.1 m/s) | reference_rejected | jaw_drive_force_N fail (5 vs 17.7) | - |
| E01_z12 | DYNAMIXEL XM430-W350-T | rejected | full_stroke_close_s fail (0.865 vs 0.6) | 12-tooth pinion is below the 17-tooth undercut limit; needs profile shift |
| E01_z20 | DYNAMIXEL XM430-W350-T | feasible | - | - |
| E01_z30 | DYNAMIXEL XM430-W350-T | feasible | - | - |
| E01_z40 | DYNAMIXEL XM430-W350-T | feasible | - | - |
| E03_z12 | Feetech STS3215 C001 smart servo (7.4 V, 1/345) | rejected | supply_voltage_V fail; jaw_drive_force_N unknown; full_stroke_close_s unknown; rail_worst_case_A unknown | 12-tooth pinion is below the 17-tooth undercut limit; needs profile shift; relies on search-snippet values; verify against a datasheet |
| E03_z20 | Feetech STS3215 C001 smart servo (7.4 V, 1/345) | rejected | supply_voltage_V fail; jaw_drive_force_N unknown; full_stroke_close_s unknown; rail_worst_case_A unknown | relies on search-snippet values; verify against a datasheet |
| E03_z30 | Feetech STS3215 C001 smart servo (7.4 V, 1/345) | rejected | supply_voltage_V fail; jaw_drive_force_N unknown; full_stroke_close_s unknown; rail_worst_case_A unknown | relies on search-snippet values; verify against a datasheet |
| E03_z40 | Feetech STS3215 C001 smart servo (7.4 V, 1/345) | rejected | supply_voltage_V fail; jaw_drive_force_N unknown; full_stroke_close_s unknown; rail_worst_case_A unknown | relies on search-snippet values; verify against a datasheet |
| E04_z12 | Feetech STS3215 smart servo (12 V) | rejected | full_stroke_close_s fail (0.883 vs 0.6); z_payload_N unknown | 12-tooth pinion is below the 17-tooth undercut limit; needs profile shift; relies on search-snippet values; verify against a datasheet |
| E04_z20 | Feetech STS3215 smart servo (12 V) | undetermined | z_payload_N unknown | relies on search-snippet values; verify against a datasheet |
| E04_z30 | Feetech STS3215 smart servo (12 V) | undetermined | z_payload_N unknown | relies on search-snippet values; verify against a datasheet |
| E04_z40 | Feetech STS3215 smart servo (12 V) | undetermined | z_payload_N unknown | relies on search-snippet values; verify against a datasheet |

## Simulation (300 paired seeds)

| Variant | Rotor inertia (kg m²) | Grip limit (N) | Success | Outcomes | Mean close phase (s) | Mean successful episode (s) | Peak pad force mean / max (N) |
|---|---|---|---|---|---|---|---|
| baseline_example_drive | - | 5.0 | 87.0% | {'slip': 39, 'success': 261} | 0.33 | 2.17 | 5.3 / 5.7 |
| E01_z20_J1e-08 | 1e-08 (armature 12.5 kg) | 17.7 | 100.0% | {'success': 300} | 0.47 | 2.30 | 46.9 / 69.7 |
| E01_z20_J1e-07 | 1e-07 (armature 125 kg) | 17.7 | 100.0% | {'success': 300} | 1.10 | 2.94 | 200.9 / 379.8 |
| E01_z30_J1e-08 | 1e-08 (armature 5.55 kg) | 17.7 | 100.0% | {'success': 300} | 0.37 | 2.21 | 37.5 / 54.5 |
| E01_z30_J1e-07 | 1e-07 (armature 55.5 kg) | 17.7 | 100.0% | {'success': 300} | 0.64 | 2.48 | 187.8 / 371.4 |
| E01_z40_J1e-08 | 1e-08 (armature 3.12 kg) | 17.7 | 100.0% | {'success': 300} | 0.33 | 2.16 | 33.1 / 45.0 |
| E01_z40_J1e-07 | 1e-07 (armature 31.2 kg) | 17.7 | 100.0% | {'success': 300} | 0.47 | 2.30 | 163.2 / 319.3 |

## What holds regardless of the unknown rotor inertia

| Design | Worst-case success | Success robust? | Peak pad force range (N) vs grip limit | Impact force depends on rotor inertia? |
|---|---|---|---|---|
| E01_z20 | 100.0% | yes | 70–380 vs 17.7 | yes |
| E01_z30 | 100.0% | yes | 54–371 vs 17.7 | yes |
| E01_z40 | 100.0% | yes | 45–319 vs 17.7 | yes |

## Does the requirement model predict the simulator?

On the reference drive: slip if m*(g + a_lift) > mu * F_drive (two pads, each F_drive/2), a_lift = 2 m/s2, no safety factor.

Agreement 97.3% over 300 episodes: 39 predicted slips slipped, 253 predicted holds held, 8 predicted slips held, 0 predicted holds slipped.

## Ranking

Feasible designs ranked by worst-case simulated success over the inertia sweep, then worst-case successful episode time:

1. E01_z40
2. E01_z30
3. E01_z20

## Holding the grip: torque, current and power (estimates)

| Design | Holding torque (N·m) | Current (A) | Electrical power at the rail (W) |
|---|---|---|---|
| E01_z40 | 0.39 | 0.22 | 2.7 |
| E01_z30 | 0.30 | 0.17 | 2.0 |
| E01_z20 | 0.20 | 0.11 | 1.3 |

From current proportional to torque between zero and the published stall point (assumption); the stall point is published (verification in the screening checks), the linear line between is not.

## Bill of materials: E01_z40

| Item | Part | Qty |
|---|---|---|
| jaw servo | E01 DYNAMIXEL XM430-W350-T | 1 |
| pinion | module 1, 40 teeth, 20 deg (proposed, catalog M05) | 1 |
| racks | module 1 racks on each jaw carriage (proposed, catalog M05) | 2 |
| jaws and base | parallel jaws per example.json (proposed, catalog M13) | 1 |
| jaw guides | linear guide, e.g. MGN-family (catalog C06; size not selected) | 2 |
| bus adapter | E20 ROBOTIS U2D2 (USB to TTL/RS-485) | 1 |
| supply | E72 SO-101 12 V supply option (README minimum "12V 5A+") | 1 |

## Not claimed

- a built or tested gripper
- continuous torque or thermal capacity (unpublished for these servos)
- backlash, rack friction or compliance (not modeled)
- packaging: whether the pinion, racks and servo fit the 100 x 50 mm gripper base (not checked; a 40-tooth module-1 pinion is 40 mm across)
- gentle handling: impact pad forces exceed the grip limit and depend on the unpublished rotor inertia
- electrical behavior of the carriage drives (not catalog parts)
- accuracy of MuJoCo contact for these materials
