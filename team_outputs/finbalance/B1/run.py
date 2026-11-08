#!/usr/bin/env python3
"""Reto F (FinBalance): paquetes de documentos -> asientos + balance final, o inconsistencia.
Uso: python3 run.py <records.jsonl> <salida.json>
El codigo calcula todo; no hay ids, importes ni nombres de empresa fijos. Solo libreria estandar."""
import json, os, re, sys, traceback
from collections import defaultdict, OrderedDict
from datetime import date, datetime

TOL = 0.011  # un centimo de redondeo

# ----------------------------------------------------------------------------- lectura
def money(v):
    """'$1,234.56' 'EUR 5.817,25' 'GBP 142,02' '$-64.98' '(12.00)' '0.07' -> float o None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(' ', ' ')
    neg = '-' in s or (s.startswith('(') and s.endswith(')'))
    t = re.sub(r'[^\d.,]', '', s)
    if not t or not re.search(r'\d', t):
        return None
    if ',' in t and '.' in t:
        dec = ',' if t.rfind(',') > t.rfind('.') else '.'
    elif t.count(',') > 1:
        dec = '.'
    elif t.count('.') > 1:
        dec = ','
    elif ',' in t:
        dec = ',' if len(t) - t.rfind(',') - 1 != 3 else '.'
    else:
        dec = '.'
    t = t.replace('.', '').replace(',', '.') if dec == ',' else t.replace(',', '')
    try:
        x = float(t)
    except ValueError:
        return None
    return -x if neg else x


def pct(v):
    if v is None:
        return None
    s = str(v)
    x = money(s)
    if x is None:
        return None
    return x / 100.0 if '%' in s or x > 1.0 else x


def r2(x):
    return round(x + 1e-9 if x >= 0 else x - 1e-9, 2)


def parse_date(s, fmt=None):
    if not s:
        return None
    s = str(s).strip()[:10]
    fmts = ['%Y-%m-%d']
    if fmt:
        f = fmt.upper().replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d')
        fmts.insert(0, f)
    fmts += ['%d/%m/%Y', '%m/%d/%Y', '%d.%m.%Y', '%d-%m-%Y']
    for f in fmts:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


ITEM_KEYS = ['Allocated Transaction Price', 'Invoice Line Amount', 'Released This Period', 'Release Pattern',
             'Running Balance', 'Extended Cost', 'Unit Cost', 'Unit Price', 'Ssp Amount', 'System Qty', 'Counted Qty',
             'Document Type', 'Past Due', 'Description', 'Amount', 'Quantity', 'Sku', 'Date', 'Reference', 'Status',
             'Section', 'Account', 'Unit', 'Tenant', 'Customer', 'Current', 'Obligation', 'Rate', 'Tax', 'Batch']


def parse_doc(d):
    """Texto OCR -> campos {clave: [valores]} e items [dict]. Une lineas partidas por el ancho del OCR."""
    raw = [l.rstrip() for l in d.get('ocr_text', '').splitlines()]
    lines = []
    for l in raw:
        if lines and len(lines[-1]) >= 78 and l.strip() and not l.lstrip().startswith('- ') \
                and not re.match(r'^[A-Z][A-Za-z /&\-()]*:\s', l.strip()) and not set(l.strip()) <= set('=-'):
            lines[-1] = lines[-1] + ' ' + l.strip()
        else:
            lines.append(l)
    fields = defaultdict(list)
    items = []
    for l in lines:
        s = l.strip()
        if s.startswith('- '):
            it = {}
            for seg in s[2:].split(' | '):
                seg = seg.strip()
                if not seg:
                    continue
                k = next((k for k in ITEM_KEYS if seg.startswith(k + ' ')), None)
                if k is None:
                    parts = seg.split(' ', 1)
                    k, v = parts[0], parts[1] if len(parts) > 1 else ''
                else:
                    v = seg[len(k) + 1:]
                it[k.lower()] = v.strip()
            items.append(it)
            continue
        m = re.match(r'^([A-Za-z][A-Za-z0-9 /&\-()\']*?):\s*(.*)$', s)
        if m:
            fields[m.group(1).strip().lower()].append(m.group(2).strip())
    return fields, items


class Doc:
    def __init__(self, d, ctx):
        self.id = d['doc_id']
        self.type = d.get('doc_type', '')
        self.text = d.get('ocr_text', '')
        self.f, self.items = parse_doc(d)
        self.date = parse_date(d.get('date'), ctx.get('date_format'))

    def g(self, *keys):
        for k in keys:
            v = self.f.get(k.lower())
            if v and v[0] not in ('', 'None'):
                return v[0]
        return None

    def m(self, *keys):
        v = self.g(*keys)
        return money(v) if v is not None else None

    def all_vals(self, *keys):
        out = []
        for k in keys:
            out += self.f.get(k.lower(), [])
        return out


# ----------------------------------------------------------------------------- cuentas
def acct_section(name, opening):
    for sec in ('assets', 'liabilities', 'equity'):
        if name in opening.get(sec, {}):
            return sec
    n = name.lower()
    if 'accumulated' in n:
        return 'assets'
    if any(w in n for w in ('revenue', 'expense', 'cost of goods', 'gain', 'loss', 'income', 'shrinkage', 'sales returns')):
        return 'pl'
    if any(w in n for w in ('payable', 'accrued', 'unearned', 'deferred revenue', 'liability', 'deposits payable')):
        return 'liabilities'
    if any(w in n for w in ('capital', 'equity', 'retained', 'drawings', 'reserve fund')):
        return 'equity'
    return 'assets'


class Ctx:
    def __init__(self, rec):
        self.rec = rec
        self.allowed = list(rec.get('allowed_accounts', []))
        self.low = {a.lower(): a for a in self.allowed}
        self.c = rec.get('context', {})
        self.regime = (self.c.get('tax_regime') or '').lower()
        self.industry = rec.get('industry', '')

    def has(self, a):
        return a.lower() in self.low

    def pick(self, *cands, default=None):
        for c in cands:
            if c and c.lower() in self.low:
                return self.low[c.lower()]
        return default if default is not None else (cands[0] if cands else None)

    def find_in(self, text, kind='expense'):
        """Cuenta permitida cuyo nombre aparece literalmente en un texto (la mas larga)."""
        t = (text or '').lower()
        best = None
        for a in self.allowed:
            al = a.lower()
            if kind and kind not in al:
                continue
            if al in t and (best is None or len(al) > len(best)):
                best = a
        if best is None and kind == 'expense':
            # 'repairs expense' -> 'Repairs Expense' ; 'repairs' -> 'Repairs Expense'
            for a in self.allowed:
                al = a.lower()
                if al.endswith(' expense'):
                    stem = al[:-8]
                    if re.search(r'\b' + re.escape(stem) + r'\b', t):
                        if best is None or len(al) > len(best):
                            best = a
        return best

    # cuentas tipicas
    def revenue(self):
        if self.industry in ('manufacturing', 'wholesale_distribution', 'retail'):
            return self.pick('Sales Revenue', 'Service Revenue', 'Revenue')
        return self.pick('Service Revenue', 'Sales Revenue', 'Revenue')

    def inventory(self):
        if self.industry == 'manufacturing':
            return self.pick('Raw Materials Inventory', 'Inventory')
        return self.pick('Inventory', 'Merchandise Inventory', 'Raw Materials Inventory', 'Supplies Inventory',
                         'Medical Supplies', 'Office Supplies')

    def fg_inventory(self):
        return self.pick('Finished Goods Inventory', 'Inventory')

    def out_tax(self):
        return self.pick('Sales Tax Payable', 'VAT Payable', 'GST Payable', 'Output Tax Payable')

    def in_tax(self):
        return self.pick('Input Tax Receivable', 'VAT Receivable', 'GST Receivable')

    def unearned(self):
        return self.pick('Unearned Revenue', 'Deferred Revenue', 'Contract Liability')

    def fixed_asset(self):
        return self.pick('Equipment', 'Store Fixtures', 'Furniture and Fixtures', 'Property and Equipment',
                         'Vehicles', 'Medical Equipment', 'Furniture')

    def fee_expense(self):
        c = self.pick('Bank Fees Expense', 'Bank Fees', 'Merchant Fees Expense', 'Card Processing Fees',
                      'Processing Fees Expense', 'Bank Charges', default='')
        if c and self.has(c):
            return c
        skip = ('salaries', 'payroll', 'depreciation', 'interest', 'cost of goods', 'shrinkage', 'bad debt', 'tax',
                'rent', 'insurance', 'amortization', 'loss', 'utilities')
        for a in self.allowed:
            al = a.lower()
            if al.endswith('expense') and not any(s in al for s in skip):
                return a
        return self.pick('Maintenance Expense')


# ----------------------------------------------------------------------------- motor
class Packet:
    def __init__(self, rec):
        self.rec = rec
        self.cx = Ctx(rec)
        ctx = rec.get('context', {})
        self.docs = [Doc(d, ctx) for d in rec.get('documents', [])]
        self.byid = {d.id: d for d in self.docs}
        self.entries = []
        self.issues = []  # (code, note)
        self.used = set()
        self.ps = parse_date(rec.get('period_start'))
        self.pe = parse_date(rec.get('period_end'))

    # -------- utilidades
    def post(self, refs, dr, cr, amt, tag=None):
        if amt is None:
            return
        amt = r2(amt)
        if abs(amt) < 0.005:
            return
        if amt < 0:
            dr, cr, amt = cr, dr, -amt
        refs = [r for i, r in enumerate(refs) if r and r not in refs[:i]]
        self.entries.append({'doc_refs': refs, 'debit_account': dr, 'credit_account': cr, 'amount': amt})

    def flag(self, code, note):
        if code not in [c for c, _ in self.issues]:
            self.issues.append((code, note))

    def of(self, *types):
        return [d for d in self.docs if d.type in types]

    def ids_of(self, d):
        """Identificadores propios del documento: campos '... Number' / '... ID' / 'Shipment Ref'."""
        out = []
        for k, vals in d.f.items():
            if k in ('account number', 'terminal id', 'batch id', 'note reference', 'tax id'):
                continue
            if re.search(r'(number|\bid)$', k) or k in ('shipment ref',):
                out += vals
        return [o for o in out if o]

    def ref_index(self):
        idx = defaultdict(list)
        for d in self.docs:
            for i in self.ids_of(d):
                idx[i].append(d)
        return idx

    # -------- importes de una factura
    def inv_amounts(self, d):
        lines = [money(it.get('amount')) for it in d.items if it.get('amount') is not None]
        lines = [x for x in lines if x is not None]
        line_sum = r2(sum(lines)) if lines else None
        sub = d.m('subtotal')
        tax = d.m('tax amount') or 0.0
        total = d.m('total', 'invoice total', 'total amount')
        if sub is None:
            if line_sum is not None:
                sub = line_sum
            elif total is not None:
                sub = r2(total - tax)
        if total is None and sub is not None:
            total = r2(sub + tax)
        return sub, tax, total, line_sum

    def check_invoice(self, d):
        sub, tax, total, line_sum = self.inv_amounts(d)
        has_sub = d.m('subtotal') is not None
        has_total = d.m('total', 'invoice total', 'total amount') is not None
        rate = pct(d.g('tax rate'))
        if line_sum is not None and has_sub and abs(line_sum - d.m('subtotal')) > TOL:
            self.flag('invoice_total_mismatch', f'{d.id}: line items {line_sum} vs subtotal {d.m("subtotal")}')
        if line_sum is not None and has_total and not has_sub and d.m('tax amount') is None \
                and abs(line_sum - total) > TOL:
            self.flag('invoice_total_mismatch', f'{d.id}: line items {line_sum} vs total {total}')
        if has_sub and has_total and d.m('tax amount') is not None and abs(r2(sub + tax) - total) > TOL:
            # total por encima de subtotal+impuesto: total de factura inflado; por debajo: cuadre fiscal roto
            code = 'invoice_total_mismatch' if total > sub + tax else 'tax_total_mismatch'
            self.flag(code, f'{d.id}: subtotal {sub} + tax {tax} != total {total}')
        if rate is not None and has_sub and d.m('tax amount') is not None and abs(sub * rate - tax) > 0.0151:
            self.flag('tax_rate_mismatch', f'{d.id}: {sub} x {rate} != tax {tax}')

    # -------- tasa / jurisdiccion
    def gst_split(self, tax, counter_docs, doc=None, base=None, rate=None):
        """India GST: CGST+SGST mismo estado, IGST distinto estado. Usa los importes visibles si los hay."""
        if doc is not None:
            c, s_, i = doc.m('cgst amount'), doc.m('sgst amount'), doc.m('igst amount')
            if c is not None or s_ is not None:
                return [('C', c or 0.0), ('S', s_ if s_ is not None else r2(tax - (c or 0)))]
            if i is not None:
                return [('I', i)]
        same = True
        for d in counter_docs:
            t = d.text.lower()
            ss = d.g('same state')
            if ss is not None:
                same = ss.strip().lower().startswith('t') or ss.strip().lower().startswith('y')
            elif 'igst' in t and 'cgst' not in t:
                same = False
            elif 'different-state' in t or 'inter-state' in t or 'interstate' in t:
                same = False
            cj, pj = d.g('company jurisdiction'), d.g('counterparty jurisdiction', 'customer jurisdiction',
                                                       'supplier jurisdiction', 'vendor jurisdiction')
            if cj and pj and ss is None:
                same = cj.strip().lower() == pj.strip().lower()
        if same:
            c = r2(base * rate / 2) if base and rate else r2(int(round(tax * 100)) // 2 / 100.0)
            return [('C', c), ('S', r2(tax - c))]
        return [('I', tax)]

    def notes_for(self, d, tax):
        """Avisos de regimen fiscal que soportan este documento (por referencia o por importe de impuesto)."""
        out = []
        ids = self.ids_of(d)
        for n in self.of('tax_regime_notice'):
            refv = n.all_vals('reference', 'invoice reference', 'document reference')
            ja = n.m('jurisdiction tax amount', 'tax amount')
            if any(r in ids for r in refv) or (tax and ja is not None and abs(ja - tax) <= TOL):
                out.append(n)
        return out

    def is_india(self, rel_docs):
        if self.cx.regime == 'india_gst':
            return True
        for d in rel_docs:
            r = (d.g('tax regime') or '').lower()
            if 'india' in r:
                return True
            if 'india gst' in (d.g('tax label') or '').lower():
                return True
        return False

    def is_us_sales_tax(self, rel_docs):
        if self.cx.regime == 'us_sales_tax':
            return True
        for d in rel_docs:
            r = (d.g('tax regime') or '').lower()
            if r == 'us_sales_tax':
                return True
        return False

    # -------- proceso principal
    def run(self):
        cx = self.cx
        idx = self.ref_index()
        docs = self.docs
        # documentos que no se contabilizan: copias, cancelados
        withdrawn = set()
        for d in self.of('cancellation_note'):
            for w in d.all_vals('withdrawn reference', 'cancelled reference', 'voided reference'):
                withdrawn.add(w)
        skip = set()
        for d in docs:
            if d.type in ('secondary_copy',):
                skip.add(d.id)
            if any(i in withdrawn for i in self.ids_of(d)):
                skip.add(d.id)
        # duplicados: misma referencia y mismo tipo
        seen = {}
        for d in docs:
            if d.id in skip or d.type in ('opening_trial_balance', 'memo', 'bank_statement'):
                continue
            key = None
            num = d.g('invoice number', 'roll number', 'receipt number', 'advice number', 'remittance number')
            if num:
                key = (d.type, num)
            if key:
                if key in seen:
                    o = seen[key]
                    a1 = self.inv_amounts(o)[2] if 'invoice' in d.type else o.m('amount', 'paid amount')
                    a2 = self.inv_amounts(d)[2] if 'invoice' in d.type else d.m('amount', 'paid amount')
                    if a1 is not None and a2 is not None and abs(a1 - a2) > TOL:
                        self.flag('duplicate_reference_conflict', f'{o.id} and {d.id} share {num} with totals {a1} vs {a2}')
                    skip.add(d.id)
                else:
                    seen[key] = d
        # secondary copy con importe distinto -> conflicto
        for d in self.of('secondary_copy'):
            src = d.g('source reference')
            tot = d.m('total', 'amount', 'invoice total')
            st = (d.g('status') or '').lower()
            if src and src in idx and tot is not None:
                for o in idx[src]:
                    if o.type == 'secondary_copy':
                        continue
                    ot = self.inv_amounts(o)[2] if 'invoice' in o.type else o.m('amount')
                    if ot is not None and abs(ot - tot) > TOL:
                        self.flag('duplicate_reference_conflict', f'{d.id} copy of {src} shows {tot} vs {ot}')
        self.skip = skip
        live = [d for d in docs if d.id not in skip]
        self.live = live
        self.idx = idx

        handlers = HANDLERS
        for d in live:
            h = handlers.get(d.type)
            if h is None:
                continue
            try:
                h(self, d)
            except Exception:
                if os.environ.get('FB_DEBUG'):
                    traceback.print_exc()
        try:
            self.bank_unbooked()
        except Exception:
            if os.environ.get('FB_DEBUG'):
                traceback.print_exc()
        try:
            self.global_checks()
        except Exception:
            if os.environ.get('FB_DEBUG'):
                traceback.print_exc()

    def asset_account(self, d):
        """Cuenta del activo: la que nombra el documento, la del saldo inicial que indica la etiqueta OPEN-XXX, o la generica."""
        cx = self.cx
        for k in ('asset account', 'asset class', 'asset name'):
            v = d.g(k)
            if v and cx.has(v) and acct_section(cx.low[v.lower()], self.rec.get('opening_balance', {})) == 'assets':
                return cx.low[v.lower()]
        tag = d.g('asset tag') or ''
        m = re.match(r'OPEN-([A-Z]+)', tag)
        if m:
            for a in (self.rec.get('opening_balance', {}).get('assets') or {}):
                if a.upper().replace(' ', '').startswith(m.group(1)) and 'accumulated' not in a.lower():
                    return a
        # activo comprado en el periodo con esa etiqueta
        for e in self.of('equipment_invoice'):
            if tag and e.g('asset tag') == tag and e.id != d.id:
                return self.asset_account(e) if e.type != d.type else cx.fixed_asset()
        return cx.fixed_asset()

    def bank_rows_for(self, ids):
        out = []
        for b in self.of('bank_statement'):
            for it in b.items:
                desc = it.get('description', '')
                a = money(it.get('amount'))
                if a is None:
                    continue
                if any(i and re.search(r'(?<![\w-])' + re.escape(i) + r'(?![\w-])', desc) for i in ids):
                    out.append((a, b))
        return out

    def bank_unbooked(self):
        """Cobros/pagos que solo aparecen en el extracto (p. ej. cobro anticipado de una factura): Cash contra AR/AP."""
        cash_like = set(['Cash'])
        for b in self.of('bank_statement'):
            nm = (b.g('account name') or '').lower()
            if 'reserve' in nm or 'saving' in nm:
                continue
            for it in b.items:
                desc = it.get('description', '')
                a = money(it.get('amount'))
                if a is None:
                    continue
                toks = re.findall(r'[A-Z][A-Z0-9]*-[A-Z0-9-]+', desc)
                tgt = [o for t in toks for o in self.idx.get(t, []) if o.id not in self.skip]
                if not tgt:
                    continue
                ids = [o.id for o in tgt]
                hit = any(abs(e['amount'] - abs(a)) <= TOL and 'Cash' in (e['debit_account'], e['credit_account'])
                          for e in self.entries)
                if hit:
                    continue
                o = tgt[0]
                if o.type in ('customer_invoice', 'patient_invoice', 'rent_roll') and a > 0:
                    self.post([b.id] + ids, 'Cash', 'Accounts Receivable', a)
                elif o.type in ('vendor_invoice', 'supplier_invoice', 'utilities_statement') and a < 0:
                    self.post([b.id] + ids, 'Accounts Payable', 'Cash', -a)

    # ---------------------------------------------------------------- comprobaciones globales
    def global_checks(self):
        for d in self.of('bank_statement'):
            op, cl = d.m('opening balance'), d.m('closing balance')
            rows = [money(it.get('amount')) for it in d.items if it.get('amount')]
            if op is not None and cl is not None:
                if abs(r2(op + sum(rows)) - cl) > TOL:
                    self.flag('bank_closing_mismatch', f'{d.id}: opening {op} + movements {r2(sum(rows))} != closing {cl}')
                else:
                    run = op
                    for it in d.items:
                        a = money(it.get('amount'))
                        rb = money(it.get('running balance'))
                        if a is None:
                            continue
                        run = r2(run + a)
                        if rb is not None and abs(run - rb) > TOL:
                            self.flag('bank_closing_mismatch', f'{d.id}: running balance {rb} vs computed {run}')
                            break
        for d in self.of('vendor_statement', 'customer_statement'):
            cl = d.m('closing balance')
            rows = [money(it.get('amount')) for it in d.items if it.get('amount')]
            if cl is not None and rows and abs(r2(sum(rows)) - cl) > TOL:
                self.flag('statement_balance_mismatch', f'{d.id}: open lines {r2(sum(rows))} != closing {cl}')
        for d in self.of('inventory_rollforward'):
            o, a, u, w, e = (d.m('opening balance'), d.m('additions'), d.m('usage or sales', 'usage', 'cost of sales'),
                             d.m('write down', 'write-down', 'shrinkage') or 0.0, d.m('ending balance'))
            if None not in (o, a, u, e) and abs(r2(o + a - u - w) - e) > TOL:
                self.flag('inventory_rollforward_mismatch', f'{d.id}: {o}+{a}-{u}-{w} != {e}')
        for d in self.of('revenue_recognition_schedule'):
            o, a, rl, e = d.m('opening deferred'), d.m('added deferred') or 0.0, d.m('released this period'), d.m('ending deferred')
            if None not in (o, rl, e) and abs(r2(o + a - rl) - e) > TOL:
                self.flag('schedule_rollforward_mismatch', f'{d.id}: {o}+{a}-{rl} != {e}')
        for d in self.of('fixed_asset_rollforward'):
            o, a, x, e = d.m('opening balance'), d.m('additions') or 0.0, d.m('disposals') or 0.0, d.m('ending balance')
            if None not in (o, e) and abs(r2(o + a - x) - e) > TOL:
                self.flag('schedule_rollforward_mismatch', f'{d.id}: {o}+{a}-{x} != {e}')
        for d in self.of('payment_advice'):
            amt = d.m('amount')
            alloc = [money(it.get('amount')) for it in d.items if it.get('amount')]
            if amt is not None and alloc and abs(r2(sum(alloc)) - amt) > TOL:
                self.flag('payment_allocation_mismatch', f'{d.id}: allocations {r2(sum(alloc))} != advice {amt}')
        for d in self.of('lease_amortization_schedule'):
            ob, p, i, pr, eb = (d.m('opening liability balance'), d.m('payment amount'), d.m('interest amount'),
                                d.m('principal amount'), d.m('ending liability balance'))
            if None not in (p, i, pr) and abs(r2(i + pr) - p) > TOL:
                self.flag('lease_schedule_mismatch', f'{d.id}: interest {i} + principal {pr} != payment {p}')
            elif None not in (ob, pr, eb) and abs(r2(ob - pr) - eb) > TOL:
                self.flag('lease_schedule_mismatch', f'{d.id}: {ob} - {pr} != {eb}')
        for d in self.of('lease_payment_notice'):
            p, i, pr = d.m('payment amount'), d.m('interest amount'), d.m('principal amount')
            if None not in (p, i, pr) and abs(r2(i + pr) - p) > TOL:
                self.flag('lease_schedule_mismatch', f'{d.id}: interest {i} + principal {pr} != payment {p}')
        for d in self.of('lease_modification_notice'):
            o, n, dl, rou = (d.m('old liability balance'), d.m('remeasured liability balance'),
                             d.m('liability remeasurement delta amount'), d.m('rou asset adjustment amount'))
            if None not in (o, n, dl) and abs(r2(n - o) - dl) > TOL:
                self.flag('lease_remeasurement_mismatch', f'{d.id}: {n}-{o} != {dl}')
            elif None not in (dl, rou) and abs(dl - rou) > TOL:
                self.flag('lease_remeasurement_mismatch', f'{d.id}: delta {dl} != ROU adj {rou}')
        for d in self.of('asset_disposal_notice'):
            c, a, nbv, p, gl = (d.m('original cost'), d.m('accumulated depreciation'), d.m('net book value'),
                                d.m('proceeds amount'), d.m('gain loss amount'))
            bad = False
            if None not in (c, a, nbv) and abs(r2(c - a) - nbv) > TOL:
                bad = True
            if None not in (p, nbv, gl) and abs(abs(r2(p - nbv)) - gl) > TOL:
                bad = True
            for s in self.of('sale_proceeds_advice'):
                if s.g('asset tag') == d.g('asset tag') and p is not None and s.m('proceeds amount') is not None \
                        and abs(s.m('proceeds amount') - p) > TOL:
                    bad = True
            if bad:
                self.flag('asset_disposal_mismatch', f'{d.id}: cost {c}, acc dep {a}, NBV {nbv}, proceeds {p}, G/L {gl}')
        for d in self.of('deferred_tax_memo'):
            o, mv, e, ex = (d.m('opening deferred tax liability', 'opening deferred tax asset'),
                            d.m('current period deferred tax movement'),
                            d.m('deferred tax liability ending', 'deferred tax asset ending'), d.m('deferred tax expense amount'))
            bad = None not in (o, mv, e) and abs(r2(o + mv) - e) > TOL
            sch = [t for t in self.of('tax_depreciation_schedule') if t.g('asset tag') == d.g('asset tag')]
            okc = []
            for t in sch:
                b, tx, td, rt = (t.m('book depreciation amount'), t.m('tax depreciation amount'),
                                 t.m('temporary difference amount'), pct(t.g('tax rate')))
                good = True
                if None not in (b, tx, td) and abs(abs(r2(tx - b)) - td) > TOL:
                    good = False
                if None not in (td, rt, mv) and abs(td * rt - abs(mv)) > 0.0151:
                    good = False
                okc.append(good)
            if sch and not any(okc):
                bad = True
            if bad:
                self.flag('deferred_tax_rollforward_mismatch', f'{d.id}: opening {o} + movement {mv} vs ending {e}')
        for d in self.of('exchange_rate_notice'):
            sa, rt, fa = d.m('source amount'), money(d.g('exchange rate')), d.m('functional amount')
            if None not in (sa, rt, fa) and abs(r2(sa * rt) - fa) > TOL:
                self.flag('exchange_rate_mismatch', f'{d.id}: {sa} x {rt} != {fa}')
        for d in self.of('fx_remeasurement_memo'):
            sa, bk, rt, rm, df = (d.m('source amount'), d.m('booked amount'), money(d.g('closing rate')),
                                  d.m('remeasured amount'), d.m('difference amount'))
            bad = None not in (sa, rt, rm) and abs(r2(sa * rt) - rm) > TOL
            if None not in (bk, rm, df) and abs(abs(r2(bk - rm)) - abs(df)) > TOL:
                bad = True
            if bad:
                self.flag('remeasurement_mismatch', f'{d.id}: {sa} x {rt} vs {rm}; booked {bk}, diff {df}')
        for d in self.of('fx_settlement_advice', 'fx_settlement_memo', 'foreign_currency_settlement'):
            bk, pd, df = d.m('booked amount'), d.m('paid amount', 'settled amount', 'functional paid amount'), \
                d.m('fx difference', 'difference amount', 'fx gain loss amount')
            if None not in (bk, pd, df) and abs(abs(r2(bk - pd)) - abs(df)) > TOL:
                self.flag('fx_settlement_mismatch', f'{d.id}: booked {bk} paid {pd} diff {df}')
        for d in self.of('ssp_rate_card'):
            pass
        for d in self.of('performance_obligation_schedule'):
            tp, at, rel = d.m('transaction price'), d.m('allocation total'), d.m('released this period')
            ssps = [money(it.get('ssp amount')) for it in d.items]
            allocs = [money(it.get('allocated transaction price')) for it in d.items]
            rels = [money(it.get('released this period')) for it in d.items]
            if None not in (tp, at) and abs(tp - at) > TOL:
                self.flag('ssp_allocation_mismatch', f'{d.id}: transaction price {tp} != allocation total {at}')
            if ssps and None not in ssps and None not in allocs and tp is not None and sum(ssps) > 0:
                if abs(r2(sum(allocs)) - tp) > TOL:
                    self.flag('ssp_allocation_mismatch', f'{d.id}: allocations {r2(sum(allocs))} != price {tp}')
                else:
                    for s, a in zip(ssps, allocs):
                        if abs(r2(tp * s / sum(ssps)) - a) > 0.05:
                            self.flag('ssp_allocation_mismatch', f'{d.id}: {a} != {tp} x {s}/{r2(sum(ssps))}')
                            break
            if rels and None not in rels and rel is not None and abs(r2(sum(rels)) - rel) > TOL:
                self.flag('performance_obligation_release_mismatch', f'{d.id}: line releases {r2(sum(rels))} != {rel}')
            # aceptacion vs liberacion de implantacion
            for a in self.of('implementation_acceptance_memo'):
                acc = a.m('accepted amount')
                ob = (a.g('accepted obligation') or '').lower()
                for it in d.items:
                    if ob and ob in (it.get('obligation') or '').lower():
                        r = money(it.get('released this period'))
                        if acc is not None and r is not None and abs(acc - r) > TOL:
                            self.flag('performance_obligation_release_mismatch', f'{a.id}: accepted {acc} vs released {r}')
            # ratable
            term = None
            for o in self.of('subscription_order_form'):
                if o.g('form number') == d.g('contract reference'):
                    term = money(o.g('term months'))
            for it in d.items:
                pat = (it.get('release pattern') or '').lower()
                m = re.search(r'ratable over (\d+)', pat)
                if m:
                    n = int(m.group(1))
                    a, r = money(it.get('allocated transaction price')), money(it.get('released this period'))
                    if a is not None and r is not None and abs(r2(a / n) - r) > 0.02 and \
                            not any(abs(r2(a / n * k) - r) <= 0.02 for k in range(2, n + 1)):
                        self.flag('performance_obligation_release_mismatch', f'{d.id}: ratable {a}/{n} vs {r}')
            if None not in (tp, rel):
                e = d.m('ending deferred')
                if e is not None and abs(r2(tp - rel) - e) > TOL:
                    self.flag('performance_obligation_release_mismatch', f'{d.id}: {tp}-{rel} != {e}')
        for d in self.of('transfer_advice'):
            amt = d.m('amount')
            ref = [d.g('transfer number'), d.g('reference')]
            found = []
            for b in self.of('bank_statement'):
                for it in b.items:
                    desc = it.get('description', '')
                    if any(r and r in desc for r in ref):
                        found.append(money(it.get('amount')))
            if amt is not None and found and any(abs(abs(x) - amt) > TOL for x in found if x is not None):
                self.flag('transfer_mismatch', f'{d.id}: advice {amt} vs bank rows {found}')
        for d in self.of('reclassification_memo'):
            orig = d.g('original reference')
            amt = d.m('amount')
            if orig and orig in self.idx and amt is not None:
                o = [x for x in self.idx[orig] if x.type != 'secondary_copy'][0]
                lines = [money(it.get('amount')) for it in o.items if it.get('amount')]
                tot = sum(x for x in lines if x is not None)
                if not any(abs(x - amt) <= TOL for x in lines if x is not None) and abs(tot - amt) > TOL:
                    self.flag('reclassification_support_mismatch', f'{d.id}: amount {amt} not on {orig}')
        def regime_of(label):
            l = (label or '').lower().replace(' ', '_')
            for k in ('india_gst', 'us_sales_tax', 'sales_tax', 'vat', 'gst'):
                if k in l:
                    return k
            return l
        for d in self.of('tax_regime_notice'):
            rt, ja = pct(d.g('tax rate')), d.m('jurisdiction tax amount')
            cands = [i for i in self.live if i.type in ('supplier_invoice', 'vendor_invoice', 'customer_invoice')
                     and i.date == d.date and i.m('tax amount') is not None
                     and regime_of(i.g('tax label')) == regime_of(d.g('tax regime'))]
            if len(cands) == 1 and ja is not None:
                i = cands[0]
                sub, tax = i.m('subtotal'), i.m('tax amount')
                if abs(tax - ja) > TOL or (rt is not None and sub is not None and abs(sub * rt - ja) > 0.0151):
                    self.flag('jurisdiction_tax_mismatch', f'{d.id}: jurisdiction tax {ja} at {rt} vs {i.id} tax {tax} on {sub}')
        for i in self.live:
            if i.type in ('supplier_invoice', 'vendor_invoice', 'expense_receipt', 'utilities_statement'):
                tax = i.m('tax amount')
                parts = [i.m('cgst amount'), i.m('sgst amount'), i.m('igst amount'), i.m('input tax amount'),
                         i.m('recoverable tax amount')]
                parts = [x for x in parts if x is not None]
                if tax is not None and parts and abs(r2(sum(parts)) - tax) > TOL:
                    self.flag('input_tax_mismatch', f'{i.id}: input tax fields {parts} != tax {tax}')
        fmt = self.cx.c.get('date_format')
        for c in self.of('tax_exemption_certificate'):
            who = c.g('counterparty', 'customer')
            st = (c.g('exemption status') or '').lower()
            ef, ex = parse_date(c.g('effective date'), fmt), parse_date(c.g('expiration date'), fmt)
            for i in self.live:
                if i.type != 'customer_invoice' or i.g('customer') != who or i.m('tax amount') is None:
                    continue
                if regime_of(i.g('tax label')) != regime_of(c.g('tax regime')) and c.g('tax regime'):
                    continue
                covered = st.startswith('valid') and (not (ef and ex and i.date) or ef <= i.date <= ex)
                tax = i.m('tax amount')
                if covered and tax > TOL:
                    self.flag('tax_exemption_conflict', f'{c.id} exempts {who} but {i.id} charges tax {tax}')
                if not covered and tax <= TOL and (pct(i.g('tax rate')) or 0) == 0:
                    self.flag('tax_exemption_conflict', f'{i.id} zero-rated but certificate {c.id} not valid for its date')

    # ---------------------------------------------------------------- balance
    def balance(self):
        ob = self.rec.get('opening_balance', {}) or {}
        bal = defaultdict(float)
        for sec in ('assets', 'liabilities', 'equity'):
            for a, v in (ob.get(sec) or {}).items():
                bal[a] += v if sec == 'assets' else -v
        for e in self.entries:
            bal[e['debit_account']] += e['amount']
            bal[e['credit_account']] -= e['amount']
        re_acct = self.cx.pick('Retained Earnings', default='Retained Earnings')
        out = {'assets': {}, 'liabilities': {}, 'equity': {}}
        ni = 0.0
        for a, v in bal.items():
            sec = acct_section(a, ob)
            if sec == 'pl':
                ni += v
                continue
        for a, v in bal.items():
            sec = acct_section(a, ob)
            if sec == 'pl':
                continue
            if a == re_acct:
                continue
            val = r2(v if sec == 'assets' else -v)
            if abs(val) >= 0.005:
                out[sec][a] = val
        rev = bal.get(re_acct, 0.0) + ni
        if abs(rev) >= 0.005 or re_acct in (ob.get('equity') or {}):
            out['equity'][re_acct] = r2(-rev)
        return out


# ----------------------------------------------------------------------------- handlers
def related(p, d, keys=('reference', 'contract ref', 'contract reference', 'reference invoice', 'claim reference',
                        'source reference', 'original reference', 'agreement number', 'purchase ref', 'shipment ref',
                        'batch id', 'reference sheet')):
    out = []
    for k in keys:
        for v in d.f.get(k, []):
            for part in re.split(r'[,;]\s*|\s+and\s+', v):
                part = part.strip()
                for o in p.idx.get(part, []):
                    if o.id != d.id and o not in out and o.id not in p.skip:
                        out.append(o)
    return out


def h_customer_invoice(p, d):
    cx = p.cx
    p.check_invoice(d)
    sub, tax, total, _ = p.inv_amounts(d)
    rel = related(p, d)
    refs = [d.id]
    cust = d.g('customer')
    # tasa de cambio
    fx = [x for x in p.of('exchange_rate_notice') if x.g('reference') in p.ids_of(d)]
    if fx:
        f = fx[0]
        rate = money(f.g('exchange rate'))
        fa = f.m('functional amount')
        if fa is not None and total is not None and sub is not None:
            k = fa / total if total else 1
            tax = r2(tax * rate) if tax else 0.0
            sub = r2(fa - tax)
            total = fa
        refs.append(f.id)
    # exencion
    exempt = False
    certs = [c for c in p.of('tax_exemption_certificate') if cust and (c.g('counterparty', 'customer') or '') == cust]
    for c in certs:
        st = (c.g('exemption status') or '').lower()
        ef, ex = parse_date(c.g('effective date'), cx.c.get('date_format')), parse_date(c.g('expiration date'), cx.c.get('date_format'))
        ok = st.startswith('valid') or st.startswith('active')
        if ok and d.date and ef and ex and not (ef <= d.date <= ex):
            ok = False
        if ok:
            exempt = True
            refs.append(c.id)
            for tp in p.of('customer_tax_profile'):
                if (tp.g('customer') or '') == cust:
                    refs.append(tp.id)
    # contrato diferido (suscripcion / retainer / ASC 606)
    deferred = False
    for o in rel:
        if o.type in ('subscription_order_form', 'retainer_agreement_memo'):
            deferred = True
            refs.append(o.id)
    for s in p.of('revenue_recognition_schedule', 'performance_obligation_schedule'):
        if s.g('contract reference') in p.ids_of(d) + d.all_vals('contract ref'):
            deferred = True
    fgt = [o for o in rel if o.type == 'finished_goods_transfer_note']
    dn = [o for o in p.live if o.type in ('delivery_note', 'work_order') and
          (o.g('customer') == cust) and o.id not in p.used and
          (o.g('shipment ref') in d.all_vals('contract ref', 'reference', 'shipment ref') or
           o.g('work order number', 'job number') in d.all_vals('contract ref', 'reference') or
           not d.all_vals('contract ref'))]
    for o in fgt:
        refs.append(o.id)
    if dn:
        o = dn[0]
        p.used.add(o.id)
        refs.insert(0, o.id)
    rev_acct = cx.unearned() if deferred and cx.has(cx.unearned()) else cx.revenue()
    # la exencion valida solo aporta soporte: el impuesto se toma tal como lo muestra la factura
    if not exempt:
        refs = [r for r in refs if p.byid[r].type not in ('tax_exemption_certificate', 'customer_tax_profile')]
    elif tax:
        refs = [r for r in refs if p.byid[r].type not in ('tax_exemption_certificate', 'customer_tax_profile')]
    p.post(refs, 'Accounts Receivable', rev_acct, sub)
    if tax:
        tax_docs = [x for x in p.of('tax_regime_notice', 'customer_tax_profile') if True]
        if p.is_india([d] + p.notes_for(d, tax)):
            prof = [x for x in p.of('customer_tax_profile') if x.g('customer') == cust] or tax_docs
            for k, v in p.gst_split(tax, prof, d, sub, pct(d.g('tax rate'))):
                p.post(refs, 'Accounts Receivable', cx.pick(k + 'GST Payable'), v)
        else:
            p.post(refs, 'Accounts Receivable', cx.out_tax(), tax)
    for o in fgt:
        p.post(refs, 'Cost of Goods Sold', cx.fg_inventory(), o.m('transfer value'))
    if dn and dn[0].type == 'delivery_note':
        o = dn[0]
        cost = o.m('cost basis amount')
        if cost is None:
            cost = sum(money(it.get('extended cost')) or 0 for it in o.items)
        p.post(refs, 'Cost of Goods Sold', cx.inventory(), cost)


def h_delivery_note(p, d):
    # si no hay factura enlazada, ingreso por el importe facturado
    if d.id in p.used:
        return
    cx = p.cx
    cust = d.g('customer')
    if any(i.g('customer') == cust for i in p.of('customer_invoice') if i.id not in p.skip):
        return  # la factura lo contabilizara
    if d.type == 'delivery_note':
        billed = d.m('billed amount')
        p.post([d.id], 'Accounts Receivable', cx.revenue(), billed)
        p.post([d.id], 'Cost of Goods Sold', cx.inventory(), d.m('cost basis amount'))


def purchase_tax(p, d, refs, tax, credit='Accounts Payable', sub_acct=None):
    cx = p.cx
    if not tax:
        return 0.0
    rel = p.notes_for(d, tax)
    if p.is_us_sales_tax([d] + rel):
        return tax  # se integra en el coste
    if p.is_india([d] + rel):
        notes = rel
        for k, v in p.gst_split(tax, notes, d, d.m('subtotal'), pct(d.g('tax rate'))):
            p.post(refs, cx.pick('Input ' + k + 'GST Receivable'), credit, v)
        return 0.0
    p.post(refs, cx.in_tax(), credit, tax)
    return 0.0


def h_supplier_invoice(p, d):
    cx = p.cx
    p.check_invoice(d)
    sub, tax, total, _ = p.inv_amounts(d)
    refs = [d.id]
    grn = [o for o in p.live if o.type == 'goods_receipt_note' and
           (o.g('purchase ref') in d.all_vals('purchase ref', 'po number', 'reference') or
            o.g('supplier') == (d.g('supplier', 'vendor')))]
    if grn:
        refs = [grn[0].id, d.id]
    trn = p.notes_for(d, tax)
    if trn and tax:
        refs = [trn[0].id] + refs
    lab = d.g('expense label', 'expense category', 'expense account', 'account')
    acct = cx.low.get(lab.lower()) if lab and lab.lower() in cx.low else None
    if acct is None:
        acct = cx.inventory() if (d.type == 'supplier_invoice' or grn) else cx.pick('Office Supplies Expense')
    fx = [x for x in p.of('exchange_rate_notice') if x.g('reference') in p.ids_of(d)]
    if fx:
        f = fx[0]
        rate = money(f.g('exchange rate'))
        fa = f.m('functional amount')
        if fa is not None:
            tax = r2(tax * rate) if tax else 0.0
            sub = r2(fa - tax)
        refs.append(f.id)
    extra = purchase_tax(p, d, refs, tax)
    p.post(refs, acct, 'Accounts Payable', r2(sub + extra))


def h_utilities(p, d):
    cx = p.cx
    sub, tax, total, ls = p.inv_amounts(d)
    acct = cx.pick('Utilities Expense')
    extra = purchase_tax(p, d, [d.id], tax)
    p.post([d.id], acct, 'Accounts Payable', r2(sub + extra))


def h_expense_receipt(p, d):
    cx = p.cx
    sub, tax, total, ls = p.inv_amounts(d)
    acct = None
    lab = d.g('expense label', 'expense category', 'expense account', 'category')
    if lab and cx.has(lab):
        acct = cx.low[lab.lower()]
    if acct is None and d.items:
        acct = cx.find_in(d.items[0].get('description', ''), 'expense')
    if acct is None:
        acct = cx.find_in(d.text, 'expense') or cx.pick('Office Supplies Expense')
    pm = (d.g('payment method') or '').lower()
    credit = 'Cash'
    if 'payable' in pm or 'credit' in pm and 'card' not in pm:
        credit = 'Accounts Payable'
    extra = purchase_tax(p, d, [d.id], tax, credit=credit)
    p.post([d.id], acct, credit, r2(sub + extra))


def h_equipment_invoice(p, d):
    cx = p.cx
    lab = d.g('asset account', 'asset class')
    acct = cx.low.get(lab.lower()) if lab and lab.lower() in cx.low else cx.fixed_asset()
    cash, fin = d.m('paid cash', 'cash paid'), d.m('financed amount')
    sub, tax, total, ls = p.inv_amounts(d)
    if cash is None and fin is None:
        cash = total
    p.post([d.id], acct, 'Cash', cash)
    p.post([d.id], acct, cx.pick('Notes Payable', 'Loans Payable'), fin)


def h_payment(p, d):
    cx = p.cx
    amt = d.m('amount', 'paid amount', 'payment amount')
    refs_v = d.all_vals('reference') + [it.get('reference') for it in d.items if it.get('reference')]
    tgt = []
    for v in refs_v:
        for part in re.split(r'[,;]\s*|\s+and\s+', v or ''):
            for o in p.idx.get(part.strip(), []):
                if o.id != d.id and o.id not in p.skip and o not in tgt:
                    tgt.append(o)
    pf = (d.g('payment for') or '').lower()
    ar_types = ('customer_invoice', 'rent_roll', 'patient_invoice', 'work_order')
    if 'customer' in pf or 'tenant' in pf or 'receipt' in pf or any(o.type in ar_types for o in tgt):
        side = 'AR'
    elif 'supplier' in pf or 'vendor' in pf:
        side = 'AP'
    else:
        side = 'AP' if tgt else 'AR'
    refs = [d.id] + [o.id for o in tgt]
    # liquidacion en moneda extranjera: importe registrado (tipo de la factura) vs pagado
    sa, rt = d.m('source amount'), money(d.g('exchange rate'))
    booked = None
    if sa is not None and rt is not None:
        fa, fxd = d.m('functional amount'), d.m('fx difference', 'fx gain loss', 'exchange difference')
        calc = sa * rt
        for o in tgt:
            for n in p.of('exchange_rate_notice'):
                if n.g('reference') in p.ids_of(o):
                    booked = n.m('functional amount')
                    refs.append(n.id)
        bad = (amt is not None and abs(calc - amt) > 0.0151) or (fa is not None and abs(calc - fa) > 0.0151)
        if booked is not None and fxd is not None and amt is not None and abs(abs(booked - amt) - abs(fxd)) > TOL:
            bad = True
        if bad:
            p.flag('fx_settlement_mismatch', f'{d.id}: {sa} x {rt} = {r2(calc)} vs amount {amt} / functional {fa}; booked {booked}, diff {fxd}')
        if amt is None:
            amt = fa
    cx = p.cx
    gain, loss = cx.pick('Foreign Exchange Gain', 'FX Gain'), cx.pick('Foreign Exchange Loss', 'FX Loss')
    if side == 'AR':
        p.post(refs, 'Cash', 'Accounts Receivable', amt)
        if booked is not None and amt is not None:
            df = r2(booked - amt)
            if df > 0:
                p.post(refs, loss, 'Accounts Receivable', df)
            elif df < 0:
                p.post(refs, 'Accounts Receivable', gain, -df)
    else:
        p.post(refs, 'Accounts Payable', 'Cash', amt)
        if booked is not None and amt is not None:
            df = r2(booked - amt)
            if df > 0:
                p.post(refs, 'Accounts Payable', gain, df)
            elif df < 0:
                p.post(refs, loss, 'Accounts Payable', -df)


def h_patient_invoice(p, d):
    p.post([d.id], 'Accounts Receivable', p.cx.revenue(), d.m('gross charge', 'total', 'amount'))


def h_receipt_ar(p, d):
    tgt = related(p, d)
    amt = d.m('paid amount', 'amount')
    p.post([d.id] + [o.id for o in tgt], 'Cash', 'Accounts Receivable', amt)


def h_rent_roll(p, d):
    tot = sum(money(it.get('amount')) or 0 for it in d.items)
    p.post([d.id], 'Accounts Receivable', p.cx.pick('Rental Revenue', 'Rent Revenue', 'Service Revenue'), tot)


def h_security_deposit(p, d):
    cx = p.cx
    acct = cx.pick('Security Deposits Payable', 'Tenant Deposits Payable', 'Security Deposits')
    t = d.text.lower()
    rel = [o for o in related(p, d) if o.type == 'security_deposit_notice']
    if rel or 'refund' in t or 'return' in (d.g('subject', 'type', 'notice type') or '').lower():
        p.post([d.id] + [o.id for o in rel], acct, 'Cash', d.m('amount', 'refund amount'))
    else:
        p.post([d.id], 'Cash', acct, d.m('amount'))


def months_between(a, b):
    if not a or not b:
        return None
    n = (b.year - a.year) * 12 + b.month - a.month
    if b.day >= a.day:
        n += 1
    return max(n, 1)


def h_prepaid(p, d):
    cx = p.cx
    fmt = cx.c.get('date_format')
    a = parse_date(d.g('service start', 'coverage start'), fmt)
    b = parse_date(d.g('service end', 'coverage end'), fmt)
    n = months_between(a, b) or 1
    mo = d.m('monthly amount')
    tot = d.m('total amount', 'prepaid amount', 'amount paid')
    if tot is None:
        # el banco es la mejor evidencia del importe pagado (la cuota mensual visible esta redondeada)
        rows = [abs(a) for a, _ in p.bank_rows_for(p.ids_of(d)) if a < 0]
        if len(rows) == 1 and mo is not None and abs(rows[0] - mo * n) <= max(0.05, n * 0.01):
            tot = rows[0]
    if tot is None and mo is not None:
        tot = r2(mo * n)
    if d.type == 'rent_notice':
        pre, exp = cx.pick('Prepaid Rent'), cx.pick('Rent Expense')
    else:
        pre, exp = cx.pick('Prepaid Insurance'), cx.pick('Insurance Expense')
    p.post([d.id], pre, 'Cash', tot)
    p.prepaid = getattr(p, 'prepaid', {})
    for i in p.ids_of(d):
        p.prepaid[i] = (d, pre, exp)


def h_service_memo(p, d):
    cx = p.cx
    amt = d.m('recognized amount', 'amount', 'accrued amount')
    ref = d.g('reference')
    pre = getattr(p, 'prepaid', {})
    # los avisos de prepago se procesan antes (orden de HANDLERS no garantizado): buscar directamente
    for o in p.live:
        if o.type in ('rent_notice', 'insurance_notice') and ref in p.ids_of(o):
            if o.type == 'rent_notice':
                pa, ex = cx.pick('Prepaid Rent'), cx.pick('Rent Expense')
            else:
                pa, ex = cx.pick('Prepaid Insurance'), cx.pick('Insurance Expense')
            p.post([o.id, d.id], ex, pa, amt)
            return
    txt = ' '.join(d.all_vals('subject', 'narrative'))
    tl = txt.lower()
    # liberacion de prepagos del saldo inicial
    ob = p.rec.get('opening_balance', {}).get('assets', {})
    if 'release' in tl or 'expired' in tl or 'amortiz' in tl:
        for pa in ob:
            if pa.lower().startswith('prepaid'):
                stem = pa.lower().replace('prepaid', '').strip()
                if stem and stem in tl:
                    ex = cx.find_in(stem + ' expense', 'expense') or cx.pick(stem.title() + ' Expense')
                    p.post([d.id], ex, pa, amt)
                    return
    if 'unearned' in tl or 'deferred revenue' in tl or 'revenue' in tl:
        p.post([d.id], cx.unearned(), cx.revenue(), amt)
        return
    acct = cx.find_in(txt, 'expense') or cx.pick('Accrued Expenses')
    p.post([d.id], acct, cx.pick('Accrued Expenses'), amt)


def h_payroll(p, d):
    cx = p.cx
    g, t = d.m('gross pay'), d.m('employer tax', 'employer taxes')
    p.post([d.id], cx.pick('Salaries Expense', 'Wages Expense'), 'Cash', g)
    p.post([d.id], cx.pick('Payroll Tax Expense'), 'Cash', t)


def h_loan(p, d):
    cx = p.cx
    lp = cx.pick('Loans Payable', 'Notes Payable')
    p.post([d.id], 'Cash', lp, d.m('draw amount', 'disbursement amount'))
    p.post([d.id], lp, 'Cash', d.m('principal paid'))
    p.post([d.id], cx.pick('Interest Expense'), 'Cash', d.m('interest paid'))


def h_depr(p, d):
    cx = p.cx
    p.post([d.id], cx.pick('Depreciation Expense'), cx.pick('Accumulated Depreciation'),
           d.m('current period charge', 'current charge', 'depreciation expense'))


def h_transfer(p, d):
    cx = p.cx
    t = d.text.lower()
    src, dst = 'Cash', cx.pick('Reserve Cash', 'Savings Account', 'Petty Cash')
    fa, ta = (d.g('from account') or '').lower(), (d.g('to account') or '').lower()
    if 'reserve' in fa or 'savings' in fa or ('operating' in ta):
        src, dst = dst, src
    p.post([d.id], dst, src, d.m('amount', 'transfer amount'))


def h_card_settlement(p, d):
    cx = p.cx
    clr = cx.pick('Card Settlement Clearing', 'Card Receivable')
    batches = [o for o in p.of('pos_batch_report') if any(b.get('description', '') == o.g('batch number', 'batch id')
                                                          or o.g('batch number', 'batch id') in str(b) for b in d.items)]
    refs = [d.id] + [o.id for o in batches]
    p.post(refs, 'Cash', clr, d.m('net deposit'))
    p.post(refs, cx.fee_expense(), clr, d.m('fees', 'fee amount'))


def h_sales_summary(p, d):
    cx = p.cx
    clr = cx.pick('Card Settlement Clearing', 'Card Receivable')
    net = d.m('net sales')
    if net is None:
        net = r2((d.m('gross sales') or 0) - (d.m('returns') or 0))
    tax = d.m('tax amount') or 0.0
    cash, card = d.m('cash sales') or 0.0, d.m('card sales') or 0.0
    tot = r2(net + tax)
    pos = [o for o in p.of('pos_batch_report') if o.m('batch total') is not None and abs(o.m('batch total') - card) <= TOL]
    refs = [d.id] + [o.id for o in pos[:1]]
    if tot and abs(cash + card - tot) <= 0.05:
        cr = r2(cash * net / tot)
        ct = r2(cash - cr)
    else:
        cr, ct = cash, 0.0
    kr, kt = r2(net - cr), r2(tax - ct)
    p.post(refs, 'Cash', cx.revenue(), cr)
    p.post(refs, clr, cx.revenue(), kr)
    p.post(refs, 'Cost of Goods Sold', cx.inventory(), d.m('cogs amount'))
    if p.is_india([d]):
        for k, v in p.gst_split(ct, []):
            p.post(refs, 'Cash', cx.pick(k + 'GST Payable'), v)
        for k, v in p.gst_split(kt, []):
            p.post(refs, clr, cx.pick(k + 'GST Payable'), v)
    else:
        p.post(refs, 'Cash', cx.out_tax(), ct)
        p.post(refs, clr, cx.out_tax(), kt)


def h_return(p, d):
    p.post([d.id], p.cx.revenue(), 'Cash', d.m('amount', 'refund amount'))


def h_stock_count(p, d):
    cx = p.cx
    loss = 0.0
    for it in d.items:
        s, c, u = money(it.get('system qty')), money(it.get('counted qty')), money(it.get('unit cost'))
        if None not in (s, c, u):
            loss += (s - c) * u
    adj = [o for o in p.of('inventory_adjustment_note', 'inventory_rollforward')
           if (o.g('reference sheet') in p.ids_of(d)) or True]
    adj = [o for o in adj if o.type == 'inventory_adjustment_note' and o.g('reference sheet') in p.ids_of(d)] or \
          [o for o in adj if o.type == 'inventory_rollforward'][:1]
    for o in adj:
        p.used.add(o.id)
    inv = cx.fg_inventory() if p.cx.industry == 'manufacturing' else cx.inventory()
    p.post([d.id] + [o.id for o in adj], cx.pick('Inventory Shrinkage Expense'), inv, r2(loss))


def h_inv_adj(p, d):
    if d.id in p.used:
        return
    # el ajuste se contabiliza con la hoja de recuento si existe
    if any(d.g('reference sheet') in p.ids_of(s) for s in p.of('stock_count_sheet')):
        return
    cx = p.cx
    inv = cx.fg_inventory() if cx.industry == 'manufacturing' else cx.inventory()
    p.post([d.id], cx.pick('Inventory Shrinkage Expense'), inv, d.m('amount'))


def h_scrap(p, d):
    cx = p.cx
    refs = [d.id]
    if 'OPEN' in (d.g('batch or lot') or ''):
        refs += [o.id for o in p.of('opening_trial_balance')]
    p.post(refs, cx.pick('Inventory Shrinkage Expense'), cx.fg_inventory(), d.m('write down', 'amount'))


def h_credit_memo(p, d):
    cx = p.cx
    reason = (d.g('reason') or '').lower()
    tgt = related(p, d)
    aging = p.of('ar_aging_summary')
    refs = [d.id] + [o.id for o in aging] + [o.id for o in tgt]
    if 'bad debt' in reason or 'write' in reason or 'uncollect' in reason:
        refs = [o.id for o in aging] + [d.id] + [o.id for o in tgt]
        p.post(refs, cx.pick('Bad Debt Expense'), 'Accounts Receivable', d.m('amount'))
    else:
        p.post(refs, cx.pick('Sales Returns and Allowances', 'Sales Returns', cx.revenue()), 'Accounts Receivable',
               d.m('amount'))


def h_mat_req(p, d):
    cx = p.cx
    b = [o for o in p.of('production_batch_sheet') if o.g('batch id') == d.g('batch id')]
    p.post([d.id] + [o.id for o in b], cx.pick('Work In Process'), cx.pick('Raw Materials Inventory', 'Inventory'),
           d.m('issue value', 'amount'))


def h_labor(p, d):
    cx = p.cx
    b = [o for o in p.of('production_batch_sheet') if o.g('batch id') == d.g('batch id')]
    p.post([d.id] + [o.id for o in b], cx.pick('Work In Process'), 'Cash', d.m('labor cash paid', 'labor value'))


def h_overhead(p, d):
    cx = p.cx
    b = [o for o in p.of('production_batch_sheet') if o.g('batch id') == d.g('batch id')]
    p.post([d.id] + [o.id for o in b], cx.pick('Work In Process'), cx.pick('Accrued Expenses'),
           d.m('accrued overhead', 'overhead value'))


def h_fgt(p, d):
    cx = p.cx
    b = [o for o in p.of('production_batch_sheet') if o.g('batch id') == d.g('batch id')]
    p.post([d.id] + [o.id for o in b], cx.fg_inventory(), cx.pick('Work In Process'), d.m('transfer value'))


def h_lease_agreement(p, d):
    cx = p.cx
    rou = d.m('rou asset amount') or d.m('lease liability amount')
    p.post([d.id], cx.pick('Right-of-Use Asset', 'ROU Asset'), cx.pick('Lease Liability'), rou)


def h_lease_payment(p, d):
    cx = p.cx
    sch = [o for o in p.of('lease_amortization_schedule') if o.g('agreement number') == d.g('agreement number')]
    ag = [o for o in p.of('lease_agreement') if o.g('agreement number') == d.g('agreement number')]
    refs = [o.id for o in ag] + [o.id for o in sch] + [d.id]
    p.post(refs, cx.pick('Lease Liability'), 'Cash', d.m('principal amount'))
    p.post(refs, cx.pick('Lease Interest Expense', 'Interest Expense'), 'Cash', d.m('interest amount'))


def h_lease_schedule(p, d):
    cx = p.cx
    ag = [o for o in p.of('lease_agreement') if o.g('agreement number') == d.g('agreement number')]
    pay = [o for o in p.of('lease_payment_notice') if o.g('agreement number') == d.g('agreement number')]
    refs = [o.id for o in ag] + [d.id]
    if not pay:
        p.post(refs, cx.pick('Lease Liability'), 'Cash', d.m('principal amount'))
        p.post(refs, cx.pick('Lease Interest Expense', 'Interest Expense'), 'Cash', d.m('interest amount'))
    p.post(refs, cx.pick('Lease Amortization Expense', 'Amortization Expense'), cx.pick('Right-of-Use Asset', 'ROU Asset'),
           d.m('rou amortization amount'))


def h_lease_mod(p, d):
    cx = p.cx
    dl = d.m('liability remeasurement delta amount')
    if dl is None:
        o, n = d.m('old liability balance'), d.m('remeasured liability balance')
        dl = r2(n - o) if None not in (o, n) else None
    ag = [o for o in p.of('lease_agreement') if o.g('agreement number') == d.g('agreement number')]
    p.post([d.id] + [o.id for o in ag], cx.pick('Right-of-Use Asset', 'ROU Asset'), cx.pick('Lease Liability'), dl)


def h_disposal(p, d):
    cx = p.cx
    c, a, nbv, pr, gl = (d.m('original cost'), d.m('accumulated depreciation') or 0.0, d.m('net book value'),
                         d.m('proceeds amount') or 0.0, d.m('gain loss amount'))
    sp = [o for o in p.of('sale_proceeds_advice') if o.g('asset tag') == d.g('asset tag')]
    refs = [d.id] + [o.id for o in sp]
    acct = p.asset_account(d)
    if c is None:
        return
    gain = r2(pr - (c - a))
    p.post(refs, 'Cash', acct, pr)
    p.post(refs, cx.pick('Accumulated Depreciation'), acct, a)
    if gain > 0:
        p.post(refs, acct, cx.pick('Gain on Disposal', 'Gain on Asset Disposal', 'Gain on Sale of Assets'), gain)
    elif gain < 0:
        p.post(refs, cx.pick('Loss on Disposal', 'Loss on Asset Disposal', 'Loss on Sale of Assets'), acct, -gain)


def h_deferred_tax(p, d):
    cx = p.cx
    mv = d.m('current period deferred tax movement', 'deferred tax expense amount')
    t = [o for o in p.of('tax_depreciation_schedule') if o.g('asset tag') == d.g('asset tag')]
    t2 = [o for o in t if o.m('temporary difference amount') is not None and pct(o.g('tax rate'))
          and mv is not None and abs(o.m('temporary difference amount') * pct(o.g('tax rate')) - abs(mv)) <= 0.0151]
    refs = [o.id for o in (t2 or t)[:1]] + [d.id]
    if mv is None:
        return
    if 'asset' in ' '.join(d.f.keys()) and 'liability' not in ' '.join(d.f.keys()):
        p.post(refs, cx.pick('Deferred Tax Asset'), cx.pick('Deferred Tax Benefit', 'Income Tax Expense'), mv)
    else:
        p.post(refs, cx.pick('Deferred Tax Expense', 'Income Tax Expense'), cx.pick('Deferred Tax Liability'), mv)


def h_fx_remeasure(p, d):
    cx = p.cx
    bk, rm = d.m('booked amount'), d.m('remeasured amount')
    if None in (bk, rm):
        return
    ref = d.g('reference')
    tgt = [o for o in p.idx.get(ref, []) if o.id != d.id and o.type != 'exchange_rate_notice']
    side = 'AR'
    if tgt and tgt[0].type in ('vendor_invoice', 'supplier_invoice', 'equipment_invoice'):
        side = 'AP'
    # si ya se ha cobrado/pagado, no hay saldo abierto que remedir (se deja igual: el memo manda)
    diff = r2(rm - bk)
    refs = [d.id] + [o.id for o in tgt]
    gain, loss = cx.pick('Foreign Exchange Gain', 'FX Gain'), cx.pick('Foreign Exchange Loss', 'FX Loss')
    if side == 'AR':
        if diff > 0:
            p.post(refs, 'Accounts Receivable', gain, diff)
        else:
            p.post(refs, loss, 'Accounts Receivable', -diff)
    else:
        if diff > 0:
            p.post(refs, loss, 'Accounts Payable', diff)
        else:
            p.post(refs, 'Accounts Payable', gain, -diff)


def h_revrec(p, d):
    cx = p.cx
    rel = d.m('released this period')
    ref = d.g('contract reference')
    tgt = [o for o in p.idx.get(ref, []) if o.id not in p.skip]
    p.post([d.id] + [o.id for o in tgt], cx.unearned(), cx.revenue(), rel)


def h_pob(p, d):
    cx = p.cx
    ref = d.g('contract reference')
    acc = [o for o in p.of('implementation_acceptance_memo') if o.g('contract reference') == ref]
    for it in d.items:
        r = money(it.get('released this period'))
        ob = (it.get('obligation') or '').lower()
        refs = [d.id] + ([o.id for o in acc] if 'implement' in ob else [])
        p.post(refs, cx.unearned(), cx.revenue(), r)
    if not d.items:
        p.post([d.id], cx.unearned(), cx.revenue(), d.m('released this period'))


def h_reclass(p, d):
    cx = p.cx
    orig = d.g('original reference')
    tgt = [o for o in p.idx.get(orig, []) if o.type != 'secondary_copy']
    amt = d.m('amount')
    if not tgt or amt is None:
        return
    o = tgt[0]
    # cuenta original = la del documento original; nueva = la que cita el memo, o la de la otra linea
    from_acct = None
    for e in p.entries:
        if o.id in e['doc_refs'] and acct_section(e['debit_account'], {}) == 'pl':
            from_acct = e['debit_account']
            break
    txt = ' '.join(d.all_vals('narrative', 'subject', 'to account', 'new account', 'correct account'))
    to_acct = d.g('to account', 'new account', 'correct account')
    to_acct = cx.low.get(to_acct.lower()) if to_acct and to_acct.lower() in cx.low else cx.find_in(txt, 'expense')
    if to_acct is None or to_acct == from_acct:
        cands = [cx.find_in(it.get('description', ''), 'expense') for it in o.items]
        cands = [c for c in cands if c and c != from_acct]
        to_acct = cands[0] if cands else None
    if to_acct and from_acct and to_acct != from_acct:
        p.post([d.id, o.id], to_acct, from_acct, amt)


HANDLERS = {
    'customer_invoice': h_customer_invoice,
    'delivery_note': h_delivery_note,
    'supplier_invoice': h_supplier_invoice,
    'vendor_invoice': h_supplier_invoice,
    'utilities_statement': h_utilities,
    'expense_receipt': h_expense_receipt,
    'equipment_invoice': h_equipment_invoice,
    'payment_advice': h_payment,
    'patient_invoice': h_patient_invoice,
    'insurer_remittance': h_receipt_ar,
    'copay_receipt': h_receipt_ar,
    'rent_roll': h_rent_roll,
    'security_deposit_notice': h_security_deposit,
    'rent_notice': h_prepaid,
    'insurance_notice': h_prepaid,
    'service_period_memo': h_service_memo,
    'payroll_summary': h_payroll,
    'loan_statement': h_loan,
    'depreciation_schedule': h_depr,
    'fixed_asset_rollforward': h_depr,
    'transfer_advice': h_transfer,
    'card_settlement_report': h_card_settlement,
    'sales_summary': h_sales_summary,
    'return_note': h_return,
    'stock_count_sheet': h_stock_count,
    'inventory_adjustment_note': h_inv_adj,
    'scrap_report': h_scrap,
    'credit_memo': h_credit_memo,
    'material_requisition_slip': h_mat_req,
    'direct_labor_record': h_labor,
    'overhead_accrual_memo': h_overhead,
    'finished_goods_transfer_note': h_fgt,
    'lease_agreement': h_lease_agreement,
    'lease_payment_notice': h_lease_payment,
    'lease_amortization_schedule': h_lease_schedule,
    'lease_modification_notice': h_lease_mod,
    'asset_disposal_notice': h_disposal,
    'deferred_tax_memo': h_deferred_tax,
    'fx_remeasurement_memo': h_fx_remeasure,
    'revenue_recognition_schedule': h_revrec,
    'performance_obligation_schedule': h_pob,
    'reclassification_memo': h_reclass,
}
# orden: primero lo que crea saldos, despues pagos/liberaciones/reclasificaciones
ORDER = ['opening_trial_balance', 'rent_notice', 'insurance_notice', 'customer_invoice', 'supplier_invoice',
         'vendor_invoice', 'expense_receipt', 'utilities_statement', 'equipment_invoice']
LAST = ['reclassification_memo', 'fx_remeasurement_memo']


def solve(rec):
    p = Packet(rec)
    # orden estable: documentos base primero, luego por fecha, reclasificaciones al final
    def k(d):
        return (2 if d.type in LAST else 0 if d.type in ORDER else 1, d.date or date.min, d.id)
    p.docs.sort(key=k)
    p.run()
    codes = [c for c, _ in p.issues]
    if 'exchange_rate_mismatch' in codes:
        # un tipo de cambio mal soportado arrastra la liquidacion: se informa la causa raiz
        p.issues = [(c, n) for c, n in p.issues if c != 'fx_settlement_mismatch']
    if p.issues:
        return {'has_inconsistency': True, 'inconsistency_codes': [c for c, _ in p.issues],
                'inconsistency_notes': [n for _, n in p.issues], 'entries': [],
                'balance_sheet': {'assets': {}, 'liabilities': {}, 'equity': {}}}
    return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [],
            'entries': p.entries, 'balance_sheet': p.balance()}


def main(argv):
    inp, outp = argv[1], argv[2]
    recs = []
    with open(inp, encoding='utf-8-sig') as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
    out = {}
    for rec in recs:
        rid = rec.get('record_id', str(len(out)))
        try:
            out[rid] = solve(rec)
        except Exception:
            if os.environ.get('FB_DEBUG'):
                traceback.print_exc()
            out[rid] = {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [],
                        'entries': [], 'balance_sheet': {'assets': dict((rec.get('opening_balance') or {}).get('assets') or {}),
                                                         'liabilities': dict((rec.get('opening_balance') or {}).get('liabilities') or {}),
                                                         'equity': dict((rec.get('opening_balance') or {}).get('equity') or {})}}
    d = os.path.dirname(os.path.abspath(outp))
    os.makedirs(d, exist_ok=True)
    tmp = outp + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, outp)


if __name__ == '__main__':
    main(sys.argv)
