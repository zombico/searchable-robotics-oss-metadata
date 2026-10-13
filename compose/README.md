# Composer: build a robot from catalog parts and prove it can do the task

The composer answers one question: **can a robot assembled from the parts and principles in this repository accomplish a task, and which assembly is best?** It does this in four steps, and every number it uses is traceable to the task file, a catalog record (with that value's verification level) or a named assumption.

1. **Turn the task into requirements.** From `tasks/pick/task.json`: the heaviest, most slippery box (0.3 kg, friction 0.3) needs at least 8.9 N of squeeze per jaw. The formula is `safety factor × mass × (g + lift acceleration) / (2 × friction)`. The widest box needs 50 mm of opening; the jaws must close in 0.6 s; the lift axis must carry the extra weight.
2. **Propose designs from the catalog.** v0 explores the jaw drive: a smart servo from `electronics/` driving a gear (pinion) between two racks, one on each jaw (catalog M05), with the jaws from catalog M13, on a 12 V supply. Bigger gears trade force for speed.
3. **Screen each design before simulating.** Is the servo rated for the supply voltage? Does its published torque at that voltage give enough squeeze through this gear? Does it close fast enough? Can the lift carry it? Does the supply cover it? Missing data gives `undetermined`, never a pass.
4. **Simulate the survivors** on the same 300 boxes (same sizes, weights, friction and sensor noise for every design), then rank them and list the parts.

```sh
python compose/pick_gripper.py --screen-only   # steps 1-3, no simulator needed
python compose/pick_gripper.py                 # all four steps; writes compose/reports/pick_gripper_v0.{md,json}
```

## What v0 found

Full report: [`reports/pick_gripper_v0.md`](reports/pick_gripper_v0.md).

- **The original example gripper is too weak.** Its 5 N drive gives about 2.5 N per jaw against the 8.9 N needed. In simulation it dropped 39 of 300 boxes, all heavy and slippery.
- **The simple friction formula predicts the simulator.** Applied to each box with no safety factor, it agreed with the simulated outcome 97.3% of the time. It never predicted a hold that then slipped; it was cautious on 8 boxes that held.
- **Screening rejects designs for stated reasons:**
  - a 12-tooth gear closes too slowly (0.87 s) and is below the 17-tooth limit where gear teeth get undercut;
  - the 7.4 V STS3215 servo is not rated for a 12 V supply;
  - the 12 V STS3215 is `undetermined` because its mass is unpublished and its other values come only from search results.
- **The DYNAMIXEL XM430 designs pick every box (300 of 300)** with 20-, 30- and 40-tooth gears. The 40-tooth gear ranks first because it closes fastest. Holding the grip needs about 0.4 N·m, roughly 0.2 A or 2.7 W at 12 V (a linear estimate between published points).

## What the composer could not settle, and says so

**Impact force.** A geared servo behaves as if its jaw weighed kilograms, because the motor's rotor inertia is multiplied by the square of the gear reduction. When the jaws hit the box, that momentum briefly squeezes far harder than the 17.7 N current limit: 45–380 N in simulation. How hard depends on the rotor inertia, which ROBOTIS does not publish. The composer therefore simulates every servo design at two assumed rotor inertias a decade apart and reports:

- **Robust to the unknown:** picking success (100% at both values).
- **Depends on the unknown:** peak impact force. Fragile objects would need that value, or a slow-approach strategy.

**Modelling notes.**
- Servos are modelled the way smart servos are usually run: speed-commanded, with a current limit that caps force. The torque–speed line comes from the published stall torque and no-load speed at 12 V.
- Without the reflected rotor inertia, this stiff motor line on a 40 g jaw made the simulation unstable, and an implicit integrator gave physically wrong results. Adding the physically real inertia fixed both.

## Not claimed

- A built gripper.
- Continuous torque or thermal limits (unpublished).
- Backlash, rack friction and compliance.
- Packaging: a 40-tooth gear is 40 mm across, and fit in the 100 × 50 mm base is not checked.
- Gentle handling.
- Accuracy of MuJoCo contact for real materials.

Feasible here means feasible in simulation under the stated assumptions.

## Extending it

- **Add parts:** a researched servo in `electronics/components.json` becomes a candidate by adding its ID to `ASSUMPTIONS['servo_candidates']`.
- **Next design axes:** the lift and x axes (lead screw vs belt vs rack), then mechanism choice for the jaws themselves.
- **Each new axis** follows the same pattern: requirement formula, screening checks with unknowns kept unknown, then paired simulation.
