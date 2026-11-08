import json,glob,os,subprocess,sys,tempfile
R='work'
exec(open(f'{R}/score_fb.py').read().split('SITE=')[0])
key=json.load(open(f'{R}/_claves_fb/oculto.json')); m=json.load(open('muestra.json'))
k40={r:key[r] for r in m}
pred={}; bad=0
for f in glob.glob('directo_*/salida/*.json'):
    rid=os.path.basename(f)[:-5]
    try: pred[rid]=json.load(open(f))
    except Exception: bad+=1
print('directo', len(pred), 'json malos', bad, json.dumps(score(pred,k40)))
for t in ['fb_A1','fb_A2','fb_B1','fb_B2','fb_C1','fb_C2']:
    out=tempfile.mktemp(suffix='.json')
    subprocess.run([sys.executable,f'{R}/{t}/run.py',f'{R}/fb_oculto/records.jsonl',out],capture_output=True,timeout=600)
    p=json.load(open(out)); print(t, json.dumps(score({r:p.get(r) for r in m},k40)))

# pareado por paquete
import random
def ok(p,k,r): return score({r:p.get(r)},{r:k[r]})['acierto_global']==1
teams={}
for t in ['fb_A1','fb_A2','fb_B1','fb_B2','fb_C1','fb_C2']:
    out=tempfile.mktemp(suffix='.json')
    subprocess.run([sys.executable,f'{R}/{t}/run.py',f'{R}/fb_oculto/records.jsonl',out],capture_output=True,timeout=600)
    teams[t]=json.load(open(out))
d=[ok(pred,k40,r) for r in m]
c=[sum(ok(teams[t],k40,r) for t in teams)/6 for r in m]
print('directo',sum(d)/40,'codigo medio',round(sum(c)/40,3))
print('codigo>directo en',sum(1 for a,b in zip(d,c) if b>0.5 and not a),'directo>codigo en',sum(1 for a,b in zip(d,c) if a and b<0.5))
rng=random.Random(1); diffs=[]
for _ in range(5000):
    idx=[rng.randrange(40) for _ in range(40)]
    diffs.append(sum(c[i]-d[i] for i in idx)/40)
diffs.sort(); print('diferencia media',round(sum(c)/40-sum(d)/40,3),'IC95',round(diffs[125],3),round(diffs[4875],3))
