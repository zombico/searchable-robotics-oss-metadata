# Electronics: swappable components and interfaces

The mechanical catalog (`catalog.json`) describes what moves. This concern describes what drives, senses, carries signals and supplies power: the parts that set the solver's actuator limits, sensor clocks, noise, quantization, latency and supply budget. It is kept separate because the same mechanism can be built with very different electronics, and because electronics are where OEM, ODM and open-hardware parts get substituted most often.

Research date: 13 October 2026. This is a starter set of 34 parts, protocols, standards and supplies (280 values: 161 from fetched manufacturer or standards text, 22 secondary, 92 search-snippet only, 5 catalog labels). It is not an exhaustive or purchasing-grade library. Most vendor sites were unreachable from the research environment, which is why so many values are search-only; re-verifying those is the most useful next contribution.

## Files

| File | Purpose |
|---|---|
| `interfaces.json` | Slot contracts: each interface's fields, the compatibility rule for each field, what a failure means, and how the field maps into simulation |
| `components.json` | Generated. Parts implementing those interfaces, with per-value source, quote and verification level |
| `research/*.json` | Raw research records, as collected |
| `build_components.py` | Normalizes research into `components.json`; every part needs a reviewed metadata row |
| `bindings/*.json` | Example assemblies: slots, the part bound to each, and supply rails |
| `swap.py` | Swap checker and static rail budget |

## Swap consequences

A candidate part is checked against a slot's requirements and against the part currently bound there. The worst consequence across fields decides the result:

| Result | Meaning |
|---|---|
| `drop_in` | Same interface, connection, mount and simulation-facing values |
| `retune` | Fits, but simulation-facing values differ: regenerate the model and requalify (release level reverts to `synthetic_only`) |
| `rewire` | Bus, protocol, connector or command interface differs: adapter, firmware or driver change, then retune |
| `remount` | Mechanical interface differs: the mechanical layer changes too |
| `incompatible` | A hard electrical or performance requirement fails, including overloading the shared supply rail |
| `undetermined` | A clean or retune-only result that depends on missing or conflicting data. Missing data never counts as a pass |

Definite failures are still reported when other values are missing: an unknown mass does not hide a protocol mismatch.

## Provenance

Every value carries a source, a short supporting quote and a verification level:

- `fetched_primary`: manufacturer or standards text was fetched. Several manufacturer PDFs were unreachable directly and were read from GitHub mirrors; those sources name the mirror and pin its commit.
- `fetched_secondary`: distributor, community or third-party packaging.
- `search_snippet`: seen only in a search-result summary. The swap report lists checks that rely on such values.
- `catalog_assigned`: labels this catalog assigns for comparison, such as mount-pattern names.

Where sources disagree, or a value depends on conditions (for example encoder maximum speed per resolution setting), both values are kept and the checker reports the field as conflicting rather than choosing one.

Chip ratings are not board ratings. A driver IC's datasheet current is not the current of an ODM breakout built around it, which depends on its sense resistor, copper and cooling. Parts are tagged with `level` (`ic`, `module`, `board`, `integrated_unit`, `standard`) and `sourcing` (`oem`, `odm_module`, `open_hardware`, `standard`) so that a slot bound to a module is not silently satisfied by an IC-level figure.

Voltage matters. Servo stall torque, no-load speed and stall current are published per supply voltage (an XM430-W350 is 3.8, 4.1 or 4.8 N·m at 11.1, 12 or 14.8 V). The checker uses only values published at the slot's supply voltage; a rating at another voltage, or at an unstated one, is unknown rather than reused.

## Worked example: SO-101 follower arm

`bindings/so101_follower.json` is the default build (six STS3215 C001 servos, 5 V supply); `bindings/so101_follower_12v.json` is the README's 12 V servo option. What the checker reports, from published data only:

- **Default 5 V build:** a retailer lists the 7.4 V STS3215's operating range as 6–7.4 V (search snippet), while the SO-ARM100 README powers it from 5 V and notes torque is "likely slightly less for a 5V power supply". The checker flags the supply as out of range and marks that flag search-only. No stall torque, speed or current is published at 5 V, so the solver cannot be parameterized for this build from datasheets; it needs measurement. The BOM's 5 V adapter has no stated current rating, so its rail budget is undetermined.
- **12 V option:** six servos at 2.7 A stall is 16.2 A worst case against the README's "12V 5A+" minimum. All six stalling at once is the conservative bound, not a typical load, but it shows the supply is not sized for it.
- **Swapping a 12 V STS3215 for a DYNAMIXEL XM430-W350-T:** `remount` (different mount), which also implies `rewire` (Protocol 2.0 vs Feetech protocol) and `retune` (4.1 vs 2.94 N·m and 46 vs 45 rpm at 12 V). The rail warning shows the worst case going from 16.2 to 15.8 A.

## Power: what is and is not provable

`python electronics/swap.py BINDING.json --budget` sums every load's published worst-case current on each rail (actuators at stall, all at once) and compares it with the rail source's continuous rating. That is a conservative static bound computed from datasheets. A load without a published worst-case current makes its rail `undetermined`, unless the binding declares a proposed current for that slot; declared values are reported as assumptions.

Not covered yet: dynamic current, inrush, regeneration, voltage sag, conversion efficiency, and battery capacity as a function of discharge rate and temperature. Those need per-episode power traces from the engine (planned with episode recording), and agreement with real hardware needs measured current, for example from an INA226 on the supply during the M1 motion tests. Release levels apply: a declared budget is L0, engine power traces checked against limits are L1, measured current within stated error is L2.

## Usage

```sh
python electronics/build_components.py
python electronics/swap.py electronics/bindings/so101_follower_12v.json --audit
python electronics/swap.py electronics/bindings/so101_follower_12v.json --budget
python electronics/swap.py electronics/bindings/so101_follower_12v.json shoulder_lift
python electronics/swap.py electronics/bindings/so101_follower_12v.json shoulder_lift E01
python -m unittest tests.test_electronics -v
```
