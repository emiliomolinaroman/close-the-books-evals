#!/usr/bin/env python3
"""FinBalance packet closer. Usage: python3 run.py <records.jsonl> <salida.json>

Arquitectura: parser genérico del OCR (clave: valor y líneas '- A x | B y') -> índice de referencias ->
manejadores por tipo de documento que proponen asientos -> checks de consistencia -> balance por código.
Ninguna cifra fija: todo sale de los documentos del paquete.
"""
import json, os, re, sys, traceback
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

# ----------------------------------------------------------------- parsing
LINE_KEYS = ['Section', 'Account', 'Description', 'Quantity', 'Unit Cost', 'Unit Price', 'Amount', 'Reference',
             'Allocated Amount', 'Status', 'Date', 'Running Balance', 'Obligation', 'Ssp Amount', 'Invoice Line Amount',
             'Sku', 'System Qty', 'Counted Qty', 'Unit', 'Tenant', 'Customer', 'Current', 'Past Due', 'Document Type']


def unwrap(text):
    out = []
    prev_len = 0
    for raw in text.split('\n'):
        st = raw.strip()
        if out and prev_len >= 78 and st and not set(st) <= set('=-') and not st.startswith('- ') \
                and not re.match(r'^[A-Z][A-Za-z /()&]{0,40}:( |$)', st):
            out[-1] = out[-1] + raw
            prev_len = len(raw)
            continue
        out.append(raw)
        prev_len = len(raw)
    return out


def split_item(body):
    d = {}
    for part in body.split('|'):
        part = part.strip()
        best = None
        for k in sorted(LINE_KEYS, key=len, reverse=True):
            if part.startswith(k + ' ') or part == k:
                best = k
                break
        if best:
            d[best] = part[len(best):].strip()
        else:
            m = re.match(r'^(.*?)\s+([-$A-Z]{0,4}\s?-?[\d.,]+%?)$', part)
            if m:
                d[m.group(1)] = m.group(2)
            else:
                d.setdefault('_text', part)
    return d


def parse_doc(text):
    fields, lines, section = {}, [], None
    for raw in unwrap(text):
        s = raw.strip()
        if not s or set(s) <= set('=-'):
            continue
        m = re.match(r'^-\s+(.*)$', s)
        if m:
            d = split_item(m.group(1)) if '|' in m.group(1) or ' ' in m.group(1) else {'_text': m.group(1)}
            d['_section'] = section
            lines.append(d)
            continue
        m = re.match(r'^([A-Za-z][^:]{0,60}):\s*(.*)$', s)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            if v:
                fields.setdefault(k, v)
            else:
                section = k
            continue
        section = s
    return fields, lines


def money(x):
    """'$-24,012.07' 'EUR 5.817,25' 'GBP -6,044.13' '1,920.72' '18.00%' -> float."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    neg = '-' in s or (s.startswith('(') and s.endswith(')'))
    t = re.sub(r'[^\d.,]', '', s)
    if not t or not re.search(r'\d', t):
        return None
    if re.search(r',\d{1,2}$', t):
        t = t.replace('.', '').replace(',', '.')
    elif re.search(r'\.\d{1,2}$', t) or re.search(r'\.\d+$', t) and t.count('.') == 1 and ',' not in t:
        t = t.replace(',', '')
    else:
        t = t.replace(',', '').replace('.', '') if re.search(r'[.,]\d{3}$', t) else t.replace(',', '')
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def rate(x):
    v = money(x)
    if v is None:
        return None
    return v / 100.0 if '%' in str(x) else v


def r2(x):
    return round(x + 1e-9, 2) if x >= 0 else -round(-x + 1e-9, 2)


def eq(a, b, tol=0.011):
    return a is not None and b is not None and abs(a - b) <= tol


# ----------------------------------------------------------------- accounts
def is_pl(acc):
    a = acc.lower()
    return any(w in a for w in ('expense', 'revenue', 'gain', 'loss', 'cost of goods')) and 'unearned' not in a \
        and 'deferred revenue' not in a


def section_of(acc, opening):
    for sec in ('assets', 'liabilities', 'equity'):
        if acc in opening.get(sec, {}):
            return sec
    a = acc.lower()
    if any(w in a for w in ('payable', 'liability', 'unearned', 'accrued', 'deferred revenue', 'deposits payable')):
        return 'liabilities'
    if any(w in a for w in ("equity", 'capital', 'retained', 'drawings')):
        return 'equity'
    return 'assets'


class Ctx:
    def __init__(self, rec):
        self.rec = rec
        self.allowed = rec.get('allowed_accounts') or []
        self.ctx = rec.get('context') or {}
        self.func = self.ctx.get('functional_currency_code') or self.ctx.get('currency_code')
        self.regime = (self.ctx.get('tax_regime') or '').lower()
        self.docs = []
        for d in rec.get('documents', []):
            f, l = parse_doc(d.get('ocr_text') or '')
            self.docs.append({'id': d['doc_id'], 'type': d.get('doc_type', ''), 'date': d.get('date'), 'f': f, 'l': l,
                              'text': d.get('ocr_text') or ''})
        self.byid = {d['id']: d for d in self.docs}
        self.ref = defaultdict(list)  # reference string -> docs carrying it as their own number
        own_keys = ('Invoice Number', 'Roll Number', 'Notice Number', 'Receipt Number', 'Run Number', 'Loan Number',
                    'Batch ID', 'Report ID', 'Settlement ID', 'GRN Number', 'Delivery Number', 'Work Order Number',
                    'Transfer Number', 'Slip Number', 'Schedule ID', 'Memo ID', 'Memo Number', 'Agreement Number',
                    'Form Number', 'Rate Card ID', 'Certificate Number', 'Profile ID', 'Advice Number', 'Statement Number',
                    'Sheet ID', 'Note ID', 'Rollforward ID', 'Summary ID', 'Return ID', 'Report Number', 'Modification Number',
                    'Note Number', 'Copy ID', 'Shipment Ref', 'Job Code', 'Contract Ref', 'Remittance Number')
        for d in self.docs:
            for k in own_keys:
                v = d['f'].get(k)
                if v:
                    self.ref[v].append(d)
        self.entries = []
        self.notes = []
        self.codes = []

    def acc(self, *names):
        for n in names:
            if n and n in self.allowed:
                return n
        return names[0] if names else None

    def find(self, ref, types=None):
        for d in self.ref.get(ref, []):
            if types is None or d['type'] in types:
                return d
        return None

    def post(self, refs, dr, cr, amount):
        if amount is None:
            return
        amount = r2(amount)
        if abs(amount) < 0.005:
            return
        if amount < 0:
            dr, cr, amount = cr, dr, -amount
        seen = []
        for x in refs:
            if x and x not in seen:
                seen.append(x)
        self.entries.append({'doc_refs': seen, 'debit_account': dr, 'credit_account': cr, 'amount': amount})

    # tax helpers
    def tax_parts(self, f):
        parts = []
        for k, a in (('CGST Amount', 'CGST'), ('SGST Amount', 'SGST'), ('IGST Amount', 'IGST')):
            v = money(f.get(k))
            if v:
                parts.append((a, v))
        return parts

    def out_tax_accounts(self, f):
        tax = money(f.get('Tax Amount')) or 0.0
        parts = self.tax_parts(f)
        if parts:
            return [(self.acc(f'{a} Payable'), v) for a, v in parts]
        if tax:
            return [(self.acc('Sales Tax Payable', 'VAT Payable', 'GST Payable'), tax)]
        return []

    def in_tax_accounts(self, f, support_capitalize=False):
        tax = money(f.get('Tax Amount')) or 0.0
        parts = self.tax_parts(f)
        if parts:
            return [(self.acc(f'Input {a} Receivable'), v) for a, v in parts], 0.0
        if not tax:
            return [], 0.0
        label = (f.get('Tax Label') or '').lower()
        us = 'us sales' in label or (self.regime == 'us_sales_tax' and 'sales tax' in label)
        if us or support_capitalize:
            return [], tax  # embedded into cost
        return [(self.acc('Input Tax Receivable', 'VAT Receivable'), tax)], 0.0


# ----------------------------------------------------------------- posting rules
def withdrawn_refs(c):
    w = set()
    for d in c.docs:
        if d['type'] == 'cancellation_note':
            v = d['f'].get('Withdrawn Reference')
            if v:
                w.add(v)
    return w


def fx_functional(c, d):
    """Functional amount of a foreign-currency doc from an exchange_rate_notice referencing it."""
    num = d['f'].get('Invoice Number')
    for e in c.docs:
        if e['type'] == 'exchange_rate_notice' and e['f'].get('Reference') == num:
            return money(e['f'].get('Functional Amount')), e
    return None, None


def is_foreign(c, d):
    cur = d['f'].get('Currency')
    return bool(cur and c.func and cur.strip().upper() != c.func.upper())


def collected_in_bank(c, num):
    payers = ('payment_advice', 'insurer_remittance', 'copay_receipt', 'card_settlement_report')
    for d in c.docs:
        if d['type'] in payers and (num in d['f'].values() or any(num in l.values() for l in d['l'])):
            return False
    for d in c.docs:
        if d['type'] == 'bank_statement':
            for l in d['l']:
                desc = l.get('Description') or ''
                if re.search(r'\b' + re.escape(num) + r'\b', desc) and (money(l.get('Amount')) or 0) > 0:
                    return True
    return False


def revenue_account(c, kind='service'):
    if kind == 'sales':
        return c.acc('Sales Revenue', 'Service Revenue')
    if kind == 'rental':
        return c.acc('Rental Revenue', 'Service Revenue', 'Sales Revenue')
    return c.acc('Service Revenue', 'Sales Revenue')


def inv_account(c):
    return c.acc('Inventory', 'Finished Goods Inventory', 'Raw Materials Inventory')


def post_customer_invoices(c, used, withdrawn):
    deliveries = {d['f'].get('Shipment Ref'): d for d in c.docs if d['type'] == 'delivery_note'}
    fgts = {d['f'].get('Transfer Number'): d for d in c.docs if d['type'] == 'finished_goods_transfer_note'}
    work_orders = [d for d in c.docs if d['type'] == 'work_order']
    sofs = {d['f'].get('Form Number'): d for d in c.docs if d['type'] == 'subscription_order_form'}
    revrec_refs = {d['f'].get('Contract Reference') for d in c.docs if d['type'] == 'revenue_recognition_schedule'}
    certs = {d['f'].get('Certificate Number'): d for d in c.docs if d['type'] == 'tax_exemption_certificate'}
    profiles = [d for d in c.docs if d['type'] == 'customer_tax_profile']
    for d in c.docs:
        if d['type'] != 'customer_invoice':
            continue
        f = d['f']
        num = f.get('Invoice Number')
        if num in withdrawn:
            continue
        total = money(f.get('Total'))
        sub = money(f.get('Subtotal'))
        taxes = c.out_tax_accounts(f)
        net = sub if sub is not None else total - sum(v for _, v in taxes)
        refs = [d['id']]
        kind = 'service'
        cogs = None
        dl = deliveries.get(f.get('Shipment Ref')) if f.get('Shipment Ref') else None
        if dl:
            refs = [dl['id'], d['id']]
            kind = 'sales'
            cogs = (money(dl['f'].get('Cost Basis Amount')), inv_account(c), refs)
        fg = fgts.get(f.get('Contract Ref')) if f.get('Contract Ref') else None
        if fg:
            refs = [d['id'], fg['id']]
            kind = 'sales'
            cogs = (money(fg['f'].get('Transfer Value')), c.acc('Finished Goods Inventory', 'Inventory'), refs)
        for wo in work_orders:
            if wo['f'].get('Customer') == f.get('Customer') and eq(money(wo['f'].get('Approved Amount')), net):
                refs = [wo['id'], d['id']]
                break
        cert = certs.get(f.get('Exemption Certificate')) if f.get('Exemption Certificate') else None
        if cert:
            prof = [p['id'] for p in profiles if p['f'].get('Exemption Certificate') == cert['f'].get('Certificate Number')]
            refs = [cert['id']] + prof + [d['id']]
        if kind == 'service' and 'Service Revenue' not in c.allowed:
            kind = 'sales'
        credit = revenue_account(c, kind)
        sof = sofs.get(f.get('Contract Ref'))
        if (sof or num in revrec_refs) and 'Unearned Revenue' in c.allowed:
            credit = 'Unearned Revenue'
            if sof:
                refs = refs + [sof['id']]
        if is_foreign(c, d):
            fa, rn = fx_functional(c, d)
            if fa is None:
                c.notes.append(f'{d["id"]}: foreign currency without rate')
                continue
            c.post([d['id'], rn['id']], c.acc('Accounts Receivable'), credit, fa)
            used.add(d['id'])
            continue
        dr = c.acc('Accounts Receivable')
        if num and collected_in_bank(c, num):
            dr = c.acc('Cash')  # cobro anticipado visible en el extracto, sin aviso de pago
        c.post(refs, dr, credit, net)
        for a, v in taxes:
            c.post(refs, dr, a, v)
        if cogs and cogs[0]:
            c.post(cogs[2], c.acc('Cost of Goods Sold'), cogs[1], cogs[0])
        used.add(d['id'])


def post_purchases(c, withdrawn):
    grns = {d['f'].get('GRN Number'): d for d in c.docs if d['type'] == 'goods_receipt_note'}
    notices = [d for d in c.docs if d['type'] == 'tax_regime_notice']
    for d in c.docs:
        if d['type'] not in ('supplier_invoice', 'vendor_invoice', 'utilities_statement'):
            continue
        f = d['f']
        num = f.get('Invoice Number')
        if num in withdrawn:
            continue
        total = money(f.get('Total'))
        sub = money(f.get('Subtotal'))
        refs = [d['id']]
        if d['type'] == 'utilities_statement':
            dr = c.acc('Utilities Expense')
        elif d['type'] == 'vendor_invoice':
            dr = c.acc(f.get('Expense Label') or 'Office Supplies Expense')
        else:
            cat = f.get('Expense Category')
            if cat == 'Inventory' or not cat:
                dr = c.acc('Inventory', 'Raw Materials Inventory') if cat else c.acc('Raw Materials Inventory', 'Inventory')
            else:
                dr = c.acc(cat)
        g = grns.get(f.get('Goods Receipt Ref'))
        if g:
            refs = [g['id'], d['id']]
            dr = c.acc('Inventory', 'Raw Materials Inventory')
        capitalize = False
        tax = money(f.get('Tax Amount'))
        for n in notices:
            if tax and eq(money(n['f'].get('Jurisdiction Tax Amount')), tax):
                refs = [n['id'], d['id']]
                dr = c.acc('Inventory', 'Raw Materials Inventory')
                if 'capitaliz' in (n['f'].get('Treatment') or '').lower():
                    capitalize = True
        if is_foreign(c, d):
            fa, rn = fx_functional(c, d)
            if fa is None:
                c.notes.append(f'{d["id"]}: foreign bill without rate')
                continue
            c.post([d['id'], rn['id']], dr, c.acc('Accounts Payable'), fa)
            continue
        parts, embed = c.in_tax_accounts(f, capitalize)
        net = sub if sub is not None else (total or 0) - sum(v for _, v in parts) - embed
        c.post(refs, dr, c.acc('Accounts Payable'), net + embed)
        for a, v in parts:
            c.post(refs, a, c.acc('Accounts Payable'), v)


def post_payments(c, withdrawn):
    for d in c.docs:
        if d['type'] != 'payment_advice':
            continue
        f = d['f']
        amt = money(f.get('Amount'))
        pf = (f.get('Payment For') or '').lower()
        allocs = [l for l in d['l'] if 'Allocated Amount' in l]
        refs_n = [l.get('Reference') for l in allocs] if allocs else [f.get('Reference')]
        targets = [c.find(r) for r in refs_n]
        trefs = [t['id'] for t in targets if t]
        ttypes = {t['type'] for t in targets if t}
        customer = 'customer' in pf or 'receivable' in pf or ttypes & {'customer_invoice', 'rent_roll', 'patient_invoice'}
        supplier = 'supplier' in pf or 'payable' in pf or ttypes & {'supplier_invoice', 'vendor_invoice', 'utilities_statement'}
        if 'foreign' in pf:
            fa = money(f.get('Functional Amount'))  # booked functional amount per advice
            paid = amt
            booked = None
            for t in targets:
                if t:
                    booked, rn = fx_functional(c, t)
                    if rn:
                        trefs.append(rn['id'])
            if booked is None:
                booked = fa
            diff = (paid or 0) - (booked or 0)
            if customer and not supplier:
                c.post([d['id']] + trefs, c.acc('Cash'), c.acc('Accounts Receivable'), booked)
                if diff > 0:
                    c.post([d['id']] + trefs, c.acc('Cash'), c.acc('Foreign Exchange Gain'), diff)
                elif diff < 0:
                    c.post([d['id']] + trefs, c.acc('Foreign Exchange Loss'), c.acc('Accounts Receivable'), -diff)
            else:
                c.post([d['id']] + trefs, c.acc('Accounts Payable'), c.acc('Cash'), booked)
                if diff > 0:
                    c.post([d['id']] + trefs, c.acc('Foreign Exchange Loss'), c.acc('Cash'), diff)
                elif diff < 0:
                    c.post([d['id']] + trefs, c.acc('Accounts Payable'), c.acc('Foreign Exchange Gain'), -diff)
            continue
        if customer and not supplier:
            c.post([d['id']] + trefs, c.acc('Cash'), c.acc('Accounts Receivable'), amt)
        elif supplier:
            c.post([d['id']] + trefs, c.acc('Accounts Payable'), c.acc('Cash'), amt)
        else:
            c.notes.append(f'{d["id"]}: payment direction unknown')


def asset_account(c, name, tag=None):
    n = (name or '').lower()
    if tag and tag.startswith('OPEN-'):
        stem = tag[5:].lower()
        for a in c.allowed:
            if a.lower().startswith(stem) and not is_pl(a) and 'accumulated' not in a.lower():
                return a
    for a in c.allowed:
        if a.lower() == n:
            return a
    if 'fixture' in n and 'Store Fixtures' in c.allowed and 'Equipment' not in c.allowed:
        return 'Store Fixtures'
    if 'Store Fixtures' in c.allowed and 'fixture' in n:
        return 'Store Fixtures'
    if any(w in n for w in ('van', 'truck', 'vehicle')) and 'Vehicles' in c.allowed and 'Equipment' not in c.allowed:
        return 'Vehicles'
    if 'furniture' in n and 'Furniture' in c.allowed:
        return 'Furniture'
    return c.acc('Equipment', 'Store Fixtures', 'Vehicles', 'Furniture')


def post_others(c, withdrawn):
    docs = c.docs
    by_type = defaultdict(list)
    for d in docs:
        by_type[d['type']].append(d)
    batches = {d['f'].get('Batch ID'): d for d in by_type['production_batch_sheet']}
    asset_by_tag = {}
    for d in by_type['equipment_invoice']:
        asset_by_tag[d['f'].get('Asset Tag')] = asset_account(c, d['f'].get('Asset Name'))
    dep_tags = set()
    for d in docs:
        f, t, i = d['f'], d['type'], d['id']
        try:
            if t == 'patient_invoice':
                c.post([i], c.acc('Accounts Receivable'), revenue_account(c), money(f.get('Gross Charge')))
            elif t in ('insurer_remittance', 'copay_receipt'):
                ref = f.get('Claim Reference') or f.get('Reference Invoice')
                tg = c.find(ref)
                amt = money(f.get('Paid Amount')) if t == 'insurer_remittance' else money(f.get('Amount'))
                c.post([i] + ([tg['id']] if tg else []), c.acc('Cash'), c.acc('Accounts Receivable'), amt)
            elif t == 'rent_roll':
                c.post([i], c.acc('Accounts Receivable'), revenue_account(c, 'rental'), money(f.get('Total Rent')))
            elif t == 'payroll_summary':
                c.post([i], c.acc('Salaries Expense'), c.acc('Cash'), money(f.get('Gross Pay')))
                c.post([i], c.acc('Payroll Tax Expense'), c.acc('Cash'), money(f.get('Employer Tax')))
            elif t == 'loan_statement':
                c.post([i], c.acc('Cash'), c.acc('Loans Payable'), money(f.get('Draw Amount')))
                c.post([i], c.acc('Loans Payable'), c.acc('Cash'), money(f.get('Principal Paid')))
                c.post([i], c.acc('Interest Expense'), c.acc('Cash'), money(f.get('Interest Paid')))
            elif t == 'equipment_invoice':
                a = asset_account(c, f.get('Asset Name'))
                c.post([i], a, c.acc('Cash'), money(f.get('Paid Cash')))
                c.post([i], a, c.acc('Notes Payable'), money(f.get('Financed Amount')))
            elif t in ('depreciation_schedule', 'fixed_asset_rollforward'):
                key = (f.get('Asset Tag'), f.get('Current Period Charge') or f.get('Current Charge'))
                if key in dep_tags:
                    continue
                dep_tags.add(key)
                c.post([i], c.acc('Depreciation Expense'), c.acc('Accumulated Depreciation'),
                       money(f.get('Current Period Charge') or f.get('Current Charge')))
            elif t == 'expense_receipt':
                desc = d['l'][0].get('Description') if d['l'] else None
                a = desc if desc in c.allowed else c.acc('Travel Expense', 'Fuel Expense', 'Office Supplies Expense')
                c.post([i], a, c.acc('Cash'), money(f.get('Total')))
            elif t == 'rent_notice':
                c.post([i], c.acc('Prepaid Rent'), c.acc('Cash'), money(f.get('Total')))
            elif t == 'insurance_notice':
                c.post([i], c.acc('Prepaid Insurance'), c.acc('Cash'), money(f.get('Total Premium') or f.get('Total')))
            elif t == 'service_period_memo':
                amt = money(f.get('Recognized Amount'))
                tg = c.find(f.get('Reference'), ('rent_notice', 'insurance_notice'))
                if tg:
                    if tg['type'] == 'rent_notice':
                        c.post([tg['id'], i], c.acc('Rent Expense'), c.acc('Prepaid Rent'), amt)
                    else:
                        c.post([tg['id'], i], c.acc('Insurance Expense'), c.acc('Prepaid Insurance'), amt)
                else:
                    subj = ((f.get('Subject') or '') + ' ' + (f.get('Narrative') or '')).lower()
                    if 'rent' in subj and 'Prepaid Rent' in c.allowed and 'release' in subj:
                        c.post([i], c.acc('Rent Expense'), c.acc('Prepaid Rent'), amt)
                    elif 'insurance' in subj and 'release' in subj:
                        c.post([i], c.acc('Insurance Expense'), c.acc('Prepaid Insurance'), amt)
                    else:
                        exp = None
                        for a in c.allowed:
                            if a.endswith('Expense') and a[:-8].lower() in subj:
                                exp = a
                                break
                        c.post([i], exp or c.acc('Office Supplies Expense'), c.acc('Accrued Expenses'), amt)
            elif t == 'security_deposit_notice':
                amt = money(f.get('Amount'))
                if 'REF' in (f.get('Notice Number') or '').upper() or 'refund' in d['text'].lower():
                    orig = [x['id'] for x in by_type['security_deposit_notice'] if x is not d and
                            x['f'].get('Tenant') == f.get('Tenant') and 'REF' not in (x['f'].get('Notice Number') or '')]
                    c.post([i] + orig[:1], c.acc('Security Deposits Payable'), c.acc('Cash'), amt)
                else:
                    c.post([i], c.acc('Cash'), c.acc('Security Deposits Payable'), amt)
            elif t == 'transfer_advice':
                c.post([i], c.acc(f.get('To Account') or 'Reserve Cash'), c.acc(f.get('From Account') or 'Cash'),
                       money(f.get('Amount')))
            elif t == 'sales_summary':
                net = money(f.get('Net Sales'))
                tax = money(f.get('Tax Amount')) or 0.0
                cash = money(f.get('Cash Sales')) or 0.0
                card = money(f.get('Card Sales')) or 0.0
                gross = cash + card
                pos = [p for p in by_type['pos_batch_report'] if eq(money(p['f'].get('Batch Total')), card)]
                refs = [i] + [p['id'] for p in pos[:1]]
                rev = c.acc('Sales Revenue', 'Service Revenue')
                taxacc = c.acc('Sales Tax Payable')
                if gross:
                    cash_rev = r2(cash * net / gross)
                    card_rev = r2(net - cash_rev)
                    cash_tax = r2(cash - cash_rev)
                    card_tax = r2(tax - cash_tax)
                else:
                    cash_rev, card_rev, cash_tax, card_tax = 0, net, 0, tax
                c.post(refs, c.acc('Cash'), rev, cash_rev)
                c.post(refs, c.acc('Card Settlement Clearing'), rev, card_rev)
                c.post(refs, c.acc('Cost of Goods Sold'), inv_account(c), money(f.get('COGS Amount')))
                c.post(refs, c.acc('Cash'), taxacc, cash_tax)
                c.post(refs, c.acc('Card Settlement Clearing'), taxacc, card_tax)
            elif t == 'card_settlement_report':
                brefs = [l.get('_text') for l in d['l'] if l.get('_text')]
                pos = [p['id'] for p in by_type['pos_batch_report'] if p['f'].get('Batch ID') in brefs]
                c.post([i] + pos, c.acc('Cash'), c.acc('Card Settlement Clearing'), money(f.get('Net Deposit')))
                c.post([i] + pos, c.acc('Card Processing Fees', 'Bank Fees Expense', 'Merchant Fees Expense',
                                        'Maintenance Expense', 'Office Supplies Expense'),
                       c.acc('Card Settlement Clearing'), money(f.get('Fees')))
            elif t == 'return_note':
                c.post([i], c.acc('Sales Revenue', 'Service Revenue'), c.acc('Cash'), money(f.get('Amount')))
            elif t == 'inventory_adjustment_note':
                sh = c.find(f.get('Reference Sheet'), ('stock_count_sheet',))
                c.post(([sh['id']] if sh else []) + [i], c.acc('Inventory Shrinkage Expense'), inv_account(c),
                       money(f.get('Amount')))
            elif t == 'inventory_rollforward':
                sheets = by_type['stock_count_sheet']
                rfs = by_type['inventory_rollforward']
                k = rfs.index(d)
                adj_sheets = {x['f'].get('Reference Sheet') for x in by_type['inventory_adjustment_note']}
                free = [s for s in sheets if s['f'].get('Sheet ID') not in adj_sheets]
                refs = ([free[k]['id']] if k < len(free) else []) + [i]
                c.post(refs, c.acc('Inventory Shrinkage Expense'), inv_account(c), money(f.get('Write Down')))
            elif t == 'scrap_report':
                lot = (f.get('Batch Or Lot') or '').upper()
                a = c.acc('Finished Goods Inventory', 'Inventory') if 'FG' in lot else (
                    c.acc('Raw Materials Inventory', 'Inventory') if 'RM' in lot else inv_account(c))
                otb = [x['id'] for x in by_type['opening_trial_balance']] if 'OPEN' in lot else []
                c.post([i] + otb, c.acc('Inventory Shrinkage Expense'), a, money(f.get('Write Down')))
            elif t == 'material_requisition_slip':
                b = batches.get(f.get('Batch ID'))
                mat = f.get('Material')
                sup = [x['id'] for x in by_type['supplier_invoice'] if any(l.get('Description') == mat for l in x['l'])]
                c.post([i] + ([b['id']] if b else []) + sup[:1], c.acc('Work In Process'),
                       c.acc('Raw Materials Inventory'), money(f.get('Issue Value')))
            elif t == 'direct_labor_record':
                b = batches.get(f.get('Batch ID'))
                c.post([i] + ([b['id']] if b else []), c.acc('Work In Process'), c.acc('Cash'),
                       money(f.get('Labor Cash Paid') or f.get('Labor Value')))
            elif t == 'overhead_accrual_memo':
                b = batches.get(f.get('Batch ID'))
                c.post([i] + ([b['id']] if b else []), c.acc('Work In Process'), c.acc('Accrued Expenses'),
                       money(f.get('Accrued Overhead') or f.get('Overhead Value')))
            elif t == 'finished_goods_transfer_note':
                b = batches.get(f.get('Batch ID'))
                c.post([i] + ([b['id']] if b else []), c.acc('Finished Goods Inventory'), c.acc('Work In Process'),
                       money(f.get('Transfer Value')))
            elif t == 'credit_memo':
                inv = c.find(f.get('Reference'))
                reason = (f.get('Reason') or '').lower()
                if 'bad debt' in reason or 'writeoff' in reason or 'write-off' in reason:
                    ag = [x['id'] for x in by_type['ar_aging_summary']]
                    c.post(ag[:1] + [i] + ([inv['id']] if inv else []), c.acc('Bad Debt Expense'),
                           c.acc('Accounts Receivable'), money(f.get('Amount')))
                else:
                    c.post([i] + ([inv['id']] if inv else []), revenue_account(c), c.acc('Accounts Receivable'),
                           money(f.get('Amount')))
            elif t == 'reclassification_memo':
                orig = c.find(f.get('Original Reference'))
                c.post([i] + ([orig['id']] if orig else []), c.acc(f.get('To Account')), c.acc(f.get('From Account')),
                       money(f.get('Amount')))
            elif t == 'asset_disposal_notice':
                tag = f.get('Asset Tag')
                a = asset_by_tag.get(tag) or asset_account(c, f.get('Asset Name'), tag)
                sp = [x['id'] for x in by_type['sale_proceeds_advice'] if x['f'].get('Asset Tag') == tag]
                refs = [i] + sp
                proceeds = money(f.get('Proceeds Amount'))
                accdep = money(f.get('Accumulated Depreciation'))
                gl = money(f.get('Gain Loss Amount'))
                c.post(refs, c.acc('Cash'), a, proceeds)
                c.post(refs, c.acc('Accumulated Depreciation'), a, accdep)
                if 'loss' in (f.get('Gain Loss Type') or '').lower():
                    c.post(refs, c.acc('Loss on Disposal'), a, gl)
                else:
                    c.post(refs, a, c.acc('Gain on Disposal'), gl)
            elif t == 'lease_agreement':
                c.post([i], c.acc('Right-of-Use Asset'), c.acc('Lease Liability'),
                       money(f.get('Lease Liability Amount') or f.get('ROU Asset Amount')))
            elif t == 'lease_payment_notice':
                ag = c.find(f.get('Agreement Number'), ('lease_agreement',))
                sch = [x['id'] for x in by_type['lease_amortization_schedule']
                       if x['f'].get('Agreement Number') == f.get('Agreement Number') and
                       eq(money(x['f'].get('Payment Amount')), money(f.get('Payment Amount')))]
                refs = ([ag['id']] if ag else []) + sch[:1] + [i]
                c.post(refs, c.acc('Lease Liability'), c.acc('Cash'), money(f.get('Principal Amount')))
                c.post(refs, c.acc('Lease Interest Expense'), c.acc('Cash'), money(f.get('Interest Amount')))
            elif t == 'lease_amortization_schedule':
                ag = c.find(f.get('Agreement Number'), ('lease_agreement',))
                c.post(([ag['id']] if ag else []) + [i], c.acc('Lease Amortization Expense'), c.acc('Right-of-Use Asset'),
                       money(f.get('ROU Amortization Amount')))
            elif t == 'lease_modification_notice':
                ag = c.find(f.get('Agreement Number'), ('lease_agreement',))
                c.post([i] + ([ag['id']] if ag else []), c.acc('Right-of-Use Asset'), c.acc('Lease Liability'),
                       money(f.get('ROU Asset Adjustment Amount') or f.get('Liability Remeasurement Delta Amount')))
            elif t == 'deferred_tax_memo':
                tds = [x['id'] for x in by_type['tax_depreciation_schedule'] if x['f'].get('Asset Tag') == f.get('Asset Tag')]
                mv = money(f.get('Current Period Deferred Tax Movement') or f.get('Deferred Tax Expense Amount'))
                c.post([i] + tds, c.acc('Deferred Tax Expense'), c.acc('Deferred Tax Liability'), mv)
            elif t == 'fx_remeasurement_memo':
                tg = c.find(f.get('Reference'))
                booked = money(f.get('Booked Amount'))
                rem = money(f.get('Remeasured Amount'))
                diff = (rem or 0) - (booked or 0)
                refs = [i] + ([tg['id']] if tg else [])
                payable = tg and tg['type'] in ('supplier_invoice', 'vendor_invoice')
                if payable:
                    if diff > 0:
                        c.post(refs, c.acc('Foreign Exchange Loss'), c.acc('Accounts Payable'), diff)
                    else:
                        c.post(refs, c.acc('Accounts Payable'), c.acc('Foreign Exchange Gain'), -diff)
                else:
                    if diff > 0:
                        c.post(refs, c.acc('Accounts Receivable'), c.acc('Foreign Exchange Gain'), diff)
                    else:
                        c.post(refs, c.acc('Foreign Exchange Loss'), c.acc('Accounts Receivable'), -diff)
            elif t == 'revenue_recognition_schedule':
                c.post([i] + [x['id'] for x in c.ref.get(f.get('Contract Reference'), []) if x['type'] == 'customer_invoice'][:1],
                       c.acc('Unearned Revenue'), revenue_account(c), money(f.get('Released This Period')))
            elif t == 'performance_obligation_schedule':
                cref = f.get('Contract Reference')
                rel = money(f.get('Released This Period'))
                acc_m = [x for x in by_type['implementation_acceptance_memo'] if x['f'].get('Contract Reference') == cref]
                ssp = [x['id'] for x in by_type['ssp_rate_card'] if x['f'].get('Contract Reference') == cref]
                tp = money(f.get('Transaction Price') or f.get('Allocation Total'))
                tssp = money(f.get('Total SSP'))
                impl_ssp = None
                for l in d['l']:
                    if 'implement' in (l.get('Obligation') or '').lower():
                        impl_ssp = money(l.get('Ssp Amount'))
                impl = r2(tp * impl_ssp / tssp) if (acc_m and impl_ssp and tp and tssp) else 0.0
                if impl and impl <= rel + 0.01:
                    c.post([acc_m[0]['id'], i] + ssp, c.acc('Unearned Revenue'), revenue_account(c), impl)
                    c.post([i] + ssp, c.acc('Unearned Revenue'), revenue_account(c), rel - impl)
                else:
                    c.post([i] + ssp + [x['id'] for x in acc_m], c.acc('Unearned Revenue'), revenue_account(c), rel)
        except Exception as e:  # cada regla aislada
            c.notes.append(f'{i} {t}: {e}')


DATE_MDY = [False]


def to_date(x):
    from datetime import datetime
    if not x:
        return None
    fmts = ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%d.%m.%Y') if DATE_MDY[0] else \
        ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d.%m.%Y')
    for fmt in fmts:
        try:
            return datetime.strptime(str(x).strip()[:10], fmt).date()
        except ValueError:
            pass
    return None


# ----------------------------------------------------------------- consistency checks
def checks(c):
    """Return list of (code, note). Each check compares numbers printed on the documents themselves."""
    out = []

    def add(code, msg):
        if code not in [x[0] for x in out]:
            out.append((code, msg))

    for d in c.docs:
        f, t = d['f'], d['type']
        try:
            total, sub, tax = money(f.get('Total')), money(f.get('Subtotal')), money(f.get('Tax Amount'))
            if t in ('customer_invoice', 'supplier_invoice', 'vendor_invoice', 'utilities_statement'):
                amts = [money(l.get('Amount')) for l in d['l'] if l.get('Amount') not in (None, '')]
                amts = [a for a in amts if a is not None]
                base = sub if sub is not None else total
                if amts and len(amts) == len([l for l in d['l'] if 'Description' in l]) and base is not None \
                        and not eq(sum(amts), base, 0.015):
                    add('invoice_total_mismatch', f'{d["id"]} lines {sum(amts):.2f} vs {base:.2f}')
                if sub is not None and tax is not None and total is not None and not eq(sub + tax, total, 0.015):
                    add('tax_total_mismatch', f'{d["id"]} subtotal+tax != total')
                rt = rate(f.get('Tax Rate'))
                if sub is not None and tax is not None and rt is not None and abs(sub * rt - tax) > 0.0151:
                    add('tax_rate_mismatch', f'{d["id"]} {sub}*{rt} != {tax}')
                parts = c.tax_parts(f)
                if parts and tax is not None and not eq(sum(v for _, v in parts), tax, 0.015):
                    add('input_tax_mismatch' if t != 'customer_invoice' else 'tax_total_mismatch',
                        f'{d["id"]} GST components != tax')
                ex = f.get('Exemption Certificate')
                if ex and tax:
                    add('tax_exemption_conflict', f'{d["id"]} exempt but taxed')
            elif t == 'patient_invoice':
                g, pd_, idue = (money(f.get(k)) for k in ('Gross Charge', 'Patient Due', 'Insurer Due'))
                if None not in (g, pd_, idue) and not eq(pd_ + idue, g, 0.015):
                    add('invoice_total_mismatch', f'{d["id"]} patient+insurer due != gross')
            elif t == 'rent_roll':
                amts = [money(l.get('Amount')) for l in d['l'] if l.get('Amount')]
                tr = money(f.get('Total Rent'))
                if amts and tr is not None and None not in amts and not eq(sum(amts), tr, 0.015):
                    add('invoice_total_mismatch', f'{d["id"]} rent roll lines != total')
            elif t == 'bank_statement':
                op, cl = money(f.get('Opening Balance')), money(f.get('Closing Balance'))
                rows = [money(l.get('Amount')) for l in d['l'] if 'Amount' in l]
                if op is not None and cl is not None and all(r is not None for r in rows) and not eq(op + sum(rows), cl, 0.015):
                    add('bank_closing_mismatch', f'{d["id"]} opening+rows {op + sum(rows):.2f} != closing {cl:.2f}')
            elif t == 'vendor_statement':
                cl = money(f.get('Closing Balance'))
                rows = [money(l.get('Amount')) for l in d['l'] if 'Amount' in l]
                if cl is not None and rows and not eq(sum(r for r in rows if r is not None), cl, 0.015):
                    add('statement_balance_mismatch', f'{d["id"]} open lines != closing')
            elif t == 'payment_advice':
                allocs = [money(l.get('Allocated Amount')) for l in d['l'] if 'Allocated Amount' in l]
                amt = money(f.get('Amount'))
                if allocs and amt is not None and not eq(sum(a for a in allocs if a is not None), amt, 0.015):
                    add('payment_allocation_mismatch', f'{d["id"]} allocations != amount')
                if 'foreign' in (f.get('Payment For') or '').lower():
                    tg = c.find(f.get('Reference'))
                    booked = fx_functional(c, tg)[0] if tg else None
                    fa, diff = money(f.get('Functional Amount')), money(f.get('FX Difference'))
                    src, rt = money(f.get('Source Amount')), rate(f.get('Exchange Rate'))
                    bad = False
                    if src and rt and fa is not None and abs(src * rt - fa) > 0.015:
                        bad = True
                    if booked is not None and fa is not None and diff is not None and not eq(abs(fa - booked), abs(diff), 0.015):
                        bad = True
                    if bad:
                        add('fx_settlement_mismatch', f'{d["id"]} FX settlement does not reconcile')
            elif t in ('revenue_recognition_schedule',):
                o, a, r, e = (money(f.get(k)) for k in ('Opening Deferred', 'Added Deferred', 'Released This Period', 'Ending Deferred'))
                if None not in (o, a, r, e) and not eq(o + a - r, e, 0.015):
                    add('schedule_rollforward_mismatch', f'{d["id"]} rollforward')
            elif t == 'inventory_rollforward':
                o, a, u, w, e = (money(f.get(k)) for k in ('Opening Balance', 'Additions', 'Usage Or Sales', 'Write Down', 'Ending Balance'))
                if None not in (o, a, u, e) and not eq(o + a - u - (w or 0), e, 0.015):
                    add('inventory_rollforward_mismatch', f'{d["id"]} rollforward')
            elif t == 'transfer_advice':
                amt, ref = money(f.get('Amount')), f.get('Reference')
                for b in c.docs:
                    if b['type'] != 'bank_statement':
                        continue
                    for l in b['l']:
                        desc = l.get('Description') or ''
                        if ref and ref in desc and 'transfer' in desc.lower():
                            v = money(l.get('Amount'))
                            if v is not None and not eq(abs(v), amt, 0.015):
                                add('transfer_mismatch', f'{d["id"]} advice {amt} vs bank {v}')
            elif t == 'reclassification_memo':
                orig = c.find(f.get('Original Reference'))
                amt = money(f.get('Amount'))
                if orig is not None:
                    vals = [money(orig['f'].get('Total'))] + [money(l.get('Amount')) for l in orig['l']]
                    if not any(eq(v, amt, 0.015) for v in vals if v is not None):
                        add('reclassification_support_mismatch', f'{d["id"]} amount not in original support')
                elif f.get('Original Reference'):
                    add('reclassification_support_mismatch', f'{d["id"]} original missing')
            elif t == 'lease_amortization_schedule':
                o, p, it, pr, e = (money(f.get(k)) for k in ('Opening Liability Balance', 'Payment Amount', 'Interest Amount',
                                                            'Principal Amount', 'Ending Liability Balance'))
                if None not in (o, p, it, pr, e) and (not eq(it + pr, p, 0.015) or not eq(o - pr, e, 0.015)):
                    add('lease_schedule_mismatch', f'{d["id"]} lease schedule')
            elif t == 'lease_payment_notice':
                p, it, pr = (money(f.get(k)) for k in ('Payment Amount', 'Interest Amount', 'Principal Amount'))
                if None not in (p, it, pr) and not eq(it + pr, p, 0.015):
                    add('lease_schedule_mismatch', f'{d["id"]} lease payment split')
            elif t == 'lease_modification_notice':
                o, n, dl, ra = (money(f.get(k)) for k in ('Old Liability Balance', 'Remeasured Liability Balance',
                                                         'Liability Remeasurement Delta Amount', 'ROU Asset Adjustment Amount'))
                if None not in (o, n, dl) and (not eq(n - o, dl, 0.015) or (ra is not None and not eq(ra, dl, 0.015))):
                    add('lease_remeasurement_mismatch', f'{d["id"]} remeasurement')
            elif t == 'asset_disposal_notice':
                co, ad, nbv, pr, gl = (money(f.get(k)) for k in ('Original Cost', 'Accumulated Depreciation', 'Net Book Value',
                                                                'Proceeds Amount', 'Gain Loss Amount'))
                bad = None not in (co, ad, nbv) and not eq(co - ad, nbv, 0.015)
                if None not in (nbv, pr, gl) and not eq(abs(pr - nbv), abs(gl), 0.015):
                    bad = True
                for s in c.docs:
                    if s['type'] == 'sale_proceeds_advice' and s['f'].get('Asset Tag') == f.get('Asset Tag'):
                        if not eq(money(s['f'].get('Proceeds Amount')), pr, 0.015):
                            bad = True
                if bad:
                    add('asset_disposal_mismatch', f'{d["id"]} disposal')
            elif t == 'deferred_tax_memo':
                o, m, e = (money(f.get(k)) for k in ('Opening Deferred Tax Liability', 'Current Period Deferred Tax Movement',
                                                    'Deferred Tax Liability Ending'))
                bad = None not in (o, m, e) and not eq(o + m, e, 0.015)
                tds = [x for x in c.docs if x['type'] == 'tax_depreciation_schedule' and x['f'].get('Asset Tag') == f.get('Asset Tag')]
                if tds and m is not None:
                    exp = 0.0
                    for x in tds:
                        td, rt = money(x['f'].get('Temporary Difference Amount')), rate(x['f'].get('Tax Rate'))
                        if td is not None and rt is not None:
                            exp_one = td * rt
                            exp += exp_one
                    if not any(eq(x, m, 0.02) for x in [exp] + [money(x['f'].get('Temporary Difference Amount')) * rate(x['f'].get('Tax Rate'))
                                                         for x in tds if x['f'].get('Temporary Difference Amount') and x['f'].get('Tax Rate')]):
                        bad = True
                if bad:
                    add('deferred_tax_rollforward_mismatch', f'{d["id"]} deferred tax')
            elif t == 'exchange_rate_notice':
                s, rt, fa = money(f.get('Source Amount')), rate(f.get('Exchange Rate')), money(f.get('Functional Amount'))
                if None not in (s, rt, fa) and abs(s * rt - fa) > 0.015:
                    add('exchange_rate_mismatch', f'{d["id"]} rate')
                tg = c.find(f.get('Reference'))
                if tg and s is not None and not eq(money(tg['f'].get('Total')), s, 0.015):
                    add('exchange_rate_mismatch', f'{d["id"]} source amount vs document')
            elif t == 'fx_remeasurement_memo':
                s, rt, rm, bk, df = (money(f.get(k)) if k != 'Closing Rate' else rate(f.get(k))
                                     for k in ('Source Amount', 'Closing Rate', 'Remeasured Amount', 'Booked Amount', 'Difference Amount'))
                bad = None not in (s, rt, rm) and abs(s * rt - rm) > 0.015
                if None not in (rm, bk, df) and not eq(abs(rm - bk), abs(df), 0.015):
                    bad = True
                if bad:
                    add('remeasurement_mismatch', f'{d["id"]} remeasurement')
            elif t in ('ssp_rate_card', 'performance_obligation_schedule'):
                tssp = money(f.get('Total SSP'))
                ssps = [money(l.get('Ssp Amount')) for l in d['l'] if l.get('Ssp Amount')]
                bad = tssp is not None and ssps and not eq(sum(ssps), tssp, 0.015)
                if t == 'performance_obligation_schedule':
                    tp, at = money(f.get('Transaction Price')), money(f.get('Allocation Total'))
                    if tp is not None and at is not None and not eq(tp, at, 0.015):
                        bad = True
                if bad:
                    add('ssp_allocation_mismatch', f'{d["id"]} SSP allocation')
                if t == 'performance_obligation_schedule':
                    cref = f.get('Contract Reference')
                    tp = money(f.get('Transaction Price'))
                    rel, end = money(f.get('Released This Period')), money(f.get('Ending Deferred'))
                    if tp is not None and rel is not None and end is not None and not eq(tp - rel, end, 0.015):
                        add('performance_obligation_release_mismatch', f'{d["id"]} release vs ending')
                    impl_ssp = None
                    for l in d['l']:
                        if 'implement' in (l.get('Obligation') or '').lower():
                            impl_ssp = money(l.get('Ssp Amount'))
                    for m in c.docs:
                        if m['type'] == 'implementation_acceptance_memo' and m['f'].get('Contract Reference') == cref:
                            acc_amt = money(m['f'].get('Accepted Amount'))
                            if impl_ssp and tssp and tp and acc_amt is not None and abs(tp * impl_ssp / tssp - acc_amt) > 0.02:
                                add('performance_obligation_release_mismatch', f'{m["id"]} accepted amount vs allocation')
            elif t == 'tax_regime_notice':
                tr = (f.get('Treatment') or '').lower()
                same = f.get('Company Jurisdiction') == f.get('Counterparty Jurisdiction')
                ja = money(f.get('Jurisdiction Tax Amount'))
                for s in c.docs:
                    if s['type'] in ('supplier_invoice', 'vendor_invoice') and eq(money(s['f'].get('Tax Amount')), ja, 0.015):
                        parts = dict(c.tax_parts(s['f']))
                        if 'india' in tr or 'gst' in tr:
                            if same and ('IGST' in parts or 'same-state' not in tr):
                                add('jurisdiction_tax_mismatch', f'{d["id"]} jurisdiction')
                            if not same and ('CGST' in parts or 'different-state' not in tr):
                                add('jurisdiction_tax_mismatch', f'{d["id"]} jurisdiction')
            elif t == 'customer_tax_profile':
                same = (f.get('Same State') or '').lower() == 'true'
                for s in c.docs:
                    if s['type'] == 'customer_invoice' and s['f'].get('Customer') == f.get('Customer'):
                        parts = dict(c.tax_parts(s['f']))
                        if (same and 'IGST' in parts) or (not same and ('CGST' in parts or 'SGST' in parts)):
                            add('jurisdiction_tax_mismatch', f'{s["id"]} GST split vs profile')
                cj, kj = f.get('Customer Jurisdiction'), f.get('Company Jurisdiction')
                if cj and kj and (cj == kj) != same:
                    add('jurisdiction_tax_mismatch', f'{d["id"]} profile same-state flag')
            elif t == 'tax_exemption_certificate':
                st = (f.get('Exemption Status') or '').lower()
                ef, ex = to_date(f.get('Effective Date')), to_date(f.get('Expiration Date'))
                for s in c.docs:
                    if s['type'] == 'customer_invoice' and s['f'].get('Exemption Certificate') == f.get('Certificate Number'):
                        dt = to_date(s.get('date')) or to_date(s['f'].get('Date') or s['f'].get('Document Date'))
                        bad = 'valid' != st
                        if dt and ef and dt < ef or dt and ex and dt > ex:
                            bad = True
                        if f.get('Counterparty') and s['f'].get('Customer') and f.get('Counterparty') != s['f'].get('Customer'):
                            bad = True
                        if bad and not money(s['f'].get('Tax Amount')):
                            add('tax_exemption_conflict', f'{d["id"]} certificate not applicable to {s["id"]}')
        except Exception as e:
            c.notes.append(f'check {d["id"]}: {e}')
    # duplicates: same own reference with conflicting totals
    seen = {}
    for d in c.docs:
        if d['type'] in ('customer_invoice', 'supplier_invoice', 'vendor_invoice', 'secondary_copy'):
            ref = d['f'].get('Invoice Number') or d['f'].get('Source Reference')
            tot = money(d['f'].get('Total'))
            if ref in seen and tot is not None and seen[ref] is not None and not eq(seen[ref], tot, 0.015):
                add('duplicate_reference_conflict', f'{ref} totals {seen[ref]} vs {tot}')
            seen.setdefault(ref, tot)
    for d in c.docs:
        if d['type'] == 'secondary_copy':
            src = c.find(d['f'].get('Source Reference'))
            tot = money(d['f'].get('Total'))
            st = money(src['f'].get('Total') or src['f'].get('Gross Charge') or src['f'].get('Total Rent')
                       or src['f'].get('Amount')) if src else None
            if src and tot is not None and st is not None and not eq(st, tot, 0.015):
                add('duplicate_reference_conflict', f'{d["id"]} copy total vs {src["id"]}')
    return out


# ----------------------------------------------------------------- balance sheet
def balance(c):
    opening = c.rec.get('opening_balance') or {}
    bal = defaultdict(float)
    sec = {}
    for s in ('assets', 'liabilities', 'equity'):
        for a, v in (opening.get(s) or {}).items():
            sign = 1 if s == 'assets' else -1
            bal[a] += sign * float(v)
            sec[a] = s
    for e in c.entries:
        bal[e['debit_account']] += e['amount']
        bal[e['credit_account']] -= e['amount']
    ni = 0.0
    out = {'assets': {}, 'liabilities': {}, 'equity': {}}
    for a in list(bal):
        if is_pl(a) and a not in sec:
            ni += -bal[a]
            del bal[a]
    re_acc = 'Retained Earnings'
    bal[re_acc] = bal.get(re_acc, 0.0) - ni
    for a, v in bal.items():
        s = sec.get(a) or section_of(a, opening)
        val = r2(v if s == 'assets' else -v)
        if abs(val) < 0.005:
            continue
        out[s][a] = val
    return out


def solve(rec):
    c = Ctx(rec)
    DATE_MDY[0] = str(c.ctx.get('date_format') or '').upper().startswith('MM')
    found = checks(c)
    if found:
        code, msg = found[0]
        return {'has_inconsistency': True, 'inconsistency_codes': [code], 'inconsistency_notes': [msg],
                'entries': [], 'balance_sheet': {'assets': {}, 'liabilities': {}, 'equity': {}}}, c
    withdrawn = withdrawn_refs(c)
    used = set()
    post_customer_invoices(c, used, withdrawn)
    post_purchases(c, withdrawn)
    post_payments(c, withdrawn)
    post_others(c, withdrawn)
    return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [],
            'entries': c.entries, 'balance_sheet': balance(c)}, c


def main():
    src, dst = sys.argv[1], sys.argv[2]
    out = {}
    with open(src, encoding='utf-8-sig') as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            rid = rec.get('record_id')
            try:
                out[rid] = solve(rec)[0]
            except Exception:
                traceback.print_exc()
                out[rid] = {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [],
                            'entries': [], 'balance_sheet': {'assets': dict(rec.get('opening_balance', {}).get('assets', {})),
                                                             'liabilities': dict(rec.get('opening_balance', {}).get('liabilities', {})),
                                                             'equity': dict(rec.get('opening_balance', {}).get('equity', {}))}}
    d = os.path.dirname(os.path.abspath(dst))
    os.makedirs(d, exist_ok=True)
    tmp = dst + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, dst)


if __name__ == '__main__':
    main()
