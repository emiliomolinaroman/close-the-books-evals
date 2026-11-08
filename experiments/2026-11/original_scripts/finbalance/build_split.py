import json, random, os, shutil
SRC='data/finbalance/repo/data'
OUT='work'
KEEP_META=['period_label','entity_name','currency_code','currency_symbol','functional_currency_code','date_format','tax_regime','tax_label']
def strip(r):
    return {'record_id':r['record_id'],'industry':r['industry'],'difficulty_level':r['difficulty_level'],
            'period_start':r['period_start'],'period_end':r['period_end'],'opening_balance':r['opening_balance'],
            'allowed_accounts':r['allowed_accounts'],
            'context':{k:r['metadata'].get(k) for k in KEEP_META},
            'documents':[{k:d.get(k) for k in ('doc_id','doc_type','title','date','ocr_text')} for d in r['documents']]}
def answer(r):
    return {'has_inconsistency':r['expected_inconsistency'],'inconsistency_codes':r['expected_inconsistency_codes'],
            'inconsistency_notes':r.get('inconsistency_reasons',[]),
            'entries':[{k:e[k] for k in ('doc_refs','debit_account','credit_account','amount')} for e in r['expected_entries']],
            'balance_sheet':{k:r['expected_balance_sheet'].get(k,{}) for k in ('assets','liabilities','equity')}}
main=[json.loads(l) for l in open(f'{SRC}/main/records.jsonl')]
rng=random.Random(7)
# estratificado: por nivel y por consistencia
rng.shuffle(main)
cons=[r for r in main if not r['expected_inconsistency']]; inc=[r for r in main if r['expected_inconsistency']]
def pick(lst,n,used):
    out=[];
    bylvl={}
    for r in lst:
        if r['record_id'] in used: continue
        bylvl.setdefault(r['difficulty_level'],[]).append(r)
    i=0
    while len(out)<n:
        for l in sorted(bylvl):
            if bylvl[l] and len(out)<n: out.append(bylvl[l].pop())
    used.update(x['record_id'] for x in out); return out
used=set()
ejemplos=pick(cons,24,used)+pick(inc,6,used)
publico=pick(cons,45,used)+pick(inc,15,used)
rng.shuffle(ejemplos); rng.shuffle(publico)
oculto=[json.loads(l) for l in open(f'{SRC}/fresh_seed_20260712/coverage/records.jsonl')]
D=f'{OUT}/fb_datos'; K=f'{OUT}/_claves_fb'
os.makedirs(D,exist_ok=True); os.makedirs(K,exist_ok=True)
with open(f'{D}/ejemplos_resueltos.jsonl','w') as f:
    for r in ejemplos:
        x=strip(r); x['respuesta_correcta']=answer(r); f.write(json.dumps(x,ensure_ascii=False)+'\n')
with open(f'{D}/publico.jsonl','w') as f:
    for r in publico: f.write(json.dumps(strip(r),ensure_ascii=False)+'\n')
os.makedirs(f'{OUT}/fb_oculto',exist_ok=True)
with open(f'{OUT}/fb_oculto/records.jsonl','w') as f:
    for r in oculto: f.write(json.dumps(strip(r),ensure_ascii=False)+'\n')
json.dump({r['record_id']:answer(r) for r in publico},open(f'{K}/publico.json','w'))
json.dump({r['record_id']:answer(r) for r in oculto},open(f'{K}/oculto.json','w'))
print(len(ejemplos),len(publico),len(oculto), sum(r['expected_inconsistency'] for r in oculto))

# --- anonymise hidden ids (the original ids reveal the contradiction code) ---
recs=[json.loads(l) for l in open(f'{OUT}/fb_oculto/records.jsonl')]
key=json.load(open(f'{K}/oculto.json')); nk={}
with open(f'{OUT}/fb_oculto/records.jsonl','w') as f:
    for i,r in enumerate(recs):
        new=f'H{i:03d}'; nk[new]=key[r['record_id']]; r['record_id']=new; f.write(json.dumps(r,ensure_ascii=False)+'\n')
json.dump(nk,open(f'{K}/oculto.json','w'))
# --- second hidden set: 150 packets from the fresh-seed main split ---
recs=[json.loads(l) for l in open(f'{SRC}/fresh_seed_20260712/main/records.jsonl')]
rng=random.Random(2026); rng.shuffle(recs)
sel=[r for r in recs if not r['expected_inconsistency']][:120]+[r for r in recs if r['expected_inconsistency']][:30]; rng.shuffle(sel)
os.makedirs(f'{OUT}/fb_oculto2',exist_ok=True); k2={}
with open(f'{OUT}/fb_oculto2/records.jsonl','w') as f:
    for i,r in enumerate(sel):
        x=strip(r); x['record_id']=f'Q{i:03d}'; k2[x['record_id']]=answer(r); f.write(json.dumps(x,ensure_ascii=False)+'\n')
json.dump(k2,open(f'{K}/oculto2.json','w'))
shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)),'score.py'),f'{OUT}/score_fb.py')
print('hidden sets ready')
