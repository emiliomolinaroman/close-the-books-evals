#!/usr/bin/env python3
"""Reto F (FinBalance): paquete de documentos -> asientos + balance final, o inconsistencia.
Uso: python3 run.py <records.jsonl> <salida.json>
El código decide y calcula: todo importe sale del texto OCR del paquete; nada de ids ni importes fijos.
"""
import json, os, re, sys, traceback
from collections import defaultdict

# ----------------------------------------------------------------------------- parsing
ITEM_KEYS = ['Allocated Transaction Price', 'Invoice Line Amount', 'Released This Period', 'Release Pattern',
             'Running Balance', 'Allocated Amount', 'Extended Cost', 'Document Type', 'Unit Cost', 'Unit Price',
             'System Qty', 'Counted Qty', 'Ssp Amount', 'Past Due', 'Description', 'Obligation', 'Reference',
             'Customer', 'Quantity', 'Section', 'Account', 'Amount', 'Status', 'Tenant', 'Current', 'Date', 'Unit',
             'Sku']
ITEM_KEYS.sort(key=len, reverse=True)
KV_RE = re.compile(r"^([A-Z][A-Za-z0-9 /'&().-]{0,60}?):(?:\s+(.*))?$")


def parse_item(s):
    out = {}
    for fld in re.sub(r'\s+', ' ', s).strip().split(' | '):
        fld = fld.strip()
        for k in ITEM_KEYS:
            if fld == k or fld.startswith(k + ' '):
                out.setdefault(k.lower(), fld[len(k):].strip())
                break
        else:
            out.setdefault('_' + str(len(out)), fld)
    return out


def parse_doc(d):
    text = d.get('ocr_text') or ''
    lines = text.split('\n')
    kv, items = {}, []
    cur_item = None
    last_key = None
    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
        if not s:
            if cur_item is not None:
                items.append(parse_item(cur_item)); cur_item = None
            last_key = None; i += 1; continue
        if nxt and set(nxt) <= set('=-') and len(nxt) >= 3:  # section header
            if cur_item is not None:
                items.append(parse_item(cur_item)); cur_item = None
            last_key = None; i += 2; continue
        if re.match(r'^\s*-\s', raw):
            if cur_item is not None:
                items.append(parse_item(cur_item))
            cur_item = re.sub(r'^\s*-\s', '', raw); i += 1; continue
        if cur_item is not None:
            cur_item += ' ' + s; i += 1; continue
        m = KV_RE.match(s)
        if m:
            k = m.group(1).strip().lower(); v = (m.group(2) or '').strip()
            if k not in kv or not kv[k]:
                kv[k] = v
            last_key = k
        elif last_key:
            kv[last_key] = (kv[last_key] + ' ' + s).strip()
        i += 1
    if cur_item is not None:
        items.append(parse_item(cur_item))
    return {'id': d.get('doc_id'), 'type': d.get('doc_type') or '', 'date': d.get('date') or '', 'kv': kv,
            'items': items, 'text': text}


class Money:
    def __init__(self, dec='.'):
        self.dec = dec

    def __call__(self, s):
        if s is None:
            return None
        if isinstance(s, (int, float)):
            return float(s)
        s = str(s)
        m = re.search(r'-?\(?\s*-?[\d][\d.,\s]*', s)
        if not m:
            return None
        t = m.group(0)
        neg = '-' in t or '(' in t or re.search(r'-\s*[\$€£]', s) is not None
        t = re.sub(r'[^\d.,]', '', t).rstrip('.,')
        if not t:
            return None
        if self.dec == ',':
            t = t.replace('.', '').replace(',', '.')
        else:
            t = t.replace(',', '')
        try:
            v = float(t)
        except ValueError:
            return None
        return -v if neg else v


def detect_dec(rec):
    txt = ' '.join(d.get('ocr_text', '') for d in rec.get('documents', []))
    c = len(re.findall(r'\d\.\d{3},\d{2}(?!\d)', txt)) + len(re.findall(r'(?<![\d.,])\d{1,3},\d{2}(?![\d])', txt))
    p = len(re.findall(r'\d,\d{3}\.\d{2}(?!\d)', txt)) + len(re.findall(r'(?<![\d.,])\d{1,3}\.\d{2}(?![\d])', txt))
    return ',' if c > p else '.'


def r2(x):
    return round(x + 0.0, 2)


def eq(a, b, tol=0.011):
    return a is not None and b is not None and abs(a - b) <= tol


def pct(s):
    if s is None:
        return None
    m = re.search(r'(-?\d+(?:[.,]\d+)?)\s*%', str(s))
    if m:
        return float(m.group(1).replace(',', '.')) / 100.0
    m = re.search(r'-?\d+(?:\.\d+)?', str(s))
    if m:
        v = float(m.group(0))
        return v / 100.0 if v > 1 else v
    return None


# ----------------------------------------------------------------------------- accounts
PL_WORDS = ('Revenue', 'Expense', 'Cost of Goods Sold', 'Gain', 'Loss', 'Income', 'Fees', 'Shrinkage', 'Returns')


def is_pl(acc):
    if acc in ('Unearned Revenue', 'Deferred Revenue') or 'Accrued' in acc or 'Prepaid' in acc or 'Payable' in acc or 'Receivable' in acc or 'Liability' in acc:
        return False
    return any(w in acc for w in PL_WORDS)


def section_of(acc, opening):
    for sec in ('assets', 'liabilities', 'equity'):
        if acc in (opening.get(sec) or {}):
            return sec
    if any(w in acc for w in ('Payable', 'Accrued', 'Liabilit', 'Unearned', 'Deferred Revenue', 'Deposits Payable',
                              'Customer Deposits')):
        return 'liabilities'
    if 'Deferred Tax' in acc and 'Asset' not in acc:
        return 'liabilities'
    if any(w in acc for w in ('Capital', 'Equity', 'Retained', 'Drawings', 'Dividend')):
        return 'equity'
    return 'assets'


# ----------------------------------------------------------------------------- engine
CODES_DESC = {
    "invoice_total_mismatch": "Invoice total does not match the visible line items.",
    "bank_closing_mismatch": "Bank statement closing balance does not reconcile with the listed movements.",
    "statement_balance_mismatch": "Statement closing balance does not reconcile with the listed open lines.",
    "payment_allocation_mismatch": "Payment advice amount does not reconcile with the listed invoice allocations.",
    "duplicate_reference_conflict": "Two documents show the same reference with conflicting totals or status.",
    "schedule_rollforward_mismatch": "Schedule opening, additions, and releases do not roll forward to the stated ending balance.",
    "inventory_rollforward_mismatch": "Inventory rollforward does not reconcile from opening through ending balance.",
    "transfer_mismatch": "Inter-bank transfer support does not reconcile between the advice and bank evidence.",
    "reclassification_support_mismatch": "Correction memo details do not reconcile with the linked original posting support.",
    "tax_total_mismatch": "Subtotal, indirect tax, and total do not reconcile on the document.",
    "tax_rate_mismatch": "Shown indirect tax amount does not reconcile with the shown tax rate and basis.",
    "input_tax_mismatch": "Recoverable input tax fields do not reconcile with the underlying bill amounts.",
    "jurisdiction_tax_mismatch": "Jurisdiction-specific tax treatment does not reconcile with the applicable support documents.",
    "tax_exemption_conflict": "Tax exemption certificate evidence conflicts with the invoice tax treatment.",
    "ssp_allocation_mismatch": "ASC 606 allocation does not reconcile transaction price to standalone selling prices.",
    "performance_obligation_release_mismatch": "Performance obligation release evidence does not reconcile to the recognition schedule.",
    "asset_disposal_mismatch": "Fixed asset disposal support does not reconcile cost, accumulated depreciation, NBV, proceeds, and gain or loss.",
    "deferred_tax_rollforward_mismatch": "Deferred tax rollforward does not reconcile the opening liability, current movement, and ending liability.",
    "lease_schedule_mismatch": "Lease amortization schedule does not reconcile payment, interest, principal, and ending liability.",
    "lease_remeasurement_mismatch": "Lease modification support does not reconcile liability remeasurement and equal ROU asset adjustment.",
    "exchange_rate_mismatch": "Exchange-rate support does not reconcile the foreign amount into the stated functional amount.",
    "fx_settlement_mismatch": "Foreign-currency settlement support does not reconcile booked amount, paid amount, and FX difference.",
    "remeasurement_mismatch": "Closing-rate remeasurement does not reconcile the open foreign balance to the stated functional amount.",
}

REF_KEYS = ('invoice number', 'roll number', 'notice number', 'statement number', 'receipt number', 'agreement number',
            'transfer number', 'delivery number', 'form number', 'work order number', 'run number', 'report id',
            'batch id', 'slip number', 'grn number', 'memo id', 'schedule id', 'sheet id', 'note id', 'advice number',
            'remittance number', 'loan number', 'settlement id', 'return id', 'memo number', 'copy id',
            'rollforward id', 'summary id', 'profile id', 'certificate number', 'rate card id', 'modification number',
            'shipment ref')


class Packet:
    def __init__(self, rec):
        self.rec = rec
        self.m = Money(detect_dec(rec))
        self.docs = [parse_doc(d) for d in rec.get('documents', [])]
        self.byid = {d['id']: d for d in self.docs}
        self.allowed = list(rec.get('allowed_accounts') or [])
        self.aset = set(self.allowed)
        self.ctx = rec.get('context') or {}
        self.regime = (self.ctx.get('tax_regime') or 'none').lower()
        self.opening = rec.get('opening_balance') or {}
        self.entries = []
        self.codes = []
        self.used = set()
        self.ref_index = defaultdict(list)
        for d in self.docs:
            for k in REF_KEYS:
                v = d['kv'].get(k)
                if v:
                    self.ref_index[v.strip()].append(d['id'])

    # helpers
    def g(self, d, *keys):
        for k in keys:
            v = d['kv'].get(k)
            if v not in (None, ''):
                return v
        return None

    def amt(self, d, *keys):
        v = self.g(d, *keys)
        return self.m(v) if v is not None else None

    def acc(self, *cands, default=None):
        for c in cands:
            if c and c in self.aset:
                return c
        return default if default is not None else (cands[0] if cands else None)

    def post(self, refs, dr, cr, amount):
        if amount is None:
            return
        amount = r2(amount)
        if abs(amount) < 0.005:
            return
        if amount < 0:
            dr, cr, amount = cr, dr, -amount
        refs = [r for i, r in enumerate(refs) if r and r not in refs[:i]]
        self.entries.append({'doc_refs': refs, 'debit_account': dr, 'credit_account': cr, 'amount': amount})

    def find(self, ref, types=None):
        out = []
        for did in self.ref_index.get((ref or '').strip(), []):
            d = self.byid[did]
            if types is None or d['type'] in types:
                out.append(d)
        return out

    def docs_of(self, *types):
        return [d for d in self.docs if d['type'] in types]

    # ------------------------------------------------------------------ tax helpers
    def regime_notice(self, d):
        tax = self.amt(d, 'tax amount')
        ns = self.docs_of('tax_regime_notice')
        for n in ns:
            if tax is not None and eq(self.amt(n, 'jurisdiction tax amount'), tax):
                return n
        return None

    def tax_accounts(self, side, d=None, company_state=None, cp_state=None):
        """side='out' (sales) or 'in' (purchases). Returns list of (account, share)"""
        regime = self.regime
        n = self.regime_notice(d) if d else None
        if n:
            regime = (self.g(n, 'tax regime') or regime).lower()
            company_state = self.g(n, 'company jurisdiction') or company_state
            cp_state = self.g(n, 'counterparty jurisdiction') or cp_state
            tr = (self.g(n, 'treatment') or '').lower()
            if 'igst' in tr and 'cgst' not in tr:
                cp_state = (company_state or '') + '_other'
        if regime == 'india_gst':
            same = True
            if company_state and cp_state:
                same = company_state.strip().lower() == cp_state.strip().lower()
            if same:
                if side == 'out':
                    return [('CGST Payable', .5), ('SGST Payable', .5)]
                return [('Input CGST Receivable', .5), ('Input SGST Receivable', .5)]
            return [('IGST Payable', 1.0)] if side == 'out' else [('Input IGST Receivable', 1.0)]
        if side == 'out':
            label = (self.g(d, 'tax label') if d else None) or self.ctx.get('tax_label') or ''
            cands = []
            if label:
                cands.append(label + ' Payable')
            cands += ['Sales Tax Payable', 'VAT Payable', 'GST Payable', 'Output Tax Payable']
            return [(self.acc(*cands), 1.0)]
        return [(self.acc('Input Tax Receivable', 'Input VAT Receivable', 'Input GST Receivable', 'VAT Receivable'), 1.0)]

    def split_tax(self, tax, accts, base=None, rate=None):
        if len(accts) == 1:
            return [(accts[0][0], tax)]
        from decimal import Decimal, ROUND_HALF_EVEN
        first = float((Decimal(str(r2(tax))) / 2).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN))
        return [(accts[0][0], first), (accts[1][0], r2(tax - first))]

    def jurisdiction(self, inv):
        """Find a tax regime notice / customer profile relevant to this doc."""
        comp = cp = None
        for d in self.docs_of('tax_regime_notice', 'customer_tax_profile'):
            comp = self.g(d, 'company jurisdiction') or comp
            cpj = self.g(d, 'counterparty jurisdiction', 'customer jurisdiction')
            name = self.g(d, 'customer', 'counterparty')
            invname = self.g(inv, 'customer', 'supplier', 'vendor')
            if cpj and (not name or not invname or name == invname):
                cp = cpj
        return comp, cp

    # ------------------------------------------------------------------ posting rules
    def revenue_account(self, goods=False):
        ind = (self.rec.get('industry') or '')
        if goods or ind in ('retail', 'wholesale_distribution', 'manufacturing'):
            order = ['Sales Revenue', 'Service Revenue']
        elif ind == 'property_management':
            order = ['Rental Revenue', 'Service Revenue', 'Sales Revenue']
        elif ind == 'subscription_saas':
            order = ['Subscription Revenue', 'Service Revenue', 'Sales Revenue']
        else:
            order = ['Service Revenue', 'Sales Revenue']
        for a in order:
            if a in self.aset:
                return a
        for a in self.allowed:
            if 'Revenue' in a and a not in ('Unearned Revenue', 'Deferred Revenue'):
                return a
        return order[0]

    def inventory_account(self):
        return self.acc('Inventory', 'Merchandise Inventory', 'Raw Materials Inventory')

    def withdrawn_refs(self):
        out = set()
        for d in self.docs_of('cancellation_note'):
            w = self.g(d, 'withdrawn reference')
            if w:
                out.add(w.strip())
        return out

    def asset_account_for(self, tag=None, name=None):
        if tag and tag.upper().startswith('OPEN-'):
            code = tag.upper()[5:]
            for a in (self.opening.get('assets') or {}):
                if a.upper().startswith(code[:3]) and 'Accumulated' not in a:
                    return a
        nm = (name or '').lower()
        for kw, a in (('vehicle', 'Vehicles'), ('van', 'Vehicles'), ('truck', 'Vehicles'), ('furniture', 'Furniture'),
                      ('fixture', 'Store Fixtures'), ('computer', 'Computer Equipment')):
            if kw in nm and a in self.aset:
                return a
        return self.acc('Equipment', 'Store Fixtures', 'Furniture', 'Vehicles')

    def fx_rate_for(self, ref):
        for d in self.docs_of('exchange_rate_notice'):
            if (self.g(d, 'reference') or '').strip() == (ref or '').strip():
                return d
        return None

    def build(self):
        withdrawn = self.withdrawn_refs()
        P = self.post
        handled = set()
        seen_numbers = {}
        types_skip = {'opening_trial_balance', 'secondary_copy', 'memo', 'bank_statement', 'vendor_statement',
                      'cancellation_note', 'customer_tax_profile', 'tax_exemption_certificate', 'ssp_rate_card',
                      'renewal_notice'}
        for d in sorted(self.docs, key=lambda x: x['id']):
            t = d['type']
            num = self.g(d, 'invoice number')
            if num and num.strip() in withdrawn:
                continue
            if num and t in ('customer_invoice', 'vendor_invoice', 'supplier_invoice', 'utilities_statement',
                             'patient_invoice'):
                if num in seen_numbers:
                    continue  # duplicate copy of the same reference
                seen_numbers[num] = d['id']
            try:
                fn = getattr(self, 'do_' + t, None)
                if fn and t not in types_skip:
                    fn(d)
            except Exception:
                traceback.print_exc(file=sys.stderr)

    # sales -----------------------------------------------------------------
    def do_customer_invoice(self, d):
        P = self.post
        total = self.amt(d, 'total')
        sub = self.amt(d, 'subtotal')
        tax = self.amt(d, 'tax amount') or 0.0
        if sub is None:
            sub = (total or 0) - tax
        refs = [d['id']]
        goods = False
        cogs = []
        ship = self.g(d, 'shipment ref')
        if ship:
            for dn in self.docs_of('delivery_note'):
                if (self.g(dn, 'shipment ref') or '').strip() == ship.strip():
                    refs = [dn['id'], d['id']]
                    goods = True
                    cost = self.amt(dn, 'cost basis amount')
                    cogs.append((cost, self.inventory_account(), [dn['id'], d['id']]))
        cref = self.g(d, 'contract ref')
        unearned = False
        if cref:
            for x in self.find(cref):
                if x['type'] == 'finished_goods_transfer_note':
                    goods = True
                    refs = [d['id'], x['id']]
                    cogs.append((self.amt(x, 'transfer value'), self.acc('Finished Goods Inventory'), refs))
                elif x['type'] == 'work_order':
                    refs = [x['id'], d['id']]
        if not goods:
            cust = self.g(d, 'customer')
            for w in self.docs_of('work_order'):
                if self.g(w, 'customer') == cust and eq(self.amt(w, 'approved amount'), sub):
                    refs = [w['id'], d['id']]
                    break
        for x in self.docs_of('revenue_recognition_schedule'):
            if num_eq(self.g(x, 'contract reference'), self.g(d, 'invoice number')):
                unearned = True
        for x in self.docs_of('performance_obligation_schedule'):
            if num_eq(self.g(x, 'contract reference'), cref):
                unearned = True
        exempt = False
        cert = self.g(d, 'exemption certificate')
        if cert:
            for c in self.find(cert, ('tax_exemption_certificate',)):
                if 'valid' in (self.g(c, 'exemption status') or '').lower() and \
                        'invalid' not in (self.g(c, 'exemption status') or '').lower():
                    exempt = True
                    refs = [c['id']] + [p['id'] for p in self.docs_of('customer_tax_profile')
                                        if (self.g(p, 'exemption certificate') or '') == cert] + refs
        fxd = self.fx_rate_for(self.g(d, 'invoice number'))
        conv = 1.0
        if fxd:
            fa, sa = self.amt(fxd, 'functional amount'), self.amt(fxd, 'source amount')
            refs = refs + [fxd['id']]
            if fa and sa:
                conv = fa / sa
                if eq(sa, total or sub):
                    total = fa
                    conv = 1.0000001
        ar_acc = self.acc('Accounts Receivable')
        if self.advance_collected(d):
            ar_acc = self.acc('Cash')
            unearned = True
        rev_acc = self.acc('Unearned Revenue', 'Deferred Revenue') if unearned else self.revenue_account(goods)
        if conv == 1.0000001:
            P(refs, ar_acc, rev_acc, total)
        elif conv != 1.0:
            P(refs, ar_acc, rev_acc, (total or sub) * conv)
        else:
            P(refs, ar_acc, rev_acc, sub)
            if tax and not exempt:
                comp, cp = self.jurisdiction(d)
                for a, v in self.split_tax(tax, self.tax_accounts('out', d, comp, cp), sub, pct(self.g(d, 'tax rate'))):
                    P(refs, ar_acc, a, v)
        for cost, inv, rf in cogs:
            P(rf, self.acc('Cost of Goods Sold'), inv, cost)

    def advance_collected(self, d):
        num = (self.g(d, 'invoice number') or '').strip()
        if not num:
            return False
        for p in self.docs_of('payment_advice', 'copay_receipt', 'insurer_remittance'):
            if num in p['text']:
                return False
        for b in self.docs_of('bank_statement'):
            for it in b['items']:
                desc = (it.get('description') or '').lower()
                if num.lower() in desc.split() and ('advance' in desc or 'deposit' in desc or 'prepay' in desc):
                    return True
        return False

    def do_patient_invoice(self, d):
        P = self.post
        P([d['id']], self.acc('Accounts Receivable'), self.revenue_account(), self.amt(d, 'gross charge', 'total'))

    def do_rent_roll(self, d):
        self.post([d['id']], self.acc('Accounts Receivable'), self.acc('Rental Revenue', default=self.revenue_account()),
                  self.amt(d, 'total rent', 'total'))

    def do_copay_receipt(self, d):
        refs = [d['id']] + [x['id'] for x in self.find(self.g(d, 'reference invoice') or '')]
        self.post(refs, self.acc('Cash'), self.acc('Accounts Receivable'), self.amt(d, 'amount'))

    def do_insurer_remittance(self, d):
        refs = [d['id']] + [x['id'] for x in self.find(self.g(d, 'claim reference') or '')]
        self.post(refs, self.acc('Cash'), self.acc('Accounts Receivable'), self.amt(d, 'paid amount', 'amount'))

    def do_sales_summary(self, d):
        net = self.amt(d, 'net sales')
        tax = self.amt(d, 'tax amount') or 0.0
        cash = self.amt(d, 'cash sales') or 0.0
        card = self.amt(d, 'card sales') or 0.0
        cogs = self.amt(d, 'cogs amount')
        refs = [d['id']] + [x['id'] for x in self.docs_of('pos_batch_report')
                            if eq(self.amt(x, 'batch total'), card)]
        gross = cash + card
        clr = self.acc('Card Settlement Clearing')
        rev = self.revenue_account(True)
        taxacc = self.tax_accounts('out', d)[0][0]
        if gross and net is not None:
            rc = r2(net * cash / gross)
            rk = r2(net - rc)
            if cash:
                self.post(refs, self.acc('Cash'), rev, rc)
            if card:
                self.post(refs, clr, rev, rk)
            if tax:
                self.post(refs, self.acc('Cash'), taxacc, r2(cash - rc))
                self.post(refs, clr, taxacc, r2(card - rk))
        self.post(refs, self.acc('Cost of Goods Sold'), self.inventory_account(), cogs)

    def do_card_settlement_report(self, d):
        refs = [d['id']]
        for it in d['items']:
            for v in it.values():
                refs += [x['id'] for x in self.find(v.strip(), ('pos_batch_report',))]
        clr = self.acc('Card Settlement Clearing')
        self.post(refs, self.acc('Cash'), clr, self.amt(d, 'net deposit'))
        fee_acc = self.acc('Card Processing Fees', 'Merchant Fees Expense', 'Bank Fees Expense', 'Bank Charges',
                           'Maintenance Expense', 'Office Supplies Expense')
        self.post(refs, fee_acc, clr, self.amt(d, 'fees', 'fee amount'))

    def do_return_note(self, d):
        self.post([d['id']], self.revenue_account(True), self.acc('Cash'), self.amt(d, 'amount'))

    def do_work_order(self, d):
        pass  # support for the linked invoice

    def do_delivery_note(self, d):
        pass  # posted with the linked invoice

    # purchases ----------------------------------------------------------------
    def purchase(self, d, debit_acc, refs=None):
        refs = refs or [d['id']]
        total = self.amt(d, 'total')
        sub = self.amt(d, 'subtotal')
        tax = self.amt(d, 'tax amount') or 0.0
        if sub is None:
            sub = (total or 0) - tax
        ap = self.acc('Accounts Payable')
        fxd = self.fx_rate_for(self.g(d, 'invoice number'))
        if fxd and eq(self.amt(fxd, 'source amount'), total if total is not None else sub):
            self.post(refs + [fxd['id']], debit_acc, ap, self.amt(fxd, 'functional amount'))
            return
        n = self.regime_notice(d) if tax else None
        eff = ((self.g(n, 'tax regime') or '') if n else self.regime).lower()
        treat = ((self.g(n, 'treatment') or '') if n else '').lower()
        if tax and (eff == 'us_sales_tax' or 'capitaliz' in treat or 'embedded' in treat) and 'recoverable' not in treat:
            self.post(refs, debit_acc, ap, sub + tax)
            return
        self.post(refs, debit_acc, ap, sub)
        if tax:
            comp, cp = self.jurisdiction(d)
            for a, v in self.split_tax(tax, self.tax_accounts('in', d, comp, cp), sub, pct(self.g(d, 'tax rate'))):
                self.post(refs, a, ap, v)

    def expense_label(self, d, default):
        lab = self.g(d, 'expense label', 'expense category', 'expense account', 'account')
        if lab and lab in self.aset:
            return lab
        return self.acc(*default) if isinstance(default, (list, tuple)) else default

    def do_vendor_invoice(self, d):
        self.purchase(d, self.expense_label(d, ['Office Supplies Expense', 'Maintenance Expense']))

    def do_utilities_statement(self, d):
        self.purchase(d, self.acc('Utilities Expense'))

    def do_supplier_invoice(self, d):
        grn = self.g(d, 'goods receipt ref')
        refs = [d['id']]
        if grn:
            refs = [x['id'] for x in self.find(grn, ('goods_receipt_note',))] + [d['id']]
            acc = self.inventory_account()
        else:
            lab = self.g(d, 'expense label', 'expense category')
            if lab and lab in self.aset:
                acc = lab
            else:
                acc = self.acc('Raw Materials Inventory', 'Inventory')
        n = self.regime_notice(d)
        if n:
            refs = [n['id']] + refs
        self.purchase(d, acc, refs)

    def do_expense_receipt(self, d):
        acc = None
        for it in d['items']:
            desc = it.get('description', '')
            if desc in self.aset:
                acc = desc; break
        if acc is None:
            acc = self.expense_label(d, ['Travel Expense', 'Office Supplies Expense'])
        self.post([d['id']], acc, self.acc('Cash'), self.amt(d, 'total'))

    def do_payroll_summary(self, d):
        self.post([d['id']], self.acc('Salaries Expense', 'Wages Expense'), self.acc('Cash'), self.amt(d, 'gross pay'))
        self.post([d['id']], self.acc('Payroll Tax Expense'), self.acc('Cash'), self.amt(d, 'employer tax'))

    # settlements -----------------------------------------------------------
    def do_payment_advice(self, d):
        pf = (self.g(d, 'payment for') or '').lower()
        amount = self.amt(d, 'amount')
        if self.g(d, 'source amount') and self.g(d, 'exchange rate'):
            ref = self.g(d, 'reference') or ''
            fxd = self.fx_rate_for(ref)
            targets = [x for x in self.find(ref) if x['id'] != d['id']]
            booked = self.amt(fxd, 'functional amount') if fxd else self.amt(d, 'functional amount')
            refs = [d['id']] + [x['id'] for x in targets] + ([fxd['id']] if fxd else [])
            payable = 'payable' in pf or 'supplier' in pf or any(x['type'] in ('vendor_invoice', 'supplier_invoice')
                                                                 for x in targets)
            gain, loss = self.acc('Foreign Exchange Gain'), self.acc('Foreign Exchange Loss')
            if payable:
                self.post(refs, self.acc('Accounts Payable'), self.acc('Cash'), booked)
                diff = r2(amount - booked)
                if diff > 0:
                    self.post(refs, loss, self.acc('Cash'), diff)
                elif diff < 0:
                    self.post(refs, self.acc('Cash'), gain, -diff)
            else:
                self.post(refs, self.acc('Cash'), self.acc('Accounts Receivable'), amount)
                diff = r2(booked - amount)
                if diff > 0:
                    self.post(refs, loss, self.acc('Accounts Receivable'), diff)
                elif diff < 0:
                    self.post(refs, self.acc('Accounts Receivable'), gain, -diff)
            return
        allocs = [(it.get('reference'), self.m(it.get('allocated amount'))) for it in d['items']
                  if it.get('allocated amount')]
        if not allocs:
            allocs = [(self.g(d, 'reference'), amount)]
        for ref, a in allocs:
            targets = [x for x in self.find(ref or '') if x['id'] != d['id']]
            ttypes = {x['type'] for x in targets}
            supplier = 'supplier' in pf or 'vendor' in pf or ttypes & {'vendor_invoice', 'supplier_invoice',
                                                                     'utilities_statement'}
            refs = [d['id']] + [x['id'] for x in targets]
            if supplier and 'customer' not in pf:
                self.post(refs, self.acc('Accounts Payable'), self.acc('Cash'), a)
            else:
                self.post(refs, self.acc('Cash'), self.acc('Accounts Receivable'), a)

    def do_loan_statement(self, d):
        L = self.acc('Loans Payable', 'Notes Payable')
        self.post([d['id']], self.acc('Cash'), L, self.amt(d, 'draw amount'))
        self.post([d['id']], L, self.acc('Cash'), self.amt(d, 'principal paid'))
        self.post([d['id']], self.acc('Interest Expense'), self.acc('Cash'), self.amt(d, 'interest paid'))

    def do_security_deposit_notice(self, d):
        txt = d['text'].lower()
        L = self.acc('Security Deposits Payable')
        if 'refund' in txt:
            m = re.search(r'deposit\s+([A-Z]+-\d+)', d['text'])
            refs = [d['id']] + ([x['id'] for x in self.find(m.group(1))] if m else [])
            self.post(refs, L, self.acc('Cash'), self.amt(d, 'amount'))
        else:
            self.post([d['id']], self.acc('Cash'), L, self.amt(d, 'amount'))

    def do_transfer_advice(self, d):
        fa = self.g(d, 'from account'); ta = self.g(d, 'to account')
        self.post([d['id']], self.acc(ta) if ta else self.acc('Reserve Cash'), self.acc(fa) if fa else 'Cash',
                  self.amt(d, 'amount'))

    # fixed assets ------------------------------------------------------------
    def do_equipment_invoice(self, d):
        acc = self.asset_account_for(self.g(d, 'asset tag'), self.g(d, 'asset name'))
        paid = self.amt(d, 'paid cash')
        fin = self.amt(d, 'financed amount')
        if paid is None and fin is None:
            self.post([d['id']], acc, self.acc('Accounts Payable'), self.amt(d, 'total'))
            return
        self.post([d['id']], acc, self.acc('Cash'), paid)
        self.post([d['id']], acc, self.acc('Notes Payable', 'Loans Payable'), fin)

    def do_depreciation_schedule(self, d):
        self.post([d['id']], self.acc('Depreciation Expense'), self.acc('Accumulated Depreciation'),
                  self.amt(d, 'current period charge', 'current charge'))

    do_fixed_asset_rollforward = do_depreciation_schedule

    def do_asset_disposal_notice(self, d):
        tag = self.g(d, 'asset tag')
        refs = [d['id']] + [x['id'] for x in self.docs_of('sale_proceeds_advice')
                            if (self.g(x, 'asset tag') or '') == (tag or '')]
        acc = self.asset_account_for(tag, self.g(d, 'asset name'))
        cost = self.amt(d, 'original cost')
        ad = self.amt(d, 'accumulated depreciation') or 0.0
        proceeds = self.amt(d, 'proceeds amount') or 0.0
        gl = self.amt(d, 'gain loss amount')
        typ = (self.g(d, 'gain loss type') or '').lower()
        self.post(refs, self.acc('Cash'), acc, proceeds)
        self.post(refs, self.acc('Accumulated Depreciation'), acc, ad)
        if gl:
            if 'loss' in typ:
                self.post(refs, self.acc('Loss on Disposal', 'Loss on Asset Disposal'), acc, abs(gl))
            else:
                self.post(refs, acc, self.acc('Gain on Disposal', 'Gain on Asset Disposal'), abs(gl))

    # prepaid / accruals --------------------------------------------------------
    def prepaid(self, d, prepaid_acc, exp_acc):
        self.post([d['id']], prepaid_acc, self.acc('Cash'), self.amt(d, 'total premium', 'total'))
        num = self.g(d, 'notice number')
        for m in self.docs_of('service_period_memo'):
            if num and num_eq(self.g(m, 'reference'), num):
                self.post([d['id'], m['id']], exp_acc, prepaid_acc, self.amt(m, 'recognized amount'))
                self.used.add(m['id'])

    def do_insurance_notice(self, d):
        self.prepaid(d, self.acc('Prepaid Insurance'), self.acc('Insurance Expense'))

    def do_rent_notice(self, d):
        self.prepaid(d, self.acc('Prepaid Rent'), self.acc('Rent Expense'))

    def do_service_period_memo(self, d):
        if d['id'] in self.used:
            return
        ref = self.g(d, 'reference') or ''
        if self.find(ref, ('insurance_notice', 'rent_notice')):
            return
        narr = (self.g(d, 'narrative', 'details') or '') + ' ' + (self.g(d, 'subject') or '')
        amt = self.amt(d, 'recognized amount', 'amount')
        low = narr.lower()
        # explicit account names in the narrative
        exp = None
        for a in sorted(self.allowed, key=len, reverse=True):
            if is_pl(a) and a.lower() in low:
                exp = a; break
        if exp is None:
            for a in self.allowed:
                if a.endswith(' Expense'):
                    w = a[:-8].lower()
                    if w and re.search(r'\b' + re.escape(w) + r'\b', low):
                        exp = a; break
        if 'unearned' in low or 'deferred revenue' in low or 'revenue' in low and 'release' in low:
            self.post([d['id']], self.acc('Unearned Revenue', 'Deferred Revenue'), self.revenue_account(), amt)
            return
        if exp is None:
            exp = self.acc('Office Supplies Expense')
        if 'prepaid' in low:
            pre = self.acc('Prepaid Insurance' if 'insur' in low else 'Prepaid Rent')
            self.post([d['id']], exp, pre, amt)
        else:
            self.post([d['id']], exp, self.acc('Accrued Expenses'), amt)

    # inventory / manufacturing --------------------------------------------------
    def do_stock_count_sheet(self, d):
        sid = self.g(d, 'sheet id')
        notes = [x for x in self.docs_of('inventory_adjustment_note')
                 if (self.g(x, 'reference sheet') or '') == (sid or '')]
        if notes:
            a = self.amt(notes[0], 'amount')
            refs = [d['id'], notes[0]['id']]
        else:
            a = 0.0
            for it in d['items']:
                try:
                    a += (float(it.get('system qty', 0)) - float(it.get('counted qty', 0))) * (self.m(it.get('unit cost')) or 0)
                except ValueError:
                    pass
            refs = [d['id']]
            rf = [x for x in self.docs_of('inventory_rollforward') if eq(self.amt(x, 'write down'), a)]
            if rf:
                refs.append(rf[0]['id'])
        self.post(refs, self.acc('Inventory Shrinkage Expense'), self.inventory_account(), a)

    def do_inventory_rollforward(self, d):
        wd = self.amt(d, 'write down')
        for sc in self.docs_of('stock_count_sheet'):
            if self.docs_of('inventory_adjustment_note'):
                continue
            a = 0.0
            for it in sc['items']:
                try:
                    a += (float(it.get('system qty', 0)) - float(it.get('counted qty', 0))) * (self.m(it.get('unit cost')) or 0)
                except ValueError:
                    pass
            if eq(a, wd):
                return
        self.post([d['id']], self.acc('Inventory Shrinkage Expense'), self.inventory_account(),
                  self.amt(d, 'write down'))

    def do_scrap_report(self, d):
        lot = (self.g(d, 'batch or lot') or '').upper()
        inv = self.acc('Finished Goods Inventory') if 'FG' in lot or 'Finished Goods Inventory' in self.aset else \
            self.inventory_account()
        refs = [d['id']] + [x['id'] for x in self.docs_of('opening_trial_balance')]
        self.post(refs, self.acc('Inventory Shrinkage Expense'), inv, self.amt(d, 'write down', 'amount'))

    def batch_docs(self, bid, types=('production_batch_sheet',)):
        return [x for x in self.docs if x['type'] in types and (self.g(x, 'batch id') or '') == (bid or '')]

    def do_material_requisition_slip(self, d):
        b = self.batch_docs(self.g(d, 'batch id'))
        mat = (self.g(d, 'material') or '').lower()
        sup = [x['id'] for x in sorted(self.docs_of('supplier_invoice'), key=lambda z: z['id'])
               if any(mat and mat == (it.get('description') or '').lower() for it in x['items'])]
        self.post([d['id']] + [x['id'] for x in b] + sup[:1], self.acc('Work In Process'),
                  self.acc('Raw Materials Inventory'), self.amt(d, 'issue value'))

    def do_direct_labor_record(self, d):
        b = self.batch_docs(self.g(d, 'batch id'))
        self.post([d['id']] + [x['id'] for x in b], self.acc('Work In Process'), self.acc('Cash'),
                  self.amt(d, 'labor cash paid', 'labor value'))

    def do_overhead_accrual_memo(self, d):
        b = self.batch_docs(self.g(d, 'batch id'))
        self.post([d['id']] + [x['id'] for x in b], self.acc('Work In Process'), self.acc('Accrued Expenses'),
                  self.amt(d, 'accrued overhead', 'overhead value'))

    def do_finished_goods_transfer_note(self, d):
        b = self.batch_docs(self.g(d, 'batch id'))
        self.post([d['id']] + [x['id'] for x in b], self.acc('Finished Goods Inventory'), self.acc('Work In Process'),
                  self.amt(d, 'transfer value'))

    def do_ar_aging_summary(self, d):
        cms = self.docs_of('credit_memo')
        for cm in cms:
            reason = (self.g(cm, 'reason') or '').lower()
            if 'bad debt' in reason or 'write' in reason:
                ref = self.g(cm, 'reference')
                inv = [x['id'] for x in self.find(ref or '', ('customer_invoice', 'patient_invoice'))]
                self.post([d['id'], cm['id']] + inv, self.acc('Bad Debt Expense'), self.acc('Accounts Receivable'),
                          self.amt(cm, 'amount'))
                self.used.add(cm['id'])

    def do_credit_memo(self, d):
        if d['id'] in self.used:
            return
        reason = (self.g(d, 'reason') or '').lower()
        ref = self.g(d, 'reference')
        inv = [x['id'] for x in self.find(ref or '')]
        if 'bad debt' in reason or 'write' in reason:
            if not self.docs_of('ar_aging_summary'):
                self.post([d['id']] + inv, self.acc('Bad Debt Expense'), self.acc('Accounts Receivable'),
                          self.amt(d, 'amount'))
            return
        self.post([d['id']] + inv, self.revenue_account(), self.acc('Accounts Receivable'), self.amt(d, 'amount'))

    # leases -------------------------------------------------------------------
    def do_lease_agreement(self, d):
        self.post([d['id']], self.acc('Right-of-Use Asset'), self.acc('Lease Liability'),
                  self.amt(d, 'lease liability amount', 'rou asset amount'))
        ag = self.g(d, 'agreement number')
        scheds = [x for x in self.docs_of('lease_amortization_schedule') if self.g(x, 'agreement number') == ag]
        pays = [x for x in self.docs_of('lease_payment_notice') if self.g(x, 'agreement number') == ag]
        for p in pays:
            ms = [s for s in scheds if eq(self.amt(s, 'payment amount'), self.amt(p, 'payment amount'))] or scheds
            refs = [d['id']] + [s['id'] for s in ms[:1]] + [p['id']]
            self.post(refs, self.acc('Lease Liability'), self.acc('Cash'), self.amt(p, 'principal amount'))
            self.post(refs, self.acc('Lease Interest Expense', 'Interest Expense'), self.acc('Cash'),
                      self.amt(p, 'interest amount'))
        for s in scheds:
            self.post([d['id'], s['id']], self.acc('Lease Amortization Expense', 'Amortization Expense'),
                      self.acc('Right-of-Use Asset'), self.amt(s, 'rou amortization amount'))

    def do_lease_modification_notice(self, d):
        ag = self.g(d, 'agreement number')
        refs = [d['id']] + [x['id'] for x in self.docs_of('lease_agreement') if self.g(x, 'agreement number') == ag]
        delta = self.amt(d, 'liability remeasurement delta amount', 'rou asset adjustment amount')
        self.post(refs, self.acc('Right-of-Use Asset'), self.acc('Lease Liability'), delta)

    def do_fx_remeasurement_memo(self, d):
        ref = self.g(d, 'reference') or ''
        targets = [x for x in self.find(ref) if x['id'] != d['id']]
        refs = [d['id']] + [x['id'] for x in targets]
        bk, rm = self.amt(d, 'booked amount'), self.amt(d, 'remeasured amount')
        if bk is None or rm is None:
            return
        payable = any(x['type'] in ('vendor_invoice', 'supplier_invoice') for x in targets)
        gain, loss = self.acc('Foreign Exchange Gain'), self.acc('Foreign Exchange Loss')
        diff = r2(rm - bk)
        if payable:
            ap = self.acc('Accounts Payable')
            self.post(refs, loss, ap, diff) if diff > 0 else self.post(refs, ap, gain, -diff)
        else:
            ar = self.acc('Accounts Receivable')
            self.post(refs, ar, gain, diff) if diff > 0 else self.post(refs, loss, ar, -diff)

    def do_performance_obligation_schedule(self, d):
        cref = self.g(d, 'contract reference') or ''
        inv = [x['id'] for x in self.docs_of('customer_invoice') if num_eq(self.g(x, 'contract ref'), cref)]
        rev = self.revenue_account()
        for it in d['items']:
            rel = self.m(it.get('released this period'))
            ob = (it.get('obligation') or '').lower()
            refs = [d['id']]
            for a in self.docs_of('implementation_acceptance_memo'):
                if num_eq(self.g(a, 'contract reference'), cref) and \
                        (self.g(a, 'accepted obligation') or '').lower() == ob:
                    refs = [a['id'], d['id']]
            self.post(refs + inv, self.acc('Unearned Revenue', 'Deferred Revenue'), rev, rel)

    # deferred tax -------------------------------------------------------------
    def do_deferred_tax_memo(self, d):
        tag = self.g(d, 'asset tag')
        refs = [d['id']] + [x['id'] for x in self.docs_of('tax_depreciation_schedule') if self.g(x, 'asset tag') == tag]
        self.post(refs, self.acc('Deferred Tax Expense', 'Income Tax Expense'), self.acc('Deferred Tax Liability'),
                  self.amt(d, 'current period deferred tax movement', 'deferred tax expense amount'))

    # revenue schedules ----------------------------------------------------------
    def do_revenue_recognition_schedule(self, d):
        ref = self.g(d, 'contract reference')
        refs = [d['id']] + [x['id'] for x in self.find(ref or '')]
        self.post(refs, self.acc('Unearned Revenue', 'Deferred Revenue'), self.revenue_account(),
                  self.amt(d, 'released this period'))

    def do_reclassification_memo(self, d):
        fa, ta = self.g(d, 'from account'), self.g(d, 'to account')
        ref = self.g(d, 'original reference')
        refs = [d['id']] + [x['id'] for x in self.find(ref or '')]
        if fa and ta:
            self.post(refs, self.acc(ta), self.acc(fa), self.amt(d, 'amount'))


def norm_date(s):
    if not s:
        return None
    s = s.strip()
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return s[:10]
    m = re.match(r'(\d{2})[/.-](\d{2})[/.-](\d{4})', s)
    if m:
        return '%s-%s-%s' % (m.group(3), m.group(2), m.group(1))
    return None


def num_eq(a, b):
    return bool(a) and bool(b) and a.strip() == b.strip()


# ----------------------------------------------------------------------------- consistency checks
def checks(pk):
    """Arithmetic self-consistency of each document. Returns set of codes."""
    codes = set()
    g, a, m = pk.g, pk.amt, pk.m
    withdrawn = pk.withdrawn_refs()

    def add(c):
        codes.add(c)

    for d in pk.docs:
        t = d['type']
        try:
            if t == 'bank_statement':
                op, cl = a(d, 'opening balance'), a(d, 'closing balance')
                rows = [m(it.get('amount')) for it in d['items'] if it.get('amount')]
                if op is not None and cl is not None and not eq(op + sum(rows), cl, 0.015):
                    add('bank_closing_mismatch')
            elif t in ('customer_invoice', 'vendor_invoice', 'supplier_invoice', 'utilities_statement'):
                if (g(d, 'invoice number') or '').strip() in withdrawn:
                    continue
                tot, sub, tax = a(d, 'total'), a(d, 'subtotal'), a(d, 'tax amount')
                rate = pct(g(d, 'tax rate'))
                lines = [m(it.get('amount')) for it in d['items'] if it.get('amount')]
                base = sub if sub is not None else (tot - (tax or 0) if tot is not None else None)
                if lines and base is not None and not eq(sum(lines), base, 0.015):
                    add('invoice_total_mismatch')
                if sub is not None and tax is not None and tot is not None and not eq(sub + tax, tot, 0.015):
                    add('tax_total_mismatch')
                if sub is not None and tax is not None and rate is not None and rate > 0 and \
                        not eq(r2(sub * rate), tax, 0.015):
                    add('tax_rate_mismatch')
            elif t == 'vendor_statement':
                cl = a(d, 'closing balance')
                rows = [m(it.get('amount')) for it in d['items'] if it.get('amount')]
                if cl is not None and rows and not eq(sum(rows), cl, 0.015):
                    add('statement_balance_mismatch')
            elif t == 'payment_advice':
                amt = a(d, 'amount')
                sa, rt, fa, fd = a(d, 'source amount'), a(d, 'exchange rate'), a(d, 'functional amount'), a(d, 'fx difference')
                if sa is not None and rt:
                    fxd = pk.fx_rate_for(g(d, 'reference') or '')
                    booked = a(fxd, 'functional amount') if fxd else None
                    bad = False
                    if amt is not None and not eq(r2(sa * rt), amt, 0.015):
                        bad = True
                    if fa is not None and amt is not None and not eq(fa, amt, 0.015):
                        bad = True
                    if booked is not None and fd is not None and amt is not None and not eq(abs(booked - amt), abs(fd), 0.015):
                        bad = True
                    if bad:
                        add('fx_settlement_mismatch')
                al = [m(it.get('allocated amount')) for it in d['items'] if it.get('allocated amount')]
                if al and amt is not None and not eq(sum(al), amt, 0.015):
                    add('payment_allocation_mismatch')
            elif t == 'revenue_recognition_schedule':
                o, ad, rl, e = (a(d, 'opening deferred'), a(d, 'added deferred') or 0.0, a(d, 'released this period'),
                                a(d, 'ending deferred'))
                if None not in (o, rl, e) and not eq(o + ad - rl, e, 0.015):
                    add('schedule_rollforward_mismatch')
            elif t == 'inventory_rollforward':
                o, ad, u, w, e = (a(d, 'opening balance'), a(d, 'additions') or 0.0, a(d, 'usage or sales') or 0.0,
                                  a(d, 'write down') or 0.0, a(d, 'ending balance'))
                if o is not None and e is not None and not eq(o + ad - u - w, e, 0.015):
                    add('inventory_rollforward_mismatch')
            elif t == 'lease_amortization_schedule':
                o, p, i, pr, e = (a(d, 'opening liability balance'), a(d, 'payment amount'), a(d, 'interest amount'),
                                  a(d, 'principal amount'), a(d, 'ending liability balance'))
                if None not in (p, i, pr) and not eq(i + pr, p, 0.015):
                    add('lease_schedule_mismatch')
                if None not in (o, pr, e) and not eq(o - pr, e, 0.015):
                    add('lease_schedule_mismatch')
            elif t == 'lease_payment_notice':
                p, i, pr = a(d, 'payment amount'), a(d, 'interest amount'), a(d, 'principal amount')
                if None not in (p, i, pr) and not eq(i + pr, p, 0.015):
                    add('lease_schedule_mismatch')
            elif t == 'lease_modification_notice':
                o, n, dl, ra = (a(d, 'old liability balance'), a(d, 'remeasured liability balance'),
                                a(d, 'liability remeasurement delta amount'), a(d, 'rou asset adjustment amount'))
                if None not in (o, n, dl) and not eq(n - o, dl, 0.015):
                    add('lease_remeasurement_mismatch')
                if None not in (dl, ra) and not eq(dl, ra, 0.015):
                    add('lease_remeasurement_mismatch')
            elif t == 'asset_disposal_notice':
                c, ad, nbv, pr, gl = (a(d, 'original cost'), a(d, 'accumulated depreciation'), a(d, 'net book value'),
                                      a(d, 'proceeds amount'), a(d, 'gain loss amount'))
                typ = (g(d, 'gain loss type') or '').lower()
                if None not in (c, ad, nbv) and not eq(c - ad, nbv, 0.015):
                    add('asset_disposal_mismatch')
                if None not in (nbv, pr, gl):
                    sg = -1 if 'loss' in typ else 1
                    if not eq(pr - nbv, sg * abs(gl), 0.015):
                        add('asset_disposal_mismatch')
                for s in pk.docs_of('sale_proceeds_advice'):
                    if g(s, 'asset tag') == g(d, 'asset tag') and pr is not None and not eq(a(s, 'proceeds amount'), pr, 0.015):
                        add('asset_disposal_mismatch')
            elif t == 'deferred_tax_memo':
                o, mv, e = (a(d, 'opening deferred tax liability') or 0.0, a(d, 'current period deferred tax movement'),
                            a(d, 'deferred tax liability ending'))
                if None not in (mv, e) and not eq(o + mv, e, 0.015):
                    add('deferred_tax_rollforward_mismatch')
                cands = [s for s in pk.docs_of('tax_depreciation_schedule') if g(s, 'asset tag') == g(d, 'asset tag')]
                okany = not cands
                for s in cands:
                    td, rt = a(s, 'temporary difference amount'), pct(g(s, 'tax rate'))
                    bd, tx = a(s, 'book depreciation amount'), a(s, 'tax depreciation amount')
                    good = True
                    if None not in (bd, tx, td) and not eq(tx - bd, td, 0.015):
                        good = False
                    if None not in (td, rt, mv) and not eq(td * rt, mv, 0.011):
                        good = False
                    okany = okany or good
                if not okany:
                    add('deferred_tax_rollforward_mismatch')
            elif t == 'exchange_rate_notice':
                sa, rt, fa = a(d, 'source amount'), a(d, 'exchange rate'), a(d, 'functional amount')
                if None not in (sa, rt, fa) and not eq(r2(sa * rt), fa, 0.015):
                    add('exchange_rate_mismatch')
            elif t == 'fx_remeasurement_memo':
                sa, bk, rt, rm, df = (a(d, 'source amount'), a(d, 'booked amount'), a(d, 'closing rate'),
                                      a(d, 'remeasured amount'), a(d, 'difference amount'))
                if None not in (sa, rt, rm) and not eq(r2(sa * rt), rm, 0.015):
                    add('remeasurement_mismatch')
                if None not in (bk, rm, df) and not eq(abs(bk - rm), abs(df), 0.015):
                    add('remeasurement_mismatch')
            elif t == 'transfer_advice':
                amt = a(d, 'amount')
                ref = g(d, 'reference') or ''
                for b in pk.docs_of('bank_statement'):
                    for it in b['items']:
                        if ref and ref in (it.get('description') or ''):
                            v = m(it.get('amount'))
                            if v is not None and amt is not None and not eq(abs(v), amt, 0.015):
                                add('transfer_mismatch')
            elif t == 'reclassification_memo':
                ref = g(d, 'original reference')
                amt = a(d, 'amount')
                fa = g(d, 'from account')
                origs = [o for o in pk.find(ref or '') if o['id'] != d['id']]
                for o in origs:
                    tot = a(o, 'total', 'amount')
                    if tot is not None and amt is not None and not eq(amt, tot, 0.015):
                        add('reclassification_support_mismatch')
                if ref and not origs:
                    add('reclassification_support_mismatch')
            elif t == 'performance_obligation_schedule':
                tp, ssp_t, at, rel, end = (a(d, 'transaction price'), a(d, 'total ssp'), a(d, 'allocation total'),
                                           a(d, 'released this period'), a(d, 'ending deferred'))
                obs = d['items']
                alloc = [m(o.get('allocated transaction price')) for o in obs if o.get('allocated transaction price')]
                ssps = [m(o.get('ssp amount')) for o in obs if o.get('ssp amount')]
                rels = [m(o.get('released this period')) for o in obs if o.get('released this period')]
                if tp is not None and alloc and not eq(sum(alloc), tp, 0.03):
                    add('ssp_allocation_mismatch')
                if tp and ssp_t and alloc and ssps and len(alloc) == len(ssps):
                    for al, sp in zip(alloc, ssps):
                        if not eq(al, tp * sp / ssp_t, 0.03):
                            add('ssp_allocation_mismatch')
                if rels and rel is not None and not eq(sum(rels), rel, 0.03):
                    add('performance_obligation_release_mismatch')
                cref = g(d, 'contract reference')
                for acc_m in pk.docs_of('implementation_acceptance_memo'):
                    if num_eq(g(acc_m, 'contract reference'), cref):
                        ob = (g(acc_m, 'accepted obligation') or '').lower()
                        for o in obs:
                            if (o.get('obligation') or '').lower() == ob and o.get('released this period'):
                                if not eq(m(o.get('released this period')), a(acc_m, 'accepted amount'), 0.015):
                                    add('performance_obligation_release_mismatch')
                for rc in pk.docs_of('ssp_rate_card'):
                    if num_eq(g(rc, 'contract reference'), cref):
                        card = {(it.get('obligation') or '').lower(): m(it.get('ssp amount')) for it in rc['items']}
                        for o in obs:
                            k = (o.get('obligation') or '').lower()
                            if k in card and o.get('ssp amount') and not eq(card[k], m(o.get('ssp amount')), 0.015):
                                add('ssp_allocation_mismatch')
                if None not in (tp, rel, end) and not eq(tp - rel, end, 0.03):
                    add('performance_obligation_release_mismatch')
        except Exception:
            traceback.print_exc(file=sys.stderr)
    # jurisdiction notices vs the invoice they support
    try:
        invs = pk.docs_of('customer_invoice', 'vendor_invoice', 'supplier_invoice')
        for n in pk.docs_of('tax_regime_notice'):
            ja, jr = a(n, 'jurisdiction tax amount'), pct(g(n, 'tax rate'))
            linked = [i for i in invs if eq(a(i, 'tax amount'), ja)] or \
                     [i for i in invs if i['date'] == n['date'] and (a(i, 'tax amount') or 0) > 0]
            for i in linked[:1]:
                sub, tx, ir = a(i, 'subtotal'), a(i, 'tax amount'), pct(g(i, 'tax rate'))
                if tx is not None and ja is not None and not eq(tx, ja, 0.015):
                    add('jurisdiction_tax_mismatch')
                if jr is not None and ir is not None and abs(jr - ir) > 1e-6:
                    add('jurisdiction_tax_mismatch')
                if sub is not None and jr and ja is not None and not eq(sub * jr, ja, 0.011):
                    add('jurisdiction_tax_mismatch')
            cj, pj = g(n, 'company jurisdiction'), g(n, 'counterparty jurisdiction')
            tr = (g(n, 'treatment') or '').lower()
            if cj and pj and (g(n, 'tax regime') or '').lower() == 'india_gst':
                same = cj.strip().lower() == pj.strip().lower()
                if (same and 'igst' in tr and 'cgst' not in tr) or (not same and 'cgst' in tr):
                    add('jurisdiction_tax_mismatch')
        # exemption certificates
        for i in pk.docs_of('customer_invoice'):
            cert = g(i, 'exemption certificate')
            if not cert:
                continue
            cs = pk.find(cert, ('tax_exemption_certificate',))
            if not cs:
                continue
            c = cs[0]
            st = (g(c, 'exemption status') or '').lower()
            valid = 'valid' in st and 'invalid' not in st
            from_, to_ = norm_date(g(c, 'effective date')), norm_date(g(c, 'expiration date'))
            dt = i['date']
            if valid and from_ and dt and dt < from_:
                valid = False
            if valid and to_ and dt and dt > to_:
                valid = False
            cp, cu = g(c, 'counterparty'), g(i, 'customer')
            if valid and cp and cu and cp.strip().lower() != cu.strip().lower():
                valid = False
            tx = a(i, 'tax amount') or 0.0
            if valid != (abs(tx) < 0.005):
                add('tax_exemption_conflict')
    except Exception:
        traceback.print_exc(file=sys.stderr)
    # duplicate references with conflicting totals
    try:
        seen = {}
        for d in pk.docs:
            if d['type'] in ('customer_invoice', 'vendor_invoice', 'supplier_invoice', 'secondary_copy'):
                ref = g(d, 'invoice number', 'source reference')
                if not ref or ref.strip() in withdrawn:
                    continue
                tot = a(d, 'total')
                if ref in seen and tot is not None and seen[ref] is not None and not eq(seen[ref], tot, 0.015):
                    add('duplicate_reference_conflict')
                seen.setdefault(ref, tot)
    except Exception:
        traceback.print_exc(file=sys.stderr)
    return codes


# ----------------------------------------------------------------------------- balance sheet
def balance_sheet(pk):
    bal = defaultdict(float)
    sec = {}
    op = pk.opening
    for s in ('assets', 'liabilities', 'equity'):
        for k, v in (op.get(s) or {}).items():
            sign = 1 if s == 'assets' else -1
            bal[k] += sign * float(v)
            sec[k] = s
    pl = 0.0
    for e in pk.entries:
        bal[e['debit_account']] += e['amount']
        bal[e['credit_account']] -= e['amount']
    out = {'assets': {}, 'liabilities': {}, 'equity': {}}
    re_acc = 'Retained Earnings'
    for k, v in bal.items():
        if is_pl(k):
            pl += v
    bal[re_acc] = bal.get(re_acc, 0.0) + pl
    for k, v in bal.items():
        if is_pl(k):
            continue
        s = sec.get(k) or section_of(k, op)
        val = v if s == 'assets' else -v
        val = r2(val)
        if abs(val) < 0.005 and k not in (op.get(s) or {}):
            continue
        out[s][k] = val
    return out


def solve(rec):
    pk = Packet(rec)
    codes = sorted(checks(pk))
    if codes:
        return {'has_inconsistency': True, 'inconsistency_codes': codes,
                'inconsistency_notes': [CODES_DESC[c] for c in codes], 'entries': [],
                'balance_sheet': {'assets': {}, 'liabilities': {}, 'equity': {}}}
    pk.build()
    return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [],
            'entries': pk.entries, 'balance_sheet': balance_sheet(pk)}


def empty():
    return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [], 'entries': [],
            'balance_sheet': {'assets': {}, 'liabilities': {}, 'equity': {}}}


def main(inp, outp):
    out = {}
    with open(inp, encoding='utf-8-sig') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            rid = rec.get('record_id')
            try:
                out[rid] = solve(rec)
            except Exception:
                traceback.print_exc(file=sys.stderr)
                out[rid] = empty()
    d = os.path.dirname(os.path.abspath(outp))
    os.makedirs(d, exist_ok=True)
    tmp = outp + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, outp)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('uso: python3 run.py <records.jsonl> <salida.json>')
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
