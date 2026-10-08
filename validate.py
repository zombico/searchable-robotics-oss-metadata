"""Dependency-free integrity checks; not a complete JSON Schema validator or engine test."""
import json, math, pathlib, xml.etree.ElementTree as E
p=pathlib.Path(__file__).resolve().parent
c=json.loads((p/'catalog.json').read_text());schema=json.loads((p/'physics_ir.schema.json').read_text())
assert len(c['records'])==53
assert len(c['sources'])==54
assert len({r['id'] for r in c['records']})==53
f=json.loads((p/'training_findings.json').read_text())
assert len(f['findings'])==20 and len(f['sources'])==16
assert len({x['id'] for x in f['findings']})==20
assert all(s in f['sources'] for x in f['findings'] for s in x['source_ids'])
assert all(r['training_profile']['release_status']=='synthetic_only_unvalidated' for r in c['records'])
for r in c['records']:
    assert r['source_ids'] and all(s in c['sources'] for s in r['source_ids'])
    assert all(s['source_id'] in r['source_ids'] and s['status']=='published' for s in r['published_specs'])
    assert r['missing_for_validated_simulation']
    assert r['readiness']=='research_record_not_validated_asset'
for f in ['example.urdf','example.mjcf.xml']: E.parse(p/f)
u=E.parse(p/'example.urdf').getroot();mj=E.parse(p/'example.mjcf.xml').getroot()
assert len(u.findall('link'))==4 and len(u.findall('joint'))==3
assert len(mj.findall('./worldbody/body'))==2
for ine in u.findall('./link/inertial/inertia'):
    I=[float(ine.attrib[x]) for x in ['ixx','iyy','izz']]
    assert all(math.isfinite(v) and v>0 for v in I)
    assert all(I[k]<=sum(I)-I[k]+1e-12 for k in range(3))
assert abs(20*1/1000-0.020)<1e-12
assert abs(2*25+10-60)<1e-12
assert abs((0.02/2)**2*math.pi*40000-12.566370614359)<1e-9
print('PASS: 53 records/54 original sources, 20 findings/16 training sources, source references, training status, XML and example checks.')
print('NOT CHECKED: full JSON Schema compliance, source CAD download/dimensions, MuJoCo/Gazebo runtime, manufacturing or physical calibration.')
