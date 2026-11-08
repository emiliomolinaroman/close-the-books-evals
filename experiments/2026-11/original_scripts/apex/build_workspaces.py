import os, shutil, glob, json
T='data/apex-accounting-harbor/tasks'; W='data/apex_world'
OUT='work'; PL='scaffold'
G={'G1':[14,6,5,4,26],'G2':[23,13,17,7,30]}
dirs={int(d.split('-')[3]):d for d in os.listdir(T)}
os.makedirs(f'{OUT}/_claves_apex',exist_ok=True)
for n,d in dirs.items():
    shutil.copy(f'{T}/{d}/tests/grading_config.json',f'{OUT}/_claves_apex/T{n}_rubrica.json')
    shutil.copy(f'{T}/{d}/tests/golden_reference.txt',f'{OUT}/_claves_apex/T{n}_oro.txt')
enun=open(f'{OUT}/ENUNCIADO_APEX.md').read()
for g,ts in G.items():
    for arm in 'AB':
        w=f'{OUT}/apex_{g}_{arm}'
        if os.path.exists(w): shutil.rmtree(w)
        shutil.copytree(W,f'{w}/mundo',ignore=shutil.ignore_patterns('_apps'))
        shutil.copytree(f'{W}/_apps/quickbooks',f'{w}/mundo/quickbooks_app')
        for n in ts:
            d=dirs[n]; td=f'{w}/tareas/T{n}'; os.makedirs(td)
            ins=open(f'{T}/{d}/instruction.md').read()
            ins=ins.split('\n---\n',1)[1].strip() if '\n---\n' in ins else ins
            open(f'{td}/ENCARGO.md','w').write(ins+'\n')
            fs=f'{T}/{d}/environment/task_files/filesystem'
            if os.path.isdir(fs): shutil.copytree(fs,f'{td}/archivos')
        os.makedirs(f'{w}/salida')
        shutil.copy(f'{OUT}/ENUNCIADO_APEX.md',w)
        if arm=='B':
            for x in os.listdir(PL):
                if x=='_versiones': continue
                s=f'{PL}/{x}'
                (shutil.copytree if os.path.isdir(s) else shutil.copy)(s,f'{w}/{x}')
for arm in ('A1','A2','B1','B2'):
    w=f'{OUT}/fb_{arm}'
    if os.path.exists(w): shutil.rmtree(w)
    shutil.copytree(f'{OUT}/fb_datos',f'{w}/datos'); os.makedirs(f'{w}/salida'); shutil.copy(f'{OUT}/ENUNCIADO_FB.md',w)
    if arm[0]=='B':
        for x in os.listdir(PL):
            if x=='_versiones': continue
            s=f'{PL}/{x}'
            (shutil.copytree if os.path.isdir(s) else shutil.copy)(s,f'{w}/{x}')
print('ok')
