#!/usr/bin/env python3
"""Reto F - cierre de paquetes FinBalance. Motor de reglas determinista (solo stdlib).
Uso: python3 run.py <records.jsonl> <salida.json>"""
import json, re, sys
from collections import defaultdict, OrderedDict

# ---------------------------------------------------------------- parsing
SEG_KEYS = ['Allocated Transaction Price', 'Invoice Line Amount', 'Released This Period', 'Release Pattern',
            'Ssp Amount', 'Obligation', 'Running Balance', 'Document Type', 'Allocated Amount', 'Extended Cost',
            'Unit Cost', 'Unit Price', 'System Qty', 'Counted Qty', 'Past Due', 'Description', 'Quantity', 'Amount',
            'Sku', 'Date', 'Reference', 'Status', 'Customer', 'Current', 'Section', 'Account', 'Unit', 'Tenant']


def money(s):
    if s is None:
        return None
    s = str(s).strip()
    s = re.sub(r'^(USD|GBP|EUR|INR|CAD|AUD|JPY|\$|€|£|Rs\.?)\s*', '', s)
    s = s.replace('$', '').replace(' ', '')
    m = re.match(r'^-?[\d.,]+', s)
    if not m:
        return None
    t = m.group(0)
    if re.match(r'^-?\d{1,3}(\.\d{3})*,\d+$', t) or re.match(r'^-?\d+,\d{1,2}$', t):
        t = t.replace('.', '').replace(',', '.')
    else:
        t = t.replace(',', '')
    try:
        return float(t)
    except ValueError:
        return None


def r2(x):
    return round(x + 1e-9 if x >= 0 else x - 1e-9, 2)


class Doc:
    def __init__(self, d):
        self.id = d['doc_id']
        self.type = d['doc_type']
        self.date = d.get('date', '')
        self.title = d.get('title', '')
        txt = d.get('ocr_text', '')
        # unwrap OCR line breaks: a line not starting a new field joins the previous one
        raw = txt.split('\n')
        lines = []
        for ln in raw:
            if lines and lines[-1].endswith(' ') and ln and not ln.startswith('  -'):
                lines[-1] = lines[-1] + ln
            elif lines and lines[-1].startswith('  -') and ln and not ln.startswith('  -') and \
                    not re.match(r'^[A-Z][A-Za-z /()\-]*:', ln) and not re.match(r'^[A-Z][a-z]+( [A-Za-z]+)*$', ln) \
                    and not re.match(r'^[-=]+$', ln):
                lines[-1] = lines[-1].rstrip() + ' ' + ln.strip()
            else:
                lines.append(ln)
        self.text = '\n'.join(lines)
        self.f = OrderedDict()
        self.items = []
        for ln in lines:
            m = re.match(r'^\s+- (.*)$', ln)
            if m:
                it = {}
                for seg in m.group(1).split(' | '):
                    seg = seg.strip()
                    if not seg:
                        continue
                    k = None
                    for key in SEG_KEYS:
                        if seg == key or seg.startswith(key + ' '):
                            k = key
                            break
                    if k is None:
                        it.setdefault('_', []).append(seg)
                        continue
                    it[k] = seg[len(k):].strip()
                self.items.append(it)
                continue
            m = re.match(r'^([A-Z][A-Za-z0-9 /()\-]*?):\s*(.*)$', ln)
            if m:
                k, v = m.group(1).strip(), m.group(2).strip()
                if k not in self.f:
                    self.f[k] = v

    def g(self, *keys):
        for k in keys:
            if k in self.f and self.f[k] != '':
                return self.f[k]
        return None

    def m(self, *keys):
        v = self.g(*keys)
        return money(v) if v is not None else None


# ---------------------------------------------------------------- accounts
ASSET_HINT = ['Cash', 'Receivable', 'Inventory', 'Prepaid', 'Equipment', 'Furniture', 'Fixtures', 'Vehicles',
              'Accumulated Depreciation', 'Right-of-Use', 'Clearing', 'Office Supplies', 'Work In Process', 'Land',
              'Building', 'Deposit Asset', 'Deferred Tax Asset', 'Computer', 'Machinery']
LIAB_HINT = ['Payable', 'Accrued', 'Unearned', 'Liability', 'Deferred Revenue', 'Loan', 'Customer Deposits']
EQ_HINT = ['Capital', "Owner's Equity", 'Retained Earnings', 'Common Stock', 'Equity', 'Drawings', 'Dividends']
PL_HINT = ['Revenue', 'Expense', 'Cost of', 'Gain', 'Loss', 'Income', 'Shrinkage', 'Fees']


def section_of(acct, opening_sections):
    if acct in opening_sections:
        return opening_sections[acct]
    if acct.endswith('Expense') or acct.endswith('Revenue') and 'Unearned' not in acct and 'Deferred' not in acct \
            or acct.startswith('Cost of') or acct.startswith('Gain') or acct.startswith('Loss') \
            or 'Exchange Gain' in acct or 'Exchange Loss' in acct or acct.endswith('Income'):
        return 'pl'
    if acct in ('Office Supplies Expense',):
        return 'pl'
    for h in EQ_HINT:
        if h in acct:
            return 'equity'
    for h in LIAB_HINT:
        if h in acct:
            return 'liabilities'
    for h in ASSET_HINT:
        if h in acct:
            return 'assets'
    for h in PL_HINT:
        if h in acct:
            return 'pl'
    return 'assets'


class Ctx:
    def __init__(self, rec):
        self.rec = rec
        self.allowed = rec.get('allowed_accounts', [])
        self.aset = set(self.allowed)
        c = rec.get('context', {})
        self.regime = c.get('tax_regime', 'none')
        self.fc = c.get('functional_currency_code', 'USD')
        self.industry = rec.get('industry', '')
        self.period_label = c.get('period_label', '')
        self.entries = []
        self.notes = []
        self.codes = []

    def pick(self, *cands, default=None):
        for c in cands:
            if c in self.aset:
                return c
        return default if default is not None else cands[0]

    def find(self, pred, default=None):
        for a in self.allowed:
            if pred(a):
                return a
        return default

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

    def flag(self, code, note):
        if code not in self.codes:
            self.codes.append(code)
            self.notes.append(note)

    # common accounts
    def revenue_acct(self, kind=None):
        if kind == 'sales':
            return self.pick('Sales Revenue', 'Service Revenue', 'Revenue')
        if kind == 'rental':
            return self.pick('Rental Revenue', 'Service Revenue')
        if kind == 'subscription':
            return self.pick('Subscription Revenue', 'Service Revenue', 'Sales Revenue')
        ind = self.industry
        if ind in ('retail', 'wholesale_distribution', 'manufacturing'):
            return self.pick('Sales Revenue', 'Service Revenue')
        if ind == 'property_management':
            return self.pick('Rental Revenue', 'Service Revenue')
        if ind == 'subscription_saas':
            return self.pick('Subscription Revenue', 'Service Revenue', 'Sales Revenue')
        return self.pick('Service Revenue', 'Sales Revenue', 'Rental Revenue', 'Subscription Revenue')

    def inventory_acct(self):
        return self.pick('Inventory', 'Merchandise Inventory', 'Raw Materials Inventory', 'Finished Goods Inventory')

    def ar(self):
        return self.pick('Accounts Receivable')

    def ap(self):
        return self.pick('Accounts Payable')

    def cash(self):
        return self.pick('Cash')

    def match_account(self, text, suffix=None):
        """Find an allowed account whose name appears in text (longest first)."""
        if not text:
            return None
        t = text.lower()
        best = None
        for a in self.allowed:
            if suffix and not a.endswith(suffix):
                continue
            if a.lower() in t:
                if best is None or len(a) > len(best):
                    best = a
        return best


# ---------------------------------------------------------------- main solver
def tax_parts(ctx, d, sign_out):
    """Return list of (account, amount) for indirect tax shown on doc. sign_out True -> output (payable)."""
    tax = d.m('Tax Amount')
    res = []
    cg, sg, ig = d.m('CGST Amount'), d.m('SGST Amount'), d.m('IGST Amount')
    if cg or sg or ig:
        if sign_out:
            if cg: res.append((ctx.pick('CGST Payable'), cg))
            if sg: res.append((ctx.pick('SGST Payable'), sg))
            if ig: res.append((ctx.pick('IGST Payable'), ig))
        else:
            if cg: res.append((ctx.pick('Input CGST Receivable'), cg))
            if sg: res.append((ctx.pick('Input SGST Receivable'), sg))
            if ig: res.append((ctx.pick('Input IGST Receivable'), ig))
        return res
    if tax:
        if sign_out:
            res.append((ctx.pick('Sales Tax Payable', 'VAT Payable', 'GST Payable'), tax))
        else:
            res.append((ctx.pick('Input Tax Receivable', 'VAT Receivable'), tax))
    return res


def check_doc_arith(ctx, d):
    """Generic arithmetic consistency checks per document."""
    t = d.type
    sub, tax, tot, rate = d.m('Subtotal'), d.m('Tax Amount'), d.m('Total'), d.g('Tax Rate')
    line_amts = [money(it.get('Amount')) for it in d.items if it.get('Amount') is not None]
    if t in ('customer_invoice', 'vendor_invoice', 'supplier_invoice'):
        base = sub if sub is not None else tot
        if line_amts and base is not None and abs(sum(line_amts) - base) > 0.011:
            ctx.flag('invoice_total_mismatch', '%s line items do not sum to invoice amount' % d.id)
        if sub is not None and tax is not None and tot is not None and abs(sub + tax - tot) > 0.011:
            if tot > sub + tax:
                ctx.flag('invoice_total_mismatch', '%s total exceeds subtotal plus tax' % d.id)
            else:
                ctx.flag('tax_total_mismatch', '%s subtotal plus tax does not equal total' % d.id)
        if sub is not None and tax is not None and rate:
            rv = money(rate.replace('%', ''))
            if rv is not None and abs(r2(sub * rv / 100.0) - tax) > 0.011 + 0.0001 * sub * 0 and abs(sub * rv / 100.0 - tax) > 0.02:
                ctx.flag('tax_rate_mismatch', '%s tax amount does not match rate times subtotal' % d.id)
        cg, sg, ig = d.m('CGST Amount'), d.m('SGST Amount'), d.m('IGST Amount')
        if tax is not None and (cg or sg or ig):
            if abs((cg or 0) + (sg or 0) + (ig or 0) - tax) > 0.011:
                if t == 'customer_invoice':
                    ctx.flag('tax_total_mismatch', '%s GST components do not sum to tax' % d.id)
                else:
                    ctx.flag('input_tax_mismatch', '%s input GST components do not sum to tax' % d.id)
    if t == 'bank_statement':
        op, cl = d.m('Opening Balance'), d.m('Closing Balance')
        mv = [money(it.get('Amount')) for it in d.items if it.get('Amount') is not None]
        if op is not None and cl is not None and abs(op + sum(mv) - cl) > 0.011:
            ctx.flag('bank_closing_mismatch', '%s opening plus movements does not equal closing balance' % d.id)
    if t == 'vendor_statement':
        cl = d.m('Closing Balance')
        mv = [money(it.get('Amount')) for it in d.items if it.get('Amount') is not None]
        if cl is not None and mv and abs(sum(mv) - cl) > 0.011:
            ctx.flag('statement_balance_mismatch', '%s open lines do not sum to closing balance' % d.id)
    if t == 'ar_aging_summary':
        cl = d.m('Total Open')
        s = sum((money(it.get('Current')) or 0) + (money(it.get('Past Due')) or 0) for it in d.items)
        if cl is not None and d.items and abs(s - cl) > 0.011:
            ctx.flag('statement_balance_mismatch', '%s aging lines do not sum to total open' % d.id)
    if t == 'payment_advice':
        amt = d.m('Amount')
        al = [money(it.get('Allocated Amount')) for it in d.items if it.get('Allocated Amount') is not None]
        if al and amt is not None and abs(sum(al) - amt) > 0.011:
            ctx.flag('payment_allocation_mismatch', '%s allocations do not sum to payment amount' % d.id)
        sa, rt, fa = d.m('Source Amount'), d.m('Exchange Rate'), d.m('Functional Amount')
        if sa is not None and rt is not None and fa is not None and abs(r2(sa * rt) - fa) > 0.011:
            ctx.flag('fx_settlement_mismatch', '%s source amount times rate does not equal functional amount' % d.id)
    if t == 'exchange_rate_notice':
        sa, rt, fa = d.m('Source Amount'), d.m('Exchange Rate'), d.m('Functional Amount')
        if sa is not None and rt is not None and fa is not None and abs(r2(sa * rt) - fa) > 0.011:
            ctx.flag('exchange_rate_mismatch', '%s source amount times rate does not equal functional amount' % d.id)
    if t == 'fx_remeasurement_memo':
        sa, rt, ra, bk, df = d.m('Source Amount'), d.m('Closing Rate'), d.m('Remeasured Amount'), d.m('Booked Amount'), d.m('Difference Amount')
        if sa is not None and rt is not None and ra is not None and abs(r2(sa * rt) - ra) > 0.011:
            ctx.flag('remeasurement_mismatch', '%s remeasured amount does not equal source times closing rate' % d.id)
        elif bk is not None and ra is not None and df is not None and abs(abs(bk - ra) - abs(df)) > 0.011:
            ctx.flag('remeasurement_mismatch', '%s remeasurement difference does not reconcile' % d.id)
    if t == 'inventory_rollforward':
        o, a, u, w, e = [d.m(k) for k in ('Opening Balance', 'Additions', 'Usage Or Sales', 'Write Down', 'Ending Balance')]
        if None not in (o, a, u, e) and abs(o + a - u - (w or 0) - e) > 0.011:
            ctx.flag('inventory_rollforward_mismatch', '%s inventory rollforward does not reconcile' % d.id)
    if t == 'revenue_recognition_schedule':
        o, a, rl, e = [d.m(k) for k in ('Opening Deferred', 'Added Deferred', 'Released This Period', 'Ending Deferred')]
        if None not in (o, rl, e) and abs(o + (a or 0) - rl - e) > 0.011:
            ctx.flag('schedule_rollforward_mismatch', '%s deferred revenue schedule does not roll forward' % d.id)
    if t == 'fixed_asset_rollforward':
        o, a, dsp, e = [d.m(k) for k in ('Opening Balance', 'Additions', 'Disposals', 'Ending Balance')]
        if None not in (o, e) and abs(o + (a or 0) - (dsp or 0) - e) > 0.011:
            ctx.flag('schedule_rollforward_mismatch', '%s fixed asset rollforward does not reconcile' % d.id)
    if t in ('lease_amortization_schedule',):
        o, p, i, pr, e = [d.m(k) for k in ('Opening Liability Balance', 'Payment Amount', 'Interest Amount', 'Principal Amount', 'Ending Liability Balance')]
        if None not in (p, i, pr) and abs(i + pr - p) > 0.011:
            ctx.flag('lease_schedule_mismatch', '%s lease payment does not equal interest plus principal' % d.id)
        elif None not in (o, pr, e) and abs(o - pr - e) > 0.011:
            ctx.flag('lease_schedule_mismatch', '%s lease liability does not roll forward' % d.id)
    if t == 'lease_payment_notice':
        p, i, pr = d.m('Payment Amount'), d.m('Interest Amount'), d.m('Principal Amount')
        if None not in (p, i, pr) and abs(i + pr - p) > 0.011:
            ctx.flag('lease_schedule_mismatch', '%s lease payment does not equal interest plus principal' % d.id)
    if t == 'lease_modification_notice':
        o, n, dl, ra = [d.m(k) for k in ('Old Liability Balance', 'Remeasured Liability Balance', 'Liability Remeasurement Delta Amount', 'ROU Asset Adjustment Amount')]
        if None not in (o, n, dl) and abs(abs(n - o) - abs(dl)) > 0.011:
            ctx.flag('lease_remeasurement_mismatch', '%s lease remeasurement delta does not reconcile' % d.id)
        elif dl is not None and ra is not None and abs(abs(dl) - abs(ra)) > 0.011:
            ctx.flag('lease_remeasurement_mismatch', '%s ROU adjustment does not equal liability delta' % d.id)
    if t == 'asset_disposal_notice':
        c, a, n, p, gl = [d.m(k) for k in ('Original Cost', 'Accumulated Depreciation', 'Net Book Value', 'Proceeds Amount', 'Gain Loss Amount')]
        typ = (d.g('Gain Loss Type') or '').lower()
        bad = False
        if None not in (c, a, n) and abs(c - a - n) > 0.011:
            bad = True
        if None not in (n, p, gl):
            sg = p - n
            if abs(abs(sg) - gl) > 0.011 or (typ.startswith('gain') and sg < -0.01) or (typ.startswith('loss') and sg > 0.01):
                bad = True
        if bad:
            ctx.flag('asset_disposal_mismatch', '%s disposal computation does not reconcile' % d.id)
    if t == 'deferred_tax_memo':
        o, mv, e = d.m('Opening Deferred Tax Liability'), d.m('Current Period Deferred Tax Movement'), d.m('Deferred Tax Liability Ending')
        if None not in (o, mv, e) and abs(o + mv - e) > 0.011:
            ctx.flag('deferred_tax_rollforward_mismatch', '%s deferred tax rollforward does not reconcile' % d.id)
    if t == 'tax_depreciation_schedule':
        b, tx, td, rt = d.m('Book Depreciation Amount'), d.m('Tax Depreciation Amount'), d.m('Temporary Difference Amount'), d.g('Tax Rate')
        if None not in (b, tx, td) and abs(abs(tx - b) - abs(td)) > 0.011:
            ctx.flag('deferred_tax_rollforward_mismatch', '%s temporary difference does not reconcile' % d.id)
    if t == 'performance_obligation_schedule':
        tp, ts, at = d.m('Transaction Price'), d.m('Total SSP'), d.m('Allocation Total')
        alloc = [money(it.get('Allocated Transaction Price')) for it in d.items if it.get('Allocated Transaction Price')]
        ssps = [money(it.get('Ssp Amount')) for it in d.items if it.get('Ssp Amount')]
        bad = False
        if tp is not None and at is not None and abs(tp - at) > 0.011:
            bad = True
        if alloc and tp is not None and abs(sum(alloc) - tp) > 0.011:
            bad = True
        if ssps and ts is not None and abs(sum(ssps) - ts) > 0.011:
            bad = True
        if ts and tp and alloc and ssps and len(alloc) == len(ssps):
            for s, a in zip(ssps, alloc):
                if abs(s * tp / ts - a) > 0.02:
                    bad = True
        if bad:
            ctx.flag('ssp_allocation_mismatch', '%s allocation does not reconcile to SSP' % d.id)
    if t == 'performance_obligation_schedule':
        tp, rel, end = d.m('Transaction Price'), d.m('Released This Period'), d.m('Ending Deferred')
        lrel = [money(it.get('Released This Period')) for it in d.items if it.get('Released This Period')]
        bad = False
        if lrel and rel is not None and abs(sum(lrel) - rel) > 0.011:
            bad = True
        if tp is not None and rel is not None and end is not None and abs(tp - rel - end) > 0.011:
            bad = True
        for it in d.items:
            pat = it.get('Release Pattern') or ''
            mm = re.search(r'over (\d+) months', pat)
            a, r_ = money(it.get('Allocated Transaction Price')), money(it.get('Released This Period'))
            if mm and a is not None and r_ is not None:
                n = int(mm.group(1))
                if abs(a / n - r_) > 0.011 and all(abs(a * k / n - r_) > 0.011 for k in range(1, n + 1)):
                    bad = True
        if bad:
            ctx.flag('performance_obligation_release_mismatch', '%s released amounts do not reconcile to schedule' % d.id)
    if t == 'ssp_rate_card':
        ts = d.m('Total SSP')
        ssps = [money(it.get('Ssp Amount')) for it in d.items if it.get('Ssp Amount')]
        if ssps and ts is not None and abs(sum(ssps) - ts) > 0.011:
            ctx.flag('ssp_allocation_mismatch', '%s SSP lines do not sum to total' % d.id)
    if t == 'payroll_summary':
        g, e, c = d.m('Gross Pay'), d.m('Employer Tax'), d.m('Cash Outflow')
        if None not in (g, e, c) and abs(g + e - c) > 0.011:
            ctx.flag('bank_closing_mismatch', '%s payroll cash outflow does not reconcile' % d.id)
    if t == 'loan_statement':
        o, dr, pp, e = d.m('Opening Principal'), d.m('Draw Amount'), d.m('Principal Paid'), d.m('Ending Principal')
        if None not in (o, e) and abs(o + (dr or 0) - (pp or 0) - e) > 0.011:
            ctx.flag('schedule_rollforward_mismatch', '%s loan principal does not roll forward' % d.id)


def solve(rec):
    ctx = Ctx(rec)
    docs = [Doc(d) for d in rec.get('documents', [])]
    docs.sort(key=lambda d: (d.id))
    byid = {d.id: d for d in docs}
    T = defaultdict(list)
    for d in docs:
        T[d.type].append(d)

    # ---------------- references & cancellations
    withdrawn = set()
    for d in T['cancellation_note']:
        w = d.g('Withdrawn Reference')
        if w:
            withdrawn.add(w)
    inv_by_num = {}
    dup_seen = {}
    for t in ('customer_invoice', 'vendor_invoice', 'supplier_invoice', 'patient_invoice', 'utilities_statement',
              'rent_roll', 'equipment_invoice'):
        for d in T[t]:
            num = d.g('Invoice Number', 'Roll Number', 'Statement Number')
            if num:
                if num in inv_by_num and num not in withdrawn:
                    o = inv_by_num[num]
                    if o.m('Total', 'Gross Charge', 'Total Rent') != d.m('Total', 'Gross Charge', 'Total Rent'):
                        ctx.flag('duplicate_reference_conflict', '%s and %s share reference %s with different totals' % (o.id, d.id, num))
                    dup_seen[d.id] = True
                    continue
                inv_by_num[num] = d
            for alt in ('Statement Number',):
                v = d.g(alt)
                if v and v not in inv_by_num:
                    inv_by_num[v] = d
    for d in T['secondary_copy']:
        src = d.g('Source Reference')
        if src in inv_by_num:
            o = inv_by_num[src]
            ot = o.m('Total', 'Gross Charge', 'Total Rent')
            if ot is not None and d.m('Total') is not None and abs(ot - d.m('Total')) > 0.011:
                ctx.flag('duplicate_reference_conflict', '%s copy of %s shows a different total' % (d.id, src))

    for d in docs:
        check_doc_arith(ctx, d)

    # cross-document checks
    num_index = {}
    for d in docs:
        for k in ('Receipt Number', 'Invoice Number', 'Statement Number', 'Notice Number', 'Roll Number', 'Advice Number'):
            v = d.g(k)
            if v and v not in num_index:
                num_index[v] = d
    for d in T['reclassification_memo']:
        o = num_index.get(d.g('Original Reference'))
        amt = d.m('Amount')
        if o is not None and amt is not None:
            ot = o.m('Total', 'Subtotal', 'Amount')
            if ot is not None and abs(ot - amt) > 0.011:
                ctx.flag('reclassification_support_mismatch', '%s reclass amount does not match original %s' % (d.id, o.id))
    bank_rows = []
    for b in T['bank_statement']:
        for it in b.items:
            bank_rows.append((b, it.get('Description', ''), money(it.get('Amount'))))
    for d in T['transfer_advice']:
        amt = d.m('Amount')
        keys = [k for k in (d.g('Reference'), d.g('Transfer Number')) if k]
        for b, desc, a in bank_rows:
            if a is not None and amt is not None and any(re.search(r'\b%s\b' % re.escape(k), desc) for k in keys):
                if abs(abs(a) - amt) > 0.011:
                    ctx.flag('transfer_mismatch', '%s transfer amount does not match bank row in %s' % (d.id, b.id))

    # jurisdiction / exemption checks
    def date_key(v):
        if not v:
            return None
        m_ = re.match(r'(\d{4})-(\d{2})-(\d{2})', v)
        if m_:
            return m_.group(1) + m_.group(2) + m_.group(3)
        m_ = re.match(r'(\d{2})/(\d{2})/(\d{4})', v)
        if m_:
            return m_.group(3) + m_.group(2) + m_.group(1)
        return None
    capitalize_docs = set()
    notice_links = {}
    all_inv = T['supplier_invoice'] + T['vendor_invoice'] + T['customer_invoice']
    for n in T['tax_regime_notice']:
        jt = n.m('Jurisdiction Tax Amount')
        cands = [d for d in all_inv if (d.g('Invoice Number') or '').startswith('TAX')]
        if not cands and jt is not None:
            cands = [d for d in all_inv if d.m('Tax Amount') is not None and abs(d.m('Tax Amount') - jt) < 0.011]
        if not cands:
            cands = [d for d in all_inv if d.date == n.date]
        treat = (n.g('Treatment') or '').lower()
        for d in cands[:1]:
            notice_links[d.id] = n
            if 'capitaliz' in treat or 'embedded' in treat:
                capitalize_docs.add(d.id)
            bad = False
            rt_n, rt_d = money((n.g('Tax Rate') or '').replace('%', '')), money((d.g('Tax Rate') or '').replace('%', ''))
            if rt_n is not None and rt_d is not None and abs(rt_n - rt_d) > 0.001:
                bad = True
            if jt is not None and d.m('Tax Amount') is not None and abs(jt - d.m('Tax Amount')) > 0.011:
                bad = True
            cj, pj = n.g('Company Jurisdiction'), n.g('Counterparty Jurisdiction')
            if (n.g('Tax Regime') or '') == 'india_gst' and cj and pj:
                same = cj.strip().lower() == pj.strip().lower()
                has_cs = bool(d.m('CGST Amount') or d.m('SGST Amount'))
                has_i = bool(d.m('IGST Amount'))
                if same and (has_i or not has_cs):
                    bad = True
                if not same and (has_cs or not has_i):
                    bad = True
                if ('same-state' in treat and not same) or ('different-state' in treat and same):
                    bad = True
            if bad:
                ctx.flag('jurisdiction_tax_mismatch', '%s tax treatment conflicts with jurisdiction notice %s' % (d.id, n.id))
    for c in T['tax_exemption_certificate']:
        cp = c.g('Counterparty')
        valid = (c.g('Exemption Status') or '').lower().startswith('valid')
        ef, ex = date_key(c.g('Effective Date')), date_key(c.g('Expiration Date'))
        for d in T['customer_invoice']:
            if d.g('Exemption Certificate') != c.g('Certificate Number') and not (d.g('Customer') == cp and d.date == c.date):
                continue
            dk = d.date.replace('-', '')
            in_period = (ef is None or dk >= ef) and (ex is None or dk <= ex)
            tax = d.m('Tax Amount') or 0
            if valid and in_period and tax > 0.005:
                ctx.flag('tax_exemption_conflict', '%s charges tax despite valid exemption certificate %s' % (d.id, c.id))
            elif (not valid or not in_period) and d.g('Exemption Certificate') and tax < 0.005 and (d.m('Subtotal') or 0) > 0:
                ctx.flag('tax_exemption_conflict', '%s relies on invalid/expired exemption certificate %s' % (d.id, c.id))

    for dm in T['deferred_tax_memo']:
        mv = dm.m('Current Period Deferred Tax Movement', 'Deferred Tax Expense Amount')
        ex_amt = dm.m('Deferred Tax Expense Amount')
        if mv is not None and ex_amt is not None and abs(mv - ex_amt) > 0.011:
            ctx.flag('deferred_tax_rollforward_mismatch', '%s deferred tax expense differs from movement' % dm.id)
        sch = [x for x in T['tax_depreciation_schedule'] if x.g('Asset Tag') == dm.g('Asset Tag')]
        if sch and mv is not None:
            okk = False
            for x in sch:
                td, rt = x.m('Temporary Difference Amount'), money((x.g('Tax Rate') or '').replace('%', ''))
                if td is not None and rt is not None and abs(r2(td * rt / 100.0) - abs(mv)) <= 0.011:
                    okk = True
            if not okk:
                ctx.flag('deferred_tax_rollforward_mismatch', '%s deferred tax movement does not equal temporary difference times rate' % dm.id)
    for pa in T['payment_advice']:
        for it in pa.items:
            ref, al, st = it.get('Reference'), money(it.get('Allocated Amount')), (it.get('Status') or '').lower()
            inv = inv_by_num.get(ref)
            if inv is None or al is None:
                continue
            tot_ = inv.m('Total')
            if tot_ is None:
                continue
            if al > tot_ + 0.011 or ('partial' in st and al >= tot_ - 0.005):
                ctx.flag('payment_allocation_mismatch', '%s allocation to %s inconsistent with invoice total' % (pa.id, ref))

    # FX rates per reference
    fx = {}
    for d in T['exchange_rate_notice']:
        ref = d.g('Reference')
        fx[ref] = d

    def conv(d, amt, ref=None):
        """Convert doc amount into functional currency."""
        cur = d.g('Currency')
        if amt is None:
            return None
        if not cur or cur == ctx.fc:
            return amt
        n = fx.get(ref or d.g('Invoice Number'))
        if n is not None:
            rate = n.m('Exchange Rate')
            sa, fa = n.m('Source Amount'), n.m('Functional Amount')
            if sa is not None and fa is not None and abs(sa - amt) < 0.006:
                return fa
            if rate:
                return r2(amt * rate)
        return amt

    # tax certificates
    exempt_valid = {}
    for d in T['tax_exemption_certificate']:
        exempt_valid[d.g('Counterparty')] = ((d.g('Exemption Status') or '').lower().startswith('valid'), d)

    # deferred-revenue linkage
    revrec_by_ref = defaultdict(list)
    for d in T['revenue_recognition_schedule']:
        revrec_by_ref[d.g('Contract Reference')].append(d)
    sof = {d.g('Form Number'): d for d in T['subscription_order_form']}
    pob_by_ctr = {d.g('Contract Reference'): d for d in T['performance_obligation_schedule']}
    accept_by_ctr = defaultdict(list)
    for d in T['implementation_acceptance_memo']:
        accept_by_ctr[d.g('Contract Reference')].append(d)
    ssp_by_ctr = {d.g('Contract Reference'): d for d in T['ssp_rate_card']}
    deliveries = {d.g('Shipment Ref'): d for d in T['delivery_note']}
    work_orders = {}
    for d in T['work_order']:
        work_orders[d.g('Work Order Number')] = d
    fg_by_batch = {}
    for d in T['finished_goods_transfer_note']:
        fg_by_batch[d.g('Transfer Number')] = d
        fg_by_batch[d.g('Batch ID')] = d
    grn = {d.g('GRN Number'): d for d in T['goods_receipt_note']}
    tax_notice_list = T['tax_regime_notice']

    unearned = ctx.pick('Unearned Revenue', 'Deferred Revenue')

    # ---------------- customer invoices
    for d in T['customer_invoice']:
        num = d.g('Invoice Number')
        if num in withdrawn or d.id in dup_seen:
            continue
        refs = [d.id]
        sub, tot = d.m('Subtotal'), d.m('Total')
        base = sub if sub is not None else tot
        if base is None:
            continue
        base_f = conv(d, base)
        if sub is None and tot is not None:
            base_f = conv(d, tot)
        kind = None
        cogs = None
        ship = d.g('Shipment Ref')
        pre = []
        if ship and ship in deliveries:
            dn = deliveries[ship]
            pre = [dn.id]
            kind = 'sales'
            cogs = (dn.m('Cost Basis Amount'), ctx.inventory_acct(), dn.id)
        fgref = None
        for k in ('Transfer Ref', 'Finished Goods Ref', 'Batch ID', 'Transfer Number', 'FG Transfer Ref'):
            v = d.g(k)
            if v and v in fg_by_batch:
                fgref = fg_by_batch[v]
        if fgref is None and T['finished_goods_transfer_note']:
            for k, v in d.f.items():
                if v in fg_by_batch:
                    fgref = fg_by_batch[v]
        if fgref is not None:
            kind = 'sales'
            refs = [d.id, fgref.id]
            cogs = (fgref.m('Transfer Value'), ctx.pick('Finished Goods Inventory', 'Inventory'), fgref.id)
        wo = None
        for k, v in d.f.items():
            if v in work_orders:
                wo = work_orders[v]
        if wo is not None:
            refs = [wo.id, d.id]
        cust = d.g('Customer')
        if cust in exempt_valid and (d.g('Exemption Certificate') or d.date == exempt_valid[cust][1].date):
            cd = exempt_valid[cust][1]
            prof = [p.id for p in T['customer_tax_profile'] if p.g('Customer') == cust]
            refs = [cd.id] + prof + [d.id]
        if pre:
            refs = pre + [d.id]
        cref = d.g('Contract Ref')
        credit = ctx.revenue_acct(kind)
        deferred = False
        if num in revrec_by_ref or cref in revrec_by_ref or (cref and cref in sof) or (cref and cref in pob_by_ctr):
            deferred = True
        if cref and cref in sof:
            refs = [sof[cref].id, d.id] if False else refs
        if deferred:
            credit = unearned
        debit = ctx.ar()
        paid_refs = set()
        for pa in T['payment_advice']:
            paid_refs.add(pa.g('Reference'))
            for it in pa.items:
                paid_refs.add(it.get('Reference'))
        if num not in paid_refs and (any(re.search(r'(?i)advance (collection|receipt|payment).*\b%s\b' % re.escape(num or '#'), desc) for _, desc, _a in bank_rows)
                                     or (d.g('Due Date') is None and deferred and not bank_rows)):
            debit = ctx.cash()
        ctx.post(refs, debit, credit, base_f)
        if cogs and cogs[0]:
            ctx.post(refs, ctx.pick('Cost of Goods Sold'), cogs[1], cogs[0])
        for acct, amt in tax_parts(ctx, d, True):
            ctx.post(refs, debit, acct, conv(d, amt))

    # ---------------- revenue recognition
    rev_sub = ctx.revenue_acct('subscription') if ctx.industry == 'subscription_saas' else ctx.revenue_acct()
    for d in T['revenue_recognition_schedule']:
        rl = d.m('Released This Period')
        ref = d.g('Contract Reference')
        refs = [d.id]
        if ref in inv_by_num:
            refs = [d.id, inv_by_num[ref].id]
        ctx.post(refs, unearned, rev_sub, rl)
    for ctr, pob in pob_by_ctr.items():
        acc = accept_by_ctr.get(ctr, [])
        for it in pob.items:
            ob = (it.get('Obligation') or '').lower()
            rel = money(it.get('Released This Period'))
            if rel is None:
                continue
            if 'implement' in ob:
                if acc:
                    a = acc[0]
                    ctx.post([a.id, pob.id], unearned, ctx.pick('Implementation Revenue', 'Service Revenue', rev_sub), a.m('Accepted Amount') or rel)
            else:
                ctx.post([pob.id], unearned, ctx.pick('Subscription Revenue', rev_sub), rel)

    # ---------------- AR misc
    for d in T['patient_invoice']:
        if d.id in dup_seen:
            continue
        ctx.post([d.id], ctx.ar(), ctx.pick('Service Revenue', 'Patient Service Revenue'), d.m('Gross Charge', 'Total'))
    for d in T['rent_roll']:
        if d.id in dup_seen:
            continue
        ctx.post([d.id], ctx.ar(), ctx.revenue_acct('rental'), d.m('Total Rent', 'Total'))

    # ---------------- AP invoices
    def purchase(d, acct, extra_refs=()):
        refs = list(extra_refs) + [d.id]
        sub, tot = d.m('Subtotal'), d.m('Total')
        taxes = tax_parts(ctx, d, False)
        lab = (d.g('Tax Label') or '').lower()
        embed = d.id in capitalize_docs or 'us sales tax' in lab or (not lab and ctx.regime in ('us_sales_tax', 'none'))
        if embed or not taxes:
            # embedded in cost
            ctx.post(refs, acct, ctx.ap(), conv(d, tot if tot is not None else sub))
            return
        if sub is None:
            ctx.post(refs, acct, ctx.ap(), conv(d, tot))
            return
        ctx.post(refs, acct, ctx.ap(), conv(d, sub))
        for a, amt in taxes:
            ctx.post(refs, a, ctx.ap(), conv(d, amt))

    for d in T['vendor_invoice']:
        if d.g('Invoice Number') in withdrawn or d.id in dup_seen:
            continue
        lab = d.g('Expense Label')
        acct = lab if lab in ctx.aset else (ctx.match_account(lab or '') or ctx.pick('Office Supplies Expense', 'Maintenance Expense'))
        purchase(d, acct)
    for d in T['supplier_invoice']:
        if d.g('Invoice Number') in withdrawn or d.id in dup_seen:
            continue
        g = d.g('Goods Receipt Ref')
        extra = []
        if g and g in grn:
            extra = [grn[g].id]
            acct = ctx.pick('Inventory', 'Raw Materials Inventory', 'Merchandise Inventory')
        else:
            if 'Raw Materials Inventory' in ctx.aset:
                acct = 'Raw Materials Inventory'
            elif ctx.industry == 'field_services' and 'Repairs Expense' in ctx.aset:
                acct = 'Repairs Expense'
            elif 'Inventory' in ctx.aset:
                acct = 'Inventory'
            else:
                acct = ctx.pick('Repairs Expense', 'Supplies Expense', 'Office Supplies Expense')
        if d.id in notice_links:
            extra = [notice_links[d.id].id]
        purchase(d, acct, extra)
    for d in T['utilities_statement']:
        if d.id in dup_seen:
            continue
        ctx.post([d.id], ctx.pick('Utilities Expense'), ctx.ap(), d.m('Total'))

    # ---------------- payments
    def settle(d, ref, amt, customer):
        inv = inv_by_num.get(ref)
        refs = [d.id] + ([inv.id] if inv else [])
        if inv is not None and inv.type == 'customer_invoice':
            customer = True
        elif inv is not None and inv.type in ('vendor_invoice', 'supplier_invoice', 'utilities_statement'):
            customer = False
        if customer:
            ctx.post(refs, ctx.cash(), ctx.ar(), amt)
        else:
            ctx.post(refs, ctx.ap(), ctx.cash(), amt)

    for d in T['payment_advice']:
        pf = (d.g('Payment For') or '').lower()
        customer = 'customer' in pf
        amt = d.m('Amount')
        sa, fa, fxd = d.m('Source Amount'), d.m('Functional Amount'), d.m('FX Difference')
        ref = d.g('Reference')
        if fa is not None:
            inv = inv_by_num.get(ref)
            refs = [d.id] + ([inv.id] if inv else [])
            if inv is not None and inv.type == 'customer_invoice':
                customer = True
            booked = conv(inv, inv.m('Total')) if inv is not None else None
            if booked is None:
                booked = fa
            if customer:
                diff = r2(fa - booked)
                if diff >= 0:
                    ctx.post(refs, ctx.cash(), ctx.ar(), booked)
                    ctx.post(refs, ctx.cash(), ctx.pick('Foreign Exchange Gain'), diff)
                else:
                    ctx.post(refs, ctx.cash(), ctx.ar(), fa)
                    ctx.post(refs, ctx.pick('Foreign Exchange Loss'), ctx.ar(), -diff)
            else:
                diff = r2(fa - booked)
                if diff >= 0:
                    ctx.post(refs, ctx.ap(), ctx.cash(), booked)
                    ctx.post(refs, ctx.pick('Foreign Exchange Loss'), ctx.cash(), diff)
                else:
                    ctx.post(refs, ctx.ap(), ctx.cash(), fa)
                    ctx.post(refs, ctx.ap(), ctx.pick('Foreign Exchange Gain'), -diff)
            continue
        allocs = [it for it in d.items if it.get('Allocated Amount')]
        if allocs:
            for it in allocs:
                settle(d, it.get('Reference'), money(it.get('Allocated Amount')), customer)
        else:
            settle(d, ref, amt, customer)
    for d in T['copay_receipt']:
        inv = inv_by_num.get(d.g('Reference Invoice'))
        ctx.post([d.id] + ([inv.id] if inv else []), ctx.cash(), ctx.ar(), d.m('Amount'))
    for d in T['insurer_remittance']:
        inv = inv_by_num.get(d.g('Claim Reference'))
        ctx.post([d.id] + ([inv.id] if inv else []), ctx.cash(), ctx.ar(), d.m('Paid Amount'))

    # ---------------- FX remeasurement
    for d in T['fx_remeasurement_memo']:
        ref = d.g('Reference')
        inv = inv_by_num.get(ref)
        bk, ra = d.m('Booked Amount'), d.m('Remeasured Amount')
        if bk is None or ra is None:
            continue
        diff = r2(ra - bk)
        refs = [d.id] + ([inv.id] if inv else [])
        is_ap = inv is not None and inv.type in ('vendor_invoice', 'supplier_invoice')
        if not is_ap:
            if diff > 0:
                ctx.post(refs, ctx.ar(), ctx.pick('Foreign Exchange Gain'), diff)
            else:
                ctx.post(refs, ctx.pick('Foreign Exchange Loss'), ctx.ar(), -diff)
        else:
            if diff > 0:
                ctx.post(refs, ctx.pick('Foreign Exchange Loss'), ctx.ap(), diff)
            else:
                ctx.post(refs, ctx.ap(), ctx.pick('Foreign Exchange Gain'), -diff)

    # ---------------- cash expenses
    for d in T['expense_receipt']:
        acct = None
        for it in d.items:
            desc = it.get('Description', '')
            if desc in ctx.aset:
                acct = desc
                break
        if acct is None:
            for it in d.items:
                acct = ctx.match_account(it.get('Description', ''))
                if acct:
                    break
        if acct is None:
            acct = ctx.pick('Travel Expense', 'Fuel Expense', 'Office Supplies Expense')
        ctx.post([d.id], acct, ctx.cash(), d.m('Total'))
    for d in T['payroll_summary']:
        ctx.post([d.id], ctx.pick('Salaries Expense', 'Wages Expense'), ctx.cash(), d.m('Gross Pay'))
        ctx.post([d.id], ctx.pick('Payroll Tax Expense'), ctx.cash(), d.m('Employer Tax'))
    for d in T['loan_statement']:
        num = d.g('Loan Number') or ''
        lp = ctx.pick('Notes Payable', 'Loans Payable') if num.startswith('NOTE') else ctx.pick('Loans Payable', 'Notes Payable')
        ctx.post([d.id], ctx.cash(), lp, d.m('Draw Amount'))
        ctx.post([d.id], lp, ctx.cash(), d.m('Principal Paid'))
        ctx.post([d.id], ctx.pick('Interest Expense'), ctx.cash(), d.m('Interest Paid'))

    # ---------------- fixed assets
    fa_accts = [a for a in ctx.allowed if a in ('Equipment', 'Store Fixtures', 'Vehicles', 'Furniture', 'Machinery',
                                                  'Computer Equipment', 'Furniture and Fixtures', 'Buildings', 'Medical Equipment')]

    def fa_acct(name):
        n = (name or '').lower()
        for a in fa_accts:
            if a.lower() in n or n in a.lower():
                return a
        if ('van' in n or 'truck' in n or 'vehicle' in n) and 'Vehicles' in ctx.aset:
            return 'Vehicles'
        if ('fixture' in n or 'display' in n or 'shelving' in n) and 'Store Fixtures' in ctx.aset:
            return 'Store Fixtures'
        if ('desk' in n or 'chair' in n or 'furniture' in n) and 'Furniture' in ctx.aset:
            return 'Furniture'
        return fa_accts[0] if fa_accts else 'Equipment'

    for d in T['equipment_invoice']:
        acct = fa_acct(d.g('Asset Name'))
        tot, paid, fin = d.m('Total'), d.m('Paid Cash'), d.m('Financed Amount')
        if paid is None and fin is None:
            paid = tot
        ctx.post([d.id], acct, ctx.cash(), paid)
        np_ = d.g('Note Reference') or ''
        ctx.post([d.id], acct, ctx.pick('Notes Payable', 'Loans Payable') if True else None, fin)
    accdep = ctx.pick('Accumulated Depreciation')
    for d in T['depreciation_schedule']:
        ctx.post([d.id], ctx.pick('Depreciation Expense'), accdep, d.m('Current Period Charge', 'Current Charge'))
    for d in T['fixed_asset_rollforward']:
        ctx.post([d.id], ctx.pick('Depreciation Expense'), accdep, d.m('Current Charge', 'Current Period Charge'))
    proceeds = {}
    for d in T['sale_proceeds_advice']:
        proceeds[d.g('Asset Tag')] = d
    for d in T['asset_disposal_notice']:
        tag = d.g('Asset Tag')
        pr = proceeds.get(tag)
        refs = [d.id] + ([pr.id] if pr else [])
        acct = fa_acct(d.g('Asset Name'))
        if tag and tag.startswith('OPEN-'):
            code = tag[5:]
            for a in fa_accts:
                if a.upper().startswith(code):
                    acct = a
        cost, ad, p, gl = d.m('Original Cost'), d.m('Accumulated Depreciation'), d.m('Proceeds Amount'), d.m('Gain Loss Amount')
        typ = (d.g('Gain Loss Type') or '').lower()
        ctx.post(refs, ctx.cash(), acct, p)
        ctx.post(refs, accdep, acct, ad)
        if gl:
            if typ.startswith('loss'):
                ctx.post(refs, ctx.pick('Loss on Disposal'), acct, gl)
            else:
                ctx.post(refs, acct, ctx.pick('Gain on Disposal'), gl)

    # ---------------- deferred tax
    for d in T['deferred_tax_memo']:
        tag = d.g('Asset Tag')
        sup = [x.id for x in T['tax_depreciation_schedule'] if x.g('Asset Tag') == tag]
        amt = d.m('Deferred Tax Expense Amount', 'Current Period Deferred Tax Movement')
        ctx.post([d.id] + sup, ctx.pick('Deferred Tax Expense'), ctx.pick('Deferred Tax Liability'), amt)

    # ---------------- prepaids / accruals
    prepaid_notice = {}
    for d in T['rent_notice']:
        prepaid_notice[d.g('Notice Number')] = (d, ctx.pick('Prepaid Rent'), ctx.pick('Rent Expense'))
        ctx.post([d.id], ctx.pick('Prepaid Rent'), ctx.cash(), d.m('Total'))
    for d in T['insurance_notice']:
        prepaid_notice[d.g('Notice Number')] = (d, ctx.pick('Prepaid Insurance'), ctx.pick('Insurance Expense'))
        ctx.post([d.id], ctx.pick('Prepaid Insurance'), ctx.cash(), d.m('Total Premium', 'Total'))
    for d in T['service_period_memo']:
        ref = d.g('Reference')
        amt = d.m('Recognized Amount')
        if ref in prepaid_notice:
            n, pa, ex = prepaid_notice[ref]
            ctx.post([n.id, d.id], ex, pa, amt)
            continue
        narr = d.g('Narrative') or ''
        m = re.search(r'[Aa]ccrue unpaid (.+?) expense', narr)
        acct = None
        if m:
            acct = ctx.match_account(m.group(1) + ' expense', 'Expense')
            if acct is None:
                acct = ctx.find(lambda a: a.lower().startswith(m.group(1).lower().split()[0]) and a.endswith('Expense'))
        if acct is None:
            acct = ctx.match_account(narr, 'Expense') or ctx.pick('Office Supplies Expense', 'Utilities Expense')
        ctx.post([d.id], acct, ctx.pick('Accrued Expenses'), amt)

    # ---------------- property
    dep_notices = T['security_deposit_notice']
    for d in dep_notices:
        txt = d.text.lower()
        refund = 'refund' in txt or 'return' in (d.g('Purpose', 'Type', 'Status') or '').lower()
        if refund:
            ctx.post([d.id], ctx.pick('Security Deposits Payable'), ctx.cash(), d.m('Amount'))
        else:
            ctx.post([d.id], ctx.cash(), ctx.pick('Security Deposits Payable'), d.m('Amount'))

    # ---------------- transfers & reclasses
    for d in T['transfer_advice']:
        fr, to = d.g('From Account'), d.g('To Account')
        fr = fr if fr in ctx.aset else ctx.cash()
        to = to if to in ctx.aset else ctx.pick('Reserve Cash')
        ctx.post([d.id], to, fr, d.m('Amount'))
    for d in T['reclassification_memo']:
        fr, to = d.g('From Account'), d.g('To Account')
        orig = d.g('Original Reference')
        refs = [d.id] + ([inv_by_num[orig].id] if orig in inv_by_num else [])
        ctx.post(refs, to, fr, d.m('Amount'))

    # ---------------- retail
    clearing = ctx.pick('Card Settlement Clearing')
    fee_acct = ctx.pick('Card Processing Fees', 'Merchant Fees', 'Bank Fees', 'Bank Charges', 'Maintenance Expense', 'Office Supplies Expense')
    batches = {d.g('Batch ID'): d for d in T['pos_batch_report']}
    used_batch = set()
    for d in T['sales_summary']:
        cash_s, card_s, net, tax, cogs = d.m('Cash Sales'), d.m('Card Sales'), d.m('Net Sales'), d.m('Tax Amount'), d.m('COGS Amount')
        b = None
        for bid, bd in batches.items():
            if bid not in used_batch and card_s is not None and bd.m('Batch Total') is not None and abs(bd.m('Batch Total') - card_s) < 0.011:
                b = bd
                used_batch.add(bid)
                break
        refs = [d.id] + ([b.id] if b else [])
        tax = tax or 0.0
        tot = (cash_s or 0) + (card_s or 0)
        if ctx.regime in ('none',) and not tax:
            tax = 0.0
        tax_cash = r2(tax * (cash_s or 0) / tot) if tot else 0
        tax_card = r2(tax - tax_cash)
        rev = ctx.revenue_acct('sales')
        ctx.post(refs, ctx.cash(), rev, (cash_s or 0) - tax_cash)
        ctx.post(refs, clearing, rev, (card_s or 0) - tax_card)
        ctx.post(refs, ctx.pick('Cost of Goods Sold'), ctx.inventory_acct(), cogs)
        stp = ctx.pick('Sales Tax Payable')
        ctx.post(refs, ctx.cash(), stp, tax_cash)
        ctx.post(refs, clearing, stp, tax_card)
    for d in T['card_settlement_report']:
        brefs = [it.get('_', [''])[0] if '_' in it else '' for it in d.items]
        bdocs = [batches[b].id for b in brefs if b in batches]
        refs = [d.id] + bdocs
        ctx.post(refs, ctx.cash(), clearing, d.m('Net Deposit'))
        ctx.post(refs, fee_acct, clearing, d.m('Fees'))
    for d in T['return_note']:
        ctx.post([d.id], ctx.revenue_acct('sales'), ctx.cash(), d.m('Amount'))

    # ---------------- inventory adjustments
    inv_acct = ctx.inventory_acct()
    shrink = ctx.pick('Inventory Shrinkage Expense', 'Inventory Write-Down Expense')
    adj_sheets = set()
    for d in T['inventory_adjustment_note']:
        sh = d.g('Reference Sheet')
        sd = [x.id for x in T['stock_count_sheet'] if x.g('Sheet ID') == sh]
        adj_sheets.add(sh)
        ctx.post(sd + [d.id], shrink, inv_acct, d.m('Amount'))
    rolls = list(T['inventory_rollforward'])
    sheets = [x for x in T['stock_count_sheet'] if x.g('Sheet ID') not in adj_sheets]
    for i, d in enumerate(rolls):
        sd = [sheets[i].id] if i < len(sheets) else []
        ctx.post(sd + [d.id], shrink, inv_acct, d.m('Write Down'))
    for d in T['scrap_report']:
        lot = d.g('Batch Or Lot') or ''
        acct = ctx.pick('Finished Goods Inventory', 'Inventory') if 'FG' in lot or 'Finished Goods Inventory' in ctx.aset else inv_acct
        refs = [d.id] + ([T['opening_trial_balance'][0].id] if lot.startswith('OPEN') and T['opening_trial_balance'] else [])
        ctx.post(refs, shrink, acct, d.m('Write Down'))

    # ---------------- credit memos
    for d in T['credit_memo']:
        ref = d.g('Reference')
        inv = inv_by_num.get(ref)
        reason = (d.g('Reason') or '').lower()
        ag = [x.id for x in T['ar_aging_summary']]
        if 'bad debt' in reason or 'write' in reason:
            ctx.post(ag + [d.id] + ([inv.id] if inv else []), ctx.pick('Bad Debt Expense'), ctx.ar(), d.m('Amount'))
        else:
            ctx.post([d.id] + ([inv.id] if inv else []), ctx.revenue_acct(), ctx.ar(), d.m('Amount'))

    # ---------------- manufacturing
    batch_sheet = {d.g('Batch ID'): d for d in T['production_batch_sheet']}
    wip = ctx.pick('Work In Process')
    for d in T['material_requisition_slip']:
        b = batch_sheet.get(d.g('Batch ID'))
        ctx.post([d.id] + ([b.id] if b else []), wip, ctx.pick('Raw Materials Inventory'), d.m('Issue Value'))
    for d in T['direct_labor_record']:
        b = batch_sheet.get(d.g('Batch ID'))
        paid = d.m('Labor Cash Paid')
        val = d.m('Labor Value')
        ctx.post([d.id] + ([b.id] if b else []), wip, ctx.cash(), paid if paid is not None else val)
        if paid is not None and val is not None and val - paid > 0.005:
            ctx.post([d.id] + ([b.id] if b else []), wip, ctx.pick('Accrued Expenses'), val - paid)
    for d in T['overhead_accrual_memo']:
        b = batch_sheet.get(d.g('Batch ID'))
        ctx.post([d.id] + ([b.id] if b else []), wip, ctx.pick('Accrued Expenses'), d.m('Accrued Overhead', 'Overhead Value'))
    for d in T['finished_goods_transfer_note']:
        b = batch_sheet.get(d.g('Batch ID'))
        ctx.post([d.id] + ([b.id] if b else []), ctx.pick('Finished Goods Inventory'), wip, d.m('Transfer Value'))

    # ---------------- leases
    lease_paid = set()
    for d in T['lease_agreement']:
        ctx.post([d.id], ctx.pick('Right-of-Use Asset'), ctx.pick('Lease Liability'), d.m('Lease Liability Amount', 'ROU Asset Amount'))
    agr = {d.g('Agreement Number'): d for d in T['lease_agreement']}
    sched = defaultdict(list)
    for d in T['lease_amortization_schedule']:
        sched[d.g('Agreement Number')].append(d)
    for d in T['lease_payment_notice']:
        an = d.g('Agreement Number')
        a = agr.get(an)
        s = sched.get(an, [])
        refs = ([a.id] if a else []) + [x.id for x in s[:1]] + [d.id]
        ctx.post(refs, ctx.pick('Lease Liability'), ctx.cash(), d.m('Principal Amount'))
        ctx.post(refs, ctx.pick('Lease Interest Expense', 'Interest Expense'), ctx.cash(), d.m('Interest Amount'))
        lease_paid.add(an)
    for an, ss in sched.items():
        a = agr.get(an)
        for s in ss:
            refs = ([a.id] if a else []) + [s.id]
            if an not in lease_paid:
                ctx.post(refs, ctx.pick('Lease Liability'), ctx.cash(), s.m('Principal Amount'))
                ctx.post(refs, ctx.pick('Lease Interest Expense', 'Interest Expense'), ctx.cash(), s.m('Interest Amount'))
            ctx.post(refs, ctx.pick('Lease Amortization Expense', 'Amortization Expense'), ctx.pick('Right-of-Use Asset'), s.m('ROU Amortization Amount'))
    for d in T['lease_modification_notice']:
        an = d.g('Agreement Number')
        a = agr.get(an)
        delta = d.m('Liability Remeasurement Delta Amount')
        o, n = d.m('Old Liability Balance'), d.m('Remeasured Liability Balance')
        if o is not None and n is not None:
            delta = n - o
        refs = ([a.id] if a else []) + [d.id]
        ctx.post(refs, ctx.pick('Right-of-Use Asset'), ctx.pick('Lease Liability'), delta)

    # ---------------- result
    return ctx, docs, T


def build_balance(rec, entries):
    ob = rec.get('opening_balance', {})
    sec = {}
    bal = OrderedDict()
    for s in ('assets', 'liabilities', 'equity'):
        for a, v in ob.get(s, {}).items():
            sec[a] = s
            bal[a] = bal.get(a, 0.0) + (v if s == 'assets' else -v)
    for e in entries:
        for a, sgn in ((e['debit_account'], 1), (e['credit_account'], -1)):
            bal[a] = bal.get(a, 0.0) + sgn * e['amount']
    out = {'assets': OrderedDict(), 'liabilities': OrderedDict(), 'equity': OrderedDict()}
    pl = 0.0
    for a, v in bal.items():
        s = section_of(a, sec)
        if s == 'pl':
            pl += v
            continue
        if s == 'assets':
            out['assets'][a] = r2(v)
        else:
            out[s][a] = r2(-v)
    re_name = 'Retained Earnings'
    out['equity'][re_name] = r2(out['equity'].get(re_name, 0.0) - pl)
    for s in out:
        for a in list(out[s].keys()):
            if abs(out[s][a]) < 0.005 and a != 'Retained Earnings':
                del out[s][a]
    return out


def answer(rec):
    ctx, docs, T = solve(rec)
    if ctx.codes:
        return {'has_inconsistency': True, 'inconsistency_codes': ctx.codes, 'inconsistency_notes': ctx.notes,
                'entries': [], 'balance_sheet': {'assets': {}, 'liabilities': {}, 'equity': {}}}
    bs = build_balance(rec, ctx.entries)
    return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [],
            'entries': ctx.entries, 'balance_sheet': bs}


def main():
    src, dst = sys.argv[1], sys.argv[2]
    out = {}
    with open(src) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            try:
                out[rec['record_id']] = answer(rec)
            except Exception as ex:  # never crash the whole run
                bs = build_balance(rec, [])
                out[rec['record_id']] = {'has_inconsistency': False, 'inconsistency_codes': [],
                                         'inconsistency_notes': [], 'entries': [], 'balance_sheet': bs}
                sys.stderr.write('ERROR %s: %r\n' % (rec.get('record_id'), ex))
    with open(dst, 'w') as f:
        json.dump(out, f, indent=1)


if __name__ == '__main__':
    main()
