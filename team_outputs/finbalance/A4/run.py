#!/usr/bin/env python3
"""FinBalance packet closer (hackathon reto F). Rule-based: parse OCR key/values, post entries per document type,
run reconciliation checks to flag inconsistent packets, roll opening balance + entries into a balance sheet.
Usage: python3 run.py <records.jsonl> <salida.json>   (stdlib only)"""
import json, re, sys

AMT_RE = re.compile(r'(?:[A-Z]{3}\s?|[$€£₹]\s?)?-?\(?\d[\d.,]*\)?')

def num(s):
    """Parse an amount string in US or European format. Returns float or None."""
    if s is None: return None
    s = str(s).strip()
    m = re.search(r'-?\d[\d.,]*', s)
    if not m: return None
    t = m.group(0).rstrip('.,')
    neg = t.startswith('-') or ('(' in s and ')' in s)
    t = t.lstrip('-')
    if ',' in t and '.' in t:
        if t.rfind(',') > t.rfind('.'):
            t = t.replace('.', '').replace(',', '.')
        else:
            t = t.replace(',', '')
    elif ',' in t:
        parts = t.split(',')
        if len(parts[-1]) == 3 and len(parts) >= 2:
            t = t.replace(',', '')
        else:
            t = t.replace(',', '.')
            if t.count('.') > 1:
                p = t.split('.'); t = ''.join(p[:-1]) + '.' + p[-1]
    elif t.count('.') > 1:
        p = t.split('.')
        if all(len(x) == 3 for x in p[1:]): t = ''.join(p)
        else: t = ''.join(p[:-1]) + '.' + p[-1]
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v

def unwrap(text):
    lines = text.split('\n')
    out = []
    for l in lines:
        if out and len(out[-1]) >= 78 and l.strip() and not l.startswith('  - ') \
                and not re.match(r'^[-=]{3,}$', l.strip()):
            out[-1] = out[-1] + l
        else:
            out.append(l)
    return out

LABELS = ['Allocated Transaction Price', 'Invoice Line Amount', 'Released This Period', 'Release Pattern',
          'Ssp Amount', 'Extended Cost', 'Unit Cost', 'Unit Price', 'System Qty', 'Counted Qty', 'Document Type',
          'Past Due', 'Tax Amount', 'Tax Rate', 'Net Amount', 'Gross Amount']

def parse_part(p):
    p = p.strip()
    for L in LABELS:
        if p.startswith(L + ' ') or p == L:
            return L, p[len(L):].strip()
    m = re.match(r'^(\S+)\s*(.*)$', p)
    if m: return m.group(1), m.group(2)
    return p, ''

def parse_doc(d):
    lines = unwrap(d.get('ocr_text', ''))
    fields = {}
    allf = []
    items = []
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith('- ') and l.startswith('  '):
            body = s[2:]
            if '|' in body or True:
                parts = [parse_part(x) for x in body.split('|')]
                it = {}
                for k, v in parts:
                    if k in it: k = k + '_2'
                    it[k] = v
                it['_raw'] = body
                items.append(it)
            continue
        m = re.match(r'^([A-Za-z][A-Za-z /&\'()-]*?):\s*(.*)$', s)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            allf.append((k, v))
            if k not in fields: fields[k] = v
    return {'id': d['doc_id'], 'type': d['doc_type'], 'title': d.get('title', ''), 'date': d.get('date', ''),
            'f': fields, 'all': allf, 'items': items, 'text': '\n'.join(lines)}

def fnum(doc, *keys):
    for k in keys:
        if k in doc['f']:
            v = num(doc['f'][k])
            if v is not None: return v
    return None
ASSETS = {'Accounts Receivable','Accumulated Depreciation','Card Settlement Clearing','Cash','Equipment',
 'Finished Goods Inventory','Furniture','Input CGST Receivable','Input IGST Receivable','Input SGST Receivable',
 'Input Tax Receivable','Inventory','Office Supplies','Prepaid Insurance','Prepaid Rent','Raw Materials Inventory',
 'Reserve Cash','Right-of-Use Asset','Store Fixtures','Vehicles','Work In Process'}
LIABS = {'Accounts Payable','Accrued Expenses','CGST Payable','SGST Payable','IGST Payable','Deferred Tax Liability',
 'Lease Liability','Loans Payable','Notes Payable','Sales Tax Payable','Security Deposits Payable','Unearned Revenue'}
EQUITY = {"Owner's Equity",'Retained Earnings','Share Capital'}

def section(a):
    if a in ASSETS: return 'assets'
    if a in LIABS: return 'liabilities'
    if a in EQUITY: return 'equity'
    al = a.lower()
    if 'expense' in al or 'revenue' in al and 'unearned' not in al: return 'pl'
    if 'payable' in al or 'liabilit' in al or 'unearned' in al or 'deferred revenue' in al: return 'liabilities'
    if 'receivable' in al or 'inventory' in al or 'prepaid' in al or 'cash' in al or 'asset' in al: return 'assets'
    if 'expense' in al or 'revenue' in al or 'gain' in al or 'loss' in al or 'cost of' in al: return 'pl'
    return 'pl'

def build_bs(opening, entries):
    bal = {}  # debit-positive
    for s in ('assets','liabilities','equity'):
        for a, v in opening.get(s, {}).items():
            bal[a] = bal.get(a, 0.0) + (v if s == 'assets' else -v)
    for e in entries:
        amt = e['amount']
        bal[e['debit_account']] = bal.get(e['debit_account'], 0.0) + amt
        bal[e['credit_account']] = bal.get(e['credit_account'], 0.0) - amt
    bs = {'assets': {}, 'liabilities': {}, 'equity': {}}
    ni = 0.0
    for a, v in bal.items():
        s = section(a)
        if s == 'pl':
            ni -= v
            continue
        bs[s][a] = bs[s].get(a, 0.0) + (v if s == 'assets' else -v)
    bs['equity']['Retained Earnings'] = bs['equity'].get('Retained Earnings', 0.0) + ni
    for s in bs:
        bs[s] = {a: round(v, 2) for a, v in bs[s].items() if abs(round(v, 2)) >= 0.005}
    return bs

REV_ACCTS = ['Sales Revenue', 'Service Revenue', 'Rental Revenue']


def r2(x):
    return round(x + 0.0, 2)


class Ctx:
    def __init__(self, rec):
        self.rec = rec
        self.allowed = set(rec['allowed_accounts'])
        self.regime = rec['context'].get('tax_regime', 'none')
        self.func = rec['context'].get('functional_currency_code', 'USD')
        self.docs = [parse_doc(d) for d in rec['documents']]
        self.by_id = {d['id']: d for d in self.docs}
        self.entries = []
        self.issues = []
        self.used = set()
        self.rev = next((a for a in ['Rental Revenue', 'Service Revenue', 'Sales Revenue'] if a in self.allowed), 'Sales Revenue')
        if self.rev == 'Rental Revenue' and 'Service Revenue' in self.allowed:
            pass
        self.fa = 'Store Fixtures' if ('Store Fixtures' in self.allowed and 'Equipment' not in self.allowed) else 'Equipment'
        # reference index: any value of a "... Number"/"ID"/Ref field -> docs
        self.ref = {}
        for d in self.docs:
            for k, v in d['all']:
                if k in ('Document ID', 'Document Type', 'Period', 'Page marker'):
                    continue
                if re.search(r'(Number|ID)$', k) and v:
                    self.ref.setdefault(v.strip(), [])
                    if d not in self.ref[v.strip()]:
                        self.ref[v.strip()].append(d)

    def add(self, refs, dr, cr, amt):
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

    def find(self, ref, types=None):
        for d in self.ref.get((ref or '').strip(), []):
            if types is None or d['type'] in types:
                return d
        return None

    def flag(self, code, note):
        self.issues.append((code, note))


def f(d, k):
    return d['f'].get(k)


def amt_of(d, *keys):
    return fnum(d, *keys)


def tax_split(ctx, d):
    """Return list of (kind, amount) tax components shown on doc."""
    comps = []
    c = amt_of(d, 'CGST Amount'); s = amt_of(d, 'SGST Amount'); i = amt_of(d, 'IGST Amount')
    if c or s:
        comps += [('CGST', c or 0.0), ('SGST', s or 0.0)]
    if i:
        comps.append(('IGST', i))
    if not comps:
        t = amt_of(d, 'Tax Amount')
        if t:
            comps.append(('TAX', t))
    return comps


def check_tax(ctx, d):
    sub = amt_of(d, 'Subtotal'); tax = amt_of(d, 'Tax Amount'); tot = amt_of(d, 'Total')
    rate = amt_of(d, 'Tax Rate')
    lines = [num(it.get('Amount')) for it in d['items'] if it.get('Amount') is not None]
    lines = [x for x in lines if x is not None]
    purchase_doc = d['type'] in ('vendor_invoice', 'supplier_invoice', 'utilities_statement')
    if sub is not None and tax is not None and tot is not None:
        if lines and abs(sum(lines) - sub) > 0.011:
            ctx.flag('invoice_total_mismatch', f"{d['id']} lines != subtotal")
        elif abs(sub + tax - tot) > 0.011:
            ctx.flag('invoice_total_mismatch' if purchase_doc else 'tax_total_mismatch', f"{d['id']} subtotal+tax != total")
        elif rate is not None and tax > 0 and abs(r2(sub * rate / 100.0) - tax) > 0.011:
            ctx.flag('tax_rate_mismatch', f"{d['id']} tax != rate*basis")
    elif tot is not None and lines and sub is None and tax is None:
        if abs(sum(lines) - tot) > 0.011:
            ctx.flag('invoice_total_mismatch', f"{d['id']} lines != total")
    c = amt_of(d, 'CGST Amount'); s = amt_of(d, 'SGST Amount'); ig = amt_of(d, 'IGST Amount')
    purchase = d['type'] in ('vendor_invoice', 'supplier_invoice', 'utilities_statement')
    comp = (c or 0) + (s or 0) + (ig or 0)
    if (c is not None or s is not None or ig is not None) and tax is not None and abs(comp - tax) > 0.011:
        ctx.flag('input_tax_mismatch' if purchase else 'tax_total_mismatch', f"{d['id']} tax components != tax amount")


OUT_TAX = {'CGST': 'CGST Payable', 'SGST': 'SGST Payable', 'IGST': 'IGST Payable', 'TAX': 'Sales Tax Payable'}
IN_TAX = {'CGST': 'Input CGST Receivable', 'SGST': 'Input SGST Receivable', 'IGST': 'Input IGST Receivable', 'TAX': 'Input Tax Receivable'}


def pdate(s):
    s = (s or '').strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m: return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{2})/(\d{2})/(\d{4})', s)
    if m: return (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def fx_info(ctx, d):
    """If doc denominated in foreign currency, return (rate, functional_amount, rate_doc) from exchange_rate_notice."""
    cur = (f(d, 'Currency') or '').strip()
    tot_raw = f(d, 'Total') or f(d, 'Amount') or ''
    m = re.match(r'^([A-Z]{3})\s', tot_raw.strip())
    if m and m.group(1) != ctx.func:
        cur = m.group(1)
    if not cur or cur == ctx.func:
        return None
    num_ = f(d, 'Invoice Number')
    for x in ctx.docs:
        if x['type'] == 'exchange_rate_notice' and (f(x, 'Reference') == num_):
            return x
    return 'missing'


def build(ctx):
    D = ctx.docs
    # ---------- cancellations / withdrawn ----------
    withdrawn = set()
    cancel_docs = {}
    for d in D:
        if d['type'] == 'cancellation_note':
            w = f(d, 'Withdrawn Reference')
            if w:
                withdrawn.add(w.strip()); cancel_docs[w.strip()] = d
    def active(d):
        n = f(d, 'Invoice Number')
        return not (n and n.strip() in withdrawn)
    # duplicate references among postable invoices
    seen_inv = {}
    skip = set()
    for d in D:
        if d['type'] in ('customer_invoice', 'vendor_invoice', 'supplier_invoice', 'patient_invoice', 'utilities_statement') and active(d):
            n = f(d, 'Invoice Number')
            if not n: continue
            if n in seen_inv:
                o = seen_inv[n]
                if abs((amt_of(o, 'Total', 'Gross Charge') or 0) - (amt_of(d, 'Total', 'Gross Charge') or 0)) > 0.011:
                    ctx.flag('duplicate_reference_conflict', f"{o['id']} and {d['id']} share {n} with different totals")
                skip.add(d['id'])
            else:
                seen_inv[n] = d
    # also secondary copies conflicting with originals
    for d in D:
        if d['type'] == 'secondary_copy':
            src = f(d, 'Source Reference')
            o = seen_inv.get(src)
            if o is not None:
                t1 = amt_of(o, 'Total', 'Gross Charge'); t2 = amt_of(d, 'Total')
                if t1 is not None and t2 is not None and abs(t1 - t2) > 0.011:
                    ctx.flag('duplicate_reference_conflict', f"{d['id']} copy of {src} shows different total")

    deferred_inv = {}  # invoice number -> schedule doc
    for d in D:
        if d['type'] == 'revenue_recognition_schedule':
            deferred_inv[(f(d, 'Contract Reference') or '').strip()] = d
    asc_forms = {}
    for d in D:
        if d['type'] in ('subscription_order_form',):
            asc_forms[(f(d, 'Form Number') or '').strip()] = d
    advance = {}
    paid_refs = set()
    for d in D:
        if d['type'] == 'payment_advice':
            paid_refs.add((f(d, 'Reference') or '').strip())
            for it in d['items']:
                if it.get('Reference'): paid_refs.add(it['Reference'].strip())
    for d in D:
        if d['type'] == 'bank_statement':
            for it in d['items']:
                m = re.match(r'Advance collection\s+(\S+)', (it.get('Description') or '').strip())
                if m and m.group(1) not in paid_refs:
                    advance[m.group(1)] = d['id']
    shipments = {}
    for d in D:
        if d['type'] == 'delivery_note':
            shipments[(f(d, 'Shipment Ref') or '').strip()] = d
    work_orders = [d for d in D if d['type'] == 'work_order']
    grns = {(f(d, 'GRN Number') or '').strip(): d for d in D if d['type'] == 'goods_receipt_note'}
    taxnotices = [d for d in D if d['type'] == 'tax_regime_notice']
    exempt = {(f(d, 'Certificate Number') or '').strip(): d for d in D if d['type'] == 'tax_exemption_certificate'}
    profiles = [d for d in D if d['type'] == 'customer_tax_profile']

    deferred_reclass = []
    for d in D:
        t = d['type']
        if d['id'] in skip or not active(d):
            continue
        i = d['id']
        if t == 'customer_invoice':
            check_tax(ctx, d)
            sub = amt_of(d, 'Subtotal'); tot = amt_of(d, 'Total')
            comps = tax_split(ctx, d)
            base = sub if sub is not None else (tot - sum(a for _, a in comps) if tot is not None else None)
            if base is None: continue
            refs = [i]
            rev = ctx.rev
            cref = (f(d, 'Contract Ref') or '').strip()
            sref = (f(d, 'Shipment Ref') or '').strip()
            n = (f(d, 'Invoice Number') or '').strip()
            cogs = None
            if sref and sref in shipments:
                dn = shipments[sref]; refs = [dn['id'], i]
                cogs = (amt_of(dn, 'Cost Basis Amount'), 'Inventory' if 'Inventory' in ctx.allowed else 'Finished Goods Inventory')
                billed = amt_of(dn, 'Billed Amount')
                if billed is not None and tot is not None and abs(billed - tot) > 0.011:
                    ctx.flag('invoice_total_mismatch', f"{dn['id']} billed != {i} total")
            elif cref.startswith('FGT'):
                fg = ctx.find(cref, ['finished_goods_transfer_note'])
                if fg:
                    refs = [i, fg['id']]
                    cogs = (amt_of(fg, 'Transfer Value'), 'Finished Goods Inventory')
            else:
                for wo in work_orders:
                    if (f(wo, 'Customer') == f(d, 'Customer') and amt_of(wo, 'Approved Amount') is not None
                            and abs(amt_of(wo, 'Approved Amount') - base) < 0.011):
                        refs = [wo['id'], i]; break
            cust = (f(d, 'Customer') or '').strip()
            for p in profiles:
                if (f(p, 'Customer') or '').strip() == cust:
                    ss = (f(p, 'Same State') or '').strip().lower()
                    cj = (f(p, 'Company Jurisdiction') or '').strip().lower(); pj = (f(p, 'Customer Jurisdiction') or '').strip().lower()
                    if cj and pj and ss in ('true', 'false') and ((ss == 'true') != (cj == pj)):
                        ctx.flag('jurisdiction_tax_mismatch', f"{p['id']} same-state flag inconsistent")
                    kinds = set(k for k, a in comps if a > 0.005)
                    if ss == 'true' and 'IGST' in kinds or ss == 'false' and ('CGST' in kinds or 'SGST' in kinds):
                        ctx.flag('jurisdiction_tax_mismatch', f"{i} GST type inconsistent with {p['id']}")
            ec = (f(d, 'Exemption Certificate') or '').strip()
            if ec and ec in exempt:
                cert = exempt[ec]
                pr = [p['id'] for p in profiles if (f(p, 'Exemption Certificate') or '').strip() == ec]
                refs = [cert['id']] + pr + refs
                valid = (f(cert, 'Exemption Status') or '').lower().startswith('valid')
                cp = (f(cert, 'Counterparty') or '').strip().lower(); cu = (f(d, 'Customer') or '').strip().lower()
                dt = pdate(d['date']); e0 = pdate(f(cert, 'Effective Date')); e1 = pdate(f(cert, 'Expiration Date'))
                in_period = not (dt and e0 and e1) or (e0 <= dt <= e1)
                taxed = comps and sum(a for _, a in comps) > 0.005
                if valid and in_period and (not cp or cp == cu):
                    if taxed:
                        ctx.flag('tax_exemption_conflict', f"{i} charges tax despite valid exemption {ec}")
                elif not taxed:
                    ctx.flag('tax_exemption_conflict', f"{i} exempted with invalid/expired/foreign certificate {ec}")
            # FX
            fx = fx_info(ctx, d)
            rate = 1.0
            if fx == 'missing':
                pass
            elif fx is not None:
                rate = num(f(fx, 'Exchange Rate')) or 1.0
                fa = amt_of(fx, 'Functional Amount'); sa = amt_of(fx, 'Source Amount')
                if fa is not None and sa is not None and abs(r2(sa * rate) - fa) > 0.011:
                    ctx.flag('exchange_rate_mismatch', f"{fx['id']} source*rate != functional")
                refs = refs + [fx['id']]
                base = fa if (fa is not None and not comps) else r2(base * rate)
                comps = [(k, r2(a * rate)) for k, a in comps]
            credit = rev
            if n in deferred_inv or cref.startswith('SOF') or cref.startswith('ASC606') or cref in asc_forms or cref.startswith('RET'):
                if 'Unearned Revenue' in ctx.allowed:
                    credit = 'Unearned Revenue'
                if cref in asc_forms:
                    refs = [asc_forms[cref]['id']] + refs
            debit = 'Accounts Receivable'
            if n in advance:
                debit = 'Cash'; refs = refs + [advance[n]]
            ctx.add(refs, debit, credit, base)
            for k, a in comps:
                ctx.add(refs, debit, OUT_TAX[k], a)
            if cogs and cogs[0]:
                ctx.add(refs, 'Cost of Goods Sold', cogs[1], cogs[0])
        elif t in ('vendor_invoice', 'supplier_invoice', 'utilities_statement'):
            check_tax(ctx, d)
            sub = amt_of(d, 'Subtotal'); tot = amt_of(d, 'Total')
            comps = tax_split(ctx, d)
            base = sub if sub is not None else (tot - sum(a for _, a in comps) if tot is not None else None)
            if base is None: continue
            refs = [i]
            force_embed = None
            if t == 'utilities_statement':
                acct = 'Utilities Expense'
            else:
                acct = f(d, 'Expense Label') or f(d, 'Expense Category')
                g = (f(d, 'Goods Receipt Ref') or '').strip()
                if g in grns:
                    refs = [grns[g]['id'], i]
                if g.startswith('GRN-TAX'):
                    for tn in taxnotices:
                        refs = [tn['id'], i]
                        tamt = amt_of(tn, 'Jurisdiction Tax Amount')
                        if tamt is not None and comps and abs(tamt - sum(a for _, a in comps)) > 0.011:
                            ctx.flag('jurisdiction_tax_mismatch', f"{tn['id']} tax differs from {i}")
                        tr = (f(tn, 'Treatment') or '').lower()
                        cj = (f(tn, 'Company Jurisdiction') or '').strip().lower(); pj = (f(tn, 'Counterparty Jurisdiction') or '').strip().lower()
                        if cj and pj and (('same-state' in tr and cj != pj) or ('different-state' in tr and cj == pj)):
                            ctx.flag('jurisdiction_tax_mismatch', f"{tn['id']} treatment inconsistent with jurisdictions")
                        trate = amt_of(tn, 'Tax Rate'); irate = amt_of(d, 'Tax Rate')
                        if trate is not None and irate is not None and abs(trate - irate) > 0.001:
                            ctx.flag('jurisdiction_tax_mismatch', f"{tn['id']} rate differs from {i}")
                        if 'capitaliz' in tr or 'embedded' in tr or 'into inventory cost' in tr:
                            force_embed = True
                        elif 'input credit' in tr or 'recoverable' in tr:
                            force_embed = False
                        tot_tax = sum(a for _, a in comps)
                        if 'igst' in tr and not any(k == 'IGST' for k, _ in comps) and comps:
                            ctx.flag('jurisdiction_tax_mismatch', f"{tn['id']} IGST vs CGST/SGST on {i}")
                        if 'cgst' in tr and any(k == 'IGST' for k, _ in comps):
                            ctx.flag('jurisdiction_tax_mismatch', f"{tn['id']} CGST/SGST vs IGST on {i}")
                        break
                if not acct or acct not in ctx.allowed:
                    if g or 'Inventory' in ctx.allowed and t == 'supplier_invoice':
                        acct = 'Inventory' if 'Inventory' in ctx.allowed else 'Raw Materials Inventory'
                    if 'Raw Materials Inventory' in ctx.allowed and t == 'supplier_invoice':
                        acct = 'Raw Materials Inventory'
                    if not acct or acct not in ctx.allowed:
                        acct = 'Office Supplies Expense' if 'Office Supplies Expense' in ctx.allowed else 'Maintenance Expense'
            fx = fx_info(ctx, d)
            if fx not in (None, 'missing'):
                rate = num(f(fx, 'Exchange Rate')) or 1.0
                fa = amt_of(fx, 'Functional Amount'); sa = amt_of(fx, 'Source Amount')
                if fa is not None and sa is not None and abs(r2(sa * rate) - fa) > 0.011:
                    ctx.flag('exchange_rate_mismatch', f"{fx['id']} source*rate != functional")
                refs = refs + [fx['id']]
                base = fa if (fa is not None and not comps) else r2(base * rate)
                comps = [(k, r2(a * rate)) for k, a in comps]
            embed = ctx.regime == 'us_sales_tax' and all(k == 'TAX' for k, _ in comps)
            if force_embed is not None:
                embed = force_embed and all(k == 'TAX' for k, _ in comps)
            if embed:
                ctx.add(refs, acct, 'Accounts Payable', base + sum(a for _, a in comps))
            else:
                ctx.add(refs, acct, 'Accounts Payable', base)
                for k, a in comps:
                    ctx.add(refs, IN_TAX[k], 'Accounts Payable', a)
        elif t == 'patient_invoice':
            g = amt_of(d, 'Gross Charge')
            pd_ = amt_of(d, 'Patient Due'); idue = amt_of(d, 'Insurer Due')
            if g is not None and pd_ is not None and idue is not None and abs(pd_ + idue - g) > 0.011:
                ctx.flag('invoice_total_mismatch', f"{i} patient+insurer != gross")
            ctx.add([i], 'Accounts Receivable', ctx.rev, g)
        elif t == 'copay_receipt':
            ri = ctx.find(f(d, 'Reference Invoice'), ['patient_invoice'])
            ctx.add([i] + ([ri['id']] if ri else []), 'Cash', 'Accounts Receivable', amt_of(d, 'Amount'))
        elif t == 'insurer_remittance':
            ri = ctx.find(f(d, 'Claim Reference'), ['patient_invoice'])
            ctx.add([i] + ([ri['id']] if ri else []), 'Cash', 'Accounts Receivable', amt_of(d, 'Paid Amount', 'Amount'))
        elif t == 'rent_roll':
            tot = amt_of(d, 'Total Rent')
            ls = [num(it.get('Amount')) for it in d['items'] if it.get('Amount')]
            if ls and tot is not None and abs(sum(ls) - tot) > 0.011:
                ctx.flag('invoice_total_mismatch', f"{i} rent rows != total")
            ctx.add([i], 'Accounts Receivable', 'Rental Revenue' if 'Rental Revenue' in ctx.allowed else ctx.rev, tot)
        elif t == 'security_deposit_notice':
            n = f(d, 'Notice Number') or ''
            a = amt_of(d, 'Amount')
            if 'REF' in n:
                orig = [x['id'] for x in D if x['type'] == 'security_deposit_notice' and x is not d and 'REF' not in (f(x, 'Notice Number') or '')
                        and f(x, 'Tenant') == f(d, 'Tenant')]
                ctx.add([i] + orig[:1], 'Security Deposits Payable', 'Cash', a)
            else:
                ctx.add([i], 'Cash', 'Security Deposits Payable', a)
        elif t == 'payment_advice':
            handle_payment(ctx, d)
        elif t == 'payroll_summary':
            gp = amt_of(d, 'Gross Pay'); et = amt_of(d, 'Employer Tax'); co = amt_of(d, 'Cash Outflow')
            ctx.add([i], 'Salaries Expense', 'Cash', gp)
            ctx.add([i], 'Payroll Tax Expense', 'Cash', et)
        elif t == 'expense_receipt':
            acct = None
            for it in d['items']:
                desc = (it.get('Description') or '').strip()
                if desc in ctx.allowed: acct = desc; break
            if not acct:
                for it in d['items']:
                    desc = (it.get('Description') or '')
                    for a in ctx.allowed:
                        if a.endswith('Expense') and a.split()[0].lower() in desc.lower(): acct = a; break
                    if acct: break
            tot = amt_of(d, 'Total')
            ls = [num(it.get('Amount')) for it in d['items'] if it.get('Amount')]
            if ls and tot is not None and abs(sum(ls) - tot) > 0.011:
                ctx.flag('invoice_total_mismatch', f"{i} receipt lines != total")
            ctx.add([i], acct or 'Office Supplies Expense', 'Cash', tot)
        elif t == 'loan_statement':
            op = amt_of(d, 'Opening Principal'); dr = amt_of(d, 'Draw Amount') or 0; pp = amt_of(d, 'Principal Paid') or 0
            ip = amt_of(d, 'Interest Paid') or 0; ep = amt_of(d, 'Ending Principal')
            if op is not None and ep is not None and abs(op + dr - pp - ep) > 0.011:
                ctx.flag('schedule_rollforward_mismatch', f"{i} loan principal does not roll forward")
            ctx.add([i], 'Cash', 'Loans Payable', dr)
            ctx.add([i], 'Loans Payable', 'Cash', pp)
            ctx.add([i], 'Interest Expense', 'Cash', ip)
        elif t == 'equipment_invoice':
            tot = amt_of(d, 'Total'); pc = amt_of(d, 'Paid Cash') or 0; fin = amt_of(d, 'Financed Amount') or 0
            if tot is not None and abs(pc + fin - tot) > 0.011:
                ctx.flag('invoice_total_mismatch', f"{i} cash+financed != total")
            ctx.add([i], ctx.fa, 'Cash', pc)
            ctx.add([i], ctx.fa, 'Notes Payable', fin)
        elif t in ('depreciation_schedule', 'fixed_asset_rollforward'):
            ch = amt_of(d, 'Current Period Charge', 'Current Charge')
            ctx.add([i], 'Depreciation Expense', 'Accumulated Depreciation', ch)
        elif t in ('rent_notice', 'insurance_notice'):
            tot = amt_of(d, 'Total', 'Total Premium')
            ctx.add([i], 'Prepaid Rent' if t == 'rent_notice' else 'Prepaid Insurance', 'Cash', tot)
        elif t == 'service_period_memo':
            handle_spm(ctx, d)
        elif t == 'transfer_advice':
            fa_ = f(d, 'From Account'); ta = f(d, 'To Account')
            if fa_ in ctx.allowed and ta in ctx.allowed:
                ctx.add([i], ta, fa_, amt_of(d, 'Amount'))
        elif t == 'asset_disposal_notice':
            handle_disposal(ctx, d)
        elif t == 'lease_agreement':
            handle_lease(ctx, d)
        elif t == 'lease_modification_notice':
            delta = amt_of(d, 'Liability Remeasurement Delta Amount'); rou = amt_of(d, 'ROU Asset Adjustment Amount')
            old = amt_of(d, 'Old Liability Balance'); new = amt_of(d, 'Remeasured Liability Balance')
            if delta is not None and rou is not None and abs(delta - rou) > 0.011:
                ctx.flag('lease_remeasurement_mismatch', f"{i} delta != ROU adjustment")
            if old is not None and new is not None and delta is not None and abs(new - old - delta) > 0.011:
                ctx.flag('lease_remeasurement_mismatch', f"{i} remeasured-old != delta")
            ag = ctx.find(f(d, 'Agreement Number'), ['lease_agreement'])
            if delta is not None:
                if new is not None and old is not None and new < old:
                    ctx.add([i] + ([ag['id']] if ag else []), 'Lease Liability', 'Right-of-Use Asset', abs(delta))
                else:
                    ctx.add([i] + ([ag['id']] if ag else []), 'Right-of-Use Asset', 'Lease Liability', abs(delta))
        elif t == 'material_requisition_slip':
            b = ctx.find(f(d, 'Batch ID'), ['production_batch_sheet'])
            mat = f(d, 'Material')
            si = [x for x in D if x['type'] == 'supplier_invoice' and any((it.get('Description') or '').strip() == mat for it in x['items'])]
            si = [x['id'] for x in sorted(si, key=lambda x: (f(x, 'Invoice Number') or 'ZZZ'))]
            ctx.add([i] + ([b['id']] if b else []) + si[:1], 'Work In Process', 'Raw Materials Inventory', amt_of(d, 'Issue Value'))
        elif t == 'direct_labor_record':
            b = ctx.find(f(d, 'Batch ID'), ['production_batch_sheet'])
            ctx.add([i] + ([b['id']] if b else []), 'Work In Process', 'Cash', amt_of(d, 'Labor Cash Paid', 'Labor Value'))
        elif t == 'overhead_accrual_memo':
            b = ctx.find(f(d, 'Batch ID'), ['production_batch_sheet'])
            ctx.add([i] + ([b['id']] if b else []), 'Work In Process', 'Accrued Expenses', amt_of(d, 'Accrued Overhead', 'Overhead Value'))
        elif t == 'finished_goods_transfer_note':
            b = ctx.find(f(d, 'Batch ID'), ['production_batch_sheet'])
            ctx.add([i] + ([b['id']] if b else []), 'Finished Goods Inventory', 'Work In Process', amt_of(d, 'Transfer Value'))
        elif t == 'inventory_adjustment_note':
            sh = ctx.find(f(d, 'Reference Sheet'), ['stock_count_sheet'])
            refs = ([sh['id']] if sh else []) + [i]
            a = amt_of(d, 'Amount')
            if sh:
                calc = 0.0
                for it in sh['items']:
                    try:
                        calc += (num(it.get('System Qty')) - num(it.get('Counted Qty'))) * num(it.get('Unit Cost'))
                    except TypeError:
                        pass
                if a is not None and abs(r2(calc) - a) > 0.011:
                    ctx.flag('inventory_rollforward_mismatch', f"{i} adjustment != count variance")
            inv = 'Inventory' if 'Inventory' in ctx.allowed else 'Finished Goods Inventory'
            ctx.add(refs, 'Inventory Shrinkage Expense', inv, a)
        elif t == 'inventory_rollforward':
            op = amt_of(d, 'Opening Balance'); ad = amt_of(d, 'Additions') or 0; us = amt_of(d, 'Usage Or Sales') or 0
            wd = amt_of(d, 'Write Down') or 0; eb = amt_of(d, 'Ending Balance')
            if op is not None and eb is not None and abs(op + ad - us - wd - eb) > 0.011:
                ctx.flag('inventory_rollforward_mismatch', f"{i} rollforward does not reconcile")
            if wd and not any(x['type'] == 'inventory_adjustment_note' for x in D):
                def _var(x):
                    v = 0.0
                    for it in x['items']:
                        try: v += (num(it.get('System Qty')) - num(it.get('Counted Qty'))) * num(it.get('Unit Cost'))
                        except TypeError: pass
                    return v
                sh = [x['id'] for x in sorted([x for x in D if x['type'] == 'stock_count_sheet'], key=lambda x: abs(_var(x) - wd))]
                inv = 'Inventory' if 'Inventory' in ctx.allowed else 'Finished Goods Inventory'
                ctx.add(sh[:1] + [i], 'Inventory Shrinkage Expense', inv, wd)
        elif t == 'scrap_report':
            lot = f(d, 'Batch Or Lot') or ''
            inv = 'Finished Goods Inventory' if 'Finished Goods Inventory' in ctx.allowed else 'Inventory'
            refs = [i]
            if lot.startswith('OPEN'):
                refs.append(next((x['id'] for x in D if x['type'] == 'opening_trial_balance'), None))
            ctx.add(refs, 'Inventory Shrinkage Expense', inv, amt_of(d, 'Write Down', 'Amount'))
        elif t == 'sales_summary':
            handle_sales(ctx, d)
        elif t == 'card_settlement_report':
            net = amt_of(d, 'Net Deposit'); fee = amt_of(d, 'Fees'); gross = amt_of(d, 'Gross Amount')
            if gross is not None and net is not None and fee is not None and abs(gross - fee - net) > 0.011:
                ctx.flag('bank_closing_mismatch', f"{i} gross-fees != net")
            bids = [it['_raw'].strip() for it in d['items']]
            bs = [x['id'] for x in D if x['type'] == 'pos_batch_report' and f(x, 'Batch ID') in bids]
            ctx.add([i] + bs, 'Cash', 'Card Settlement Clearing', net)
            feeacct = 'Maintenance Expense' if 'Maintenance Expense' in ctx.allowed else 'Office Supplies Expense'
            ctx.add([i] + bs, feeacct, 'Card Settlement Clearing', fee)
        elif t == 'return_note':
            ctx.add([i], ctx.rev, 'Cash', amt_of(d, 'Amount'))
        elif t == 'credit_memo':
            handle_credit(ctx, d)
        elif t == 'reclassification_memo':
            deferred_reclass.append(d)
        elif t == 'deferred_tax_memo':
            handle_dtax(ctx, d)
        elif t == 'revenue_recognition_schedule':
            op = amt_of(d, 'Opening Deferred'); ad = amt_of(d, 'Added Deferred') or 0; rl = amt_of(d, 'Released This Period') or 0
            eb = amt_of(d, 'Ending Deferred')
            if op is not None and eb is not None and abs(op + ad - rl - eb) > 0.011:
                ctx.flag('schedule_rollforward_mismatch', f"{i} deferred schedule does not roll forward")
            inv = ctx.find(f(d, 'Contract Reference'), ['customer_invoice'])
            refs = [i] + ([inv['id']] if inv else [])
            ctx.add(refs, 'Unearned Revenue', ctx.rev, rl)
        elif t == 'performance_obligation_schedule':
            handle_pob(ctx, d)
        elif t == 'fx_remeasurement_memo':
            handle_fxrem(ctx, d)
        elif t == 'bank_statement':
            check_bank(ctx, d)
        elif t == 'ar_aging_summary':
            check_aging(ctx, d)
        elif t == 'vendor_statement' or t == 'customer_statement':
            check_statement(ctx, d)
    for d in deferred_reclass:
        handle_reclass(ctx, d)
    return ctx


def booked_functional(ctx, inv):
    """Functional amount booked for a foreign invoice."""
    fx = fx_info(ctx, inv)
    if fx not in (None, 'missing'):
        return amt_of(fx, 'Functional Amount'), fx
    return amt_of(inv, 'Total'), None


def handle_payment(ctx, d):
    i = d['id']
    pf = (f(d, 'Payment For') or '').lower()
    amt = amt_of(d, 'Amount')
    allocs = [it for it in d['items'] if it.get('Reference')]
    def side(ref_doc):
        if 'customer' in pf or 'receivable' in pf: return 'AR'
        if 'supplier' in pf or 'payable' in pf or 'vendor' in pf: return 'AP'
        if ref_doc is not None:
            return 'AR' if ref_doc['type'] in ('customer_invoice', 'patient_invoice', 'rent_roll') else 'AP'
        return 'AR'
    if allocs:
        tot = 0.0
        for it in allocs:
            a = num(it.get('Allocated') or it.get('Allocated Amount') or it.get('Amount'))
            if a is None:
                m = re.search(r'Allocated Amount\s+(\S+)', it['_raw']); a = num(m.group(1)) if m else None
            if a is None: continue
            tot += a
            ref = it.get('Reference', '').strip()
            rd = ctx.find(ref)
            s = side(rd)
            refs = [i] + ([rd['id']] if rd else [])
            if s == 'AR': ctx.add(refs, 'Cash', 'Accounts Receivable', a)
            else: ctx.add(refs, 'Accounts Payable', 'Cash', a)
            st = (it.get('Status') or '').lower()
            if rd is not None:
                rt = amt_of(rd, 'Total')
                if rt is not None and 'closed' in st and abs(rt - a) > 0.011:
                    ctx.flag('payment_allocation_mismatch', f"{i} closes {ref} with {a} vs total {rt}")
        if amt is not None and abs(tot - amt) > 0.011:
            ctx.flag('payment_allocation_mismatch', f"{i} allocations {tot:.2f} != amount {amt}")
        return
    ref = (f(d, 'Reference') or '').strip()
    rd = ctx.find(ref)
    s = side(rd)
    refs = [i] + ([rd['id']] if rd else [])
    if f(d, 'Source Amount') and f(d, 'Exchange Rate'):
        sa = amt_of(d, 'Source Amount'); rate = num(f(d, 'Exchange Rate')); fa = amt_of(d, 'Functional Amount')
        diff = amt_of(d, 'FX Difference')
        booked, fxd = (booked_functional(ctx, rd) if rd else (None, None))
        if fxd: refs.append(fxd['id'])
        paid = amt if amt is not None else fa
        if sa is not None and rate is not None and paid is not None and abs(r2(sa * rate) - paid) > 0.011:
            ctx.flag('fx_settlement_mismatch', f"{i} source*rate != paid")
        if fa is not None and paid is not None and abs(fa - paid) > 0.011:
            ctx.flag('fx_settlement_mismatch', f"{i} functional amount != paid amount")
        if booked is None: booked = fa
        if booked is not None and paid is not None and diff is not None and abs(abs(booked - paid) - abs(diff)) > 0.011:
            # functional amount field may be booked or paid
            if fa is not None and abs(abs(fa - paid) - abs(diff)) > 0.011 and abs(abs(booked - (fa or 0)) - abs(diff)) > 0.011:
                ctx.flag('fx_settlement_mismatch', f"{i} booked/paid/difference do not reconcile")
        if s == 'AR':
            if paid <= booked + 0.005:
                ctx.add(refs, 'Cash', 'Accounts Receivable', paid)
                ctx.add(refs, 'Foreign Exchange Loss', 'Accounts Receivable', booked - paid)
            else:
                ctx.add(refs, 'Cash', 'Accounts Receivable', booked)
                ctx.add(refs, 'Cash', 'Foreign Exchange Gain', paid - booked)
        else:
            if paid >= booked - 0.005:
                ctx.add(refs, 'Accounts Payable', 'Cash', booked)
                ctx.add(refs, 'Foreign Exchange Loss', 'Cash', paid - booked)
            else:
                ctx.add(refs, 'Accounts Payable', 'Cash', paid)
                ctx.add(refs, 'Accounts Payable', 'Foreign Exchange Gain', booked - paid)
        return
    if s == 'AR': ctx.add(refs, 'Cash', 'Accounts Receivable', amt)
    else: ctx.add(refs, 'Accounts Payable', 'Cash', amt)


def handle_spm(ctx, d):
    i = d['id']
    ref = (f(d, 'Reference') or '').strip()
    a = amt_of(d, 'Recognized Amount', 'Amount')
    nd = ctx.find(ref, ['rent_notice', 'insurance_notice'])
    subj = ((f(d, 'Subject') or '') + ' ' + (f(d, 'Narrative') or '')).lower()
    if nd is not None or 'release' in subj:
        if nd is not None and nd['type'] == 'insurance_notice' or 'insurance' in subj:
            exp, pre = 'Insurance Expense', 'Prepaid Insurance'
        else:
            exp, pre = 'Rent Expense', 'Prepaid Rent'
        if nd is not None:
            m = amt_of(nd, 'Monthly Amount')
            tot_pre = amt_of(nd, 'Total', 'Total Premium')
            k = round(a / m) if (m and a) else 0
            if m is not None and a is not None and (k < 1 or abs(r2(m * k) - a) > 0.011 * k
                                                    or (tot_pre is not None and a - tot_pre > 0.011)):
                ctx.flag('schedule_rollforward_mismatch', f"{i} release != monthly amount")
        ctx.add(([nd['id']] if nd else []) + [i], exp, pre, a)
        return
    narr = (f(d, 'Narrative') or '').lower()
    acct = None
    for x in sorted(ctx.allowed, key=len, reverse=True):
        if x.endswith('Expense') and x.lower() in narr:
            acct = x; break
    ctx.add([i], acct or 'Office Supplies Expense', 'Accrued Expenses', a)


def handle_disposal(ctx, d):
    i = d['id']
    cost = amt_of(d, 'Original Cost'); ad = amt_of(d, 'Accumulated Depreciation') or 0
    nbv = amt_of(d, 'Net Book Value'); pr = amt_of(d, 'Proceeds Amount'); gl = amt_of(d, 'Gain Loss Amount')
    typ = (f(d, 'Gain Loss Type') or '').lower()
    tag = (f(d, 'Asset Tag') or '').strip()
    sp = [x for x in ctx.docs if x['type'] == 'sale_proceeds_advice' and (f(x, 'Asset Tag') or '').strip() == tag]
    refs = [i] + [x['id'] for x in sp[:1]]
    if cost is not None and nbv is not None and abs(cost - ad - nbv) > 0.011:
        ctx.flag('asset_disposal_mismatch', f"{i} cost-accdep != NBV")
    if pr is not None and nbv is not None and gl is not None:
        calc = pr - nbv
        if abs(abs(calc) - gl) > 0.011 or (calc > 0.005 and 'loss' in typ) or (calc < -0.005 and 'gain' in typ):
            ctx.flag('asset_disposal_mismatch', f"{i} proceeds-NBV != gain/loss")
    if sp:
        p2 = amt_of(sp[0], 'Proceeds Amount')
        if p2 is not None and pr is not None and abs(p2 - pr) > 0.011:
            ctx.flag('asset_disposal_mismatch', f"{i} proceeds differ from advice")
    acct = ctx.fa
    if tag.startswith('OPEN-'):
        code = tag[5:]
        for a in ('Equipment', 'Furniture', 'Vehicles', 'Store Fixtures'):
            if a.upper().startswith(code) and a in ctx.allowed:
                acct = a
    ctx.add(refs, 'Cash', acct, pr)
    ctx.add(refs, 'Accumulated Depreciation', acct, ad)
    if gl:
        if 'loss' in typ:
            ctx.add(refs, 'Loss on Disposal', acct, gl)
        else:
            ctx.add(refs, acct, 'Gain on Disposal', gl)


def handle_lease(ctx, d):
    i = d['id']
    n = (f(d, 'Agreement Number') or '').strip()
    rou = amt_of(d, 'ROU Asset Amount'); ll = amt_of(d, 'Lease Liability Amount')
    ctx.add([i], 'Right-of-Use Asset', 'Lease Liability', ll if ll is not None else rou)
    scheds = [x for x in ctx.docs if x['type'] == 'lease_amortization_schedule' and (f(x, 'Agreement Number') or '').strip() == n]
    pays = [x for x in ctx.docs if x['type'] == 'lease_payment_notice' and (f(x, 'Agreement Number') or '').strip() == n]
    for s in scheds:
        op = amt_of(s, 'Opening Liability Balance'); pm = amt_of(s, 'Payment Amount') or 0
        it = amt_of(s, 'Interest Amount') or 0; pr = amt_of(s, 'Principal Amount') or 0; eb = amt_of(s, 'Ending Liability Balance')
        if abs(it + pr - pm) > 0.011:
            ctx.flag('lease_schedule_mismatch', f"{s['id']} interest+principal != payment")
        if op is not None and eb is not None and abs(op - pr - eb) > 0.011:
            ctx.flag('lease_schedule_mismatch', f"{s['id']} opening-principal != ending")
    for p in pays:
        pm = amt_of(p, 'Payment Amount') or 0; it = amt_of(p, 'Interest Amount') or 0; pr = amt_of(p, 'Principal Amount') or 0
        if abs(it + pr - pm) > 0.011:
            ctx.flag('lease_schedule_mismatch', f"{p['id']} interest+principal != payment")
    if pays:
        for p in pays:
            sref = [s['id'] for s in scheds if abs((amt_of(s, 'Payment Amount') or 0) - (amt_of(p, 'Payment Amount') or 0)) < 0.011]
            refs = [i] + sref[:1] + [p['id']]
            ctx.add(refs, 'Lease Liability', 'Cash', amt_of(p, 'Principal Amount'))
            ctx.add(refs, 'Lease Interest Expense', 'Cash', amt_of(p, 'Interest Amount'))
            if sref:
                s = next(x for x in scheds if x['id'] == sref[0])
                if abs((amt_of(s, 'Principal Amount') or 0) - (amt_of(p, 'Principal Amount') or 0)) > 0.011:
                    ctx.flag('lease_schedule_mismatch', f"{p['id']} differs from {s['id']}")
    else:
        for s in scheds:
            ctx.add([i, s['id']], 'Lease Liability', 'Cash', amt_of(s, 'Principal Amount'))
            ctx.add([i, s['id']], 'Lease Interest Expense', 'Cash', amt_of(s, 'Interest Amount'))
    for s in scheds:
        ctx.add([i, s['id']], 'Lease Amortization Expense', 'Right-of-Use Asset', amt_of(s, 'ROU Amortization Amount'))


def handle_sales(ctx, d):
    i = d['id']
    net = amt_of(d, 'Net Sales'); tax = amt_of(d, 'Tax Amount') or 0
    cash = amt_of(d, 'Cash Sales') or 0; card = amt_of(d, 'Card Sales') or 0
    gross = amt_of(d, 'Gross Sales'); ret = amt_of(d, 'Returns') or 0
    cogs = amt_of(d, 'COGS Amount')
    if gross is not None and net is not None and abs(gross - ret - net) > 0.011:
        ctx.flag('invoice_total_mismatch', f"{i} gross-returns != net")
    if net is not None and abs(cash + card - net - tax) > 0.011:
        ctx.flag('tax_total_mismatch', f"{i} cash+card != net+tax")
    rid = f(d, 'Report ID')
    pos = [x for x in ctx.docs if x['type'] == 'pos_batch_report' and abs((amt_of(x, 'Batch Total') or -1) - card) < 0.011]
    refs = [i] + [x['id'] for x in pos[:1]]
    for p in pos[:1]:
        bt = amt_of(p, 'Batch Total'); fe = amt_of(p, 'Fee Amount') or 0; ed = amt_of(p, 'Expected Deposit')
        if bt is not None and ed is not None and abs(bt - fe - ed) > 0.011:
            ctx.flag('bank_closing_mismatch', f"{p['id']} batch-fee != deposit")
    tot = net + tax
    cash_rev = r2(cash * net / tot) if tot else 0
    cash_tax = r2(cash - cash_rev)
    card_rev = r2(net - cash_rev)
    card_tax = r2(tax - cash_tax)
    ctx.add(refs, 'Cash', ctx.rev, cash_rev)
    ctx.add(refs, 'Card Settlement Clearing', ctx.rev, card_rev)
    ctx.add(refs, 'Cost of Goods Sold', 'Inventory' if 'Inventory' in ctx.allowed else 'Finished Goods Inventory', cogs)
    ctx.add(refs, 'Cash', 'Sales Tax Payable', cash_tax)
    ctx.add(refs, 'Card Settlement Clearing', 'Sales Tax Payable', card_tax)


def handle_credit(ctx, d):
    i = d['id']
    reason = (f(d, 'Reason') or '').lower()
    a = amt_of(d, 'Amount')
    inv = ctx.find(f(d, 'Reference'), ['customer_invoice'])
    ag = [x['id'] for x in ctx.docs if x['type'] == 'ar_aging_summary']
    if 'bad debt' in reason or 'writeoff' in reason or 'write-off' in reason:
        acct = 'Bad Debt Expense' if 'Bad Debt Expense' in ctx.allowed else ctx.rev
        ctx.add(ag[:1] + [i] + ([inv['id']] if inv else []), acct, 'Accounts Receivable', a)
        for x in ctx.docs:
            if x['type'] == 'ar_aging_summary':
                for it in x['items']:
                    if it.get('Reference', '').strip() == (f(d, 'Reference') or '').strip():
                        pdue = num(it.get('Past Due'))
                        if pdue is not None and a is not None and a - pdue > 0.011:
                            ctx.flag('statement_balance_mismatch', f"{i} writeoff exceeds past due")
    else:
        ctx.add([i] + ([inv['id']] if inv else []), ctx.rev, 'Accounts Receivable', a)


def handle_reclass(ctx, d):
    i = d['id']
    fa_ = (f(d, 'From Account') or '').strip(); ta = (f(d, 'To Account') or '').strip()
    a = amt_of(d, 'Amount')
    orig = ctx.find(f(d, 'Original Reference'))
    refs = [i] + ([orig['id']] if orig else [])
    if orig is not None and a is not None:
        tot = amt_of(orig, 'Total')
        lines = [num(it.get('Amount')) for it in orig['items'] if it.get('Amount')]
        if tot is not None and a - tot > 0.011:
            ctx.flag('reclassification_support_mismatch', f"{i} amount exceeds original")
        else:
            # check posted account of original equals From Account
            posted = [e for e in ctx.entries if orig['id'] in e['doc_refs']]
            if posted and not any(e['debit_account'] == fa_ for e in posted):
                ctx.flag('reclassification_support_mismatch', f"{i} original not posted to {fa_}")
            elif lines and not any(abs(x - a) < 0.011 for x in lines) and (tot is None or abs(tot - a) > 0.011):
                ctx.flag('reclassification_support_mismatch', f"{i} amount not in original support")
    elif orig is None:
        ctx.flag('reclassification_support_mismatch', f"{i} original reference not found")
    if fa_ in ctx.allowed and ta in ctx.allowed:
        ctx.add(refs, ta, fa_, a)


def handle_dtax(ctx, d):
    i = d['id']
    op = amt_of(d, 'Opening Deferred Tax Liability') or 0
    mv = amt_of(d, 'Current Period Deferred Tax Movement')
    en = amt_of(d, 'Deferred Tax Liability Ending')
    ex = amt_of(d, 'Deferred Tax Expense Amount')
    tag = (f(d, 'Asset Tag') or '').strip()
    narr = ((f(d, 'Details') or '') + ' ' + (f(d, 'Narrative') or '')).lower()
    if 'disposal proceeds' in narr or 'combining' in narr:
        return
    td = [x for x in ctx.docs if x['type'] == 'tax_depreciation_schedule' and (f(x, 'Asset Tag') or '').strip() == tag]
    td.sort(key=lambda x: 0 if mv is not None and amt_of(x, 'Temporary Difference Amount') is not None and amt_of(x, 'Tax Rate') is not None
            and abs(amt_of(x, 'Temporary Difference Amount') * amt_of(x, 'Tax Rate') / 100 - mv) < 0.016 else 1)
    refs = [i] + [x['id'] for x in td[:1]]
    if mv is not None and en is not None and abs(op + mv - en) > 0.011:
        ctx.flag('deferred_tax_rollforward_mismatch', f"{i} opening+movement != ending")
    if td:
        x = td[0]
        bd = amt_of(x, 'Book Depreciation Amount'); tdp = amt_of(x, 'Tax Depreciation Amount')
        diff = amt_of(x, 'Temporary Difference Amount'); rate = amt_of(x, 'Tax Rate')
        if bd is not None and tdp is not None and diff is not None and abs(tdp - bd - diff) > 0.011:
            ctx.flag('deferred_tax_rollforward_mismatch', f"{x['id']} tax-book != difference")
        if diff is not None and rate is not None and mv is not None and abs(diff * rate / 100 - mv) > 0.0151:
            ctx.flag('deferred_tax_rollforward_mismatch', f"{i} movement != difference*rate")
    amt = mv if mv is not None else ex
    ctx.add(refs, 'Deferred Tax Expense', 'Deferred Tax Liability', amt)


def handle_pob(ctx, d):
    i = d['id']
    cref = (f(d, 'Contract Reference') or '').strip()
    tp = amt_of(d, 'Transaction Price'); tssp = amt_of(d, 'Total SSP')
    rel_tot = amt_of(d, 'Released This Period'); end = amt_of(d, 'Ending Deferred')
    card = [x for x in ctx.docs if x['type'] == 'ssp_rate_card' and (f(x, 'Contract Reference') or '').strip() == cref]
    acc = [x for x in ctx.docs if x['type'] == 'implementation_acceptance_memo' and (f(x, 'Contract Reference') or '').strip() == cref]
    form = asc = next((x for x in ctx.docs if x['type'] == 'subscription_order_form' and (f(x, 'Form Number') or '').strip() == cref), None)
    term = num(f(form, 'Term Months')) if form else None
    ssum = 0.0; total_rel = 0.0
    for it in d['items']:
        ssp = num(it.get('Ssp Amount')); alloc = num(it.get('Allocated Transaction Price'))
        rel = num(it.get('Released This Period')) or 0.0
        pat = (it.get('Release Pattern') or '').lower()
        ob = (it.get('Obligation') or '').strip()
        if ssp is not None: ssum += ssp
        if tp and tssp and ssp is not None and alloc is not None and abs(r2(tp * ssp / tssp) - alloc) > 0.02:
            ctx.flag('ssp_allocation_mismatch', f"{i} allocation for {ob} != TP*SSP/total")
        refs = [i]
        if 'accept' in pat:
            am = [x for x in acc if (f(x, 'Accepted Obligation') or '').strip().lower() == ob.lower()]
            if am:
                refs = [i] + [am[0]['id']]
                aa = amt_of(am[0], 'Accepted Amount')
                if aa is not None and alloc is not None and abs(aa - alloc) > 0.011:
                    ctx.flag('performance_obligation_release_mismatch', f"{am[0]['id']} accepted != allocated")
                if alloc is not None and abs(rel - alloc) > 0.011:
                    ctx.flag('performance_obligation_release_mismatch', f"{i} release != allocated on acceptance")
            else:
                if rel > 0.005:
                    ctx.flag('performance_obligation_release_mismatch', f"{i} implementation released without acceptance")
                rel = 0.0
        elif 'ratabl' in pat:
            m = re.search(r'(\d+)\s*months', pat)
            months = int(m.group(1)) if m else term
            k = round(rel / (alloc / months)) if (months and alloc) else 0
            if months and alloc is not None and rel and (k < 1 or abs(r2(alloc * k / months) - rel) > 0.02):
                ctx.flag('performance_obligation_release_mismatch', f"{i} ratable release != allocation/term")
        total_rel += rel
        if card: refs = refs + [card[0]['id']]
        ctx.add(refs, 'Unearned Revenue', ctx.rev, rel)
    if card:
        cs = amt_of(card[0], 'Total SSP')
        if cs is not None and tssp is not None and abs(cs - tssp) > 0.011:
            ctx.flag('ssp_allocation_mismatch', f"{card[0]['id']} total SSP differs from schedule")
        for it in card[0]['items']:
            ob = (it.get('Obligation') or '').strip(); s1 = num(it.get('Ssp Amount'))
            for it2 in d['items']:
                if (it2.get('Obligation') or '').strip() == ob and s1 is not None and num(it2.get('Ssp Amount')) is not None \
                        and abs(s1 - num(it2.get('Ssp Amount'))) > 0.011:
                    ctx.flag('ssp_allocation_mismatch', f"{card[0]['id']} SSP for {ob} differs")
    if tssp is not None and ssum and abs(ssum - tssp) > 0.011:
        ctx.flag('ssp_allocation_mismatch', f"{i} SSP lines != total SSP")
    if rel_tot is not None and d['items'] and abs(sum((num(it.get('Released This Period')) or 0) for it in d['items']) - rel_tot) > 0.011:
        ctx.flag('performance_obligation_release_mismatch', f"{i} released lines != released total")
    if tp is not None and end is not None and rel_tot is not None and abs(tp - rel_tot - end) > 0.011:
        ctx.flag('performance_obligation_release_mismatch', f"{i} TP-released != ending deferred")


def handle_fxrem(ctx, d):
    i = d['id']
    ref = (f(d, 'Reference') or '').strip()
    sa = amt_of(d, 'Source Amount'); bk = amt_of(d, 'Booked Amount'); cr = num(f(d, 'Closing Rate'))
    rm = amt_of(d, 'Remeasured Amount'); df = amt_of(d, 'Difference Amount')
    if sa is not None and cr is not None and rm is not None and abs(r2(sa * cr) - rm) > 0.011:
        ctx.flag('remeasurement_mismatch', f"{i} source*closing rate != remeasured")
    if bk is not None and rm is not None and df is not None and abs(abs(bk - rm) - df) > 0.011:
        ctx.flag('remeasurement_mismatch', f"{i} booked-remeasured != difference")
    rd = ctx.find(ref)
    refs = [i] + ([rd['id']] if rd else [])
    if bk is None or rm is None: return
    delta = r2(rm - bk)
    is_ap = rd is not None and rd['type'] in ('vendor_invoice', 'supplier_invoice')
    if not is_ap:
        if delta < 0: ctx.add(refs, 'Foreign Exchange Loss', 'Accounts Receivable', -delta)
        else: ctx.add(refs, 'Accounts Receivable', 'Foreign Exchange Gain', delta)
    else:
        if delta > 0: ctx.add(refs, 'Foreign Exchange Loss', 'Accounts Payable', delta)
        else: ctx.add(refs, 'Accounts Payable', 'Foreign Exchange Gain', -delta)


def check_transfers(ctx):
    for t in ctx.docs:
        if t['type'] != 'transfer_advice': continue
        a = amt_of(t, 'Amount')
        keys = [k for k in [(f(t, 'Reference') or '').strip(), (f(t, 'Transfer Number') or '').strip()] if k]
        for b in ctx.docs:
            if b['type'] != 'bank_statement': continue
            for it in b['items']:
                desc = it.get('Description') or ''
                if any(k in desc for k in keys):
                    v = num(it.get('Amount'))
                    if v is not None and a is not None and abs(abs(v) - a) > 0.011:
                        ctx.flag('transfer_mismatch', f"{t['id']} amount {a} != bank {v} in {b['id']}")


def check_bank(ctx, d):
    op = amt_of(d, 'Opening Balance'); cl = amt_of(d, 'Closing Balance')
    rows = [num(it.get('Amount')) for it in d['items'] if it.get('Amount')]
    if op is not None and cl is not None and abs(op + sum(x for x in rows if x is not None) - cl) > 0.011:
        ctx.flag('bank_closing_mismatch', f"{d['id']} opening+movements != closing")
    ctx.bank_docs = getattr(ctx, 'bank_docs', []) + [d]


def check_aging(ctx, d):
    tot = amt_of(d, 'Total Open')
    s = 0.0; any_ = False
    for it in d['items']:
        for k in ('Current', 'Past Due'):
            v = num(it.get(k))
            if v is not None: s += v; any_ = True
    if tot is not None and any_ and abs(s - tot) > 0.011:
        ctx.flag('statement_balance_mismatch', f"{d['id']} aging lines != total open")


def check_statement(ctx, d):
    cl = amt_of(d, 'Closing Balance')
    rows = [num(it.get('Amount')) for it in d['items'] if it.get('Amount')]
    if cl is not None and rows and abs(sum(x for x in rows if x is not None) - cl) > 0.011:
        ctx.flag('statement_balance_mismatch', f"{d['id']} open lines != closing")


def solve(rec):
    ctx = Ctx(rec)
    build(ctx)
    check_transfers(ctx)
    bs = build_bs(rec['opening_balance'], ctx.entries)
    return ctx, bs


ALLOWED_CODES = {
    'invoice_total_mismatch', 'bank_closing_mismatch', 'statement_balance_mismatch', 'payment_allocation_mismatch',
    'duplicate_reference_conflict', 'schedule_rollforward_mismatch', 'inventory_rollforward_mismatch', 'transfer_mismatch',
    'reclassification_support_mismatch', 'tax_total_mismatch', 'tax_rate_mismatch', 'input_tax_mismatch',
    'jurisdiction_tax_mismatch', 'tax_exemption_conflict', 'ssp_allocation_mismatch', 'performance_obligation_release_mismatch',
    'asset_disposal_mismatch', 'deferred_tax_rollforward_mismatch', 'lease_schedule_mismatch', 'lease_remeasurement_mismatch',
    'exchange_rate_mismatch', 'fx_settlement_mismatch', 'remeasurement_mismatch'}


def answer(rec):
    try:
        ctx, bs = solve(rec)
    except Exception as ex:  # never crash on one packet: fall back to opening balance
        ob = rec.get('opening_balance', {})
        bs = build_bs(ob, [])
        return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [],
                'entries': [], 'balance_sheet': bs}
    codes = []
    notes = []
    for c, n in ctx.issues:
        if c in ALLOWED_CODES and c not in codes:
            codes.append(c)
        notes.append(n)
    if codes:
        return {'has_inconsistency': True, 'inconsistency_codes': sorted(codes), 'inconsistency_notes': notes[:5],
                'entries': [], 'balance_sheet': {'assets': {}, 'liabilities': {}, 'equity': {}}}
    ents = [e for e in ctx.entries if e['debit_account'] != e['credit_account']]
    return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [],
            'entries': ents, 'balance_sheet': bs}


def main(argv):
    if len(argv) < 3:
        print('usage: python3 run.py <records.jsonl> <salida.json>')
        return 2
    out = {}
    with open(argv[1], encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec['record_id']] = answer(rec)
    with open(argv[2], 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
