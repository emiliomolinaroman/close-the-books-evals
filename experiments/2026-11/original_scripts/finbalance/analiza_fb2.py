import json,sys,subprocess,tempfile,collections
ids=json.load(open('_claves_fb/oculto_ids.json'))
orig={json.loads(l)['record_id']:json.loads(l) for l in open('data/finbalance/repo/data/fresh_seed_20260712/coverage/records.jsonl')}
# labels vistos en ejemplos+publico (entrenamiento)
main={json.loads(l)['record_id']:json.loads(l) for l in open('data/finbalance/repo/data/main/records.jsonl')}
seen_ids=[json.loads(l)['record_id'] for l in open('fb_datos/ejemplos_resueltos.jsonl')]
seen_labels=collections.Counter(e['label'] for i in seen_ids for e in main[i]['expected_entries'])
for team in sys.argv[1:]:
    out=tempfile.mktemp(suffix='.json')
    subprocess.run([sys.executable,f'{team}/run.py','fb_oculto/records.jsonl',out],capture_output=True,timeout=600)
    pred=json.load(open(out))
    miss=collections.Counter(); tot=collections.Counter()
    for rid,o in ((r,orig[ids[r]]) for r in ids):
        if o['expected_inconsistency']: continue
        p=(pred.get(rid) or {}).get('entries') or []
        keys=[(e.get('debit_account'),e.get('credit_account'),round(float(e.get('amount',0)),2)) for e in p if isinstance(e,dict)]
        for e in o['expected_entries']:
            tot[e['label']]+=1
            k=(e['debit_account'],e['credit_account'],round(e['amount'],2))
            if k in keys: keys.remove(k)
            else: miss[e['label']]+=1
    print(team, sorted(((l,f"{miss[l]}/{tot[l]}", 'visto' if seen_labels[l] else 'NO VISTO') for l in miss), key=lambda x:-int(x[1].split('/')[0])))
