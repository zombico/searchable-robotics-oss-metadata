"""Build electronics/components.json from the raw research files in electronics/research/.

Research files keep what the researcher recorded (field names, units, quotes, verification).
This script only renames fields to the interfaces.json vocabulary, converts units, merges
disjoint operating modes, and attaches reviewed metadata (ID, level, sourcing, catalog link).
Converted entries keep their original field/value/unit. Any part without a META row fails the build.
"""
import json, pathlib, re

HERE = pathlib.Path(__file__).resolve().parent

# part_number -> (id, level, sourcing, catalog_record, mechanical_interface or None, note)
META = {
    'XM430-W350-T': ('E01', 'integrated_unit', 'oem', 'C03', 'dynamixel_x430', None),
    'XM430-W350-R': ('E02', 'integrated_unit', 'oem', 'C03', 'dynamixel_x430', None),
    'STS3215 (ST-3215-C001 / C044 / C046)': ('E03', 'integrated_unit', 'odm_module', None, 'feetech_sts3215',
        'C001 (1/345) only: the SO-101 follower gearing. Leader-arm C044 (1/191) and C046 (1/147) builds are separate variants not modeled here.'),
    'STS3215 12 V (ST-3215-C018)': ('E04', 'integrated_unit', 'odm_module', None, 'feetech_sts3215', 'Optional higher-torque SO-101 follower servo.'),
    'TMC2209': ('E10', 'ic', 'oem', None, None, 'IC ratings; StepStick-style modules from many makers derate current for their sense resistors and cooling.'),
    'DRV8825': ('E11', 'ic', 'oem', None, None, 'IC ratings; carrier boards set current limit and cooling.'),
    'moteus r4.11': ('E12', 'board', 'open_hardware', 'C11', None, None),
    'ODrive S1': ('E13', 'board', 'oem', None, None, None),
    'U2D2': ('E20', 'board', 'oem', None, None, None),
    '4035': ('E14', 'board', 'oem', 'C04', None, 'Pololu DRV8874 single brushed DC motor driver carrier, chosen for the 37D gearmotor class.'),
    'AS5048A': ('E30', 'ic', 'oem', 'C09', None, 'Bare IC; breakout boards add a regulator and connector.'),
    'AS5600': ('E31', 'ic', 'oem', None, None, 'Bare IC; widely sold on generic ODM breakouts.'),
    'AS5047P': ('E32', 'ic', 'oem', None, None, None),
    'AMT102-V': ('E33', 'integrated_unit', 'oem', None, 'amt10_shaft_adapter', None),
    'BMI088': ('E34', 'ic', 'oem', 'C10', None, None),
    'ICM-42688-P': ('E35', 'ic', 'oem', None, None, None),
    'INA226': ('E36', 'ic', 'oem', None, None, None),
    'HX711': ('E37', 'ic', 'oem', None, None, 'Generic ODM breakouts often fix RATE at 10 Hz.'),
    'ISO 11898-1:2015 (CAN FD)': ('E50', 'standard', 'standard', None, None, None),
    'DYNAMIXEL Protocol 2.0': ('E51', 'standard', 'standard', None, None, None),
    'Feetech SCS/STS protocol (SCServo)': ('E52', 'standard', 'standard', None, None, 'No Feetech-hosted specification was reachable; see verification levels.'),
    'EtherCAT': ('E53', 'standard', 'standard', None, None, None),
    'TCAN1042-Q1': ('E54', 'ic', 'oem', None, None, None),
    'MCP2562FD': ('E55', 'ic', 'oem', None, None, None),
    'RP2040': ('E60', 'ic', 'oem', None, None, None),
    'RP2350': ('E61', 'ic', 'oem', None, None, None),
    'STM32G474 (RE)': ('E62', 'ic', 'oem', None, None, None),
    'ESP32-S3': ('E63', 'ic', 'oem', None, None, None),
    'Teensy 4.1': ('E64', 'board', 'oem', None, None, None),
    'D36V50F6': ('E70', 'module', 'oem', None, None, None),
    'SO-101 arm power supply (per SO-ARM100 BOM / README)': ('E71', 'module', 'odm_module', None, None, 'Generic adapter linked from the BOM; only the voltage is stated.'),
    'SO-101 arm power supply (per SO-ARM100 BOM / README) 12 V': ('E72', 'module', 'odm_module', None, None, 'Requirement stated by the README, not a specific product.'),
    'ISO 13850:2015': ('E80', 'standard', 'standard', None, None, None),
    'IEC 60204-1': ('E81', 'standard', 'standard', None, None, None),
}

def span(text):
    """'4.5 to 5.5' -> [4.5, 5.5]"""
    a, b = re.fullmatch(r'\s*([\d.]+)\s*to\s*([\d.]+)\s*', text).groups()
    return [float(a), float(b)]

# research field -> (interfaces.json field, unit, converter)
RENAME = {
    'max_clock': ('clock_max_MHz', 'MHz', lambda v, u: v),
    'supply_voltage_range': ('supply_voltage_V', 'V', lambda v, u: span(v)),
    'input_voltage_range': ('input_voltage_V', 'V', lambda v, u: span(v)),
    'output_voltage': ('output_voltage_V', 'V', lambda v, u: v),
    'output_current_typical_max': ('output_current_A', 'A', lambda v, u: v),
    'max_data_rate': ('data_rate_max_bps', 'bit/s', lambda v, u: v * 1e6 if u == 'Mbit/s' else v),
    'ppr_options': ('ppr', 'PPR', lambda v, u: v),
    'current_loop_rate_hz': ('control_rate_hz', 'Hz', lambda v, u: v),
    # 60 deg = 1/6 rev, so rpm = 60 / (6 * seconds per 60 deg)
    'no_load_speed_s_per_60deg': ('no_load_speed_rpm', 'rpm', lambda v, u: round(10 / v, 3)),
}

def convert(entry):
    if entry['field'] not in RENAME: return dict(entry)
    field, unit, fn = RENAME[entry['field']]
    out = dict(entry, field=field, value=fn(entry['value'], entry['unit']), unit=unit)
    out['original'] = {'field': entry['field'], 'value': entry['value'], 'unit': entry['unit']}
    return out

VOLTAGE_DEPENDENT = {'stall_torque_Nm', 'no_load_speed_rpm', 'stall_current_A', 'no_load_current_A'}

def tag_voltage(entry):
    """Voltage-dependent ratings record the supply voltage they were published at ('at 12.0 V', '@ 6 V')."""
    if entry['field'] in VOLTAGE_DEPENDENT:
        m = re.search(r'(?:\bat|@)\s*([\d.]+)\s*V\b', (entry.get('conditions') or '') + ' ' + entry['quote'])
        entry['at_voltage_V'] = float(m.group(1)) if m else None
    return entry

def split(c):
    """Research records that mix variants become one record per modeled variant."""
    pn = c['part_number'] or c['name']
    if pn.startswith('STS3215 (ST-3215-C001'):
        keep = [s for s in c['specs'] if s['field'] not in ('so101_leader_joint_map', 'so101_follower_gearing')
                and not (s['field'] == 'gear_ratio' and s['value'] != 345)]
        return [dict(c, part_number=pn, name='Feetech STS3215 C001 smart servo (7.4 V, 1/345)', specs=keep)]
    if pn.startswith('SO-101 arm power supply'):
        five = [s for s in c['specs'] if s['field'] == 'output_voltage_V' and s['value'] == 5]
        twelve = [s for s in c['specs'] if not (s['field'] == 'output_voltage_V' and s['value'] == 5)]
        return [dict(c, part_number=pn, name='SO-101 5 V supply (BOM default; current rating not stated)', specs=five,
                     unresolved=c.get('unresolved', []) + ['current_continuous_A of the 5 V BOM supply']),
                dict(c, part_number=pn + ' 12 V', name='SO-101 12 V supply option (README minimum "12V 5A+")', specs=twelve)]
    return [dict(c, part_number=pn)]

def merge_modes(specs, field):
    """Same-source entries for distinct operating modes become one list of ranges, not a conflict."""
    group = [s for s in specs if s['field'] == field]
    if len(group) < 2 or len({s['source_id'] for s in group}) != 1: return specs
    merged = dict(group[0], value=[s['value'] for s in group],
                  conditions=' | '.join(s.get('conditions') or '' for s in group),
                  quote=' | '.join(s['quote'] for s in group))
    return [s for s in specs if s['field'] != field] + [merged]

def build():
    sources, components = {}, []
    for path in sorted((HERE / 'research').glob('*.json')):
        data = json.loads(path.read_text())
        for sid, src in data['sources'].items():
            if sid in sources and sources[sid] != src: raise SystemExit(f'source id clash: {sid}')
            sources[sid] = src
        for c in (v for raw in data['components'] for v in split(raw)):
            if c['part_number'] not in META: raise SystemExit(f"no reviewed META row for {c['part_number']} ({path.name})")
            cid, level, sourcing, record, mount, note = META[c['part_number']]
            specs = [tag_voltage(convert(s)) for s in c['specs']]
            if c['part_number'] == 'AS5600': specs = merge_modes(specs, 'supply_voltage_V')
            if mount: specs.append({'field': 'mechanical_interface', 'value': mount, 'unit': None, 'conditions': 'label assigned by this catalog for mount-pattern comparison',
                                    'source_id': 'e_catalog_label', 'quote': 'catalog-assigned label, not a manufacturer term', 'verification': 'catalog_assigned'})
            components.append({'id': cid, 'name': c['name'], 'manufacturer': c['manufacturer'], 'part_number': c['part_number'],
                               'interface': c['interface'], 'level': level, 'sourcing': sourcing, 'catalog_record': record,
                               'variant_note': c.get('variant_note'), 'note': note, 'specs': specs,
                               'unresolved': c.get('unresolved', []), 'research_file': f'electronics/research/{path.name}'})
    missing = set(META) - {c['part_number'] for c in components}
    if missing: raise SystemExit(f'META rows without research: {sorted(missing)}')
    sources['e_catalog_label'] = {'title': 'Catalog-assigned mechanical interface label', 'url': 'electronics/build_components.py',
                                  'publisher_type': 'catalog', 'accessed_on': None}
    components.sort(key=lambda c: c['id'])
    out = {'schema_version': '0.1.0', 'generated_by': 'electronics/build_components.py',
           'verification_levels': {'fetched_primary': 'Manufacturer/standards text fetched (including manufacturer PDFs mirrored on GitHub, pinned by commit).',
                                   'fetched_secondary': 'Distributor, community or third-party packaging fetched.',
                                   'search_snippet': 'Seen only in a search-result summary; treat as unverified.',
                                   'catalog_assigned': 'Label assigned by this catalog for comparison (e.g. mount pattern); not a published value.'},
           'sources': dict(sorted(sources.items())), 'components': components}
    (HERE / 'components.json').write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    return out

if __name__ == '__main__':
    out = build(); specs = [s for c in out['components'] for s in c['specs']]
    counts = {k: sum(s['verification'] == k for s in specs) for k in out['verification_levels']}
    print(f"Built {len(out['components'])} components, {len(out['sources'])} sources, {len(specs)} spec values: {counts}")
