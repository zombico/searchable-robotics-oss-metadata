"""Rebuild training findings and enrich the catalog. Python standard library only."""
import html,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
S={
 'R01':('MuJoCo system identification','https://github.com/google-deepmind/mujoco/blob/main/python/mujoco/sysid/README.md'),
 'R02':('Contact Models in Robotics: a Comparative Analysis','https://arxiv.org/abs/2304.06372'),
 'R03':('Validating Robotics Simulators on Real-World Impacts','https://arxiv.org/abs/2110.00541'),
 'R04':('MuJoCo Menagerie','https://github.com/google-deepmind/mujoco_menagerie'),
 'R05':('Isaac Lab actuator models','https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.actuators.html'),
 'R06':('robosuite controller semantics','https://robosuite.ai/docs/modules/controllers.html'),
 'R07':('ManiSkill trajectory replay','https://maniskill.readthedocs.io/en/latest/user_guide/datasets/replay.html'),
 'R08':('LeRobotDataset v3','https://huggingface.co/docs/lerobot/main/lerobot-dataset-v3'),
 'R09':('robomimic dataset structure','https://robomimic.github.io/docs/datasets/overview.html'),
 'R10':('MimicGen CoRL paper','https://proceedings.mlr.press/v229/mandlekar23a.html'),
 'R11':('DROID paper','https://arxiv.org/abs/2403.12945'),
 'R12':('Isaac Lab randomization implementation','https://isaac-sim.github.io/IsaacLab/main/_modules/isaaclab/envs/mdp/events.html'),
 'R13':('Isaac Lab cross-engine transfer guidance','https://isaac-sim.github.io/IsaacLab/develop/source/how-to/transfer_policies_between_physx_and_newton.html'),
 'R14':('Isaac Lab sensor scheduling','https://isaac-sim.github.io/IsaacLab/v2.1.1/source/overview/core-concepts/sensors/index.html'),
 'R15':('MuJoCo state and numerical reproducibility','https://mujoco.readthedocs.io/en/3.2.0/computation/index.html'),
 'R16':('robomimic multiple datasets','https://robomimic.github.io/docs/tutorials/multi_dataset_training.html'),
}
F=[]
def add(title,fact,decision,gate,sources):
 F.append({'id':f'F{len(F)+1:02}','title':title,'source_finding':fact,'proposed_solution_change':decision,'verification_gate':gate,'source_ids':sources,'status':'research_synthesis_not_implemented_engine_feature'})
add('Task-bounded physical fidelity','Contact models make different physical and numerical approximations.','Qualify accuracy by interaction, material, load and speed, not by engine name.','Publish an applicability envelope and held-out physical errors.',['R02','R03'])
add('Fit parameters against measured trajectories','MuJoCo sysid fits model parameters using recorded sensor data and bounded optimization.','Add a calibration module with separate fitting and held-out evaluation sequences.','Report baseline versus fitted prediction errors on unseen measurements.',['R01'])
add('Physically realizable inertial estimates','MuJoCo sysid supports physically consistent inertia parameterization.','Fit mass/COM/inertia jointly when observable; retain parameter uncertainty.','Reject nonphysical inertia; examine sensitivity and identification ambiguity.',['R01'])
add('Sensor delay is not joint friction','Sysid distinguishes measurement corrections from physical model parameters.','Model sensor bias/delay independently to avoid fitting timing errors as dynamics.','Validate synchronized timestamps and delay estimates.',['R01'])
add('Asset provenance before reconstruction','Menagerie proposes parameter-provenance grades; its README does not guarantee every model has an assigned grade.','Use native models as comparison baselines; record a published grade only where available.','Record asset revision, parameter origins, unknown grade and unresolved properties.',['R04'])
add('Actuator models need more than joint limits','Isaac Lab exposes several actuator models and separates model limits from solver limits.','Store controller, saturation, delay, motor inertia and speed-dependent behavior.','Step/load sweeps must respect actual driver and continuous limits.',['R05'])
add('Action semantics are part of the environment','robosuite distinguishes action/controller modes and simulation versus policy rates.','Version units, frames, absolute/delta commands, gains, hold rules and action scaling.','Replay the same action under the same controller contract.',['R06'])
add('Action replay and state replay differ','ManiSkill can replay recorded states to recover observations, or replay controls.','Label render-only state playback separately from forward-dynamics rollouts.','Reject state-forced videos as evidence of forward-dynamics accuracy.',['R07'])
add('Synchronization survives dataset export','LeRobot organizes multimodal signals, video and episode metadata.','Use a canonical timed transition record; keep capture/release times and export mappings.','Round-trip timestamps, shapes, units and episode boundaries.',['R08'])
add('Preserve state for debugging','robomimic datasets can store simulator states and environment metadata.','Save state checkpoints and metadata beside policy-visible observations.','Restore a checkpoint under a pinned runtime and compare within tolerance.',['R09','R15'])
add('Demonstration generation needs task structure','MimicGen generates demonstrations by adapting source demonstrations to new scenes.','Track source demo, task phases, object frames, attempts and generator configuration.','Hold out source demonstrations and object families; report generation failures.',['R10'])
add('Scene diversity must be designed','DROID was collected across many real-world scenes and tasks.','Specify object, layout, camera and interaction coverage; do not equate frame count with diversity.','Evaluate on held-out scene/object families rather than adjacent frames.',['R11'])
add('Randomized mass and inertia must agree','Isaac Lab includes mass randomization with inertia recomputation/scaling options.','Sample physically coupled parameters; fixed-geometry mass scaling scales inertia too.','Verify positive inertia and correct COM reference after every sampled reset.',['R12'])
add('Cross-engine comparison is diagnostic','Isaac Lab documents policy transfer between engines and targeted randomization.','Use a second engine only after a pinned nominal baseline; investigate disagreement.','Compare trajectories/events; agreement alone is not physical validation.',['R13'])
add('Sensors have independent clocks','Isaac Lab sensors use their own update periods in simulated time.','Separate physics, controller, camera and sensor rates; record latency and exposure.','Policy observations cannot include measurements released after decision time.',['R14'])
add('Seeds are insufficient for exact replay','MuJoCo documents state, solver warmstart and numerical reproducibility considerations.','Store engine/build/hardware details, full supported state, RNG/controller state and tolerances.','Test continuation; avoid claiming cross-platform bitwise identity.',['R15'])
add('Dataset formats do not fix action mismatch','robomimic multi-dataset training requires compatible observation/action spaces.','Add explicit adapters and loss/units documentation rather than merely convert containers.','Reject incompatible control spaces without a declared tested transform.',['R16','R06'])
add('Visual realism is a separate acceptance track','Dynamics replay and observation extraction can be separate stages in ManiSkill.','Drive rendering from authoritative simulated states; test visual labels/calibration separately.','Check image-depth-pose alignment and distinguish depiction from sensor simulation.',['R07','R14'])
add('Peak and sustained capability need distinct metadata','Actuator implementations include torque/velocity limits and delay models.','Retain peak duration and thermal assumptions; unknown continuous capability blocks that claim.','Bounded-duration load tests and declared actuator envelope.',['R05'])
add('Publication must attach validation evidence','Impact studies compare simulations against measured real-world trajectories.','Create publication levels: synthetic-only, engine-checked, calibrated-envelope, transfer-tested.','No physics-accuracy label without a scoped report and measured evidence.',['R03','R02'])
data={'schema_version':'0.2.0','researched_on':'2026-10-08','sources':{k:{'title':v[0],'url':v[1],'accessed_on':'2026-10-08','revision_pin':None} for k,v in S.items()},'findings':F}
(ROOT/'training_findings.json').write_text(json.dumps(data,indent=2)+'\n')
def table(headers,rows,title,note):
 esc=html.escape
 trs=''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in rows)
 return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+esc(title)+'''</title><style>body{font:15px system-ui;margin:28px;background:#f7f9fc;color:#17283d}input{padding:12px;width:350px;max-width:80vw;margin:16px 0}table{border-collapse:collapse;background:white;min-width:1500px;font-size:13px}th{background:#183454;color:white;position:sticky;top:0;text-align:left}td,th{padding:12px;border-bottom:1px solid #d7e0ec;vertical-align:top;min-width:150px;max-width:300px}tr:nth-child(even){background:#eff4fa}.scroll{overflow:auto;max-height:75vh}a{color:#175fab}header{max-width:1000px;line-height:1.6}</style><header><h1>'''+esc(title)+'</h1><p>'+esc(note)+'''</p></header><input id="q" aria-label="Search" placeholder="Search findings, tasks, components…"><span id="count"></span><div class="scroll"><table><thead><tr>'''+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+trs+'''</tbody></table></div><script>const rows=[...document.querySelectorAll('tbody tr')];function filter(){let q=document.querySelector('#q').value.toLowerCase(),n=0;for(let r of rows){r.hidden=!r.textContent.toLowerCase().includes(q);if(!r.hidden)n++}document.querySelector('#count').textContent=n+' / '+rows.length}document.querySelector('#q').addEventListener('input',filter);filter();</script></html>'''
def refs(ids):return '<br>'.join(f'<a href="{html.escape(S[s][1])}">{html.escape(S[s][0])}</a>' for s in ids)
(ROOT/'training_findings.html').write_text(table(['ID','Finding','Source observation','Solution change','Verification gate','Primary sources'],[[html.escape(f[x]) for x in ['id','title','source_finding','proposed_solution_change','verification_gate']]+[refs(f['source_ids'])] for f in F],'Synthetic robotics training: second research pass','20 findings from 16 primary sources. Source observations are separated from proposed engineering decisions. No new simulator capability is implemented by this research table.'))
c=json.loads((ROOT/'catalog.json').read_text())
for r in c['records']:
 name=r['name'].lower()
 tier='rigid_body'
 if any(x in name for x in ['pneunet','jamming','flexure','strain-wave']):tier='deformable_or_calibrated_surrogate'
 elif any(x in name for x in ['tendon','pulley-tree','four-bar','delta','stewart','planetary']):tier='constrained_multibody'
 task='component interface verification'
 if r['category']=='Mechanism':task='bounded motion/load primitive test'
 if any(x in name for x in ['grip','finger','suction']):task='grasp, slip and release primitives before manipulation'
 if any(x in name for x in ['drive base','mecanum','quadruped','pupper','opencat']):task='traction/slip and locomotion primitives'
 r['training_profile']={'fidelity_class':tier,'first_task':task,'release_status':'synthetic_only_unvalidated','calibration_report':None,'controller_contract':None,'episode_contract':'contracts/episode.schema.json','requirements':['exact_asset_revision','task_and_action_contract','measured_or_declared_parameters','clock_and_sensor_contract','scoped_validation_report']}
c['solution_version']='0.2.0';c['training_research_file']='training_findings.json'
(ROOT/'catalog.json').write_text(json.dumps(c,indent=2)+'\n')
tr=[]
for r in c['records']:
 specs='; '.join(f"{s['name']}: {s['value']} {s['unit']}" for s in r['published_specs']) or 'Not extracted'
 src='<br>'.join(f'<a href="{html.escape(c["sources"][s]["url"])}">{html.escape(c["sources"][s]["title"])}</a>' for s in r['source_ids'])
 vals=[r['id'],r['name'],r['problem_solved'],specs,json.dumps(r['proposed_parameters']),r['physics_representation'],r['training_profile']['fidelity_class'],r['training_profile']['first_task'],r['missing_for_validated_simulation'],r['license_scope']]
 tr.append([html.escape(str(v)) for v in vals]+[src])
(ROOT/'catalog.html').write_text(table(['ID','Asset/mechanism','Problem','Published specs','Proposed parameters','Physics model','Fidelity class','First training task','Unresolved inputs','License scope','Sources'],tr,'Robotics catalog: training-oriented v0.2','53 records. All remain unvalidated research records. Proposed parameters are illustrative choices. The added training profiles define required work, not completed physics validation.'))
print('Built 20 findings / 16 sources; enriched 53 catalog entries.')
