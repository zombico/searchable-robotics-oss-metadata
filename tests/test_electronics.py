import copy,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'electronics'))
import swap
INTERFACES,CATALOG=swap.load()
VERIFICATION={'fetched_primary','fetched_secondary','search_snippet','catalog_assigned'}

def part(id,**specs):
    return {'id':id,'name':id,'interface':'actuator.smart_servo','specs':[
        {'field':k,'value':v,'unit':None,'source_id':'t','verification':'fetched_primary'} for k,v in specs.items()]}
BASE=dict(supply_voltage_V=[6,12],stall_torque_Nm=3.0,no_load_speed_rpm=50,bus_physical='ttl_half_duplex',protocol='p1',
          mechanical_interface='m1',position_resolution_counts=4096,gear_ratio=300,mass_kg=0.06)
SLOT={'slot_id':'j1','interface':'actuator.smart_servo','requirements':{'supply_voltage_V':12,'stall_torque_Nm':2.0,
      'no_load_speed_rpm':40,'bus_physical':'ttl_half_duplex','protocol':'p1','mechanical_interface':'m1'}}

class SwapRules(unittest.TestCase):
    def check(self,**changes):
        return swap.check(SLOT,part('cand',**{**BASE,**changes}),part('bound',**BASE),INTERFACES)
    def test_identical_is_drop_in(self): self.assertEqual(self.check()['classification'],'drop_in')
    def test_sim_difference_is_retune(self):
        r=self.check(stall_torque_Nm=4.0);self.assertEqual(r['classification'],'retune')
    def test_protocol_is_rewire(self): self.assertEqual(self.check(protocol='p2')['classification'],'rewire')
    def test_mount_is_remount(self): self.assertEqual(self.check(mechanical_interface='m2')['classification'],'remount')
    def test_voltage_outside_range_is_incompatible(self): self.assertEqual(self.check(supply_voltage_V=[6,8.4])['classification'],'incompatible')
    def test_disjoint_supply_modes(self):
        self.assertTrue(swap.passes('requirement_within_range',[[3.0,3.6],[4.5,5.5]],5.0))
        self.assertFalse(swap.passes('requirement_within_range',[[3.0,3.6],[4.5,5.5]],4.0))
    def test_weak_servo_is_incompatible(self): self.assertEqual(self.check(stall_torque_Nm=1.0)['classification'],'incompatible')
    def test_worst_consequence_wins(self): self.assertEqual(self.check(protocol='p2',mechanical_interface='m2')['classification'],'remount')
    def test_missing_value_is_undetermined_not_pass(self):
        c=part('cand',**{k:v for k,v in BASE.items() if k!='stall_torque_Nm'})
        r=swap.check(SLOT,c,part('bound',**BASE),INTERFACES)
        self.assertEqual(r['classification'],'undetermined');self.assertIn('stall_torque_Nm',r['unknown'])
    def test_conflicting_sources_are_not_trusted(self):
        c=part('cand',**BASE);c['specs'].append({'field':'stall_torque_Nm','value':2.5,'unit':None,'source_id':'u','verification':'fetched_primary'})
        r=swap.check(SLOT,c,part('bound',**BASE),INTERFACES)
        self.assertIn('stall_torque_Nm',r['conflicting']);self.assertEqual(r['classification'],'undetermined')
    def test_missing_value_does_not_hide_definite_rewire(self):
        c=part('cand',**{**{k:v for k,v in BASE.items() if k!='mass_kg'},'protocol':'p2'})
        self.assertEqual(swap.check(SLOT,c,part('bound',**BASE),INTERFACES)['classification'],'rewire')
    def test_wrong_interface_is_incompatible(self):
        c=part('cand',**BASE);c['interface']='sensor.imu'
        self.assertEqual(swap.check(SLOT,c,None,INTERFACES)['classification'],'incompatible')
    def test_search_snippet_values_are_flagged(self):
        c=part('cand',**BASE);c['specs'][1]['verification']='search_snippet'
        self.assertIn('stall_torque_Nm',swap.check(SLOT,c,part('bound',**BASE),INTERFACES)['search_snippet_only'])
    def test_torque_speed_line(self):
        p=swap.solver_parameters(part('x',**BASE))
        self.assertEqual(p['forcerange_Nm'],[-3.0,3.0]);self.assertAlmostEqual(p['torque_speed_slope_Nm_s_rad'],-3.0/(50*swap.RPM))

def source(id,limit):
    return {'id':id,'name':id,'interface':'power.source','specs':[{'field':'current_continuous_A','value':limit,'unit':'A','source_id':'t','verification':'fetched_primary'}]}
def with_current(p,amps):
    p=copy.deepcopy(p);p['specs'].append({'field':'stall_current_A','value':amps,'unit':'A','source_id':'t','verification':'fetched_primary'});return p
def rig(limit,currents,declared=None):
    parts={f's{i}':with_current(part(f's{i}',**BASE),a) if a is not None else part(f's{i}',**BASE) for i,a in enumerate(currents)}
    parts['psu']=source('psu',limit)
    slots=[{**SLOT,'slot_id':f'j{i}','bound_component':f's{i}'} for i in range(len(currents))]
    if declared: slots[declared[0]]['declared_current_A']={'value':declared[1],'status':'proposed'}
    return {'slots':slots,'rails':[{'rail_id':'12V','voltage_V':12,'source_component':'psu','loads':[s['slot_id'] for s in slots]}]},parts

class RailBudget(unittest.TestCase):
    def test_within(self):
        b,p=rig(5,[2,2]);r=swap.rail_budget(b,p)[0]
        self.assertEqual((r['status'],r['worst_case_total_A'],r['headroom_A']),('within_budget',4,1))
    def test_over(self): b,p=rig(5,[3,3]);self.assertEqual(swap.rail_budget(b,p)[0]['status'],'over_budget')
    def test_unknown_load_is_undetermined(self):
        b,p=rig(5,[2,None]);r=swap.rail_budget(b,p)[0]
        self.assertEqual((r['status'],r['unknown_loads']),('undetermined',['j1']))
    def test_known_overload_is_definite_despite_unknowns(self):
        b,p=rig(5,[6,None]);self.assertEqual(swap.rail_budget(b,p)[0]['status'],'over_budget')
    def test_declared_current_is_reported_as_assumption(self):
        b,p=rig(5,[2,None],declared=(1,1.5));r=swap.rail_budget(b,p)[0]
        self.assertEqual((r['status'],r['assumed_loads']),('within_budget',['j1']))
    def test_swap_that_overloads_rail_is_incompatible(self):
        b,p=rig(5,[2,2]);strong=with_current(part('strong',**BASE),4)
        r=swap.check(b['slots'][1],strong,p['s1'],INTERFACES,b,p)
        self.assertEqual(r['classification'],'incompatible');self.assertEqual(r['findings'][-1]['field'],'rail_budget')
    def test_swap_with_unknown_current_is_undetermined(self):
        b,p=rig(5,[2,2]);r=swap.check(b['slots'][1],part('mystery',**BASE),p['s1'],INTERFACES,b,p)
        self.assertEqual(r['classification'],'undetermined');self.assertIn('rail_budget (12V)',r['unknown'])

class CatalogIntegrity(unittest.TestCase):
    def test_components(self):
        ids=[c['id'] for c in CATALOG['components']];self.assertEqual(len(ids),len(set(ids)))
        for c in CATALOG['components']:
            self.assertIn(c['interface'],INTERFACES,c['id'])
            self.assertIn(c['level'],{'ic','module','integrated_unit','board','standard'},c['id'])
            self.assertIn(c['sourcing'],{'oem','odm_module','open_hardware','standard'},c['id'])
            for s in c['specs']:
                self.assertIn(s['source_id'],CATALOG['sources'],c['id']);self.assertIn(s['verification'],VERIFICATION,c['id'])
                self.assertTrue(s.get('quote'),f"{c['id']} {s['field']} needs a supporting quote")
    def test_catalog_links(self):
        records={r['id'] for r in json.loads((ROOT/'catalog.json').read_text())['records']}
        for c in CATALOG['components']:
            if c.get('catalog_record'): self.assertIn(c['catalog_record'],records)
    def test_bindings_reference_known_fields_and_parts(self):
        ids={c['id'] for c in CATALOG['components']}
        for path in (ROOT/'electronics/bindings').glob('*.json'):
            for slot in json.loads(path.read_text())['slots']:
                fields=INTERFACES[slot['interface']]['fields']
                self.assertTrue(set(slot['requirements'])<=set(fields),f'{path.name} {slot["slot_id"]}')
                self.assertIn(slot['bound_component'],ids)
if __name__=='__main__':unittest.main()
