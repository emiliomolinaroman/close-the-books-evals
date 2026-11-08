"""Lectura robusta de datos de cierre (genérico, sin nada del reto). Copiar a src/ y usar desde load.py.

Por qué existe: en las simulaciones, 2 de 3 equipos sacaron F1 = 0 en un benchmark oculto porque los CSV venían en cp1252
y su run.py se cayó al leerlos. Un fallo de lectura no puede tumbar la entrega.
"""
import csv, io, json, os, re, unicodedata
from datetime import date, datetime

def leer_texto(path):
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else ('utf-8-sig',):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    try:
        return raw.decode('cp1252')
    except UnicodeDecodeError:
        return raw.decode('latin-1')

def norm_col(c):
    c = unicodedata.normalize('NFKD', str(c)).encode('ascii', 'ignore').decode().strip().lower()
    return re.sub(r'[^a-z0-9]+', '_', c).strip('_')

def leer_tabla(path, sheet=None):
    """Devuelve lista de dicts con columnas normalizadas (minúsculas, sin tildes, _). CSV/TSV/TXT, XLSX, JSON, JSONL."""
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.xlsx', '.xlsm'):
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb[sheet] if sheet else wb.worksheets[0]
        rows = [r for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(v not in (None, '') for v in r)]
        h = _fila_cabecera(rows)
        cols = [norm_col(c) if c is not None else f'col{i}' for i, c in enumerate(rows[h])]
        return [dict(zip(cols, r)) for r in rows[h + 1:]]
    txt = leer_texto(path)
    if ext == '.json':
        d = json.loads(txt)
        return d if isinstance(d, list) else d.get(next(iter(d)), d) if isinstance(d, dict) else d
    if ext == '.jsonl':
        return [json.loads(l) for l in txt.splitlines() if l.strip()]
    lines = [l for l in txt.splitlines() if l.strip()]
    muestra = '\n'.join(lines[:50])
    try:
        sep = csv.Sniffer().sniff(muestra, delimiters=';,\t|').delimiter
    except csv.Error:
        sep = max(';,\t|', key=lambda s: muestra.count(s))
    rows = list(csv.reader(io.StringIO('\n'.join(lines)), delimiter=sep))
    h = _fila_cabecera(rows)
    cols = [norm_col(c) or f'col{i}' for i, c in enumerate(rows[h])]
    out = []
    for r in rows[h + 1:]:
        if len(r) < len(cols) // 2:  # filas de página, títulos, subtotales cortos
            continue
        out.append(dict(zip(cols, [x.strip() for x in r])))
    return out

def _fila_cabecera(rows):
    """La cabecera es la primera fila con muchas celdas de texto no numérico (salta títulos de informe)."""
    best, best_i = -1, 0
    for i, r in enumerate(rows[:30]):
        n = sum(1 for v in r if isinstance(v, str) and v.strip() and not re.fullmatch(r'[-+()\d.,\s€%/]+', v.strip()))
        if n > best:
            best, best_i = n, i
    return best_i

def num(x, dec=None):
    """'1.234,56' '1,234.56' '1 234,56' '(123,45)' '123,45-' '€ 12' '12 EUR' -> float. Vacío -> None.
    dec=',' o '.' fuerza el separador decimal (usa detectar_decimal sobre la columna entera para los casos '1.234')."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace('\u00a0', ' ')
    if not s:
        return None
    neg = (s.startswith('(') and s.endswith(')')) or s.endswith('-') or s.startswith('-')
    s = re.sub(r'[^\d.,]', '', s)
    if not s:
        return None
    if dec is None:
        if ',' in s and '.' in s:
            dec = ',' if s.rfind(',') > s.rfind('.') else '.'
        elif s.count(',') > 1:
            dec = '.'
        elif s.count('.') > 1:
            dec = ','
        elif ',' in s:
            dec = '.' if len(s) - s.rfind(',') - 1 == 3 and len(s.split(',')[0]) <= 3 and False else ','
        elif '.' in s:
            dec = '.'
        else:
            dec = '.'
    if dec == ',':
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '')
    v = float(s)
    return -v if neg else v

def detectar_decimal(valores):
    """Mira la columna entera: si algún valor tiene coma seguida de 1-2 dígitos al final, o punto y coma juntos con la coma al final, el decimal es ','."""
    coma = punto = 0
    for v in valores:
        t = re.sub(r'[^\d.,]', '', str(v))
        if re.search(r',\d{1,2}$', t) or (',' in t and '.' in t and t.rfind(',') > t.rfind('.')):
            coma += 1
        elif re.search(r'\.\d{1,2}$', t) or (',' in t and '.' in t and t.rfind('.') > t.rfind(',')):
            punto += 1
    return ',' if coma > punto else '.'

def cents(x):
    v = num(x)
    return None if v is None else int(round(v * 100))

_FMT = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%Y/%m/%d', '%d/%m/%y', '%Y%m%d', '%m/%d/%Y', '%d %b %Y')

def fecha(x, mdy=False):
    """Fechas en cualquier formato habitual. mdy=True si la columna se ha detectado como mes/día (ver detectar_mdy)."""
    if x is None or x == '':
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    s = str(x).strip()[:19].replace('T', ' ').split(' ')[0]
    fmts = ('%m/%d/%Y',) + _FMT if mdy else _FMT
    for f in fmts:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None

def detectar_mdy(valores):
    """True si en una columna de fechas con / el segundo campo pasa de 12 alguna vez (formato US)."""
    for v in valores:
        m = re.match(r'^(\d{1,2})/(\d{1,2})/\d{2,4}$', str(v).strip())
        if m and int(m.group(2)) > 12:
            return True
    return False

def escribir_seguro(salida, nombre, obj):
    os.makedirs(salida, exist_ok=True)
    tmp = os.path.join(salida, nombre + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, os.path.join(salida, nombre))

def run_protegido(main, salida, vacios=(('findings.json', []), ('ajustes.json', []), ('balance.json', {}))):
    """Ejecuta main(); si revienta, deja al menos ficheros válidos (lo ya escrito no se pisa) y el error en log."""
    try:
        main()
    except Exception as e:  # noqa
        import traceback
        os.makedirs(salida, exist_ok=True)
        open(os.path.join(salida, 'run_error.log'), 'w').write(traceback.format_exc())
        for n, v in vacios:
            if not os.path.exists(os.path.join(salida, n)):
                escribir_seguro(salida, n, v)
