#!/usr/bin/env python3
"""FinBalance close: python3 run.py <records.jsonl> <salida.json>. GENERADO por src/build.py: no editar a mano."""
import json, os, re, sys, traceback
from collections import defaultdict


# ======================= fbparse.py
"""Parser genérico de los documentos OCR de FinBalance (solo librería estándar)."""
import re

SECTION_RE = re.compile(r'^[=\-]{3,}$')


def unwrap(text):
    """Une las líneas cortadas por el OCR (el corte deja un espacio al final o al principio de la línea siguiente)."""
    lines = text.replace('\r', '').split('\n')
    out = []
    for ln in lines:
        if out and (out[-1].endswith(' ') or (ln.startswith(' ') and not ln.startswith('  -') and ln.strip())) \
                and not SECTION_RE.match(ln.strip()) and out[-1].strip() and not out[-1].rstrip().endswith(':'):
            out[-1] = out[-1] + ln
        else:
            out.append(ln)
    return out


def parse_amount(s):
    """'$-24,012.07' 'EUR 5.817,25' 'GBP 2,596.00' '(1.00)' '314.66' -> float o None."""
    if s is None:
        return None
    s = str(s).strip()
    m = re.search(r'[-(]?\s*[A-Z]{0,3}\s*[^\d\s-]{0,2}\s*-?[\d][\d.,\s]*', s)
    if not m:
        return None
    t = m.group(0)
    neg = '-' in t or t.startswith('(')
    d = re.sub(r'[^\d.,]', '', t)
    if not d:
        return None
    if ',' in d and '.' in d:
        dec = ',' if d.rfind(',') > d.rfind('.') else '.'
    elif ',' in d:
        dec = ',' if re.search(r',\d{1,2}$', d) else '.'
    elif '.' in d:
        dec = '.' if re.search(r'\.\d{1,2}$', d) or d.count('.') == 1 and not re.search(r'\.\d{3}$', d) else ','
        if d.count('.') == 1 and re.search(r'\.\d{3,}$', d):
            # 1.2996 (tipo de cambio) o 5.817 (miles). Si hay más de 3 decimales es decimal.
            dec = '.' if len(d.split('.')[1]) != 3 else ','
    else:
        dec = '.'
    if dec == ',':
        d = d.replace('.', '').replace(',', '.')
    else:
        d = d.replace(',', '')
    try:
        v = float(d)
    except ValueError:
        return None
    return -v if neg else v


def parse_rate(s):
    """'9.50%' -> 0.095 ; '0.07' -> 0.07 ; '1.2996' -> 1.2996 ; '18,00%' -> 0.18"""
    if s is None:
        return None
    s = str(s).strip()
    pct = '%' in s
    d = re.sub(r'[^\d.,-]', '', s)
    if ',' in d and '.' not in d:
        d = d.replace(',', '.')
    else:
        d = d.replace(',', '')
    try:
        v = float(d)
    except ValueError:
        return None
    return v / 100 if pct else v


def parse_doc(doc):
    """Devuelve (fields, items): fields = {clave_normalizada: [valores]}, items = lista de dicts de filas '  - A x | B y'."""
    fields, items = {}, []
    for ln in unwrap(doc.get('ocr_text') or ''):
        s = ln.strip()
        if s.startswith('- '):
            row = {}
            for part in s[2:].split(' | '):
                part = part.strip()
                m = re.match(r'^(.*?)\s+((?:[A-Z]{3}\s|[$€£¥₹-]|\(|\d).*)$', part)
                # clave = palabras hasta el primer valor; para texto libre (Description X) la primera palabra
                if part.lower().startswith(('description ', 'tenant ', 'reference ', 'customer ', 'obligation ',
                                            'release pattern ', 'document type ', 'status ', 'sku ', 'unit ', 'date ',
                                            'material ', 'account ', 'section ', 'invoice ', 'type ')):
                    # claves de varias palabras conocidas primero
                    km = re.match(r'^(Release Pattern|Document Type|Unit Cost|Unit Price|Running Balance|Invoice Line Amount|Ssp Amount)\s+(.*)$', part)
                    if km:
                        row[km.group(1).lower()] = km.group(2)
                        continue
                    k, _, v = part.partition(' ')
                    row[k.lower()] = v
                elif m:
                    row[m.group(1).lower()] = m.group(2)
                else:
                    k, _, v = part.partition(' ')
                    row[k.lower()] = v
            if row:
                row['_raw'] = s[2:]
                items.append(row)
            continue
        m = re.match(r'^([A-Za-z][A-Za-z0-9 /&\'().-]{0,60}?):\s*(.*)$', s)
        if m:
            fields.setdefault(m.group(1).strip().lower(), []).append(m.group(2).strip())
    return fields, items


def f1(fields, *keys):
    for k in keys:
        v = fields.get(k.lower())
        if v:
            return v[0]
    return None


def amt(fields, *keys):
    return parse_amount(f1(fields, *keys))


# ======================= engine.py
"""Motor de cierre FinBalance: documentos OCR -> asientos -> balance. Solo librería estándar."""
import re
from collections import defaultdict


TOL = 0.011
PNL_WORDS = ('Revenue', 'Expense', 'Cost of Goods Sold', 'Gain', 'Loss')
CONTRA_ASSET = ('Accumulated Depreciation',)
LIAB_WORDS = ('Payable', 'Accrued', 'Liability', 'Unearned', 'Deferred Revenue', 'Deferred Tax Liability')
EQUITY_WORDS = ('Capital', 'Equity', 'Retained Earnings', 'Drawings', 'Dividends')


def r2(x):
    return round(x + 1e-9 if x >= 0 else x - 1e-9, 2)


def is_pnl(a):
    return any(w in a for w in PNL_WORDS) and 'Payable' not in a


class Packet:
    def __init__(self, rec):
        self.rec = rec
        self.ctx = rec.get('context') or {}
        self.allowed = list(rec.get('allowed_accounts') or [])
        self.regime = (self.ctx.get('tax_regime') or '').lower()
        self.func = self.ctx.get('functional_currency_code') or self.ctx.get('currency_code')
        self.docs = sorted(rec.get('documents') or [], key=lambda d: d.get('doc_id', ''))
        self.P = {}
        for d in self.docs:
            try:
                self.P[d['doc_id']] = parse_doc(d)
            except Exception:
                self.P[d['doc_id']] = ({}, [])
        self.T = {d['doc_id']: d.get('doc_type', '') for d in self.docs}
        # índice de referencias -> documentos
        self.idx = defaultdict(list)
        for d in self.docs:
            f, _ = self.P[d['doc_id']]
            for k, vs in f.items():
                if re.search(r'(number|\bid|^schedule id|^report id|^batch id|^sheet id|^note id)$', k) or k in (
                        'invoice number', 'run number', 'roll number', 'grn number', 'transfer number', 'form number'):
                    for v in vs:
                        self.idx[v.strip()].append(d['doc_id'])
        self.entries = []
        self.used = set()
        self.fx = {}  # referencia -> (rate, notice doc)
        for d in self.docs:
            if self.T[d['doc_id']] == 'exchange_rate_notice':
                f, _ = self.P[d['doc_id']]
                ref = f1(f, 'reference')
                rate = parse_rate(f1(f, 'exchange rate'))
                if ref and rate:
                    self.fx[ref] = (rate, d['doc_id'], amt(f, 'functional amount'), amt(f, 'source amount'))

    # utilidades
    def acct(self, *cands, default=None):
        for c in cands:
            if c in self.allowed:
                return c
        low = {a.lower(): a for a in self.allowed}
        for c in cands:
            if c and c.lower() in low:
                return low[c.lower()]
        return default if default is not None else cands[0]

    def find(self, ref, types=None):
        out = []
        for did in self.idx.get((ref or '').strip(), []):
            if types is None or self.T[did] in types:
                out.append(did)
        return out

    def docs_of(self, *types):
        return [d['doc_id'] for d in self.docs if self.T[d['doc_id']] in types]

    def post(self, refs, dr, cr, amount):
        if amount is None:
            return
        a = r2(amount)
        if abs(a) < 0.005:
            return
        if a < 0:
            dr, cr, a = cr, dr, -a
        refs = list(dict.fromkeys([r for r in refs if r]))
        self.entries.append({'doc_refs': refs, 'debit_account': dr, 'credit_account': cr, 'amount': a})
        self.used.update(refs)

    def balance_sheet(self):
        ob = self.rec.get('opening_balance') or {}
        bal = defaultdict(float)  # saldo deudor
        section = {}
        for s in ('assets', 'liabilities', 'equity'):
            for a, v in (ob.get(s) or {}).items():
                section[a] = s
                bal[a] += v if s == 'assets' else -v
        for e in self.entries:
            bal[e['debit_account']] += e['amount']
            bal[e['credit_account']] -= e['amount']
        re_acct = self.acct('Retained Earnings')
        out = {'assets': {}, 'liabilities': {}, 'equity': {}}
        pnl = 0.0
        for a, v in bal.items():
            if a not in section and is_pnl(a):
                pnl += v
                continue
            s = section.get(a)
            if s is None:
                if a in CONTRA_ASSET or not (any(w in a for w in LIAB_WORDS) or any(w in a for w in EQUITY_WORDS)):
                    s = 'assets'
                elif any(w in a for w in EQUITY_WORDS):
                    s = 'equity'
                else:
                    s = 'liabilities'
            out[s][a] = v if s == 'assets' else -v
        out['equity'][re_acct] = out['equity'].get(re_acct, 0.0) - pnl
        for s in out:
            out[s] = {a: r2(v) for a, v in out[s].items() if abs(r2(v)) >= 0.005}
        return out


# ======================= handlers.py
"""Un manejador por tipo de documento. Cada uno propone asientos sobre Packet.post()."""
import re



SKIP_TYPES = {'opening_trial_balance', 'bank_statement', 'memo', 'secondary_copy', 'vendor_statement', 'cancellation_note',
              'production_batch_sheet', 'goods_receipt_note', 'delivery_note', 'work_order', 'tax_regime_notice',
              'tax_exemption_certificate', 'customer_tax_profile', 'pos_batch_report', 'inventory_adjustment_note',
              'lease_amortization_schedule', 'lease_payment_notice', 'sale_proceeds_advice', 'exchange_rate_notice',
              'ssp_rate_card', 'performance_obligation_schedule', 'implementation_acceptance_memo', 'tax_depreciation_schedule',
              'ar_aging_summary', 'inventory_rollforward', 'renewal_notice'}


def by_field(pk, field, value, types=None):
    out = []
    if not value:
        return out
    for d in pk.docs:
        did = d['doc_id']
        if types and pk.T[did] not in types:
            continue
        f, _ = pk.P[did]
        if value in (f.get(field) or []):
            out.append(did)
    return out


def withdrawn(pk):
    w = set()
    for did in pk.docs_of('cancellation_note'):
        f, _ = pk.P[did]
        for v in f.get('withdrawn reference', []):
            w.add(v.strip())
    return w


def fxrate(pk, f):
    """Factor a moneda funcional para un documento en otra divisa (solo con evidencia visible)."""
    num = f1(f, 'invoice number', 'reference')
    cur = f1(f, 'currency')
    if num in pk.fx:
        return pk.fx[num][0], [pk.fx[num][1]]
    if cur and pk.func and cur.strip() != pk.func:
        # sin tipo visible: no se inventa (se deja 1 y se registra)
        pk.warn.append(f'divisa {cur} sin tipo de cambio visible ({num})')
    return 1.0, []


def tax_parts(pk, f, side):
    """Devuelve lista (cuenta, importe) de impuesto indirecto para compras (side='in') o ventas (side='out')."""
    out = []
    cg, sg, ig = amt(f, 'cgst amount'), amt(f, 'sgst amount'), amt(f, 'igst amount')
    tax = amt(f, 'tax amount')
    if cg or sg or ig:
        if side == 'in':
            for a, v in (('Input CGST Receivable', cg), ('Input SGST Receivable', sg), ('Input IGST Receivable', ig)):
                if v:
                    out.append((pk.acct(a), v))
        else:
            for a, v in (('CGST Payable', cg), ('SGST Payable', sg), ('IGST Payable', ig)):
                if v:
                    out.append((pk.acct(a), v))
        return out
    if tax:
        if side == 'in':
            out.append((pk.acct('Input Tax Receivable'), tax))
        else:
            out.append((pk.acct('Sales Tax Payable'), tax))
    return out


def purchase(pk, did, base_acct, refs, cr_acct='Accounts Payable', f=None):
    f = f or pk.P[did][0]
    rate, fxrefs = fxrate(pk, f)
    refs = refs + fxrefs
    sub, total = amt(f, 'subtotal'), amt(f, 'total')
    taxes = tax_parts(pk, f, 'in')
    embed = pk.regime == 'us_sales_tax' and not (amt(f, 'cgst amount') or amt(f, 'sgst amount') or amt(f, 'igst amount'))
    if sub is None:
        sub = (total or 0) - sum(v for _, v in taxes)
    if embed:
        pk.post(refs, base_acct, cr_acct, (sub + sum(v for _, v in taxes)) * rate)
        return
    num = f1(f, 'invoice number')
    if fxrefs and not taxes and pk.fx.get(num, (0, 0, None))[2] is not None:
        pk.post(refs, base_acct, cr_acct, pk.fx[num][2])
        return
    pk.post(refs, base_acct, cr_acct, sub * rate)
    for a, v in taxes:
        pk.post(refs, a, cr_acct, v * rate)


def sale(pk, did, rev_acct, refs, dr_acct='Accounts Receivable', f=None):
    f = f or pk.P[did][0]
    rate, fxrefs = fxrate(pk, f)
    refs = refs + fxrefs
    sub, total = amt(f, 'subtotal'), amt(f, 'total')
    taxes = tax_parts(pk, f, 'out')
    if sub is None:
        sub = (total or 0) - sum(v for _, v in taxes)
    if rate != 1.0 and fxrefs and pk.fx.get(f1(f, 'invoice number'), (0, 0, None))[2] is not None and not taxes:
        pk.post(refs, dr_acct, rev_acct, pk.fx[f1(f, 'invoice number')][2])
    else:
        pk.post(refs, dr_acct, rev_acct, sub * rate)
    for a, v in taxes:
        pk.post(refs, dr_acct, a, v * rate)


# ---------------------------------------------------------------- compras

def h_supplier_invoice(pk, did):
    f, _ = pk.P[did]
    if f1(f, 'invoice number') in pk.withdrawn:
        return
    refs = [did]
    grn = f1(f, 'goods receipt ref')
    if grn:
        refs = pk.find(grn, {'goods_receipt_note'}) + refs
    # aviso de régimen fiscal que soporta el impuesto de esta factura
    tax = amt(f, 'tax amount')
    for t in pk.docs_of('tax_regime_notice'):
        tf, _ = pk.P[t]
        if tax is not None and amt(tf, 'jurisdiction tax amount') is not None and abs(amt(tf, 'jurisdiction tax amount') - tax) < 0.011:
            refs = [t] + refs
    cat = f1(f, 'expense category')
    if cat and cat in pk.allowed:
        base = cat
    else:
        base = pk.acct('Raw Materials Inventory', 'Inventory')
        if 'Raw Materials Inventory' in pk.allowed and 'Inventory' in pk.allowed:
            base = 'Inventory' if not pk.docs_of('material_requisition_slip') else 'Raw Materials Inventory'
    purchase(pk, did, base, refs)


def h_vendor_invoice(pk, did):
    f, _ = pk.P[did]
    if f1(f, 'invoice number') in pk.withdrawn:
        return
    lab = f1(f, 'expense label', 'expense category')
    base = lab if lab in pk.allowed else pk.acct(lab or 'Office Supplies Expense')
    purchase(pk, did, base, [did])


def h_utilities_statement(pk, did):
    f, it = pk.P[did]
    total = amt(f, 'total')
    if total is None:
        total = sum(parse_amount(i.get('amount')) or 0 for i in it)
    rate, fxrefs = fxrate(pk, f)
    if amt(f, 'tax amount'):
        purchase(pk, did, pk.acct('Utilities Expense'), [did])
    else:
        pk.post([did] + fxrefs, pk.acct('Utilities Expense'), pk.acct('Accounts Payable'), total * rate)


def expense_account_from_text(pk, texts, default='Office Supplies Expense'):
    exp = [a for a in pk.allowed if a.endswith('Expense')]
    for t in texts:
        for a in exp:
            if a.lower() in t.lower():
                return a
    kw = {'fuel': 'Fuel Expense', 'travel': 'Travel Expense', 'mileage': 'Travel Expense', 'hotel': 'Travel Expense',
          'taxi': 'Travel Expense', 'meal': 'Travel Expense', 'office': 'Office Supplies Expense', 'repair': 'Repairs Expense',
          'maint': 'Maintenance Expense', 'util': 'Utilities Expense'}
    for t in texts:
        for k, a in kw.items():
            if k in t.lower() and a in pk.allowed:
                return a
    return pk.acct(default)


def h_expense_receipt(pk, did):
    f, it = pk.P[did]
    total = amt(f, 'total')
    if total is None:
        total = sum(parse_amount(i.get('amount')) or 0 for i in it)
    a = expense_account_from_text(pk, [i.get('description', '') for i in it] + [f1(f, 'merchant') or ''])
    method = (f1(f, 'payment method') or '').lower()
    cr = pk.acct('Cash')
    if amt(f, 'tax amount'):
        purchase(pk, did, a, [did], cr_acct=cr)
    else:
        pk.post([did], a, cr, total)


def h_equipment_invoice(pk, did):
    f, _ = pk.P[did]
    # en los ejemplos resueltos la compra va siempre a Equipment si está permitida (aunque sea una furgoneta o un expositor)
    asset = next((a for a in ('Equipment', 'Store Fixtures', 'Furniture', 'Vehicles') if a in pk.allowed), 'Equipment')
    cash, fin, total = amt(f, 'paid cash'), amt(f, 'financed amount'), amt(f, 'total')
    if cash is None and fin is None:
        cash = total
    pk.post([did], asset, pk.acct('Cash'), cash or 0)
    pk.post([did], asset, pk.acct('Notes Payable'), fin or 0)


# ---------------------------------------------------------------- ventas

def h_customer_invoice(pk, did):
    f, it = pk.P[did]
    num = f1(f, 'invoice number')
    if num in pk.withdrawn:
        return
    refs = [did]
    rev = None
    cogs = []
    shp = f1(f, 'shipment ref')
    if shp:
        for dn in by_field(pk, 'shipment ref', shp, {'delivery_note'}):
            refs = [dn] + refs
            df, _ = pk.P[dn]
            cogs.append((dn, amt(df, 'cost basis amount'), pk.acct('Inventory', 'Finished Goods Inventory')))
            rev = pk.acct('Sales Revenue')
    cref = f1(f, 'contract ref')
    if cref:
        for fg in pk.find(cref, {'finished_goods_transfer_note'}):
            refs = refs + [fg]
            ff, _ = pk.P[fg]
            cogs.append((fg, amt(ff, 'transfer value'), pk.acct('Finished Goods Inventory', 'Inventory')))
            rev = pk.acct('Sales Revenue')
    job = f1(f, 'job code')
    if job:
        wos = pk.find(job, {'work_order'})
        refs = wos + refs
    ex = f1(f, 'exemption certificate')
    if ex:
        refs = pk.find(ex, {'tax_exemption_certificate'}) + by_field(pk, 'exemption certificate', ex, {'customer_tax_profile'}) + refs
    if rev is None:
        rev = pk.acct('Service Revenue', 'Sales Revenue')
        if pk.rec.get('industry') in ('retail', 'wholesale_distribution', 'manufacturing') and 'Sales Revenue' in pk.allowed:
            rev = 'Sales Revenue'
    # ASC 606 / retainer: el contrato decide (ver h_contracts)
    if num in pk.deferred_invoices:
        rev = pk.acct('Unearned Revenue')
        cref = f1(f, 'contract ref')
        refs = refs + (pk.find(cref, {'subscription_order_form'}) if cref else [])
    dr = pk.acct('Accounts Receivable')
    if collected_at_invoice(pk, num):
        dr = pk.acct('Cash')
    sale(pk, did, rev, refs, dr_acct=dr)
    for src, v, inv in cogs:
        pk.post(refs, pk.acct('Cost of Goods Sold'), inv, v)


def collected_at_invoice(pk, num):
    """Cobro anticipado: el extracto cita la factura y ningún documento de cobro la liquida."""
    if not num:
        return False
    pat = re.compile(r'(?<![\w-])' + re.escape(num) + r'(?![\w-])')
    for d in pk.docs_of('payment_advice', 'copay_receipt', 'insurer_remittance'):
        if pat.search(pk.text(d)):
            return False
    for b in pk.docs_of('bank_statement'):
        for i in pk.P[b][1]:
            desc = i.get('description', '')
            if pat.search(desc) and (parse_amount(i.get('amount')) or 0) > 0 and 'settlement' not in desc.lower():
                return True
    return False


def h_patient_invoice(pk, did):
    f, _ = pk.P[did]
    pk.post([did], pk.acct('Accounts Receivable'), pk.acct('Service Revenue'), amt(f, 'gross charge', 'total'))


def h_rent_roll(pk, did):
    f, it = pk.P[did]
    tot = amt(f, 'total rent')
    if tot is None:
        tot = sum(parse_amount(i.get('amount')) or 0 for i in it)
    pk.post([did], pk.acct('Accounts Receivable'), pk.acct('Rental Revenue'), tot)


def h_copay_receipt(pk, did):
    f, _ = pk.P[did]
    refs = [did] + pk.find(f1(f, 'reference invoice'))
    pk.post(refs, pk.acct('Cash'), pk.acct('Accounts Receivable'), amt(f, 'amount'))


def h_insurer_remittance(pk, did):
    f, _ = pk.P[did]
    refs = [did] + pk.find(f1(f, 'claim reference'))
    pk.post(refs, pk.acct('Cash'), pk.acct('Accounts Receivable'), amt(f, 'paid amount', 'approved amount'))


AR_TYPES = {'customer_invoice', 'patient_invoice', 'rent_roll'}
AP_TYPES = {'supplier_invoice', 'vendor_invoice', 'utilities_statement', 'equipment_invoice'}


def h_payment_advice(pk, did):
    f, it = pk.P[did]
    amount = amt(f, 'amount')
    refs_txt = [i.get('reference') for i in it if i.get('reference')] or [f1(f, 'reference')]
    targets = []
    for r in refs_txt:
        targets += pk.find(r)
    targets = [t for t in targets if pk.T[t] not in ('payment_advice', 'secondary_copy')]
    kinds = {pk.T[t] for t in targets}
    pf = (f1(f, 'payment for') or '').lower()
    if kinds & AR_TYPES or 'customer' in pf:
        side = 'ar'
    elif kinds & AP_TYPES or 'supplier' in pf or 'vendor' in pf:
        side = 'ap'
    else:
        side = 'ap'
    refs = [did] + targets
    fxd = amt(f, 'fx difference')
    if fxd and f1(f, 'source amount'):
        # liquidación en divisa: saldo registrado = importe funcional -/+ diferencia
        booked = None
        for t in targets:
            num = f1(pk.P[t][0], 'invoice number')
            if num in pk.fx and pk.fx[num][2] is not None:
                booked = pk.fx[num][2]
        if booked is None:
            booked = amount + (fxd if side == 'ap' else -fxd)
        diff = r2(amount - booked)
        if side == 'ar':
            pk.post(refs, pk.acct('Cash'), pk.acct('Accounts Receivable'), amount)
            pk.post(refs, pk.acct('Foreign Exchange Loss'), pk.acct('Accounts Receivable'), -diff) if diff < 0 else \
                pk.post(refs, pk.acct('Accounts Receivable'), pk.acct('Foreign Exchange Gain'), diff)
            pk.post(refs, pk.acct('Accounts Receivable'), pk.acct('Accounts Receivable'), 0)
        else:
            pk.post(refs, pk.acct('Accounts Payable'), pk.acct('Cash'), amount)
            if diff > 0:
                pk.post(refs, pk.acct('Foreign Exchange Loss'), pk.acct('Accounts Payable'), diff)
            else:
                pk.post(refs, pk.acct('Accounts Payable'), pk.acct('Foreign Exchange Gain'), -diff)
        return
    if side == 'ar':
        pk.post(refs, pk.acct('Cash'), pk.acct('Accounts Receivable'), amount)
    else:
        pk.post(refs, pk.acct('Accounts Payable'), pk.acct('Cash'), amount)


# ---------------------------------------------------------------- nóminas, préstamos, activos

def h_payroll_summary(pk, did):
    f, _ = pk.P[did]
    pk.post([did], pk.acct('Salaries Expense'), pk.acct('Cash'), amt(f, 'gross pay'))
    pk.post([did], pk.acct('Payroll Tax Expense'), pk.acct('Cash'), amt(f, 'employer tax'))


def h_loan_statement(pk, did):
    f, _ = pk.P[did]
    pk.post([did], pk.acct('Cash'), pk.acct('Loans Payable'), amt(f, 'draw amount'))
    pk.post([did], pk.acct('Loans Payable'), pk.acct('Cash'), amt(f, 'principal paid'))
    pk.post([did], pk.acct('Interest Expense'), pk.acct('Cash'), amt(f, 'interest paid'))


def h_depreciation(pk, did):
    f, _ = pk.P[did]
    pk.post([did], pk.acct('Depreciation Expense'), pk.acct('Accumulated Depreciation'),
            amt(f, 'current period charge', 'current charge'))


def h_asset_disposal_notice(pk, did):
    f, _ = pk.P[did]
    tag = f1(f, 'asset tag')
    refs = [did] + by_field(pk, 'asset tag', tag, {'sale_proceeds_advice'})
    cost, ad, proceeds, gl = amt(f, 'original cost'), amt(f, 'accumulated depreciation'), amt(f, 'proceeds amount'), amt(f, 'gain loss amount')
    asset = pk.acct('Equipment')
    for d2 in by_field(pk, 'asset tag', tag, {'equipment_invoice'}):
        for e in pk.entries:
            if d2 in e['doc_refs'] and e['debit_account'] not in ('Cash',):
                asset = e['debit_account']
    for a in ('Equipment', 'Vehicles', 'Furniture', 'Store Fixtures'):
        if a.lower().rstrip('s') in (f1(f, 'asset name') or '').lower() and a in pk.allowed:
            asset = a
    typ = (f1(f, 'gain loss type') or '').lower()
    if gl is None and None not in (cost, ad, proceeds):
        gl = proceeds - (cost - ad)
        typ = 'gain' if gl >= 0 else 'loss'
    pk.post(refs, pk.acct('Cash'), asset, proceeds)
    pk.post(refs, pk.acct('Accumulated Depreciation'), asset, ad)
    if 'loss' in typ:
        pk.post(refs, pk.acct('Loss on Disposal'), asset, abs(gl or 0))
    else:
        pk.post(refs, asset, pk.acct('Gain on Disposal'), abs(gl or 0))


# ---------------------------------------------------------------- inmobiliario

def h_security_deposit_notice(pk, did):
    f, _ = pk.P[did]
    num = (f1(f, 'notice number') or '').upper()
    txt = pk.text(did).lower()
    if 'REF' in num or 'refund' in txt or 'return' in txt:
        tenant = f1(f, 'tenant')
        orig = [d for d in by_field(pk, 'tenant', tenant, {'security_deposit_notice'}) if d != did and
                'REF' not in (f1(pk.P[d][0], 'notice number') or '').upper()]
        pk.post([did] + orig[:1], pk.acct('Security Deposits Payable'), pk.acct('Cash'), amt(f, 'amount'))
    else:
        pk.post([did], pk.acct('Cash'), pk.acct('Security Deposits Payable'), amt(f, 'amount'))


def h_prepaid(pk, did):
    f, _ = pk.P[did]
    t = pk.T[did]
    prepaid = pk.acct('Prepaid Insurance') if t == 'insurance_notice' else pk.acct('Prepaid Rent')
    total = amt(f, 'total premium', 'total')
    pk.post([did], prepaid, pk.acct('Cash'), total)


def h_service_period_memo(pk, did):
    f, _ = pk.P[did]
    ref = f1(f, 'reference')
    amount = amt(f, 'recognized amount', 'amount')
    src = [d for d in pk.find(ref) if d != did]
    subj = (f1(f, 'subject') or '').lower()
    for s in src:
        t = pk.T[s]
        if t == 'insurance_notice':
            pk.post([s, did], pk.acct('Insurance Expense'), pk.acct('Prepaid Insurance'), amount)
            return
        if t == 'rent_notice':
            pk.post([s, did], pk.acct('Rent Expense'), pk.acct('Prepaid Rent'), amount)
            return
        if t in ('retainer_agreement_memo', 'customer_invoice', 'subscription_order_form'):
            pk.post([did, s], pk.acct('Unearned Revenue'), pk.acct('Service Revenue'), amount)
            return
    if 'insurance' in subj and 'release' in subj:
        pk.post([did], pk.acct('Insurance Expense'), pk.acct('Prepaid Insurance'), amount)
    elif 'rent' in subj and 'release' in subj:
        pk.post([did], pk.acct('Rent Expense'), pk.acct('Prepaid Rent'), amount)
    elif 'revenue' in subj or 'retainer' in subj:
        pk.post([did] + src, pk.acct('Unearned Revenue'), pk.acct('Service Revenue'), amount)
    else:
        a = expense_account_from_text(pk, [subj, pk.text(did)], default='Office Supplies Expense')
        pk.post([did] + src, a, pk.acct('Accrued Expenses'), amount)


# ---------------------------------------------------------------- inventario / fabricación

def h_material_requisition_slip(pk, did):
    f, _ = pk.P[did]
    refs = [did] + pk.find(f1(f, 'batch id'), {'production_batch_sheet'})
    mat = f1(f, 'material')
    for s in pk.docs_of('supplier_invoice'):
        if mat and mat.lower() in pk.text(s).lower():
            refs.append(s)
            break
    pk.post(refs, pk.acct('Work In Process'), pk.acct('Raw Materials Inventory', 'Inventory'), amt(f, 'issue value'))


def h_finished_goods_transfer_note(pk, did):
    f, _ = pk.P[did]
    refs = [did] + pk.find(f1(f, 'batch id'), {'production_batch_sheet'})
    pk.post(refs, pk.acct('Finished Goods Inventory'), pk.acct('Work In Process'), amt(f, 'transfer value'))


def h_direct_labor_record(pk, did):
    f, _ = pk.P[did]
    refs = [did] + pk.find(f1(f, 'batch id'), {'production_batch_sheet'})
    pk.post(refs, pk.acct('Work In Process'), pk.acct('Cash'), amt(f, 'labor cash paid', 'labor value'))


def h_overhead_accrual_memo(pk, did):
    f, _ = pk.P[did]
    refs = [did] + pk.find(f1(f, 'batch id'), {'production_batch_sheet'})
    pk.post(refs, pk.acct('Work In Process'), pk.acct('Accrued Expenses'), amt(f, 'accrued overhead', 'overhead value'))


def h_stock_count_sheet(pk, did):
    f, it = pk.P[did]
    sid = f1(f, 'sheet id')
    notes = by_field(pk, 'reference sheet', sid, {'inventory_adjustment_note'})
    inv = pk.acct('Inventory', 'Finished Goods Inventory')
    if notes:
        for n in notes:
            pk.post([did, n], pk.acct('Inventory Shrinkage Expense'), inv, amt(pk.P[n][0], 'amount'))
        return
    # sin nota: se calcula del recuento
    tot = 0.0
    for i in it:
        try:
            tot += (float(parse_amount(i.get('system qty'))) - float(parse_amount(i.get('counted qty')))) * parse_amount(i.get('unit cost'))
        except Exception:
            pass
    tot = r2(tot)
    rf = [d for d in pk.docs_of('inventory_rollforward') if abs((amt(pk.P[d][0], 'write down') or -1) - tot) < 0.011]
    if not rf and len(pk.docs_of('stock_count_sheet')) == 1 and pk.docs_of('inventory_rollforward'):
        rf = pk.docs_of('inventory_rollforward')[:1]
        wd = amt(pk.P[rf[0]][0], 'write down')
        tot = wd if wd is not None else tot
    pk.post([did] + rf[:1], pk.acct('Inventory Shrinkage Expense'), inv, tot)


def h_scrap_report(pk, did):
    f, _ = pk.P[did]
    inv = pk.acct('Finished Goods Inventory', 'Inventory')
    refs = [did] + pk.docs_of('opening_trial_balance')
    pk.post(refs, pk.acct('Inventory Shrinkage Expense'), inv, amt(f, 'write down', 'amount'))


def h_return_note(pk, did):
    f, _ = pk.P[did]
    pk.post([did], pk.acct('Sales Revenue'), pk.acct('Cash'), amt(f, 'amount'))


def h_sales_summary(pk, did):
    f, _ = pk.P[did]
    card = amt(f, 'card sales') or 0.0
    cash = amt(f, 'cash sales') or 0.0
    tax = amt(f, 'tax amount') or 0.0
    net = amt(f, 'net sales')
    refs = [did]
    batches = [b for b in pk.docs_of('pos_batch_report') if abs((amt(pk.P[b][0], 'batch total') or -1) - card) < 0.011]
    refs += batches[:1]
    gross = cash + card
    tax_cash = r2(tax * cash / gross) if gross else 0.0
    tax_card = r2(tax - tax_cash)
    rev = pk.acct('Sales Revenue')
    clr = pk.acct('Card Settlement Clearing')
    pk.post(refs, pk.acct('Cash'), rev, cash - tax_cash)
    pk.post(refs, clr, rev, card - tax_card)
    pk.post(refs, pk.acct('Cost of Goods Sold'), pk.acct('Inventory', 'Finished Goods Inventory'), amt(f, 'cogs amount'))
    pk.post(refs, pk.acct('Cash'), pk.acct('Sales Tax Payable'), tax_cash)
    pk.post(refs, clr, pk.acct('Sales Tax Payable'), tax_card)


def h_card_settlement_report(pk, did):
    f, it = pk.P[did]
    refs = [did]
    for i in it:
        refs += pk.find(i.get('_raw', '').strip(), {'pos_batch_report'})
    fee_acct = pk.acct('Bank Fees Expense', 'Merchant Fees Expense', 'Card Fees Expense', 'Maintenance Expense')
    clr = pk.acct('Card Settlement Clearing')
    pk.post(refs, pk.acct('Cash'), clr, amt(f, 'net deposit'))
    pk.post(refs, fee_acct, clr, amt(f, 'fees'))


# ---------------------------------------------------------------- tesorería, correcciones

def h_transfer_advice(pk, did):
    f, _ = pk.P[did]
    src = f1(f, 'from account') or 'Cash'
    dst = f1(f, 'to account') or 'Reserve Cash'
    pk.post([did], pk.acct(dst), pk.acct(src), amt(f, 'amount'))


def h_reclassification_memo(pk, did):
    f, _ = pk.P[did]
    refs = [did] + pk.find(f1(f, 'original reference'))
    pk.post(refs, pk.acct(f1(f, 'to account') or ''), pk.acct(f1(f, 'from account') or ''), amt(f, 'amount'))


def h_credit_memo(pk, did):
    f, _ = pk.P[did]
    reason = (f1(f, 'reason') or '').lower()
    ref = f1(f, 'reference')
    inv = pk.find(ref, {'customer_invoice', 'patient_invoice', 'rent_roll'})
    aging = [a for a in pk.docs_of('ar_aging_summary') if ref and ref in pk.text(a)]
    if 'bad debt' in reason or 'write' in reason or aging:
        pk.post(aging + [did] + inv, pk.acct('Bad Debt Expense'), pk.acct('Accounts Receivable'), amt(f, 'amount'))
    else:
        rev = pk.acct('Sales Revenue', 'Service Revenue')
        for e in pk.entries:
            if inv and inv[0] in e['doc_refs'] and e['debit_account'] == 'Accounts Receivable' and 'Revenue' in e['credit_account']:
                rev = e['credit_account']
        pk.post([did] + inv, rev, pk.acct('Accounts Receivable'), amt(f, 'amount'))


def h_deferred_tax_memo(pk, did):
    f, _ = pk.P[did]
    tag = f1(f, 'asset tag')
    mv = amt(f, 'deferred tax expense amount', 'current period deferred tax movement')
    sch = by_field(pk, 'asset tag', tag, {'tax_depreciation_schedule'})
    best = [s for s in sch if mv is not None and amt(pk.P[s][0], 'temporary difference amount') is not None and
            parse_rate(f1(pk.P[s][0], 'tax rate')) is not None and
            abs(round(amt(pk.P[s][0], 'temporary difference amount') * parse_rate(f1(pk.P[s][0], 'tax rate')), 2) - abs(mv)) < 0.011]
    refs = (best[:1] or sch[:1]) + [did]
    # movimiento negativo (la diferencia revierte): beneficio por impuesto diferido
    pk.post(refs, pk.acct('Deferred Tax Expense'), pk.acct('Deferred Tax Liability'), mv)


def h_fx_remeasurement_memo(pk, did):
    f, _ = pk.P[did]
    ref = f1(f, 'reference')
    tgt = [d for d in pk.find(ref) if pk.T[d] in AR_TYPES | AP_TYPES]
    refs = [did] + tgt + ([pk.fx[ref][1]] if ref in pk.fx else [])
    booked, rem = amt(f, 'booked amount'), amt(f, 'remeasured amount')
    diff = (rem - booked) if None not in (booked, rem) else amt(f, 'difference amount')
    ap = any(pk.T[t] in AP_TYPES for t in tgt)
    bal = pk.acct('Accounts Payable') if ap else pk.acct('Accounts Receivable')
    if ap:
        diff = -diff
    if diff >= 0:
        pk.post(refs, bal, pk.acct('Foreign Exchange Gain'), abs(diff)) if not ap else \
            pk.post(refs, bal, pk.acct('Foreign Exchange Gain'), abs(diff))
    else:
        pk.post(refs, pk.acct('Foreign Exchange Loss'), bal, abs(diff))


def h_lease_agreement(pk, did):
    f, _ = pk.P[did]
    ag = f1(f, 'agreement number')
    rou, liab = pk.acct('Right-of-Use Asset'), pk.acct('Lease Liability')
    pk.post([did], rou, liab, amt(f, 'rou asset amount', 'lease liability amount'))
    scheds = by_field(pk, 'agreement number', ag, {'lease_amortization_schedule'})
    pays = by_field(pk, 'agreement number', ag, {'lease_payment_notice'})
    for s in scheds:
        sf, _ = pk.P[s]
        prin, intr = amt(sf, 'principal amount'), amt(sf, 'interest amount')
        if pays:
            pk.post([did, s] + pays, liab, pk.acct('Cash'), prin)
            pk.post([did, s] + pays, pk.acct('Lease Interest Expense'), pk.acct('Cash'), intr)
        pk.post([did, s], pk.acct('Lease Amortization Expense'), rou, amt(sf, 'rou amortization amount'))


def h_lease_modification_notice(pk, did):
    f, _ = pk.P[did]
    ag = f1(f, 'agreement number')
    refs = [did] + by_field(pk, 'agreement number', ag, {'lease_agreement'})
    d = amt(f, 'liability remeasurement delta amount', 'rou asset adjustment amount')
    pk.post(refs, pk.acct('Right-of-Use Asset'), pk.acct('Lease Liability'), d)


HANDLERS = {
    'supplier_invoice': h_supplier_invoice, 'vendor_invoice': h_vendor_invoice, 'utilities_statement': h_utilities_statement,
    'expense_receipt': h_expense_receipt, 'equipment_invoice': h_equipment_invoice, 'customer_invoice': h_customer_invoice,
    'patient_invoice': h_patient_invoice, 'rent_roll': h_rent_roll, 'copay_receipt': h_copay_receipt,
    'insurer_remittance': h_insurer_remittance, 'payment_advice': h_payment_advice, 'payroll_summary': h_payroll_summary,
    'loan_statement': h_loan_statement, 'depreciation_schedule': h_depreciation, 'fixed_asset_rollforward': h_depreciation,
    'asset_disposal_notice': h_asset_disposal_notice, 'security_deposit_notice': h_security_deposit_notice,
    'insurance_notice': h_prepaid, 'rent_notice': h_prepaid, 'service_period_memo': h_service_period_memo,
    'material_requisition_slip': h_material_requisition_slip, 'finished_goods_transfer_note': h_finished_goods_transfer_note,
    'direct_labor_record': h_direct_labor_record, 'overhead_accrual_memo': h_overhead_accrual_memo,
    'stock_count_sheet': h_stock_count_sheet, 'scrap_report': h_scrap_report, 'return_note': h_return_note,
    'sales_summary': h_sales_summary, 'card_settlement_report': h_card_settlement_report,
    'transfer_advice': h_transfer_advice, 'reclassification_memo': h_reclassification_memo, 'credit_memo': h_credit_memo,
    'deferred_tax_memo': h_deferred_tax_memo, 'fx_remeasurement_memo': h_fx_remeasurement_memo,
    'lease_agreement': h_lease_agreement, 'lease_modification_notice': h_lease_modification_notice,
}


# ---------------------------------------------------------------- contratos (ASC 606, retainers, suscripciones)

def prepare_contracts(pk):
    """Facturas cuyo ingreso se difiere: las que cita un calendario de reconocimiento o un contrato ASC 606."""
    pk.contract_links = {}
    for s in pk.docs_of('revenue_recognition_schedule'):
        ref = f1(pk.P[s][0], 'contract reference')
        for inv in pk.find(ref, {'customer_invoice'}):
            pk.deferred_invoices.add(ref)
            pk.contract_links.setdefault(ref, []).append(s)
    for s in pk.docs_of('subscription_order_form'):
        ref = f1(pk.P[s][0], 'form number')
        for inv in by_field(pk, 'contract ref', ref, {'customer_invoice'}):
            pk.deferred_invoices.add(f1(pk.P[inv][0], 'invoice number'))
    for s in pk.docs_of('performance_obligation_schedule', 'ssp_rate_card'):
        ref = f1(pk.P[s][0], 'contract reference')
        for inv in by_field(pk, 'contract ref', ref, {'customer_invoice'}):
            num = f1(pk.P[inv][0], 'invoice number')
            pk.deferred_invoices.add(num)


def _rev(pk):
    return pk.acct('Service Revenue', 'Sales Revenue')


def post_contracts(pk):
    une = pk.acct('Unearned Revenue')
    for s in pk.docs_of('revenue_recognition_schedule'):
        f, _ = pk.P[s]
        ref = f1(f, 'contract reference')
        invs = [i for i in pk.find(ref, {'customer_invoice'}) if f1(pk.P[i][0], 'invoice number') not in pk.withdrawn]
        refs = [s] + invs
        # soporte del contrato: retainer con el mismo valor total, o formulario de suscripción citado por la factura
        for i in invs:
            fi, _ = pk.P[i]
            cref = f1(fi, 'contract ref')
            refs += pk.find(cref, {'subscription_order_form'}) if cref else []
            for r in pk.docs_of('retainer_agreement_memo'):
                if abs((amt(pk.P[r][0], 'total contract value') or -1) - (amt(fi, 'total') or -2)) < 0.011:
                    refs.append(r)
        pk.post(refs, une, _rev(pk), amt(f, 'released this period'))
    for s in pk.docs_of('performance_obligation_schedule'):
        f, it = pk.P[s]
        ref = f1(f, 'contract reference')
        invs = by_field(pk, 'contract ref', ref, {'customer_invoice'})
        accs = by_field(pk, 'contract reference', ref, {'implementation_acceptance_memo'})
        cards = by_field(pk, 'contract reference', ref, {'ssp_rate_card'})
        for i in it:
            rel = parse_amount(i.get('released this period'))
            pat = (i.get('release pattern') or '').lower()
            ob = (i.get('obligation') or '').lower()
            if 'accept' in pat:
                acc = [a for a in accs if (f1(pk.P[a][0], 'accepted obligation') or '').lower() == ob]
                if not acc:
                    continue  # sin memo de aceptación no se libera
                pk.post([s] + acc + invs, une, _rev(pk), rel)
            else:
                pk.post([s] + invs + cards, une, _rev(pk), rel)


# ======================= checks.py
"""Detectores de paquetes inconsistentes. Cada check es aritmética sobre importes visibles en UN documento
(o en documentos enlazados por referencia). Se devuelve solo la causa raíz (un código), como en los ejemplos resueltos."""
import re


TOL = 0.015


def ne(a, b, tol=TOL):
    return a is not None and b is not None and abs(a - b) > tol


def lines_sum(items, key='amount'):
    vals = [parse_amount(i.get(key)) for i in items if i.get(key) is not None]
    vals = [v for v in vals if v is not None]
    return round(sum(vals), 2) if vals else None


def doc_checks(pk, did):
    t = pk.T[did]
    f, it = pk.P[did]
    out = []
    if t == 'bank_statement':
        o, c = amt(f, 'opening balance'), amt(f, 'closing balance')
        s = lines_sum(it)
        if o is not None and c is not None and ne(o + (s or 0), c):
            out.append(('bank_closing_mismatch', f'{did}: apertura + movimientos != cierre'))
        else:
            run = o
            for i in it:
                a, rb = parse_amount(i.get('amount')), parse_amount(i.get('running balance'))
                if run is not None and a is not None:
                    run += a
                    if rb is not None and ne(run, rb):
                        out.append(('bank_closing_mismatch', f'{did}: saldo acumulado no cuadra'))
                        break
    if t in ('customer_invoice', 'supplier_invoice', 'vendor_invoice', 'utilities_statement', 'expense_receipt'):
        sub, tax, tot = amt(f, 'subtotal'), amt(f, 'tax amount'), amt(f, 'total')
        ls = lines_sum(it)
        base = sub if sub is not None else tot
        if ls is not None and ne(ls, base):
            out.append(('invoice_total_mismatch', f'{did}: suma de líneas {ls} != {base}'))
        if sub is not None and tax is not None and tot is not None and ne(sub + tax, tot):
            out.append(('tax_total_mismatch', f'{did}: base + impuesto != total'))
        rate = parse_rate(f1(f, 'tax rate'))
        if sub is not None and tax is not None and rate is not None and ne(round(sub * rate, 2), tax, 0.011):
            ex = f1(f, 'exemption certificate')
            if not (ex and abs(tax) < 0.005):
                out.append(('tax_rate_mismatch', f'{did}: base x tipo != impuesto'))
        cg, sg, ig = amt(f, 'cgst amount'), amt(f, 'sgst amount'), amt(f, 'igst amount')
        if tax is not None and (cg or sg or ig) and ne((cg or 0) + (sg or 0) + (ig or 0), tax):
            out.append(('input_tax_mismatch' if t != 'customer_invoice' else 'tax_total_mismatch',
                        f'{did}: CGST+SGST+IGST != impuesto'))
    if t == 'patient_invoice':
        g, p, i = amt(f, 'gross charge'), amt(f, 'patient due'), amt(f, 'insurer due')
        if None not in (g, p, i) and ne(p + i, g):
            out.append(('invoice_total_mismatch', f'{did}: paciente + aseguradora != bruto'))
    if t == 'vendor_statement':
        c = amt(f, 'closing balance')
        ls = lines_sum([i for i in it if 'outstanding' in (i.get('status') or '').lower() or 'open' in (i.get('document type') or '').lower()] or it)
        if ne(ls, c):
            out.append(('statement_balance_mismatch', f'{did}: líneas abiertas != saldo'))
    if t == 'payment_advice':
        alloc = [i for i in it if i.get('allocated amount')]
        if alloc:
            s = lines_sum(alloc, 'allocated amount')
            if ne(s, amt(f, 'amount')):
                out.append(('payment_allocation_mismatch', f'{did}: asignaciones != importe'))
        sa, r, fa, pa = amt(f, 'source amount'), parse_rate(f1(f, 'exchange rate')), amt(f, 'functional amount'), amt(f, 'amount')
        if (None not in (sa, r, pa) and ne(round(sa * r, 2), pa)) or (fa is not None and sa is not None and ne(fa, pa)):
            out.append(('fx_settlement_mismatch', f'{did}: origen x tipo != funcional'))
        fxd = amt(f, 'fx difference')
        if fxd is not None and sa is not None:
            for t2 in pk.find(f1(f, 'reference')):
                num = f1(pk.P[t2][0], 'invoice number')
                if num in pk.fx and pk.fx[num][2] is not None and pa is not None and ne(abs(pk.fx[num][2] - pa), abs(fxd)):
                    out.append(('fx_settlement_mismatch', f'{did}: registrado - pagado != diferencia'))
    if t == 'revenue_recognition_schedule':
        o, a, r, e = amt(f, 'opening deferred'), amt(f, 'added deferred'), amt(f, 'released this period'), amt(f, 'ending deferred')
        if None not in (o, a, r, e) and ne(o + a - r, e):
            out.append(('schedule_rollforward_mismatch', f'{did}: diferido inicial + altas - liberado != final'))
    if t == 'inventory_rollforward':
        o, a, u, w, e = (amt(f, k) for k in ('opening balance', 'additions', 'usage or sales', 'write down', 'ending balance'))
        if None not in (o, a, u, e) and ne(o + a - u - (w or 0), e):
            out.append(('inventory_rollforward_mismatch', f'{did}: rollforward de inventario no cuadra'))
    if t == 'fixed_asset_rollforward':
        o, a, d, e = (amt(f, k) for k in ('opening balance', 'additions', 'disposals', 'ending balance'))
        if None not in (o, a, d, e) and ne(o + a - d, e):
            out.append(('schedule_rollforward_mismatch', f'{did}: rollforward de activo no cuadra'))
    if t == 'lease_amortization_schedule':
        o, p, i, pr, e = (amt(f, k) for k in ('opening liability balance', 'payment amount', 'interest amount', 'principal amount', 'ending liability balance'))
        if None not in (p, i, pr) and ne(i + pr, p):
            out.append(('lease_schedule_mismatch', f'{did}: interés + principal != cuota'))
        elif None not in (o, pr, e) and ne(o - pr, e):
            out.append(('lease_schedule_mismatch', f'{did}: pasivo inicial - principal != final'))
    if t == 'lease_payment_notice':
        p, i, pr = amt(f, 'payment amount'), amt(f, 'interest amount'), amt(f, 'principal amount')
        if None not in (p, i, pr) and ne(i + pr, p):
            out.append(('lease_schedule_mismatch', f'{did}: interés + principal != pago'))
        ag = f1(f, 'agreement number')
        sch = [pk.P[s][0] for s in pk.docs_of('lease_amortization_schedule') if f1(pk.P[s][0], 'agreement number') == ag
               and (amt(pk.P[s][0], 'payment amount') or 0) > 0.005]
        if sch and not any(all(not ne(amt(sf, k), amt(f, k)) for k in ('payment amount', 'interest amount', 'principal amount')) for sf in sch):
            out.append(('lease_schedule_mismatch', f'{did}: pago no coincide con el calendario'))
    if t == 'lease_modification_notice':
        o, n, d, r = (amt(f, k) for k in ('old liability balance', 'remeasured liability balance', 'liability remeasurement delta amount', 'rou asset adjustment amount'))
        if (None not in (o, n, d) and ne(n - o, d)) or ne(d, r):
            out.append(('lease_remeasurement_mismatch', f'{did}: remedición no cuadra'))
    if t == 'asset_disposal_notice':
        c, a, n, p, g = (amt(f, k) for k in ('original cost', 'accumulated depreciation', 'net book value', 'proceeds amount', 'gain loss amount'))
        typ = (f1(f, 'gain loss type') or '').lower()
        bad = None not in (c, a, n) and ne(c - a, n)
        if None not in (n, p, g) and not bad:
            gl = p - n
            bad = ne(abs(gl), g) or ('loss' in typ and gl > 0.01) or ('gain' in typ and gl < -0.01)
        tag = f1(f, 'asset tag')
        for s in pk.docs_of('sale_proceeds_advice'):
            sf, _ = pk.P[s]
            if f1(sf, 'asset tag') == tag and ne(amt(sf, 'proceeds amount'), p):
                bad = True
        if bad:
            out.append(('asset_disposal_mismatch', f'{did}: coste - AA / VNC / resultado no cuadran'))
    if t == 'deferred_tax_memo':
        o, m, e, x = (amt(f, k) for k in ('opening deferred tax liability', 'current period deferred tax movement', 'deferred tax liability ending', 'deferred tax expense amount'))
        bad = (None not in (o, m, e) and ne(o + m, e)) or ne(m, x)
        tag = f1(f, 'asset tag')
        cands = []
        for s in pk.docs_of('tax_depreciation_schedule'):
            sf, _ = pk.P[s]
            if f1(sf, 'asset tag') == tag:
                b, tx, td, r = amt(sf, 'book depreciation amount'), amt(sf, 'tax depreciation amount'), amt(sf, 'temporary difference amount'), parse_rate(f1(sf, 'tax rate'))
                ok = not (None not in (b, tx, td) and ne(tx - b, td)) and not (None not in (td, r, m) and ne(round(td * r, 2), m))
                cands.append(ok)
        if cands and not any(cands):
            bad = True
        if bad:
            out.append(('deferred_tax_rollforward_mismatch', f'{did}: rollforward de impuesto diferido no cuadra'))
    if t == 'exchange_rate_notice':
        sa, r, fa = amt(f, 'source amount'), parse_rate(f1(f, 'exchange rate')), amt(f, 'functional amount')
        if None not in (sa, r, fa) and ne(round(sa * r, 2), fa):
            out.append(('exchange_rate_mismatch', f'{did}: origen x tipo != funcional'))
        ref = f1(f, 'reference')
        for d2 in pk.find(ref):
            if pk.T[d2] in ('customer_invoice', 'supplier_invoice', 'vendor_invoice') and ne(amt(pk.P[d2][0], 'total'), sa):
                out.append(('exchange_rate_mismatch', f'{did}: importe origen != factura {d2}'))
    if t == 'fx_remeasurement_memo':
        sa, r, ra, ba, d = amt(f, 'source amount'), parse_rate(f1(f, 'closing rate')), amt(f, 'remeasured amount'), amt(f, 'booked amount'), amt(f, 'difference amount')
        if (None not in (sa, r, ra) and ne(round(sa * r, 2), ra)) or (None not in (ba, ra, d) and ne(abs(ba - ra), abs(d))):
            out.append(('remeasurement_mismatch', f'{did}: remedición a cierre no cuadra'))
    if t == 'transfer_advice':
        a = amt(f, 'amount')
        keys = [v for k in ('transfer number', 'reference') for v in f.get(k, [])]
        for b in pk.docs_of('bank_statement'):
            for i in pk.P[b][1]:
                desc = i.get('description', '') + ' ' + i.get('_raw', '')
                if any(k and k in desc for k in keys):
                    v = parse_amount(i.get('amount'))
                    if v is not None and ne(abs(v), a):
                        out.append(('transfer_mismatch', f'{did}: importe != extracto {b}'))
    if t == 'secondary_copy':
        src = f1(f, 'source reference')
        tot = amt(f, 'total')
        for d2 in pk.find(src):
            if d2 != did and pk.T[d2] != 'secondary_copy' and ne(amt(pk.P[d2][0], 'total', 'amount', 'total rent'), tot):
                out.append(('duplicate_reference_conflict', f'{did}: copia con total distinto a {d2}'))
    if t == 'reclassification_memo':
        ref = f1(f, 'original reference')
        a = amt(f, 'amount')
        frm = f1(f, 'from account')
        for d2 in pk.find(ref):
            if d2 == did:
                continue
            df, di = pk.P[d2]
            vals = [parse_amount(i.get('amount')) for i in di] + [amt(df, 'total'), amt(df, 'subtotal')]
            if a is not None and not any(v is not None and abs(v - a) < 0.011 for v in vals):
                out.append(('reclassification_support_mismatch', f'{did}: importe no aparece en {d2}'))
    if t == 'tax_regime_notice':
        ja = amt(f, 'jurisdiction tax amount')
        treat = (f1(f, 'treatment') or '').lower()
        same = (f1(f, 'company jurisdiction') or '') == (f1(f, 'counterparty jurisdiction') or '')
        rate = parse_rate(f1(f, 'tax rate'))
        for s in pk.docs_of('supplier_invoice', 'customer_invoice'):
            sf, _ = pk.P[s]
            if 'india' not in (f1(sf, 'tax label') or '').lower() and not (amt(sf, 'cgst amount') or amt(sf, 'igst amount')):
                continue
            tax = amt(sf, 'tax amount')
            if ja is not None and tax is not None and abs(ja - tax) < 0.011:
                cg, ig = amt(sf, 'cgst amount'), amt(sf, 'igst amount')
                if (same and ig) or (not same and cg) or ('igst' in treat and cg) or ('cgst' in treat and ig):
                    out.append(('jurisdiction_tax_mismatch', f'{did}: tratamiento CGST/SGST/IGST no coincide con {s}'))
                if rate is not None and ne(parse_rate(f1(sf, 'tax rate')), rate, 0.0001):
                    out.append(('jurisdiction_tax_mismatch', f'{did}: tipo distinto en {s}'))
    if t == 'tax_exemption_certificate':
        cert = f1(f, 'certificate number')
        valid = 'valid' == (f1(f, 'exemption status') or '').strip().lower()
        for s in pk.docs_of('customer_invoice'):
            sf, _ = pk.P[s]
            if f1(sf, 'exemption certificate') == cert and valid and (amt(sf, 'tax amount') or 0) > 0.005:
                out.append(('tax_exemption_conflict', f'{did}: certificado válido pero {s} cobra impuesto'))
    if t == 'ssp_rate_card' or t == 'performance_obligation_schedule':
        tp = amt(f, 'transaction price')
        obs = [i for i in it if i.get('ssp amount')]
        tssp = sum(parse_amount(i.get('ssp amount')) or 0 for i in obs)
        if t == 'ssp_rate_card' and ne(amt(f, 'total ssp'), round(tssp, 2)):
            out.append(('ssp_allocation_mismatch', f'{did}: suma SSP != total'))
        if t == 'performance_obligation_schedule' and obs:
            alloc = [parse_amount(i.get('allocated transaction price')) for i in obs]
            if tp is not None and None not in alloc:
                if ne(sum(alloc), tp, 0.02) or ne(amt(f, 'allocation total'), tp, 0.02):
                    out.append(('ssp_allocation_mismatch', f'{did}: asignación != precio'))
                else:
                    for i, a in zip(obs, alloc):
                        exp = tp * (parse_amount(i.get('ssp amount')) or 0) / tssp if tssp else None
                        if exp is not None and ne(round(exp, 2), a, 0.02):
                            out.append(('ssp_allocation_mismatch', f'{did}: asignación no proporcional a SSP'))
                            break
            rel = [parse_amount(i.get('released this period')) for i in obs]
            if None not in rel and ne(round(sum(rel), 2), amt(f, 'released this period'), 0.02):
                out.append(('performance_obligation_release_mismatch', f'{did}: liberado != suma de obligaciones'))
            if tp is not None and ne(tp - (amt(f, 'released this period') or 0), amt(f, 'ending deferred'), 0.02):
                out.append(('performance_obligation_release_mismatch', f'{did}: precio - liberado != diferido final'))
    if t == 'implementation_acceptance_memo':
        ref = f1(f, 'contract reference')
        acc = amt(f, 'accepted amount')
        ob = (f1(f, 'accepted obligation') or '').lower()
        for s in pk.docs_of('performance_obligation_schedule'):
            sf, si = pk.P[s]
            if f1(sf, 'contract reference') != ref:
                continue
            for i in si:
                if (i.get('obligation') or '').lower() == ob:
                    if ne(parse_amount(i.get('allocated transaction price')), acc, 0.02) or ne(parse_amount(i.get('released this period')), acc, 0.02):
                        out.append(('performance_obligation_release_mismatch', f'{did}: aceptado != asignado'))
    if t == 'pos_batch_report':
        b, fe, e = amt(f, 'batch total'), amt(f, 'fee amount'), amt(f, 'expected deposit')
        if None not in (b, fe, e) and ne(b - fe, e):
            out.append(('bank_closing_mismatch', f'{did}: lote - comisión != depósito'))
    return out


PRIORITY = []  # orden por defecto: el del documento


def run_checks(pk):
    found = []
    for d in pk.docs:
        try:
            found += doc_checks(pk, d['doc_id'])
        except Exception as e:  # noqa
            pk.warn.append(f'check {d["doc_id"]}: {e!r}')
    # copias/duplicados con la misma referencia y totales distintos (sin nota de cancelación)
    try:
        tot = {}
        for d in pk.docs:
            did = d['doc_id']
            if pk.T[did] not in ('customer_invoice', 'supplier_invoice', 'vendor_invoice', 'patient_invoice', 'utilities_statement'):
                continue
            f, _ = pk.P[did]
            num = f1(f, 'invoice number')
            if not num or num in pk.withdrawn:
                continue
            t = amt(f, 'total', 'gross charge')
            if num in tot and ne(tot[num][1], t):
                found.append(('duplicate_reference_conflict', f'{did} y {tot[num][0]}: misma referencia {num} con totales distintos'))
            tot.setdefault(num, (did, t))
    except Exception as e:  # noqa
        pk.warn.append(f'dup: {e!r}')
    pk.all_checks = found
    if not found:
        return [], []
    code = found[0][0]
    return [code], [n for c, n in found if c == code][:3]


# ======================= main.py
#!/usr/bin/env python3
"""python3 run.py <records.jsonl> <salida.json>  -> {record_id: respuesta} para cada paquete FinBalance.
Solo librería estándar. Cada paquete va aislado en try/except: un fallo nunca tumba la entrega."""
import json
import os
import sys
import traceback








def empty(codes=None, notes=None):
    return {'has_inconsistency': bool(codes), 'inconsistency_codes': codes or [], 'inconsistency_notes': notes or [],
            'entries': [], 'balance_sheet': {'assets': {}, 'liabilities': {}, 'equity': {}}}


def solve(rec):
    pk = Packet(rec)
    pk.warn = []
    pk.text = lambda did: next((d.get('ocr_text') or '' for d in pk.docs if d['doc_id'] == did), '')
    pk.withdrawn = withdrawn(pk)
    pk.deferred_invoices = set()
    codes, notes = run_checks(pk)
    if codes:
        return empty(codes, notes), pk
    prepare_contracts(pk)
    seen = set()
    for d in pk.docs:
        h = HANDLERS.get(pk.T[d['doc_id']])
        # misma factura dos veces (copia sin marcar) con el mismo total: se contabiliza una sola vez
        f = pk.P[d['doc_id']][0]
        num = (f.get('invoice number') or [None])[0]
        if num and pk.T[d['doc_id']] in AR_TYPES | AP_TYPES:
            k = (pk.T[d['doc_id']], num, (f.get('total') or [''])[0])
            if k in seen:
                continue
            seen.add(k)
        if h:
            try:
                h(pk, d['doc_id'])
            except Exception as e:  # noqa
                pk.warn.append(f"{d['doc_id']} {pk.T[d['doc_id']]}: {e!r}")
    try:
        post_contracts(pk)
    except Exception as e:  # noqa
        pk.warn.append(f'contracts: {e!r}')
    out = empty()
    out['entries'] = pk.entries
    out['balance_sheet'] = pk.balance_sheet()
    return out, pk


def main(inp, outp):
    res = {}
    for line in open(inp, encoding='utf-8-sig'):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        rid = rec.get('record_id', f'rec_{len(res)}')
        try:
            res[rid], _ = solve(rec)
        except Exception:
            sys.stderr.write(f'{rid}: {traceback.format_exc()}\n')
            res[rid] = empty()
    d = os.path.dirname(os.path.abspath(outp))
    os.makedirs(d, exist_ok=True)
    tmp = outp + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, outp)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
