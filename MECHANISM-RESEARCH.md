# Robotics mechanisms, components and compiler contract

Research date: 8 October 2026. This is a broad, primary-source starter catalog, not an exhaustive survey or a validated manufacturing library.

## Open the table

Open `catalog.html` in a browser. It works offline, with search and category filters; source links require internet. `catalog.json` contains the same 53 records and 54 sources with per-specification provenance. The 27 mechanism records, 11 open-project references, 11 standard/component records and four tool/format records cover rigid serial and parallel motion, transmission, compliant and soft actuation, grasping and mobile platforms. Proposed dimensions are never presented as published source dimensions.

The HTML table contains:

| Field | How to use it |
|---|---|
| Problem solved | Retrieve a mechanism by functional intent rather than its name |
| Published specifications | Facts attached to a source ID; not universally applicable to a family |
| Proposed dimensions | Numeric prototype inputs for exploration; not validated sizes or ranges |
| Physics representation | Joint, transmission, contact, or deformable model to compile |
| Missing inputs | Blockers to a predictive simulation or manufacturable part |
| Fabrication route | What can be printed and what should be purchased or machined |
| License scope | Distinguish software, CAD and commercial component rights |
| Priority | 1: first implementation candidates; 2: next stage; 3: advanced modeling |

## Main finding

A useful robotics compiler needs a library of mechanisms **and** a library of physical component interfaces. A mesh library alone will not provide either a manufacturing path or credible dynamics. Keep these layers separate:

1. **Function and mechanism:** desired motion, mechanical advantage, workspace, load case, fabrication constraints.
2. **Geometry and assembly:** dimensions, tolerances, attachment frames, purchased component SKUs, travel stops, collision envelopes.
3. **Physics and control:** rigid bodies, mass/COM/inertia, joints, transmissions, friction, contact, actuators, sensors, control and environment.

This separation is especially useful for a procedural 3D compiler such as Mojulo. The renderer can depict assemblies and interactions, while an independently specified physical graph defines which entities move, collide and transmit force. No Mojulo integration or API compatibility was tested in this research.

## Choose mechanisms by problem

These recommendations are engineering synthesis from the catalog, not measured comparisons between the cited projects.

| Requirement | First candidates | Important tradeoff | Start with |
|---|---|---|---|
| Fast long-stroke positioning | Belt axis, CoreXY | Belt stretch and tension versus low moving mass | M08, M10 |
| Compact linear push | Lead screw | Friction, speed and buckling; backdrivability must be checked | M09 |
| Coaxial speed reduction | Planetary, cycloidal, strain-wave | Complexity and compliance versus reduction/packaging | M02, M06, M27 |
| Move motor off the output joint | Belt reduction, tendon | Routing, elasticity, slack and friction | M07, M14 |
| Maintain gripper orientation | Four-bar parallelogram | Closed-loop constraints, singularities and collision | M11 |
| Predictable object centering | Parallel jaws | Contact/pad choice and force control | M13 |
| Adapt to uncertain object shape | Underactuated tendons, PneuNets, jamming | Compliance model and task-dependent grasp stability | M14–M18 |
| Pick smooth flat parts | Suction | Seal, leakage, effective area and peel loading | M19 |
| Cheap ground navigation | Differential drive | Caster drag, tire slip and uneven ground | M20 |
| Lateral movement on flat floors | Mecanum | Roller contacts and slip; terrain sensitivity | M21 |
| Planar handling with vertical stroke | SCARA | Reach singularities, tool load and joint stiffness | M22 |
| Rapid translational handling | Delta | Workspace and loop constraints; no generic payload rating | M23 |
| Six-axis platform motion | Stewart | Attachment geometry and singularity avoidance | M24 |
| Dynamic, backdrivable joints | QDD | Current demand and thermal limits | M25 |
| Force sensing and impact compliance | SEA | Force bandwidth and spring calibration | M26 |

## High-value starting sources

- **BOSL2:** parameterized gear geometry; the repository identifies a BSD-2-Clause license. Begin with spur/rack/planetary primitives. Treat bearing and actuator properties as separate inputs. Sources: `bosl`, `boslrepo`.
- **NopSCADlib:** reusable purchased-part geometry and assembly/BOM tools; repository identifies GPL-3.0. Useful for visual interfaces, but no automatic physical validation follows from an available model. Source: `nop`.
- **SO-101:** hardware STEP/STL and a Simulation directory, plus assembly instructions; repository identifies Apache-2.0. Extract the selected arm variant and follower motor configuration, rather than applying one generic servo model. Sources: `so`, `lerobot`.
- **OpenMANIPULATOR-X:** dimensioned small-arm benchmark; published 380 mm reach and 0.5 kg maximum payload. Exact poses, controller behavior and load conditions still matter. Sources: `omx`, `omxmanual`.
- **ODRI:** modular actuator and legged-robot mechanics/electronics under a BSD-3-Clause repository license. Strong reference for torque-controlled actuation. Sources: `odri`, `odripaper`.
- **OpenHand:** useful tendon/flexure ideas and accessible CAD, but the hardware license is CC-BY-NC-3.0. Its noncommercial restriction means it should not be grouped with unrestricted open-source hardware. Sources: `handcad`, `handlicense`.
- **PneuNets toolkit:** includes fabrication/modeling files and an FEM workflow. This is a distinct deformable-body modeling path. Sources: `pneu`, `pneucad`.

Repository license labels were checked where explicitly stated above. Individual third-party assets, commercial CAD downloads, firmware dependencies and redistribution terms were not comprehensively audited. Catalog rows retain unknown license status rather than assume permission.

## Numerical interfaces and limits

Exact component examples are more useful than nominal size labels:

| Selected component | Published dimensions / rating | Remaining issue |
|---|---|---|
| SKF 608-2Z | 8 mm bore × 22 mm outside × 7 mm width | Specify fits and suffix-specific loads/friction |
| 17HS19-2004S1 | 42×42×48 mm body; 5 mm shaft; 24 mm shaft length; 0.390 kg; 0.59 N·m holding torque at 2 A/phase | Running torque follows torque-speed curve and driver conditions |
| XM430-W350 | 28.5×46.5×34 mm; 0.082 kg; 353.5:1; 0.25° backlash; 4.1 N·m stall / 46 rpm no-load at 12 V | These are different operating points; continuous torque not established here |
| Pololu 37D family | Nominal 37 mm family; 12/24 V; 6.3:1–150:1 options; 64 CPR motor-shaft encoder variants | Select exact SKU; motor-shaft CPR is not output resolution |
| MGN12 rail family | Nominal 12 mm rail width | C and H blocks differ; complete drawing required |
| MISUMI 20×20 frame family | Nominal 20×20 mm envelope | Slot profile and T-nut series must match |

Sources: `skf`, `stepper`, `stepcurve`, `dxl`, `pololu`, `hiwin`, `extrusion` in `catalog.json`.

**AR4 conflict:** the FAQ lists 26 inches / 67 cm reach and 0.3 mm repeatability. The V1.5 manual lists 24.75 inches / 62.9 cm reach and 0.2 mm repeatability. This may reflect revisions or documentation inconsistency; the cause was not established. The catalog preserves both and blocks a canonical dimensional interpretation until a specific revision is selected. Sources: `ar4`, `ar4manual`.

## Compiler intermediate representation

Use `physics_ir.schema.json` as a proposed versioned contract, separate from the research catalog. It is a design proposal, not an existing robotics standard or a general compiler implemented here. Every field carrying a measurement should retain provenance/status outside the low-level engine export.

An assembly should have:

- Stable part and link IDs, source URLs, exact revision/commit, asset hashes and license scope.
- Explicit SI physical units, right-handed frames, Z-up world convention, and named attachment frames. Convert design mm to m once at the boundary.
- Geometry recipes for manufactured parts and exact SKU/drawing references for purchased parts. Avoid scaling standardized bearings, screws, motors or interfaces to make assemblies fit.
- Separate visual and collision shapes. Use low-complexity collision primitives/convex pieces where suitable; visual tooth detail is not automatically collision detail.
- Positive mass, COM in link coordinates, symmetric inertia tensor in kg·m², physically realizable principal moments and declared inertia frame.
- Joint origin, unit axis, limits, damping, friction, stiffness where applicable, actuator drive type and limits.
- Transmission ratio/sign, motor-versus-output coordinate convention, efficiency, reflected inertia and backlash. For ratio N=omega_motor/omega_output, reflected motor inertia is N²*J_motor; ideal output torque is N*tau_motor before losses.
- Explicit graph closure, tendon routing, differential constraints and selected assembly branch. Do not flatten a parallel mechanism into an unconnected visual tree.
- Contact material pairs, friction law, restitution/compliance settings, and environment geometry. Engine parameters such as MuJoCo solref/solimp are not interchangeable with material modulus.
- Sensors, noise, latency and sampling rates, separate from geometric depiction.
- Missing-data status: `unknown` / `proposed` / `published` / `measured` / `derived` / `validated`. Unknown physical properties remain unknown, rather than zero.

### Suggested export policy

| Target | Good fit | Limits |
|---|---|---|
| GLB / rendered HTML | Visual review, composition and interface depiction | Does not by itself carry a runnable physical/control model |
| URDF / xacro | Rigid tree descriptions and ROS tooling | Mimic/transmissions/importers vary; closed loops require additional treatment |
| MJCF | Rigid articulation, contact, tendons and explicit equality coupling | Model/solver settings need testing and calibration |
| SDF/Gazebo | Robot plus world/sensor/system description | Joint and plugin behavior depends on engine/version; URDF conversion can lose features |
| FEM model | Large-strain elastomers, flexures, deformation/stress | Requires material laws, meshing and calibrated boundary conditions |

References: `urdf`, `mj`, `mjcomp`, `sdf`, `pneu`. A single universal mesh export should not be treated as equivalent to all these targets.

## Worked compiler example

Files: `example.json`, `compile_example.py`, `example.urdf`, `example.mjcf.xml`, `smoke_sim.py`.

The implemented compiler only handles the proposed parallel gripper in `example.json`. It is deliberately small enough to inspect: two box jaws, a fixed base, two opposite-axis prismatic joints, calculated uniform-box inertias, and equal positive jaw displacements. This is a physics-format demonstrator, not a replica of a commercial gripper or a manufactured assembly.

```sh
python compile_example.py
```

Input geometry uses mm; physical outputs use m, kg and seconds. Jaws are 12×20×60 mm and each travels 25 mm, giving a gap from 10 to 60 mm. Jaw masses of 0.04 kg, damping of 1 N·s/m, joint friction of 0.1 N and contact friction 0.7 are assumptions. The ideal generalized drive-force limit is ±5 N; it is not a validated per-jaw gripping force. URDF specifies a proposed 0.1 m/s limit; the MJCF ideal force actuator does not enforce that velocity limit. These exports are therefore not fully equivalent control models.

The MJCF jaw coordinates are coupled with an equality constraint. The URDF uses mimic metadata; importers may ignore it or require control/physics extensions. The MuJoCo model includes a floor and an open keyframe; it contains no grasped object, sensors, real motor, gearbox, fasteners or rail models. Add those before testing a grasping task.

In an environment with MuJoCo installed:

```sh
python smoke_sim.py
```

The supplied optional check attempts two seconds of opening/closing, checks finite state, approximate joint limits and synchronization. It does not demonstrate physical accuracy. MuJoCo was unavailable in the research environment, so this runtime check was **not executed**. XML parsing, generation consistency, numeric geometry and inertia checks were performed.

## Promote a record into a validated asset

1. Choose one exact design/component revision and intended load case; pin source and hash downloaded assets.
2. Extract geometry, mounting interfaces, masses and material choices from CAD/BOM/datasheets. Mark missing values.
3. Compile frames and kinematics; test limit sweeps, closure residuals, branch changes and collisions.
4. Specify actuator curves and inertia, actual reductions, friction, backlash, power and thermal constraints.
5. Choose contact/deformation fidelity for the task and construct the environment.
6. Execute bounded simulation tests: finite state, energy behavior, constraints, saturation and contact stability; repeat at a smaller timestep to check convergence.
7. Compare relevant physical tests: no-load motion, step response, known-load deflection, grasp/push forces or wheel slip. Store measured versus predicted error and acceptance tolerances.

A visually successful motion sequence is a useful preview. It is not a substitute for these validation stages.

## First implementation backlog

Start with M01 spur gears, M05 rack/pinion, M08 belt axis, M09 screw axis, M11 parallelogram, M13 parallel jaws, M20 differential drive and M22 SCARA. These cover reduction, rotary/linear transmission, open and closed kinematics, contact and locomotion without beginning with large-strain materials or detailed gear contacts.

Then add tendon routing, planetary coupling, motor/current models, QDD and mecanum contact. Keep soft actuators, strain-wave cup stress, granular jamming and six-strut platforms as separate advanced workstreams.

For each primitive, acceptance should include: deterministic geometry from parameters; dimensionally correct interfaces; separated visual/collision assets; reproducible SI physics export; source provenance; and explicit unresolved data. This creates a reusable robotics vocabulary that can evolve from depiction to kinematics to calibrated dynamics without implying that one automatically supplies the next.
