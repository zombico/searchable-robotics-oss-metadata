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
    'STS3215 (7.4 V)': ('E03', 'integrated_unit', 'odm_module', None, 'feetech_sts3215', 'Sold in several gear-ratio/voltage builds; SO-101 kits mix ratios per joint.'),
    'STS3215 (12 V)': ('E04', 'integrated_unit', 'odm_module', None, 'feetech_sts3215', 'Sold in several gear-ratio/voltage builds; SO-101 kits mix ratios per joint.'),
    'TMC2209': ('E10', 'ic', 'oem', None, None, 'IC ratings; StepStick-style modules from many makers derate current for their sense resistors and cooling.'),
    'DRV8825': ('E11', 'ic', 'oem', None, None, 'IC ratings; carrier boards set current limit and cooling.'),
    'moteus r4.11': ('E12', 'board', 'open_hardware', 'C11', None, None),
    'ODrive S1': ('E13', 'board', 'oem', None, None, None),
    'U2D2': ('E20', 'board', 'oem', None, None, None),
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
}

def convert(entry):
    if entry['field'] not in RENAME: return dict(entry)
    field, unit, fn = RENAME[entry['field']]
    out = dict(entry, field=field, value=fn(entry['value'], entry['unit']), unit=unit)
    out['original'] = {'field': entry['field'], 'value': entry['value'], 'unit': entry['unit']}
    return out

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
        for c in data['components']:
            if c['part_number'] not in META: raise SystemExit(f"no reviewed META row for {c['part_number']} ({path.name})")
            cid, level, sourcing, record, mount, note = META[c['part_number']]
            specs = [convert(s) for s in c['specs']]
            if c['part_number'] == 'AS5600': specs = merge_modes(specs, 'supply_voltage_V')
            if mount: specs.append({'field': 'mechanical_interface', 'value': mount, 'unit': None, 'conditions': 'label assigned by this catalog for mount-pattern comparison',
                                    'source_id': 'e_catalog_label', 'quote': 'catalog-assigned label, not a manufacturer term', 'verification': 'catalog_assigned'})
            components.append({'id': cid, 'name': c['name'], 'manufacturer': c['manufacturer'], 'part_number': c['part_number'],
                               'interface': c['interface'], 'level': level, 'sourcing': sourcing, 'catalog_record': record,
                               'variant_note': c.get('variant_note'), 'note': note, 'specs': specs,
                               'unresolved': c.get('unresolved', []), 'research_file': f'research/{path.name}'})
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
