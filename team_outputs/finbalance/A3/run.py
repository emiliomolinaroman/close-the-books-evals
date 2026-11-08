#!/usr/bin/env python3
"""Reto F - cierre de paquetes FinBalance. Solucionador por reglas (solo stdlib).
Uso: python3 run.py <records.jsonl> <salida.json>
"""
import json, re, sys
from collections import defaultdict

TOL = 0.011

# ---------------------------------------------------------------- parsing
def num(s):
    if s is None:
        return None
    s = re.sub(r'(?<=\d)[ \u00a0\u202f](?=\d{3}(?:\D|$))', '', str(s))
    m = re.search(r'(-?)[^\d-]*?(-?)(\d[\d.,]*)', s)
    if not m:
        return None
    neg = (m.group(1) == '-' or m.group(2) == '-')
    t = m.group(3).rstrip('.,')
    if ',' in t and '.' in t:
        if t.rfind(',') > t.rfind('.'):
            t = t.replace('.', '').replace(',', '.')
        else:
            t = t.replace(',', '')
    elif ',' in t:
        if re.search(r',\d{1,2}$', t) and t.count(',') == 1:
            t = t.replace(',', '.')
        else:
            t = t.replace(',', '')
    elif t.count('.') > 1:
        t = t.replace('.', '')
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def pct(s):
    v = num(s)
    if v is None:
        return None
    if '%' in str(s):
        return v / 100.0
    return v if v < 1 else v / 100.0


ITEM_KEYS = ['Allocated Transaction Price', 'Released This Period', 'Invoice Line Amount', 'Allocated Amount',
             'Running Balance', 'Extended Cost', 'Document Type', 'Release Pattern', 'Ssp Amount', 'System Qty',
             'Counted Qty', 'Unit Cost', 'Unit Price', 'Tax Amount', 'Past Due', 'Description', 'Quantity',
             'Amount', 'Reference', 'Status', 'Date', 'Section', 'Account', 'Tenant', 'Customer', 'Current',
             'Obligation', 'Sku', 'Unit']


def parse_doc(d):
    raw = d.get('ocr_text', '') or ''
    lines = raw.split('\n')
    joined = []
    for i, l in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ''
        is_hdr = bool(re.match(r'^[-=]{3,}\s*$', nxt))
        if (joined and l.strip() and not l.startswith('  - ') and not re.match(r'^[-=]{3,}\s*$', l)
                and not is_hdr and not re.match(r"^[A-Z][A-Za-z0-9 /'()-]*: ", l) and not l.endswith(':')
                and joined[-1].strip() and not re.match(r'^[-=]{3,}\s*$', joined[-1])
                and (joined[-1].startswith('  - ') or re.match(r"^[A-Z][A-Za-z0-9 /'()-]*: ", joined[-1]))):
            joined[-1] = joined[-1].rstrip() + ' ' + l.strip()
        else:
            joined.append(l)
    fields = {}
    items = []
    for l in joined:
        if l.startswith('  - '):
            it = {}
            segs = [s.strip() for s in l[4:].split(' | ')]
            for seg in segs:
                seg = re.sub(r'\s+', ' ', seg)
                for k in ITEM_KEYS:
                    if seg.startswith(k + ' ') or seg == k:
                        it.setdefault(k, seg[len(k):].strip())
                        break
                else:
                    it.setdefault('_raw', seg)
            items.append(it)
            continue
        m = re.match(r"^([A-Z][A-Za-z0-9 /'()-]*?): (.*)$", l)
        if m:
            k, v = m.group(1).strip(), re.sub(r'\s+', ' ', m.group(2).strip())
            fields.setdefault(k, v)
    return {'id': d['doc_id'], 'type': d['doc_type'], 'date': d.get('date', ''), 'f': fields,
            'items': items, 'text': raw, 'title': d.get('title', '')}


def F(doc, k):
    return num(doc['f'].get(k))


def id_num(s):
    m = re.search(r'(\d+)', s or '')
    return int(m.group(1)) if m else 0


def half_down(x):
    c = int(round(x * 100))
    return (c // 2) / 100.0


def r2(x):
    return round(x + 1e-9 if x >= 0 else x - 1e-9, 2)


PRIORITY = ['exchange_rate_mismatch', 'fx_settlement_mismatch', 'remeasurement_mismatch', 'tax_exemption_conflict',
            'jurisdiction_tax_mismatch', 'input_tax_mismatch', 'tax_rate_mismatch', 'tax_total_mismatch',
            'invoice_total_mismatch', 'duplicate_reference_conflict', 'payment_allocation_mismatch',
            'transfer_mismatch', 'reclassification_support_mismatch', 'ssp_allocation_mismatch',
            'performance_obligation_release_mismatch', 'schedule_rollforward_mismatch',
            'inventory_rollforward_mismatch', 'asset_disposal_mismatch', 'deferred_tax_rollforward_mismatch',
            'lease_remeasurement_mismatch', 'lease_schedule_mismatch', 'statement_balance_mismatch',
            'bank_closing_mismatch']

# ---------------------------------------------------------------- accounts
def classify(acc, opening):
    for s in ('assets', 'liabilities', 'equity'):
        if acc in opening.get(s, {}):
            return s
    a = acc.lower()
    if 'unearned' in a or 'deferred revenue' in a:
        return 'liabilities'
    if 'payable' in a or 'accrued' in a or 'liability' in a:
        return 'liabilities'
    if acc in ('Retained Earnings',) or 'capital' in a or 'equity' in a or 'drawings' in a:
        return 'equity'
    if ('revenue' in a or 'expense' in a or 'cost of goods' in a or a.startswith('gain') or a.startswith('loss')
            or 'gain' in a or ' loss' in a or 'income' in a):
        return 'income'
    return 'assets'


def pick(allowed, *cands, default=None):
    for c in cands:
        if c in allowed:
            return c
    return default if default is not None else cands[0]


def match_expense(allowed, text, fallback=None):
    """find allowed expense account matching words in text."""
    t = (text or '').lower()
    best = None
    for a in allowed:
        al = a.lower()
        if not al.endswith('expense'):
            continue
        stem = al.replace(' expense', '').strip()
        if stem and stem in t:
            if best is None or len(stem) > len(best[0]):
                best = (stem, a)
    if best:
        return best[1]
    # first word match
    for a in allowed:
        al = a.lower()
        if al.endswith('expense') and t.split() and al.split()[0] == t.split()[0]:
            return a
    return fallback


# ---------------------------------------------------------------- solver
class Packet:
    def __init__(self, rec):
        self.rec = rec
        self.ctx = rec.get('context', {}) or {}
        self.allowed = list(rec.get('allowed_accounts', []))
        self.opening = rec.get('opening_balance', {}) or {}
        self.industry = rec.get('industry', '')
        self.regime = (self.ctx.get('tax_regime') or 'none').lower()
        self.fc = self.ctx.get('functional_currency_code') or self.ctx.get('currency_code')
        self.docs = [parse_doc(d) for d in rec.get('documents', [])]
        self.byid = {d['id']: d for d in self.docs}
        self.entries = []
        self.codes = []
        self.notes = []
        self.used = set()
        # cancelled references
        self.withdrawn = set()
        for d in self.docs:
            if d['type'] == 'cancellation_note':
                w = d['f'].get('Withdrawn Reference')
                if w:
                    self.withdrawn.add(w.strip())
        # fx rates by reference
        self.fx = {}
        for d in self.docs:
            if d['type'] == 'exchange_rate_notice':
                ref = d['f'].get('Reference')
                if ref:
                    self.fx[ref.strip()] = d

    # helpers
    def A(self, *c, default=None):
        return pick(self.allowed, *c, default=default)

    def post(self, refs, dr, cr, amt):
        if amt is None:
            return
        amt = r2(amt)
        if abs(amt) < 0.005:
            return
        if amt < 0:
            dr, cr, amt = cr, dr, -amt
        seen = []
        for x in refs:
            if x and x not in seen:
                seen.append(x)
        self.entries.append({'doc_refs': seen, 'debit_account': dr, 'credit_account': cr, 'amount': amt})

    def find(self, types, key, val):
        if val is None:
            return None
        val = val.strip()
        for d in self.docs:
            if d['type'] in types and (d['f'].get(key) or '').strip() == val:
                return d
        return None

    def find_any(self, val, types=None):
        if not val:
            return None
        val = val.strip()
        keys = ('Invoice Number', 'Roll Number', 'Notice Number', 'Statement Number', 'Receipt Number',
                'Work Order Number', 'Form Number', 'Agreement Number', 'Delivery Number', 'GRN Number')
        for d in self.docs:
            if types and d['type'] not in types:
                continue
            if d['type'] in ('secondary_copy',):
                continue
            for k in keys:
                if (d['f'].get(k) or '').strip() == val:
                    return d
        return None

    def conv(self, doc, amount, ref=None):
        """convert doc currency amount to functional using visible rate."""
        cur = (doc['f'].get('Currency') or '').strip()
        if not cur or cur == self.fc:
            return amount
        n = self.fx.get(ref or (doc['f'].get('Invoice Number') or '').strip())
        if n is None:
            return amount
        rate = num(n['f'].get('Exchange Rate'))
        return amount * rate if rate else amount

    # ------------------------------------------------------------ checks
    def flag(self, code, note):
        if code not in self.codes:
            self.codes.append(code)
            self.notes.append(note)

    def checks(self):
        for d in self.docs:
            t, f = d['type'], d['f']
            if d['f'].get('Invoice Number', '').strip() in self.withdrawn:
                continue
            if t in ('customer_invoice', 'vendor_invoice', 'supplier_invoice', 'utilities_statement', 'expense_receipt'):
                amts = [num(it.get('Amount')) for it in d['items'] if it.get('Amount') is not None]
                sub = F(d, 'Subtotal')
                tot = F(d, 'Total')
                tax = F(d, 'Tax Amount')
                base = sub if sub is not None else tot
                if amts and base is not None and abs(sum(amts) - base) > TOL:
                    self.flag('invoice_total_mismatch', '%s lines %.2f vs %.2f' % (d['id'], sum(amts), base))
                elif sub is not None and tax is not None and tot is not None and abs(sub + tax - tot) > TOL:
                    # lines tie to subtotal but total is off: overstated total reads as invoice total error
                    if tot > sub + tax:
                        self.flag('invoice_total_mismatch', '%s total %.2f vs lines+tax %.2f' % (d['id'], tot, sub + tax))
                    else:
                        self.flag('tax_total_mismatch', '%s subtotal+tax != total' % d['id'])
                rate = pct(f.get('Tax Rate')) if f.get('Tax Rate') else None
                if sub is not None and tax is not None and rate is not None and abs(r2(sub * rate) - tax) > 0.015:
                    self.flag('tax_rate_mismatch', '%s tax %.2f vs rate*base %.2f' % (d['id'], tax, sub * rate))
                cg, sg, ig = F(d, 'CGST Amount'), F(d, 'SGST Amount'), F(d, 'IGST Amount')
                if tax is not None and (cg is not None or ig is not None):
                    s = (cg or 0) + (sg or 0) + (ig or 0)
                    if abs(s - tax) > TOL:
                        self.flag('input_tax_mismatch' if t != 'customer_invoice' else 'tax_total_mismatch',
                                  '%s GST components' % d['id'])
            if t == 'bank_statement':
                op, cl = F(d, 'Opening Balance'), F(d, 'Closing Balance')
                rows = [num(it.get('Amount')) for it in d['items'] if it.get('Amount') is not None]
                if op is not None and cl is not None and abs(op + sum(rows) - cl) > TOL:
                    self.flag('bank_closing_mismatch', '%s opening+rows != closing' % d['id'])
            if t == 'vendor_statement':
                cl = F(d, 'Closing Balance')
                rows = [num(it.get('Amount')) for it in d['items'] if it.get('Amount') is not None]
                if cl is not None and rows and abs(sum(rows) - cl) > TOL:
                    self.flag('statement_balance_mismatch', '%s lines != closing' % d['id'])
            if t == 'ar_aging_summary':
                cl = F(d, 'Total Open')
                s = 0.0
                for it in d['items']:
                    s += (num(it.get('Current')) or 0) + (num(it.get('Past Due')) or 0)
                if cl is not None and d['items'] and abs(s - cl) > TOL:
                    self.flag('statement_balance_mismatch', '%s aging lines != total' % d['id'])
            if t == 'payment_advice':
                al = [num(it.get('Allocated Amount')) for it in d['items'] if it.get('Allocated Amount')]
                amt = F(d, 'Amount')
                if al and amt is not None and abs(sum(al) - amt) > TOL:
                    self.flag('payment_allocation_mismatch', '%s allocations != amount' % d['id'])
                if f.get('FX Difference'):
                    src, rate, fa = F(d, 'Source Amount'), num(f.get('Exchange Rate')), F(d, 'Functional Amount')
                    if src and rate and fa is not None and abs(r2(src * rate) - fa) > 0.015:
                        self.flag('fx_settlement_mismatch', '%s source*rate != functional' % d['id'])
                    ref = (f.get('Reference') or '').strip()
                    inv = self.find_any(ref)
                    fxd = F(d, 'FX Difference')
                    if inv is not None and fa is not None and fxd is not None:
                        booked = self.booked_functional(inv)
                        if booked is not None and abs(abs(fa - booked) - abs(fxd)) > 0.015:
                            self.flag('fx_settlement_mismatch', '%s booked/paid/fx diff' % d['id'])
            if t == 'secondary_copy':
                ref = (f.get('Source Reference') or '').strip()
                orig = self.find_any(ref)
                tot = F(d, 'Total')
                if orig is not None and tot is not None:
                    ot = None
                    for k in ('Total', 'Total Rent', 'Gross Charge', 'Total Premium', 'Approved Amount', 'Amount',
                              'Billed Amount', 'Contract Value'):
                        if orig['f'].get(k) is not None:
                            ot = F(orig, k)
                            break
                    if ot is not None and abs(ot - tot) > TOL:
                        self.flag('duplicate_reference_conflict', '%s copy total differs from %s' % (d['id'], orig['id']))
            if t == 'revenue_recognition_schedule':
                o, a, rl, e = F(d, 'Opening Deferred'), F(d, 'Added Deferred'), F(d, 'Released This Period'), F(d, 'Ending Deferred')
                if None not in (o, a, rl, e) and abs(o + a - rl - e) > TOL:
                    self.flag('schedule_rollforward_mismatch', '%s deferred rollforward' % d['id'])
            if t == 'fixed_asset_rollforward':
                o, a, dsp, e = F(d, 'Opening Balance'), F(d, 'Additions'), F(d, 'Disposals'), F(d, 'Ending Balance')
                if None not in (o, a, dsp, e) and abs(o + a - dsp - e) > TOL:
                    self.flag('schedule_rollforward_mismatch', '%s fixed asset rollforward' % d['id'])
            if t == 'inventory_rollforward':
                o, a, u, w, e = (F(d, 'Opening Balance'), F(d, 'Additions'), F(d, 'Usage Or Sales'),
                                 F(d, 'Write Down'), F(d, 'Ending Balance'))
                if None not in (o, a, u, e) and abs(o + a - u - (w or 0) - e) > TOL:
                    self.flag('inventory_rollforward_mismatch', '%s inventory rollforward' % d['id'])
            if t == 'transfer_advice':
                amt = F(d, 'Amount')
                ref = (f.get('Transfer Number') or '').strip()
                ref2 = (f.get('Reference') or '').strip()
                for b in self.docs:
                    if b['type'] != 'bank_statement':
                        continue
                    for it in b['items']:
                        desc = it.get('Description', '')
                        if (ref and ref in desc) or (ref2 and ref2 in desc):
                            v = num(it.get('Amount'))
                            if v is not None and amt is not None and abs(abs(v) - amt) > TOL:
                                self.flag('transfer_mismatch', '%s bank row %.2f vs advice %.2f' % (d['id'], v, amt))
            if t == 'reclassification_memo':
                ref = (f.get('Original Reference') or '').strip()
                orig = self.find_any(ref)
                amt = F(d, 'Amount')
                frm = (f.get('From Account') or '').strip()
                if orig is not None and amt is not None:
                    ok = False
                    cands = [num(it.get('Amount')) for it in orig['items'] if it.get('Amount')]
                    cands += [F(orig, 'Total'), F(orig, 'Subtotal')]
                    for c in cands:
                        if c is not None and abs(c - amt) <= TOL:
                            ok = True
                    lab = (orig['f'].get('Expense Label') or orig['f'].get('Expense Category') or '').strip()
                    if not ok:
                        self.flag('reclassification_support_mismatch', '%s amount not on %s' % (d['id'], orig['id']))
                    elif lab and frm and lab != frm and orig['type'] != 'expense_receipt':
                        self.flag('reclassification_support_mismatch', '%s from-account differs' % d['id'])
            if t == 'asset_disposal_notice':
                c, ad, nbv, p, g = (F(d, 'Original Cost'), F(d, 'Accumulated Depreciation'), F(d, 'Net Book Value'),
                                    F(d, 'Proceeds Amount'), F(d, 'Gain Loss Amount'))
                typ = (f.get('Gain Loss Type') or '').lower()
                if None not in (c, ad, nbv) and abs(c - ad - nbv) > TOL:
                    self.flag('asset_disposal_mismatch', '%s cost-AD != NBV' % d['id'])
                if None not in (nbv, p, g):
                    gg = p - nbv
                    sg = g if 'gain' in typ else -g
                    if abs(gg - sg) > TOL:
                        self.flag('asset_disposal_mismatch', '%s proceeds-NBV != gain/loss' % d['id'])
                tag = (f.get('Asset Tag') or '').strip()
                sp = self.find(('sale_proceeds_advice',), 'Asset Tag', tag)
                if sp is not None and p is not None and abs((F(sp, 'Proceeds Amount') or 0) - p) > TOL:
                    self.flag('asset_disposal_mismatch', '%s proceeds differ from advice' % d['id'])
            if t == 'deferred_tax_memo':
                o, mv, e, ex = (F(d, 'Opening Deferred Tax Liability'), F(d, 'Current Period Deferred Tax Movement'),
                                F(d, 'Deferred Tax Liability Ending'), F(d, 'Deferred Tax Expense Amount'))
                if None not in (o, mv, e) and abs(o + mv - e) > TOL:
                    self.flag('deferred_tax_rollforward_mismatch', '%s DTL rollforward' % d['id'])
                ts = self.dtax_schedule(d)
                if ts is not None and mv is not None:
                    td, rate = F(ts, 'Temporary Difference Amount'), pct(ts['f'].get('Tax Rate'))
                    bk, tx = F(ts, 'Book Depreciation Amount'), F(ts, 'Tax Depreciation Amount')
                    if td is not None and rate is not None and abs(r2(td * rate) - mv) > 0.015:
                        self.flag('deferred_tax_rollforward_mismatch', '%s movement != diff*rate' % d['id'])
                    if None not in (bk, tx, td) and abs((tx - bk) - td) > TOL:
                        self.flag('deferred_tax_rollforward_mismatch', '%s temp diff' % d['id'])
            if t == 'lease_amortization_schedule':
                o, p, i, pr, e = (F(d, 'Opening Liability Balance'), F(d, 'Payment Amount'), F(d, 'Interest Amount'),
                                  F(d, 'Principal Amount'), F(d, 'Ending Liability Balance'))
                if None not in (p, i, pr) and abs(i + pr - p) > TOL:
                    self.flag('lease_schedule_mismatch', '%s payment != interest+principal' % d['id'])
                if None not in (o, pr, e) and abs(o - pr - e) > TOL:
                    self.flag('lease_schedule_mismatch', '%s opening-principal != ending' % d['id'])
            if t == 'lease_payment_notice':
                p, i, pr = F(d, 'Payment Amount'), F(d, 'Interest Amount'), F(d, 'Principal Amount')
                if None not in (p, i, pr) and abs(i + pr - p) > TOL:
                    self.flag('lease_schedule_mismatch', '%s payment split' % d['id'])
            if t == 'lease_modification_notice':
                o, n, dl, ra = (F(d, 'Old Liability Balance'), F(d, 'Remeasured Liability Balance'),
                                F(d, 'Liability Remeasurement Delta Amount'), F(d, 'ROU Asset Adjustment Amount'))
                if None not in (o, n, dl) and abs(n - o - dl) > TOL:
                    self.flag('lease_remeasurement_mismatch', '%s delta' % d['id'])
                if None not in (dl, ra) and abs(abs(dl) - abs(ra)) > TOL:
                    self.flag('lease_remeasurement_mismatch', '%s ROU adj != delta' % d['id'])
            if t == 'exchange_rate_notice':
                s, rate, fa = F(d, 'Source Amount'), num(f.get('Exchange Rate')), F(d, 'Functional Amount')
                if None not in (s, rate, fa) and abs(r2(s * rate) - fa) > 0.015:
                    self.flag('exchange_rate_mismatch', '%s source*rate != functional' % d['id'])
            if t == 'fx_remeasurement_memo':
                s, rate, rm, bk, df = (F(d, 'Source Amount'), num(f.get('Closing Rate')), F(d, 'Remeasured Amount'),
                                       F(d, 'Booked Amount'), F(d, 'Difference Amount'))
                if None not in (s, rate, rm) and abs(r2(s * rate) - rm) > 0.015:
                    self.flag('remeasurement_mismatch', '%s source*closing != remeasured' % d['id'])
                if None not in (bk, rm, df) and abs(abs(bk - rm) - abs(df)) > TOL:
                    self.flag('remeasurement_mismatch', '%s difference' % d['id'])
            if t == 'performance_obligation_schedule':
                tp, ssp, at, rel, ed = (F(d, 'Transaction Price'), F(d, 'Total SSP'), F(d, 'Allocation Total'),
                                        F(d, 'Released This Period'), F(d, 'Ending Deferred'))
                obs = [it for it in d['items'] if it.get('Obligation')]
                if None not in (tp, at) and abs(tp - at) > TOL:
                    self.flag('ssp_allocation_mismatch', '%s allocation total != price' % d['id'])
                if obs and tp and ssp:
                    for it in obs:
                        s_, a_ = num(it.get('Ssp Amount')), num(it.get('Allocated Transaction Price'))
                        if s_ is not None and a_ is not None and abs(r2(tp * s_ / ssp) - a_) > 0.05:
                            self.flag('ssp_allocation_mismatch', '%s %s allocation' % (d['id'], it.get('Obligation')))
                    sa = sum(num(it.get('Allocated Transaction Price')) or 0 for it in obs)
                    if abs(sa - tp) > 0.05:
                        self.flag('ssp_allocation_mismatch', '%s sum allocations' % d['id'])
                    sr = sum(num(it.get('Released This Period')) or 0 for it in obs)
                    if rel is not None and abs(sr - rel) > TOL:
                        self.flag('performance_obligation_release_mismatch', '%s released lines != total' % d['id'])
                    if rel is not None and ed is not None and at is not None and abs(at - rel - ed) > TOL:
                        self.flag('performance_obligation_release_mismatch', '%s ending deferred' % d['id'])
                    # ratable check
                    for it in obs:
                        pat = (it.get('Release Pattern') or '').lower()
                        a_, r_ = num(it.get('Allocated Transaction Price')), num(it.get('Released This Period'))
                        m = re.search(r'(\d+) months', pat)
                        if m and a_ is not None and r_ is not None:
                            per = a_ / int(m.group(1))
                            k = round(r_ / per) if per else 0
                            if k < 1 or abs(per * k - r_) > 0.05 * k + 0.02:
                                self.flag('performance_obligation_release_mismatch', '%s ratable release' % d['id'])
                    acc = self.find(('implementation_acceptance_memo',), 'Contract Reference', f.get('Contract Reference'))
                    if acc is not None:
                        aa = F(acc, 'Accepted Amount')
                        for it in obs:
                            if 'implement' in (it.get('Obligation') or '').lower():
                                a_ = num(it.get('Allocated Transaction Price'))
                                r_ = num(it.get('Released This Period'))
                                if aa is not None and a_ is not None and abs(aa - a_) > TOL:
                                    self.flag('performance_obligation_release_mismatch', '%s acceptance != allocation' % acc['id'])
                                if aa is not None and r_ is not None and abs(aa - r_) > TOL:
                                    self.flag('performance_obligation_release_mismatch', '%s acceptance != release' % acc['id'])
            if t == 'ssp_rate_card':
                ts = F(d, 'Total SSP')
                s = sum(num(it.get('Ssp Amount')) or 0 for it in d['items'] if it.get('Ssp Amount'))
                if ts is not None and d['items'] and abs(s - ts) > TOL:
                    self.flag('ssp_allocation_mismatch', '%s SSP lines != total' % d['id'])
            if t == 'tax_regime_notice':
                amt = F(d, 'Jurisdiction Tax Amount')
                rate = pct(f.get('Tax Rate'))
                inv = self.tax_notice_invoice(d)
                if inv is not None:
                    sub, tax = F(inv, 'Subtotal'), F(inv, 'Tax Amount')
                    same = (f.get('Company Jurisdiction') or '').strip() == (f.get('Counterparty Jurisdiction') or '').strip()
                    if amt is not None and tax is not None and abs(amt - tax) > TOL:
                        self.flag('jurisdiction_tax_mismatch', '%s notice tax != invoice tax' % d['id'])
                    if rate is not None and sub is not None and tax is not None and abs(r2(sub * rate) - tax) > 0.015:
                        self.flag('jurisdiction_tax_mismatch', '%s notice rate' % d['id'])
                    ig, cg = F(inv, 'IGST Amount'), F(inv, 'CGST Amount')
                    if same and ig and ig > 0:
                        self.flag('jurisdiction_tax_mismatch', '%s same-state but IGST' % d['id'])
                    if not same and cg and cg > 0:
                        self.flag('jurisdiction_tax_mismatch', '%s inter-state but CGST' % d['id'])
            if t == 'tax_exemption_certificate':
                cert = (f.get('Certificate Number') or '').strip()
                status = (f.get('Exemption Status') or '').lower()
                for inv in self.docs:
                    if inv['type'] == 'customer_invoice' and (inv['f'].get('Exemption Certificate') or '').strip() == cert:
                        tax = F(inv, 'Tax Amount') or 0
                        cp = (f.get('Counterparty') or '').strip()
                        cust = (inv['f'].get('Customer') or '').strip()
                        valid = ('valid' in status and 'invalid' not in status and self.cert_in_period(d, inv)
                                 and (not cp or not cust or cp == cust))
                        if valid and tax > 0.005:
                            self.flag('tax_exemption_conflict', '%s valid cert but tax charged' % d['id'])
                        if not valid and tax <= 0.005:
                            self.flag('tax_exemption_conflict', '%s invalid cert but no tax' % d['id'])

    def cert_in_period(self, cert, inv):
        def pd(s):
            s = (s or '').strip()
            m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
            if m:
                return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            m = re.match(r'(\d{2})/(\d{2})/(\d{4})', s)
            if m:
                if (self.ctx.get('date_format') or '').startswith('MM'):
                    return (int(m.group(3)), int(m.group(1)), int(m.group(2)))
                return (int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return None
        a, b = pd(cert['f'].get('Effective Date')), pd(cert['f'].get('Expiration Date'))
        x = pd(inv['date'])
        if None in (a, b, x):
            return True
        return a <= x <= b

    def tax_notice_invoice(self, n):
        amt = F(n, 'Jurisdiction Tax Amount')
        best = None
        idx = self.docs.index(n)
        for d in self.docs:
            if d['type'] in ('supplier_invoice', 'vendor_invoice', 'customer_invoice') and 'Tax Amount' in d['f']:
                if amt is not None and abs((F(d, 'Tax Amount') or 0) - amt) <= TOL:
                    return d
        # nearest following doc with India GST label
        ids = sorted(self.docs, key=lambda d: d['id'])
        for d in ids:
            if d['id'] > n['id'] and d['type'] in ('supplier_invoice', 'vendor_invoice', 'customer_invoice') and 'Tax Amount' in d['f']:
                return d
        return best

    def booked_functional(self, inv):
        tot = F(inv, 'Total')
        if tot is None:
            return None
        cur = (inv['f'].get('Currency') or '').strip()
        if cur and cur != self.fc:
            n = self.fx.get((inv['f'].get('Invoice Number') or '').strip())
            if n is not None:
                fa = F(n, 'Functional Amount')
                return fa
        return tot

    # ------------------------------------------------------------ postings
    def tax_accounts_sale(self, d, tax, refs, rev_side='Accounts Receivable'):
        cg, sg, ig = F(d, 'CGST Amount'), F(d, 'SGST Amount'), F(d, 'IGST Amount')
        if cg or sg or ig:
            if cg:
                self.post(refs, rev_side, self.A('CGST Payable'), self.conv(d, cg))
            if sg:
                self.post(refs, rev_side, self.A('SGST Payable'), self.conv(d, sg))
            if ig:
                self.post(refs, rev_side, self.A('IGST Payable'), self.conv(d, ig))
        elif tax and self.is_india(d):
            same = self.same_state(d, 'Customer')
            if same:
                c = half_down(tax)
                self.post(refs, rev_side, self.A('CGST Payable'), self.conv(d, c))
                self.post(refs, rev_side, self.A('SGST Payable'), self.conv(d, tax - c))
            else:
                self.post(refs, rev_side, self.A('IGST Payable'), self.conv(d, tax))
        elif tax:
            self.post(refs, rev_side, self.A('Sales Tax Payable'), self.conv(d, tax))

    def is_india(self, d):
        lab = (d['f'].get('Tax Label') or '').lower()
        return 'india' in lab or (self.regime == 'india_gst' and not lab) or (self.regime == 'india_gst' and 'gst' in lab)

    def same_state(self, d, key):
        who = (d['f'].get(key) or d['f'].get('Supplier') or d['f'].get('Vendor') or '').strip()
        for x in self.docs:
            if x['type'] == 'customer_tax_profile' and (x['f'].get('Customer') or '').strip() == who:
                return (x['f'].get('Same State') or 'true').strip().lower() == 'true'
        for x in self.docs:
            if x['type'] == 'tax_regime_notice' and self.tax_notice_invoice(x) is d:
                tr = (x['f'].get('Treatment') or '').lower()
                if 'igst' in tr or 'different-state' in tr:
                    return False
                if 'cgst' in tr or 'same-state' in tr:
                    return True
                return (x['f'].get('Company Jurisdiction') or '') == (x['f'].get('Counterparty Jurisdiction') or '')
        return True

    def purchase_tax(self, d, refs, cost_acc, sub, tax, credit):
        """returns nothing; posts cost and tax."""
        cg, sg, ig = F(d, 'CGST Amount'), F(d, 'SGST Amount'), F(d, 'IGST Amount')
        label = (d['f'].get('Tax Label') or '').lower()
        embed = (self.regime == 'us_sales_tax' or 'us sales' in label) and not (cg or sg or ig)
        for x in self.docs:
            if x['type'] == 'tax_regime_notice' and self.tax_notice_invoice(x) is d:
                tr = (x['f'].get('Treatment') or '').lower()
                if 'capitaliz' in tr or 'embedded' in tr or 'included in cost' in tr:
                    embed = True
                elif 'input credit' in tr or 'recoverable' in tr:
                    embed = False
        if tax and not embed and not (cg or sg or ig) and self.is_india(d):
            if self.same_state(d, 'Supplier'):
                cg = half_down(tax)
                sg = r2(tax - cg)
            else:
                ig = tax
        if not tax:
            self.post(refs, cost_acc, credit, self.conv(d, sub))
            return
        if embed:
            self.post(refs, cost_acc, credit, self.conv(d, sub + tax))
            return
        self.post(refs, cost_acc, credit, self.conv(d, sub))
        if cg or sg or ig:
            if cg:
                self.post(refs, self.A('Input CGST Receivable'), credit, self.conv(d, cg))
            if sg:
                self.post(refs, self.A('Input SGST Receivable'), credit, self.conv(d, sg))
            if ig:
                self.post(refs, self.A('Input IGST Receivable'), credit, self.conv(d, ig))
        else:
            self.post(refs, self.A('Input Tax Receivable'), credit, self.conv(d, tax))

    def inv_account(self):
        if 'Inventory' in self.allowed:
            return 'Inventory'
        if 'Finished Goods Inventory' in self.allowed:
            return 'Finished Goods Inventory'
        return 'Inventory'

    def revenue_account(self, d):
        if self.industry in ('retail', 'wholesale_distribution', 'manufacturing'):
            return self.A('Sales Revenue', 'Service Revenue')
        if self.industry == 'property_management':
            return self.A('Rental Revenue', 'Service Revenue')
        return self.A('Service Revenue', 'Sales Revenue')

    def h_customer_invoice(self, d):
        f = d['f']
        invno = (f.get('Invoice Number') or '').strip()
        if invno in self.withdrawn:
            return
        sub = F(d, 'Subtotal')
        tot = F(d, 'Total')
        tax = F(d, 'Tax Amount') or 0.0
        if sub is None:
            sub = (tot or 0) - tax
        refs = [d['id']]
        ship = (f.get('Shipment Ref') or '').strip()
        cref = (f.get('Contract Ref') or '').strip()
        cogs = None
        rev_acc = self.revenue_account(d)
        first = None
        extra = []
        dn = self.find(('delivery_note',), 'Shipment Ref', ship) if ship else None
        if dn is not None:
            first = dn['id']
            cogs = F(dn, 'Cost Basis Amount')
            self.used.add(dn['id'])
        fgt = None
        if not cref:
            wo = self.wo_for_invoice(d)
            if wo is not None:
                first = wo['id']
        if cref:
            fgt = self.find(('finished_goods_transfer_note',), 'Transfer Number', cref)
            wo = self.find(('work_order',), 'Work Order Number', cref)
            if wo is None:
                wo = self.wo_for_invoice(d)
            if fgt is not None:
                extra.append(fgt['id'])
                cogs = F(fgt, 'Transfer Value')
            if wo is not None:
                first = wo['id']
        # exemption certificate docs
        cert_no = (f.get('Exemption Certificate') or '').strip()
        if cert_no:
            cert = self.find(('tax_exemption_certificate',), 'Certificate Number', cert_no)
            prof = self.find(('customer_tax_profile',), 'Exemption Certificate', cert_no)
            pre = []
            if cert is not None:
                pre.append(cert['id'])
            if prof is not None:
                pre.append(prof['id'])
            refs = pre + refs
        if first:
            refs = [first] + refs
        refs = refs + extra
        # deferred revenue contracts
        deferred = False
        if cref and (cref.startswith('ASC606') or cref.startswith('RET') or cref.startswith('SOF')
                     or self.find(('subscription_order_form',), 'Form Number', cref) is not None
                     or self.find(('retainer_agreement_memo',), 'Reference', cref) is not None):
            deferred = True
        if any(x['type'] == 'revenue_recognition_schedule' and (x['f'].get('Contract Reference') or '').strip() == invno
               for x in self.docs):
            deferred = True
        if deferred and 'Unearned Revenue' in self.allowed:
            rev_acc = 'Unearned Revenue'
            src = self.find(('subscription_order_form',), 'Form Number', cref) or \
                self.find(('retainer_agreement_memo',), 'Reference', cref)
            if src is not None:
                refs = [src['id']] + refs
        if deferred is False or True:
            ret = None
            for x in self.docs:
                if x['type'] == 'retainer_agreement_memo' and tot is not None and \
                        abs((F(x, 'Total Contract Value') or -1) - tot) <= TOL:
                    ret = x
            if ret is not None and ret['id'] not in refs:
                refs = [ret['id']] + refs
        n = self.fx.get(invno)
        if n is not None and (f.get('Currency') or self.fc).strip() != self.fc:
            refs = refs + [n['id']]
        dr_acc = 'Accounts Receivable'
        if self.advance_collected(invno, tot):
            dr_acc = 'Cash'
        self.post(refs, dr_acc, rev_acc, self.conv(d, sub))
        if cogs:
            self.post(refs, self.A('Cost of Goods Sold'),
                      'Finished Goods Inventory' if fgt is not None else self.inv_account(), cogs)
        self.tax_accounts_sale(d, tax, refs, dr_acc)

    def advance_collected(self, invno, tot):
        if not invno:
            return False
        for b in self.docs:
            if b['type'] != 'bank_statement':
                continue
            for it in b['items']:
                desc = (it.get('Description') or '').lower()
                if invno.lower() in desc.split() and ('advance' in desc or 'cash sale' in desc or 'collected at' in desc):
                    return True
        return False

    def expense_for_supplier(self, d):
        f = d['f']
        cat = (f.get('Expense Category') or '').strip()
        if cat:
            return cat
        if f.get('Goods Receipt Ref'):
            return self.inv_account()
        if self.industry == 'manufacturing':
            return self.A('Raw Materials Inventory', 'Inventory')
        if self.industry in ('retail', 'wholesale_distribution'):
            return self.inv_account()
        desc = ' '.join(it.get('Description', '') for it in d['items'])
        acc = match_expense(self.allowed, desc)
        if acc:
            return acc
        return self.A('Repairs Expense', 'Maintenance Expense', 'Office Supplies Expense', 'Utilities Expense')

    def h_supplier_invoice(self, d):
        f = d['f']
        if (f.get('Invoice Number') or '').strip() in self.withdrawn:
            return
        sub, tax, tot = F(d, 'Subtotal'), F(d, 'Tax Amount') or 0.0, F(d, 'Total')
        if sub is None:
            sub = (tot or 0) - tax
        acc = self.expense_for_supplier(d)
        refs = [d['id']]
        grn = (f.get('Goods Receipt Ref') or '').strip()
        if grn:
            g = self.find(('goods_receipt_note',), 'GRN Number', grn)
            if g is not None:
                refs = [g['id'], d['id']]
        for n in self.docs:
            if n['type'] == 'tax_regime_notice' and self.tax_notice_invoice(n) is d:
                refs = [n['id']] + [r for r in refs]
        self.purchase_tax(d, refs, acc, sub, tax, 'Accounts Payable')

    def h_vendor_invoice(self, d):
        f = d['f']
        if (f.get('Invoice Number') or '').strip() in self.withdrawn:
            return
        sub, tax, tot = F(d, 'Subtotal'), F(d, 'Tax Amount') or 0.0, F(d, 'Total')
        if sub is None:
            sub = (tot or 0) - tax
        acc = (f.get('Expense Label') or '').strip() or self.A('Office Supplies Expense')
        self.purchase_tax(d, [d['id']], acc, sub, tax, 'Accounts Payable')

    def h_utilities_statement(self, d):
        tot = F(d, 'Total')
        sub, tax = F(d, 'Subtotal'), F(d, 'Tax Amount') or 0.0
        if sub is None:
            sub = (tot or 0) - tax
        self.purchase_tax(d, [d['id']], self.A('Utilities Expense'), sub, tax, 'Accounts Payable')

    def h_expense_receipt(self, d):
        by = defaultdict(float)
        for it in d['items']:
            a = num(it.get('Amount'))
            if a is None:
                continue
            acc = match_expense(self.allowed, it.get('Description', ''))
            if acc is None:
                acc = self.A('Travel Expense', 'Office Supplies Expense', 'Fuel Expense', 'Maintenance Expense')
            by[acc] += a
        tot = F(d, 'Total')
        if not by and tot:
            by[self.A('Travel Expense', 'Office Supplies Expense')] = tot
        tax = F(d, 'Tax Amount')
        for acc, a in by.items():
            self.post([d['id']], acc, 'Cash', self.conv(d, a))
        if tax and self.regime != 'us_sales_tax':
            self.post([d['id']], self.A('Input Tax Receivable'), 'Cash', tax)

    def h_payment_advice(self, d):
        f = d['f']
        pf = (f.get('Payment For') or '').lower()
        ref = (f.get('Reference') or '').strip()
        amt = F(d, 'Amount')
        allocs = [it for it in d['items'] if it.get('Allocated Amount')]
        targets = []
        if allocs:
            for it in allocs:
                targets.append((self.find_any(it.get('Reference', '')), num(it.get('Allocated Amount'))))
        else:
            targets.append((self.find_any(ref), amt))
        for inv, a in targets:
            kind = None
            if inv is not None:
                if inv['type'] in ('customer_invoice', 'rent_roll', 'patient_invoice', 'work_order', 'delivery_note'):
                    kind = 'cust'
                elif inv['type'] in ('vendor_invoice', 'supplier_invoice', 'utilities_statement', 'equipment_invoice'):
                    kind = 'supp'
            if kind is None:
                if 'customer' in pf or 'tenant' in pf or 'receipt' in pf:
                    kind = 'cust'
                elif 'supplier' in pf or 'vendor' in pf:
                    kind = 'supp'
                else:
                    kind = 'cust' if ref.startswith('INV') else 'supp'
            refs = [d['id']] + ([inv['id']] if inv is not None else [])
            if f.get('FX Difference') and inv is not None:
                fa = F(d, 'Functional Amount')
                booked = self.booked_functional(inv)
                if booked is None:
                    booked = fa
                if kind == 'cust':
                    self.post(refs, 'Cash', 'Accounts Receivable', booked)
                    diff = fa - booked
                    if diff > 0:
                        self.post(refs, 'Cash', self.A('Foreign Exchange Gain'), diff)
                    elif diff < 0:
                        self.post(refs, self.A('Foreign Exchange Loss'), 'Accounts Receivable', -diff)
                else:
                    self.post(refs, 'Accounts Payable', 'Cash', booked)
                    diff = fa - booked
                    if diff > 0:
                        self.post(refs, self.A('Foreign Exchange Loss'), 'Cash', diff)
                    elif diff < 0:
                        self.post(refs, 'Accounts Payable', self.A('Foreign Exchange Gain'), -diff)
                continue
            if inv is not None:
                a2 = a
                cur = (inv['f'].get('Currency') or '').strip()
                if cur and cur != self.fc and (f.get('Currency') or cur) != self.fc:
                    a2 = self.conv(inv, a)
                a = a2
            if kind == 'cust':
                self.post(refs, 'Cash', 'Accounts Receivable', a)
            else:
                self.post(refs, 'Accounts Payable', 'Cash', a)

    def h_payroll_summary(self, d):
        self.post([d['id']], self.A('Salaries Expense'), 'Cash', F(d, 'Gross Pay'))
        self.post([d['id']], self.A('Payroll Tax Expense'), 'Cash', F(d, 'Employer Tax'))

    def h_loan_statement(self, d):
        self.post([d['id']], 'Cash', self.A('Loans Payable'), F(d, 'Draw Amount'))
        self.post([d['id']], self.A('Loans Payable'), 'Cash', F(d, 'Principal Paid'))
        self.post([d['id']], self.A('Interest Expense'), 'Cash', F(d, 'Interest Paid'))

    def asset_account(self, name, tag=None):
        n = (name or '').lower()
        if tag and tag.startswith('OPEN-'):
            code = tag[5:]
            for s in ('assets',):
                for a in self.opening.get(s, {}):
                    if a.upper().startswith(code) and 'accumulated' not in a.lower():
                        return a
        if any(w in n for w in ('van', 'truck', 'vehicle', 'car ')) and 'Vehicles' in self.allowed:
            return 'Vehicles'
        if any(w in n for w in ('fixture', 'shelving', 'display', 'counter')) and 'Store Fixtures' in self.allowed:
            return 'Store Fixtures'
        if any(w in n for w in ('furniture', 'desk', 'chair', 'table', 'cabinet')) and 'Furniture' in self.allowed:
            return 'Furniture'
        return self.A('Equipment', 'Store Fixtures', 'Furniture', 'Vehicles')

    def h_equipment_invoice(self, d):
        acc = self.asset_account(d['f'].get('Asset Name'))
        d['_asset'] = acc
        paid, fin, tot = F(d, 'Paid Cash'), F(d, 'Financed Amount'), F(d, 'Total')
        if paid is None and fin is None:
            paid = tot
        self.post([d['id']], acc, 'Cash', paid)
        self.post([d['id']], acc, self.A('Notes Payable'), fin)

    def h_depreciation(self, d):
        key = (d['f'].get('Asset Tag') or d['f'].get('Schedule ID') or '').strip()
        amt = F(d, 'Current Period Charge')
        if amt is None:
            amt = F(d, 'Current Charge')
        k = ('dep', key, amt)
        if k in self.used:
            return
        self.used.add(k)
        self.post([d['id']], self.A('Depreciation Expense'), self.A('Accumulated Depreciation'), amt)

    def h_patient_invoice(self, d):
        self.post([d['id']], 'Accounts Receivable', self.A('Service Revenue'), F(d, 'Gross Charge'))

    def h_receipt_vs_invoice(self, d, amtkey, refkey):
        inv = self.find_any(d['f'].get(refkey, ''))
        refs = [d['id']] + ([inv['id']] if inv is not None else [])
        self.post(refs, 'Cash', 'Accounts Receivable', F(d, amtkey))

    def h_rent_roll(self, d):
        self.post([d['id']], 'Accounts Receivable', self.A('Rental Revenue', 'Service Revenue'), F(d, 'Total Rent'))

    def h_security_deposit(self, d):
        t = d['text'].lower()
        amt = F(d, 'Amount')
        if 'refund' in t or 'return of deposit' in t or 'returned' in t:
            refs = [d['id']]
            for x in self.docs:
                if x is d or x['type'] != 'security_deposit_notice':
                    continue
                xt = x['text'].lower()
                if 'refund' in xt or 'returned' in xt:
                    continue
                if (x['f'].get('Tenant') == d['f'].get('Tenant') or x['f'].get('Unit') == d['f'].get('Unit')):
                    refs = [x['id'], d['id']]
                    break
            self.post(refs, self.A('Security Deposits Payable'), 'Cash', amt)
        else:
            self.post([d['id']], 'Cash', self.A('Security Deposits Payable'), amt)

    def h_prepaid(self, d, acc):
        tot = F(d, 'Total')
        if tot is None:
            tot = F(d, 'Total Premium')
        self.post([d['id']], self.A(acc), 'Cash', tot)

    def h_service_period_memo(self, d):
        f = d['f']
        ref = (f.get('Reference') or '').strip()
        amt = F(d, 'Recognized Amount')
        narr = (f.get('Narrative') or '') + ' ' + (f.get('Subject') or '')
        nl = narr.lower()
        src = None
        for x in self.docs:
            if x['type'] in ('rent_notice', 'insurance_notice') and (x['f'].get('Notice Number') or '').strip() == ref:
                src = x
        if src is not None:
            if src['type'] == 'rent_notice':
                self.post([src['id'], d['id']], self.A('Rent Expense'), self.A('Prepaid Rent'), amt)
            else:
                self.post([src['id'], d['id']], self.A('Insurance Expense'), self.A('Prepaid Insurance'), amt)
            return
        if 'rent' in nl and 'prepaid' not in nl and 'expire' in nl:
            self.post([d['id']], self.A('Rent Expense'), self.A('Prepaid Rent'), amt)
            return
        if 'insurance' in nl and 'expire' in nl:
            self.post([d['id']], self.A('Insurance Expense'), self.A('Prepaid Insurance'), amt)
            return
        if 'revenue' in nl or 'retainer' in nl or 'earned' in nl or 'deferred' in nl or 'unearned' in nl:
            refs = [d['id']]
            src = self.find(('retainer_agreement_memo',), 'Reference', ref)
            if src is not None:
                refs = [src['id'], d['id']]
            self.post(refs, self.A('Unearned Revenue'), self.A('Service Revenue', 'Sales Revenue'), amt)
            return
        m = re.search(r'accrue (?:unpaid )?([a-z ]+?) (?:expense|incurred|cost)', nl)
        acc = None
        if m:
            acc = match_expense(self.allowed, m.group(1))
        if acc is None:
            acc = match_expense(self.allowed, nl, self.A('Office Supplies Expense', 'Utilities Expense'))
        self.post([d['id']], acc, self.A('Accrued Expenses'), amt)

    def h_transfer(self, d):
        fr = (d['f'].get('From Account') or 'Cash').strip()
        to = (d['f'].get('To Account') or 'Reserve Cash').strip()
        self.post([d['id']], to, fr, F(d, 'Amount'))

    def h_credit_memo(self, d):
        f = d['f']
        reason = (f.get('Reason') or '').lower()
        ref = (f.get('Reference') or '').strip()
        inv = self.find_any(ref)
        amt = F(d, 'Amount')
        refs = []
        for x in self.docs:
            if x['type'] == 'ar_aging_summary' and ref and ref in x['text']:
                refs.append(x['id'])
        refs.append(d['id'])
        if inv is not None:
            refs.append(inv['id'])
        if 'bad debt' in reason or 'write' in reason or 'uncollect' in reason:
            self.post(refs, self.A('Bad Debt Expense'), 'Accounts Receivable', amt)
        else:
            self.post(refs, self.revenue_account(d), 'Accounts Receivable', amt)

    def h_return_note(self, d):
        self.post([d['id']], self.A('Sales Revenue', 'Service Revenue'), 'Cash', F(d, 'Amount'))

    def h_sales_summary(self, d):
        f = d['f']
        net, tax, cogs = F(d, 'Net Sales'), F(d, 'Tax Amount') or 0.0, F(d, 'COGS Amount')
        cash, card = F(d, 'Cash Sales') or 0.0, F(d, 'Card Sales') or 0.0
        refs = [d['id']]
        # find pos batch for card sales
        for x in self.docs:
            if x['type'] == 'pos_batch_report' and card and abs((F(x, 'Batch Total') or 0) - card) <= TOL:
                refs.append(x['id'])
                break
        gross = cash + card
        clr = self.A('Card Settlement Clearing', 'Cash')
        rev = self.A('Sales Revenue')
        if gross > 0:
            tax_cash = r2(tax * cash / gross)
            tax_card = r2(tax - tax_cash)
            self.post(refs, 'Cash', rev, cash - tax_cash)
            self.post(refs, clr, rev, card - tax_card)
        else:
            self.post(refs, 'Cash', rev, net)
        self.post(refs, self.A('Cost of Goods Sold'), self.inv_account(), cogs)
        if gross > 0:
            self.post(refs, 'Cash', self.A('Sales Tax Payable'), tax_cash)
            self.post(refs, clr, self.A('Sales Tax Payable'), tax_card)

    def h_card_settlement(self, d):
        refs = [d['id']]
        for it in d['items']:
            b = it.get('_raw', '')
            x = self.find(('pos_batch_report',), 'Batch ID', b)
            if x is not None:
                refs.append(x['id'])
        clr = self.A('Card Settlement Clearing', 'Cash')
        self.post(refs, 'Cash', clr, F(d, 'Net Deposit'))
        fee_acc = self.A('Bank Fees Expense', 'Merchant Fees Expense', 'Card Processing Fees', 'Bank Charges',
                         'Maintenance Expense', 'Office Supplies Expense', 'Utilities Expense')
        self.post(refs, fee_acc, clr, F(d, 'Fees'))

    def h_stock_count(self, d):
        adj = None
        sid = (d['f'].get('Sheet ID') or '').strip()
        for x in self.docs:
            if x['type'] == 'inventory_adjustment_note' and (x['f'].get('Reference Sheet') or '').strip() == sid:
                adj = x
        roll = None
        amt = 0.0
        for it in d['items']:
            s, c, u = num(it.get('System Qty')), num(it.get('Counted Qty')), num(it.get('Unit Cost'))
            if None not in (s, c, u):
                amt += (s - c) * u
        if adj is None:
            rolls = [x for x in self.docs if x['type'] == 'inventory_rollforward']
            if rolls:
                def score(x):
                    w = F(x, 'Write Down') or 0
                    return (abs(w - amt) > 0.02, abs(id_num(x['id']) - id_num(d['id']) - 1))
                roll = sorted(rolls, key=score)[0]
        if adj is not None:
            a2 = F(adj, 'Amount')
            if a2 is not None:
                amt = a2
            refs = [d['id'], adj['id']]
        elif roll is not None:
            w = F(roll, 'Write Down')
            if w:
                amt = w
            refs = [d['id'], roll['id']]
        else:
            refs = [d['id']]
        self.post(refs, self.A('Inventory Shrinkage Expense'), self.inv_account(), amt)

    def h_scrap(self, d):
        lot = (d['f'].get('Batch Or Lot') or '').upper()
        acc = 'Finished Goods Inventory' if 'FG' in lot else (
            'Raw Materials Inventory' if 'RM' in lot or 'RAW' in lot else (
                'Work In Process' if 'WIP' in lot else self.inv_account()))
        acc = self.A(acc, self.inv_account())
        refs = [d['id']]
        if lot.startswith('OPEN'):
            for x in self.docs:
                if x['type'] == 'opening_trial_balance':
                    refs.append(x['id'])
        self.post(refs, self.A('Inventory Shrinkage Expense'), acc, F(d, 'Write Down'))

    def batch_doc(self, bid):
        return self.find(('production_batch_sheet',), 'Batch ID', bid)

    def h_mrs(self, d):
        b = self.batch_doc(d['f'].get('Batch ID'))
        refs = [d['id']] + ([b['id']] if b is not None else [])
        mat = (d['f'].get('Material') or '').strip()
        sups = [x for x in self.docs if x['type'] == 'supplier_invoice' and mat
                and any(mat == it.get('Description', '') for it in x['items'])]
        sups.sort(key=lambda x: (x['f'].get('Invoice Number') or '', x['id']))
        if sups:
            refs.append(sups[0]['id'])
        self.post(refs, self.A('Work In Process'), self.A('Raw Materials Inventory'), F(d, 'Issue Value'))

    def h_labor(self, d):
        b = self.batch_doc(d['f'].get('Batch ID'))
        refs = [d['id']] + ([b['id']] if b is not None else [])
        amt = F(d, 'Labor Cash Paid')
        if amt is None:
            amt = F(d, 'Labor Value')
        self.post(refs, self.A('Work In Process'), 'Cash', amt)

    def h_overhead(self, d):
        b = self.batch_doc(d['f'].get('Batch ID'))
        refs = [d['id']] + ([b['id']] if b is not None else [])
        amt = F(d, 'Accrued Overhead')
        if amt is None:
            amt = F(d, 'Overhead Value')
        self.post(refs, self.A('Work In Process'), self.A('Accrued Expenses'), amt)

    def h_fgt(self, d):
        b = self.batch_doc(d['f'].get('Batch ID'))
        refs = [d['id']] + ([b['id']] if b is not None else [])
        self.post(refs, self.A('Finished Goods Inventory'), self.A('Work In Process'), F(d, 'Transfer Value'))

    def h_lease_agreement(self, d):
        f = d['f']
        ag = (f.get('Agreement Number') or '').strip()
        rou = F(d, 'ROU Asset Amount')
        ll = F(d, 'Lease Liability Amount')
        self.post([d['id']], self.A('Right-of-Use Asset'), self.A('Lease Liability'), ll if ll is not None else rou)
        for s in self.docs:
            if s['type'] == 'lease_amortization_schedule' and (s['f'].get('Agreement Number') or '').strip() == ag:
                self.lease_schedule(s, d)

    def lease_schedule(self, s, ag=None):
        if s['id'] in self.used:
            return
        self.used.add(s['id'])
        agn = (s['f'].get('Agreement Number') or '').strip()
        pays = [p for p in self.docs if p['type'] == 'lease_payment_notice'
                and (p['f'].get('Agreement Number') or '').strip() == agn]
        base = ([ag['id']] if ag is not None else []) + [s['id']]
        refs = base + [p['id'] for p in pays[:1]]
        self.post(refs, self.A('Lease Liability'), 'Cash', F(s, 'Principal Amount'))
        self.post(refs, self.A('Lease Interest Expense', 'Interest Expense'), 'Cash', F(s, 'Interest Amount'))
        self.post(base, self.A('Lease Amortization Expense'), self.A('Right-of-Use Asset'), F(s, 'ROU Amortization Amount'))

    def h_lease_schedule_orphan(self, d):
        if d['id'] in self.used:
            return
        ag = self.find(('lease_agreement',), 'Agreement Number', d['f'].get('Agreement Number'))
        if ag is not None:
            return  # handled by agreement
        self.lease_schedule(d, None)

    def h_lease_payment_orphan(self, d):
        agn = (d['f'].get('Agreement Number') or '').strip()
        if any(s['type'] == 'lease_amortization_schedule' and (s['f'].get('Agreement Number') or '').strip() == agn
               for s in self.docs):
            return
        self.post([d['id']], self.A('Lease Liability'), 'Cash', F(d, 'Principal Amount'))
        self.post([d['id']], self.A('Lease Interest Expense', 'Interest Expense'), 'Cash', F(d, 'Interest Amount'))

    def h_lease_mod(self, d):
        ag = self.find(('lease_agreement',), 'Agreement Number', d['f'].get('Agreement Number'))
        refs = [d['id']] + ([ag['id']] if ag is not None else [])
        delta = F(d, 'Liability Remeasurement Delta Amount')
        if delta is None:
            delta = F(d, 'ROU Asset Adjustment Amount')
        o, n = F(d, 'Old Liability Balance'), F(d, 'Remeasured Liability Balance')
        if o is not None and n is not None and n < o and delta and delta > 0:
            delta = -delta
        self.post(refs, self.A('Right-of-Use Asset'), self.A('Lease Liability'), delta)

    def h_disposal(self, d):
        f = d['f']
        tag = (f.get('Asset Tag') or '').strip()
        sp = self.find(('sale_proceeds_advice',), 'Asset Tag', tag)
        refs = [d['id']] + ([sp['id']] if sp is not None else [])
        acc = None
        for x in self.docs:
            if x['type'] == 'equipment_invoice' and (x['f'].get('Asset Tag') or '').strip() == tag:
                acc = self.asset_account(x['f'].get('Asset Name'))
        if acc is None:
            acc = self.asset_account(f.get('Asset Name'), tag)
        cost, ad, p, g = F(d, 'Original Cost'), F(d, 'Accumulated Depreciation'), F(d, 'Proceeds Amount'), F(d, 'Gain Loss Amount')
        typ = (f.get('Gain Loss Type') or '').lower()
        self.post(refs, 'Cash', acc, p)
        self.post(refs, self.A('Accumulated Depreciation'), acc, ad)
        if g:
            if 'loss' in typ:
                self.post(refs, self.A('Loss on Disposal'), acc, g)
            else:
                self.post(refs, acc, self.A('Gain on Disposal'), g)

    def dtax_schedule(self, d):
        tag = (d['f'].get('Asset Tag') or '').strip()
        mv = F(d, 'Current Period Deferred Tax Movement')
        cands = [x for x in self.docs if x['type'] == 'tax_depreciation_schedule'
                 and (x['f'].get('Asset Tag') or '').strip() == tag]
        if not cands:
            return None
        for x in cands:
            td, rate = F(x, 'Temporary Difference Amount'), pct(x['f'].get('Tax Rate'))
            if mv is not None and td is not None and rate is not None and abs(r2(td * rate) - mv) <= 0.015:
                return x
        return sorted(cands, key=lambda x: abs(id_num(x['id']) - id_num(d['id'])))[0]

    def h_deferred_tax(self, d):
        ts = self.dtax_schedule(d)
        refs = ([ts['id']] if ts is not None else []) + [d['id']]
        amt = F(d, 'Current Period Deferred Tax Movement')
        if amt is None:
            amt = F(d, 'Deferred Tax Expense Amount')
        self.post(refs, self.A('Deferred Tax Expense'), self.A('Deferred Tax Liability'), amt)

    def h_fx_remeasure(self, d):
        ref = (d['f'].get('Reference') or '').strip()
        inv = self.find_any(ref)
        bk, rm = F(d, 'Booked Amount'), F(d, 'Remeasured Amount')
        if bk is None or rm is None:
            return
        refs = [d['id']] + ([inv['id']] if inv is not None else [])
        n = self.fx.get(ref)
        if n is not None:
            refs.append(n['id'])
        diff = rm - bk
        if inv is not None and inv['type'] in ('vendor_invoice', 'supplier_invoice', 'utilities_statement'):
            if diff > 0:
                self.post(refs, self.A('Foreign Exchange Loss'), 'Accounts Payable', diff)
            else:
                self.post(refs, 'Accounts Payable', self.A('Foreign Exchange Gain'), -diff)
        else:
            if diff > 0:
                self.post(refs, 'Accounts Receivable', self.A('Foreign Exchange Gain'), diff)
            else:
                self.post(refs, self.A('Foreign Exchange Loss'), 'Accounts Receivable', -diff)

    def h_pob(self, d):
        cref = (d['f'].get('Contract Reference') or '').strip()
        acc = self.find(('implementation_acceptance_memo',), 'Contract Reference', cref)
        refs = [d['id']]
        for it in d['items']:
            ob = (it.get('Obligation') or '').lower()
            r_ = num(it.get('Released This Period'))
            if not r_:
                continue
            if 'implement' in ob and acc is not None:
                self.post([acc['id'], d['id']], self.A('Unearned Revenue'), self.A('Service Revenue'), r_)
            elif 'implement' in ob:
                continue  # no acceptance support -> no release
            else:
                self.post(refs, self.A('Unearned Revenue'), self.A('Service Revenue'), r_)

    def h_revrec(self, d):
        cref = (d['f'].get('Contract Reference') or '').strip()
        refs = [d['id']]
        src = self.find_any(cref)
        if src is not None:
            refs.append(src['id'])
        self.post(refs, self.A('Unearned Revenue'), self.A('Service Revenue', 'Sales Revenue'), F(d, 'Released This Period'))

    def h_reclass(self, d):
        f = d['f']
        orig = self.find_any((f.get('Original Reference') or '').strip())
        refs = [d['id']] + ([orig['id']] if orig is not None else [])
        self.post(refs, (f.get('To Account') or '').strip(), (f.get('From Account') or '').strip(), F(d, 'Amount'))

    def wo_for_invoice(self, inv):
        sub = F(inv, 'Subtotal')
        if sub is None:
            sub = (F(inv, 'Total') or 0) - (F(inv, 'Tax Amount') or 0)
        cust = (inv['f'].get('Customer') or '').strip()
        best = None
        for w in self.docs:
            if w['type'] != 'work_order':
                continue
            amt = F(w, 'Approved Amount')
            if amt is not None and abs(amt - sub) <= TOL:
                if (w['f'].get('Customer') or '').strip() == cust or best is None:
                    best = w
        return best

    def h_work_order(self, d):
        # posted via the invoice when one matches; otherwise support-only
        return

    def h_delivery_orphan(self, d):
        ship = (d['f'].get('Shipment Ref') or '').strip()
        for x in self.docs:
            if x['type'] == 'customer_invoice' and (x['f'].get('Shipment Ref') or '').strip() == ship:
                return
        # not invoiced -> no revenue; do nothing
        return

    def h_grn_orphan(self, d):
        g = (d['f'].get('GRN Number') or '').strip()
        for x in self.docs:
            if x['type'] == 'supplier_invoice' and (x['f'].get('Goods Receipt Ref') or '').strip() == g:
                return
        return

    # ------------------------------------------------------------ main
    def primary_codes(self):
        # one perturbation can trip several derived checks; keep the root-cause code
        if len(self.codes) <= 1:
            return self.codes, self.notes
        for c in PRIORITY:
            if c in self.codes:
                i = self.codes.index(c)
                return [c], [self.notes[i]]
        return self.codes[:1], self.notes[:1]

    def solve(self):
        self.checks()
        if self.codes:
            self.codes, self.notes = self.primary_codes()
            return {'has_inconsistency': True, 'inconsistency_codes': self.codes,
                    'inconsistency_notes': self.notes, 'entries': [],
                    'balance_sheet': {'assets': {}, 'liabilities': {}, 'equity': {}}}
        H = {
            'customer_invoice': self.h_customer_invoice,
            'supplier_invoice': self.h_supplier_invoice,
            'vendor_invoice': self.h_vendor_invoice,
            'utilities_statement': self.h_utilities_statement,
            'expense_receipt': self.h_expense_receipt,
            'payment_advice': self.h_payment_advice,
            'payroll_summary': self.h_payroll_summary,
            'loan_statement': self.h_loan_statement,
            'equipment_invoice': self.h_equipment_invoice,
            'depreciation_schedule': self.h_depreciation,
            'fixed_asset_rollforward': self.h_depreciation,
            'patient_invoice': self.h_patient_invoice,
            'insurer_remittance': lambda d: self.h_receipt_vs_invoice(d, 'Paid Amount', 'Claim Reference'),
            'copay_receipt': lambda d: self.h_receipt_vs_invoice(d, 'Amount', 'Reference Invoice'),
            'rent_roll': self.h_rent_roll,
            'security_deposit_notice': self.h_security_deposit,
            'rent_notice': lambda d: self.h_prepaid(d, 'Prepaid Rent'),
            'insurance_notice': lambda d: self.h_prepaid(d, 'Prepaid Insurance'),
            'service_period_memo': self.h_service_period_memo,
            'transfer_advice': self.h_transfer,
            'credit_memo': self.h_credit_memo,
            'return_note': self.h_return_note,
            'sales_summary': self.h_sales_summary,
            'card_settlement_report': self.h_card_settlement,
            'stock_count_sheet': self.h_stock_count,
            'scrap_report': self.h_scrap,
            'material_requisition_slip': self.h_mrs,
            'direct_labor_record': self.h_labor,
            'overhead_accrual_memo': self.h_overhead,
            'finished_goods_transfer_note': self.h_fgt,
            'lease_agreement': self.h_lease_agreement,
            'lease_amortization_schedule': self.h_lease_schedule_orphan,
            'lease_payment_notice': self.h_lease_payment_orphan,
            'lease_modification_notice': self.h_lease_mod,
            'asset_disposal_notice': self.h_disposal,
            'deferred_tax_memo': self.h_deferred_tax,
            'fx_remeasurement_memo': self.h_fx_remeasure,
            'performance_obligation_schedule': self.h_pob,
            'revenue_recognition_schedule': self.h_revrec,
            'reclassification_memo': self.h_reclass,
            'work_order': self.h_work_order,
        }
        for d in self.docs:
            h = H.get(d['type'])
            if h:
                h(d)
        return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [],
                'entries': self.entries, 'balance_sheet': self.balance_sheet()}

    def balance_sheet(self):
        bal = defaultdict(float)
        sec = {}
        for s in ('assets', 'liabilities', 'equity'):
            for a, v in (self.opening.get(s) or {}).items():
                if not isinstance(v, (int, float)):
                    continue
                sign = 1 if s == 'assets' else -1
                bal[a] += sign * v  # debit-positive
                sec[a] = s
        for e in self.entries:
            bal[e['debit_account']] += e['amount']
            bal[e['credit_account']] -= e['amount']
        out = {'assets': {}, 'liabilities': {}, 'equity': {}}
        ni = 0.0
        for a, v in bal.items():
            s = sec.get(a) or classify(a, self.opening)
            if s == 'income':
                ni += -v
                continue
            if a == 'Retained Earnings':
                continue
            val = r2(v if s == 'assets' else -v)
            if abs(val) >= 0.005:
                out[s][a] = val
        re_ = r2(-bal.get('Retained Earnings', 0.0) + ni)
        if abs(re_) >= 0.005 or 'Retained Earnings' in (self.opening.get('equity') or {}):
            out['equity']['Retained Earnings'] = re_
        return out


def solve_record(rec):
    try:
        return Packet(rec).solve()
    except Exception as ex:  # never crash the batch
        p = Packet.__new__(Packet)
        ob = rec.get('opening_balance', {}) or {}
        return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': ['error: %s' % ex],
                'entries': [], 'balance_sheet': {s: dict(ob.get(s, {})) for s in ('assets', 'liabilities', 'equity')}}


def main():
    if len(sys.argv) < 3:
        print('uso: python3 run.py <records.jsonl> <salida.json>')
        sys.exit(1)
    out = {}
    with open(sys.argv[1], encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec['record_id']] = solve_record(rec)
    with open(sys.argv[2], 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
