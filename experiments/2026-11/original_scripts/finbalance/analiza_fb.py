import json,sys,subprocess,os,tempfile,collections
sys.argv=[sys.argv[0]]+sys.argv[1:]
ids=json.load(open('_claves_fb/oculto_ids.json'))
orig={json.loads(l)['record_id']:json.loads(l) for l in open('data/finbalance/repo/data/fresh_seed_20260712/coverage/records.jsonl')}
key=json.load(open('_claves_fb/oculto.json'))
exec(open('score_fb.py').read().split('SITE=')[0])
for team in sys.argv[1:]:
    out=tempfile.mktemp(suffix='.json')
    subprocess.run([sys.executable,f'{team}/run.py','fb_oculto/records.jsonl',out],capture_output=True,timeout=600)
    pred=json.load(open(out))
    fails=collections.Counter(); tot=collections.Counter(); misscodes=[]
    for rid,k in key.items():
        o=orig[ids[rid]]; m=o['metadata']
        feats=[f for f in ('has_asc606','has_asset_disposal','has_deferred_tax','has_lease','has_tax_exemption') if m.get(f)]
        if m.get('functional_currency_code')!=m.get('currency_code') or any('fx' in s for s in m.get('scenario_sequence',[])): feats.append('fx')
        if k['has_inconsistency']: feats=['NEG']
        tag=','.join(feats) or 'basico'
        tot[tag]+=1
        r=score({rid:pred.get(rid)},{rid:k})
        if r['acierto_global']<1:
            fails[tag]+=1
            if k['has_inconsistency']: misscodes.append((k['inconsistency_codes'],(pred.get(rid) or {}).get('inconsistency_codes')))
    print(team, {t:f"{fails[t]}/{tot[t]}" for t in sorted(tot)})
    print('  codigos fallados', misscodes)
