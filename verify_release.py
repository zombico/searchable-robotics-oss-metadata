"""Minimal semantic checks, not full schema validation or physics validation."""
import hashlib,json,math,pathlib,sys

def require(ok,msg):
    if not ok: raise ValueError(msg)
def number(x): return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def vector(v,n): return isinstance(v,list) and len(v)==n and all(number(x) for x in v)
def digest(s): return isinstance(s,str) and len(s)==64 and all(x in '0123456789abcdef' for x in s)

def validate_episode(e):
    require(e['schema_version']=='0.2.0','schema version')
    require(e['origin'] in ['contract_fixture','forward_simulation','state_playback','real_recording'],'origin')
    require(e['split'] in ['train','validation','test'] and bool(e['episode_id']) and bool(e['leakage_group']),'IDs/split')
    m=e['manifest'];c=m['clock'];a=m['action_contract'];o=m['observation_contract']
    require(number(c['physics_dt_s']) and c['physics_dt_s']>0,'physics dt')
    require(type(c['control_decimation']) is int and c['control_decimation']>0,'decimation')
    dt=c['physics_dt_s']*c['control_decimation']
    require(number(c['control_hz']) and math.isclose(c['control_hz'],1/dt,rel_tol=1e-9),'clock mismatch')
    require(digest(m['asset_sha256']) and type(m['seed']) is int,'hash/seed')
    require(all(m['engine'].get(k) for k in ['name','version','runtime_scope']),'engine identity')
    if e['origin']=='forward_simulation': require(m['engine']['name']!='not_run' and m['asset_sha256']!='0'*64,'forward simulation needs engine/asset')
    require(a['mode']=='joint_force' and a['unit']=='N' and a['frame']=='joint','action semantics')
    require(a['dimension']==1 and a['hold']=='zero_order' and bool(a['controller_id']),'controller contract')
    require(number(a['lower']) and number(a['upper']) and a['lower']<a['upper'],'action limits')
    require(o['policy_channels']==['qpos'] and isinstance(o['privileged_channels'],list) and 'qpos' not in o['privileged_channels'],'observation contract')
    def obs(d,t):
        require(set(d)=={'qpos'},'undeclared or privileged policy channel')
        q=d['qpos'];require(vector(q['value'],2) and q['unit']=='m','qpos')
        require(number(q['capture_t_s']) and number(q['release_t_s']),'sensor times')
        require(q['capture_t_s']<=q['release_t_s']<=t+1e-9,'future sensor leakage')
        require(q['release_t_s']>=t-dt-1e-9,'stale sensor for this contract')
    require(bool(e['transitions']),'empty episode');previous=None
    for i,tr in enumerate(e['transitions']):
        t=tr['t_s'];nt=tr['next_t_s']
        require(number(t) and number(nt) and t>=0 and math.isclose(nt-t,dt,rel_tol=1e-8,abs_tol=1e-9),'transition timing')
        if previous is not None: require(math.isclose(t,previous,abs_tol=1e-9),'noncontiguous transition')
        require(vector(tr['action'],1) and a['lower']<=tr['action'][0]<=a['upper'],'action outside contract')
        obs(tr['observation'],t);obs(tr['next_observation'],nt)
        require(type(tr['terminated']) is bool and type(tr['truncated']) is bool,'terminal flags')
        require(tr['outcome'] in ['ongoing','success','slip','miss','collision','timeout'],'outcome')
        if i<len(e['transitions'])-1: require(not tr['terminated'] and not tr['truncated'],'transition after terminal')
        previous=nt
    return {'status':'contract_pass','origin':e['origin'],'transitions':len(e['transitions']),'physics_validated':False}

def validate_split_groups(episodes):
    seen=set();groups={}
    for e in episodes:
        require(e['episode_id'] not in seen,'duplicate episode ID');seen.add(e['episode_id'])
        require(groups.setdefault(e['leakage_group'],e['split'])==e['split'],'split leakage')

def validate_release(r,base):
    require(r['schema_version']=='0.2.0','release schema')
    level=r['qualification'];require(level in ['synthetic_only','engine_checked','calibrated_envelope','transfer_tested'],'qualification')
    require(type(r['accuracy_claim']) is bool,'accuracy claim type')
    if r['accuracy_claim']: require(level in ['calibrated_envelope','transfer_tested'],'accuracy claim without calibration')
    require(isinstance(r['evidence'],list),'evidence list');kinds=set()
    for ev in r['evidence']:
        p=(base/ev['path']).resolve()
        require(p.is_relative_to(base.resolve()) and p.is_file(),'missing or outside evidence')
        require(digest(ev['sha256']) and hashlib.sha256(p.read_bytes()).hexdigest()==ev['sha256'],'evidence hash mismatch')
        kinds.add(ev['kind'])
    if level!='synthetic_only': require({'engine_report','replay_report','convergence_report'}<=kinds,'missing engine evidence')
    if level in ['calibrated_envelope','transfer_tested']:
        require({'raw_measurements','calibration_report','heldout_report'}<=kinds,'missing calibration evidence')
        require(bool(r['operating_envelope']) and bool(r['metrics']),'missing envelope/metrics')
        for m in r['metrics']:
            require(m['dataset_role']=='heldout' and bool(m['unit']) and bool(m['name']),'metric provenance')
            require(number(m['value']) and number(m['acceptance_max']) and m['value']<=m['acceptance_max'],'metric exceeds threshold')
    if level=='transfer_tested': require('real_policy_evaluation' in kinds,'missing real evaluation')
    return {'status':'declaration_pass','qualification':level,'experiment_authenticity_verified':False}

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: python verify_release.py episode_or_release.json')
    p=pathlib.Path(sys.argv[1]);d=json.loads(p.read_text())
    try: print(json.dumps(validate_episode(d) if 'transitions' in d else validate_release(d,p.parent)))
    except (ValueError,KeyError,TypeError) as ex:
        print('FAIL: '+str(ex),file=sys.stderr);raise SystemExit(1)
