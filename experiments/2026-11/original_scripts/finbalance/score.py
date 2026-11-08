#!/usr/bin/env python3
"""Puntua FinBalance. Uso:
  python3 score_fb.py publico <predicciones.json>
  python3 score_fb.py oculto <run.py>        (ejecuta run.py sobre el oculto, sin red, 600 s)
"""
import json, os, sys, subprocess, tempfile, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
def secs(bs):
    bs=bs or {}
    return {s:{k:round(float(v),2) for k,v in (bs.get(s) or {}).items() if abs(float(v))>0.01} for s in ('assets','liabilities','equity')}
def bs_eq(a,b):
    a,b=secs(a),secs(b)
    for s in a:
        if set(a[s])!=set(b[s]): return False
        if any(abs(a[s][k]-b[s][k])>0.01 for k in a[s]): return False
    return True
def ekey(e,refs):
    k=(e.get('debit_account'),e.get('credit_account'),int(round(float(e.get('amount',0))*100)))
    return k+((tuple(sorted(e.get('doc_refs') or [])),) if refs else ())
def match(exp,pred,refs):
    rem=[ekey(e,refs) for e in exp]; tp=0
    for p in pred:
        try: k=ekey(p,refs)
        except Exception: continue
        if k in rem: rem.remove(k); tp+=1
    return tp
def score(pred,key):
    n=len(key); c={'registros':n,'sin_respuesta':0,'ok_global':0,'limpios':0,'bs_exact':0,'asientos_exactos':0,'asientos_laxos':0,
       'falsas_alarmas':0,'inconsistentes':0,'incons_marcadas':0,'incons_codigo_ok':0,'tp_lax':0,'tp_strict':0,'n_exp':0,'n_pred':0}
    for rid,k in key.items():
        p=pred.get(rid)
        if not isinstance(p,dict): c['sin_respuesta']+=1; p={}
        flag=bool(p.get('has_inconsistency'))
        if k['has_inconsistency']:
            c['inconsistentes']+=1
            if flag: c['incons_marcadas']+=1
            if flag and set(p.get('inconsistency_codes') or [])==set(k['inconsistency_codes']):
                c['incons_codigo_ok']+=1; c['ok_global']+=1
        else:
            c['limpios']+=1
            if flag: c['falsas_alarmas']+=1
            ents=p.get('entries') or []
            if not isinstance(ents,list): ents=[]
            ents=[e for e in ents if isinstance(e,dict)]
            tl=match(k['entries'],ents,False); ts=match(k['entries'],ents,True)
            c['tp_lax']+=tl; c['tp_strict']+=ts; c['n_exp']+=len(k['entries']); c['n_pred']+=len(ents)
            if tl==len(k['entries'])==len(ents): c['asientos_laxos']+=1
            if ts==len(k['entries'])==len(ents): c['asientos_exactos']+=1
            if bs_eq(k['balance_sheet'],p.get('balance_sheet')) and not flag:
                c['bs_exact']+=1; c['ok_global']+=1
    f1=lambda tp: round(2*tp/(c['n_exp']+c['n_pred']),3) if c['n_exp']+c['n_pred'] else 0
    return {'acierto_global':round(c['ok_global']/n,3),'bs_exact':round(c['bs_exact']/max(1,c['limpios']),3),
            'asientos_f1_laxo':f1(c['tp_lax']),'asientos_f1_estricto':f1(c['tp_strict']),
            'registros_asientos_laxos_ok':round(c['asientos_laxos']/max(1,c['limpios']),3),
            'incons_deteccion':round(c['incons_marcadas']/max(1,c['inconsistentes']),3),
            'incons_codigo':round(c['incons_codigo_ok']/max(1,c['inconsistentes']),3),
            'falsas_alarmas':c['falsas_alarmas'],'sin_respuesta':c['sin_respuesta']}
SITE="import socket\ndef _b(*a,**k): raise OSError('red bloqueada')\nsocket.socket=_b\nsocket.create_connection=_b\nsocket.getaddrinfo=_b\n"
def main():
    modo=sys.argv[1]
    if modo=='publico':
        key=json.load(open(os.path.join(HERE,'_claves_fb','publico.json')))
        pred=json.load(open(sys.argv[2])); print(json.dumps(score(pred,key))); return
    nombre=modo  # oculto | oculto2
    key=json.load(open(os.path.join(HERE,'_claves_fb',nombre+'.json')))
    run=os.path.abspath(sys.argv[2]); base=tempfile.mkdtemp(prefix='fbo_')
    shutil.copy(os.path.join(HERE,'fb_'+nombre,'records.jsonl'),os.path.join(base,'records.jsonl'))
    os.makedirs(os.path.join(base,'_site')); open(os.path.join(base,'_site','sitecustomize.py'),'w').write(SITE)
    env=dict(os.environ); env['PYTHONPATH']=os.path.join(base,'_site')
    err=''
    try:
        cp=subprocess.run([sys.executable,run,os.path.join(base,'records.jsonl'),os.path.join(base,'pred.json')],cwd=os.path.dirname(run),env=env,capture_output=True,timeout=600)
        if cp.returncode: err=cp.stderr.decode('utf-8','replace')[-400:]
    except subprocess.TimeoutExpired: err='timeout'
    try: pred=json.load(open(os.path.join(base,'pred.json')))
    except Exception as e: pred={}; err+=' | sin salida: '+str(e)
    r=score(pred,key); r['error']=err; print(json.dumps(r,ensure_ascii=False)); shutil.rmtree(base,ignore_errors=True)
main()
