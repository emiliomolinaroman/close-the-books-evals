#!/usr/bin/env python3
"""Reto F - cierre de paquetes FinBalance. Motor de reglas por tipo de documento.
Uso: python3 run.py <records.jsonl> <salida.json>
"""
import json, re, sys
from collections import defaultdict

TOL = 0.011

ASSET_HINT = ['Cash', 'Reserve Cash', 'Accounts Receivable', 'Inventory', 'Raw Materials Inventory', 'Work In Process',
              'Finished Goods Inventory', 'Equipment', 'Input Tax Receivable', 'Input CGST Receivable',
              'Input SGST Receivable', 'Input IGST Receivable', 'Accumulated Depreciation', 'Prepaid Insurance',
              'Prepaid Rent', 'Office Supplies', 'Vehicles', 'Store Fixtures', 'Furniture', 'Card Settlement Clearing',
              'Right-of-Use Asset']
LIAB_HINT = ['Accounts Payable', 'Accrued Expenses', 'Loans Payable', 'Notes Payable', 'Sales Tax Payable', 'CGST Payable',
             'SGST Payable', 'IGST Payable', 'Unearned Revenue', 'Security Deposits Payable', 'Lease Liability',
             'Deferred Tax Liability']
EQUITY_HINT = ['Share Capital', "Owner's Equity", 'Retained Earnings']


def r2(x):
    return round(x + 0.0, 2)


def num(s):
    """Parse an OCR amount: $1,234.56 / GBP 1,234.56 / EUR 1.234,56 / -1,234 / 18.00%"""
    if s is None:
        return None
    s = str(s)
    m = re.search(r'-?\s*[\d][\d.,]*', s.replace('$-', '-').replace(' -', ' -'))
    if not m:
        return None
    t = m.group(0).replace(' ', '')
    neg = t.startswith('-') or bool(re.search(r'-\s*[\$A-Z]*\s*\d', s[:m.start() + 1]))
    t = t.lstrip('-')
    t = t.rstrip('.,')
    if ',' in t and '.' in t:
        if t.rfind(',') > t.rfind('.'):
            t = t.replace('.', '').replace(',', '.')
        else:
            t = t.replace(',', '')
    elif ',' in t:
        parts = t.split(',')
        if len(parts[-1]) == 2 or len(parts[-1]) == 1:
            t = ''.join(parts[:-1]) + '.' + parts[-1]
        else:
            t = t.replace(',', '')
    elif '.' in t:
        parts = t.split('.')
        if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
            t = t.replace('.', '')
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


HEADER_KEY = re.compile(r"^\s*[A-Z][A-Za-z0-9 ()/'&-]*: ")
ITEM_KEYS = sorted(['Allocated Transaction Price', 'Released This Period', 'Release Pattern', 'Invoice Line Amount',
                    'Ssp Amount', 'Allocated Amount', 'Running Balance', 'Unit Cost', 'Unit Price', 'Extended Cost',
                    'System Qty', 'Counted Qty', 'Past Due', 'Document Type', 'Description', 'Quantity', 'Amount',
                    'Date', 'Reference', 'Status', 'Obligation', 'Section', 'Account', 'Unit', 'Tenant', 'Customer',
                    'Current', 'Sku'], key=len, reverse=True)


class Doc:
    def __init__(self, d):
        self.id = d['doc_id']
        self.type = d['doc_type']
        self.date = d.get('date', '')
        self.text = d.get('ocr_text', '')
        raw = self.text.split('\n')
        lines = []
        for i, l in enumerate(raw):
            nxt = raw[i + 1] if i + 1 < len(raw) else ''
            if lines and lines[-1].lstrip().startswith('- ') and l.strip() and not l.lstrip().startswith('- ') \
                    and not HEADER_KEY.match(l) and not re.match(r'^[=-]{3,}$', nxt.strip()) \
                    and not re.match(r'^[=-]{3,}$', l.strip()):
                lines[-1] = lines[-1].rstrip() + ' ' + l.strip()
            else:
                lines.append(l)
        self.lines = lines
        self.f = {}
        self.items = []
        for l in lines:
            s = l.strip()
            if s.startswith('- '):
                self.items.append(self.parse_item(s[2:]))
                continue
            m = re.match(r"^([A-Z][A-Za-z0-9 ()/'&-]*?):\s*(.*)$", s)
            if m:
                k, v = m.group(1).strip(), m.group(2).strip()
                if k not in self.f:
                    self.f[k] = v
        self.flat = ' '.join(x.strip() for x in raw)

    @staticmethod
    def parse_item(s):
        out = {}
        for seg in s.split('|'):
            seg = seg.strip()
            for k in ITEM_KEYS:
                if seg.startswith(k + ' ') or seg == k:
                    out[k] = seg[len(k):].strip()
                    break
        return out

    def g(self, k):
        return self.f.get(k)

    def n(self, k):
        v = self.f.get(k)
        return num(v) if v is not None else None


class Solver:
    def __init__(self, rec):
        self.rec = rec
        self.ctx = rec.get('context', {})
        self.allowed = list(rec.get('allowed_accounts', []))
        self.aset = set(self.allowed)
        self.industry = rec.get('industry', '')
        self.regime = self.ctx.get('tax_regime', 'none')
        self.func = self.ctx.get('functional_currency_code', self.ctx.get('currency_code', 'USD'))
        self.docs = [Doc(d) for d in rec.get('documents', [])]
        self.byid = {d.id: d for d in self.docs}
        self.entries = []
        self.codes = []
        self.withdrawn = set()
        for d in self.docs:
            if d.type == 'cancellation_note' and d.g('Withdrawn Reference'):
                self.withdrawn.add(d.g('Withdrawn Reference'))
        # index by reference numbers
        self.ref = {}
        for d in self.docs:
            for k in ('Invoice Number', 'Roll Number', 'Notice Number', 'GRN Number', 'Receipt Number',
                      'Delivery Number', 'Agreement Number', 'Form Number', 'Statement Number', 'Run Number',
                      'Certificate Number', 'Profile ID', 'Batch ID', 'Transfer Number', 'Settlement ID',
                      'Report ID', 'Sheet ID', 'Schedule ID', 'Memo ID', 'Copy ID', 'Loan Number',
                      'Slip Number', 'Work Order Number', 'Advice Number', 'Note ID', 'Summary ID',
                      'Rollforward ID', 'Rate Card ID', 'Modification Number', 'Memo Number', 'Return ID'):
                v = d.g(k)
                if v and d.type not in ('secondary_copy',):
                    if v in self.withdrawn and d.type == 'customer_invoice':
                        continue
                    self.ref.setdefault(v, d)

    # ---------------- helpers
    def acct(self, *cands):
        for c in cands:
            if c in self.aset:
                return c
        return cands[0]

    def fixed_acct(self, pref):
        if pref in self.aset:
            return pref
        for c in ('Equipment', 'Store Fixtures', 'Vehicles', 'Furniture'):
            if c in self.aset:
                return c
        return pref

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

    def flag(self, code):
        if code not in self.codes:
            self.codes.append(code)

    def neq(self, a, b, tol=TOL):
        if a is None or b is None:
            return False
        return abs(a - b) > tol

    def rev_acct(self):
        if self.industry in ('manufacturing', 'wholesale_distribution', 'retail'):
            return self.acct('Sales Revenue', 'Service Revenue')
        if self.industry == 'property_management':
            return self.acct('Rental Revenue', 'Service Revenue', 'Sales Revenue')
        return self.acct('Service Revenue', 'Sales Revenue', 'Rental Revenue')

    def inv_acct(self):
        return self.acct('Inventory', 'Finished Goods Inventory', 'Raw Materials Inventory')

    def find_type(self, t):
        return [d for d in self.docs if d.type == t]

    def fx_notice(self, ref):
        for d in self.find_type('exchange_rate_notice'):
            if d.g('Reference') == ref:
                return d
        return None

    # ---------------- checks for invoices
    def check_invoice(self, d):
        sub, tax, tot = d.n('Subtotal'), d.n('Tax Amount'), d.n('Total')
        rate = d.n('Tax Rate')
        amts = [num(it.get('Amount')) for it in d.items if it.get('Amount')]
        if amts:
            s = sum(a for a in amts if a is not None)
            base = sub if sub is not None else tot
            if self.neq(s, base, 0.02):
                self.flag('invoice_total_mismatch')
        if sub is not None and tax is not None and tot is not None and self.neq(sub + tax, tot):
            self.flag('invoice_total_mismatch' if tot > sub + tax else 'tax_total_mismatch')
        if sub is not None and tax is not None and rate is not None and not d.g('Exemption Certificate'):
            if self.neq(sub * rate / 100.0, tax, 0.011):
                self.flag('tax_rate_mismatch')
        c, sg, ig = d.n('CGST Amount'), d.n('SGST Amount'), d.n('IGST Amount')
        if tax is not None and (c is not None or sg is not None or ig is not None):
            if self.neq((c or 0) + (sg or 0) + (ig or 0), tax):
                self.flag('input_tax_mismatch' if d.type in ('supplier_invoice', 'vendor_invoice') else 'tax_total_mismatch')

    # ---------------- tax posting
    def tax_lines(self, d, side):
        """returns list of (account, amount) for indirect tax; side = 'sale' or 'purchase'"""
        tax = d.n('Tax Amount')
        if not tax:
            return []
        label = (d.g('Tax Label') or '')
        c, sg, ig = d.n('CGST Amount'), d.n('SGST Amount'), d.n('IGST Amount')
        india = 'India' in label or self.regime == 'india_gst' or c is not None or ig is not None
        if india:
            out = []
            if side == 'sale':
                if c: out.append((self.acct('CGST Payable'), c))
                if sg: out.append((self.acct('SGST Payable'), sg))
                if ig: out.append((self.acct('IGST Payable'), ig))
            else:
                if c: out.append((self.acct('Input CGST Receivable'), c))
                if sg: out.append((self.acct('Input SGST Receivable'), sg))
                if ig: out.append((self.acct('Input IGST Receivable'), ig))
            if not out:
                # no split shown: use tax notice treatment
                same = True
                for n_ in self.find_type('tax_regime_notice'):
                    if 'IGST' in (n_.g('Treatment') or ''):
                        same = False
                if same:
                    h = r2(tax / 2)
                    out = [((self.acct('CGST Payable') if side == 'sale' else self.acct('Input CGST Receivable')), h),
                           ((self.acct('SGST Payable') if side == 'sale' else self.acct('Input SGST Receivable')), r2(tax - h))]
                else:
                    out = [((self.acct('IGST Payable') if side == 'sale' else self.acct('Input IGST Receivable')), tax)]
            return out
        if side == 'sale':
            return [(self.acct('Sales Tax Payable'), tax)]
        # purchase
        if 'US Sales Tax' in label or self.regime == 'us_sales_tax':
            capital = True
            for n_ in self.find_type('tax_regime_notice'):
                t = n_.g('Treatment') or ''
                if 'input credit' in t.lower() and 'india' not in t.lower():
                    capital = False
            if capital:
                return [(None, tax)]  # embed in cost
        return [(self.acct('Input Tax Receivable'), tax)]

    # ---------------- handlers
    def h_customer_invoice(self, d):
        num_ = d.g('Invoice Number')
        if num_ in self.withdrawn:
            return
        self.check_invoice(d)
        refs = [d.id]
        ctr = d.g('Contract Ref') or ''
        sub = d.n('Subtotal')
        tot = d.n('Total')
        tax = d.n('Tax Amount') or 0.0
        base = sub if sub is not None else (tot - tax if tot is not None else None)
        cur = d.g('Currency')
        if cur and cur != self.func:
            fx = self.fx_notice(num_)
            if fx is not None:
                refs = [d.id, fx.id]
                rate = fx.n('Exchange Rate')
                famt = fx.n('Functional Amount')
                src = fx.n('Source Amount')
                if src is not None and rate is not None and self.neq(src * rate, famt, 0.011):
                    self.flag('exchange_rate_mismatch')
                if src is not None and self.neq(src, tot, 0.011):
                    self.flag('exchange_rate_mismatch')
                tot = famt
                base = famt
                tax = 0.0
        # supporting docs
        ship = d.g('Shipment Ref')
        dn = None
        if ship:
            for x in self.find_type('delivery_note'):
                if x.g('Shipment Ref') == ship:
                    dn = x
        wo = None
        for x in self.find_type('work_order'):
            if x.g('Customer') == d.g('Customer') and not self.neq(x.n('Approved Amount'), base, 0.011):
                wo = x
        cert = None
        if d.g('Exemption Certificate'):
            cert = self.ref.get(d.g('Exemption Certificate'))
            prof = None
            for x in self.find_type('customer_tax_profile'):
                if x.g('Customer') == d.g('Customer'):
                    prof = x
            refs = [x.id for x in (cert, prof) if x] + [d.id]
            self.check_exemption(d, cert)
        notice = None
        if 'TAX' in (num_ or '') or (d.g('Tax Label') and self.find_type('tax_regime_notice')):
            for x in self.find_type('tax_regime_notice'):
                if not self.neq(x.n('Jurisdiction Tax Amount'), d.n('Tax Amount'), 0.011):
                    notice = x
        if dn:
            refs = [dn.id, d.id]
        elif wo:
            refs = [wo.id, d.id]
        if notice and not cert:
            refs = [notice.id, d.id]
        fgt = None
        if ctr.startswith('FGT'):
            fgt = self.ref.get(ctr)
            if fgt:
                refs = [d.id, fgt.id]
        # revenue target
        credit = self.rev_acct()
        revsched = [x for x in self.find_type('revenue_recognition_schedule') if x.g('Contract Reference') == num_]
        if ctr.startswith('SOF') or ctr.startswith('ASC606') or revsched:
            credit = self.acct('Unearned Revenue')
        if ctr.startswith('ASC606'):
            sof = self.ref.get(ctr)
        dr = 'Accounts Receivable'
        for b in self.find_type('bank_statement'):
            for it in b.items:
                ds = it.get('Description') or ''
                if 'Advance collection' in ds and num_ and ds.endswith(num_):
                    dr = 'Cash'
        self.add(refs, dr, credit, base)
        if dn:
            self.add(refs, 'Cost of Goods Sold', self.inv_acct(), dn.n('Cost Basis Amount'))
        if fgt:
            self.add(refs, 'Cost of Goods Sold', self.acct('Finished Goods Inventory'), fgt.n('Transfer Value'))
        for a, v in self.tax_lines(d, 'sale'):
            self.add(refs, dr, a, v)
        # register booked functional for FX
        self.booked[num_] = tot

    def cert_valid(self, cert, inv):
        if cert is None:
            return False
        if (cert.g('Exemption Status') or '').lower() != 'valid':
            return False
        return True

    def check_exemption(self, inv, cert):
        if cert is None:
            self.flag('tax_exemption_conflict')
            return
        st = (cert.g('Exemption Status') or '').lower()
        if st != 'valid':
            self.flag('tax_exemption_conflict')
        if cert.g('Counterparty') and cert.g('Counterparty') != inv.g('Customer'):
            self.flag('tax_exemption_conflict')
        dt = inv.date
        ef, ex = self.pdate(cert.g('Effective Date')), self.pdate(cert.g('Expiration Date'))
        if ef and dt and dt < ef:
            self.flag('tax_exemption_conflict')
        if ex and dt and dt > ex:
            self.flag('tax_exemption_conflict')
        if inv.n('Tax Amount'):
            self.flag('tax_exemption_conflict')

    def pdate(self, s):
        if not s:
            return None
        s = s.strip()
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
        if m:
            return s[:10]
        m = re.match(r'(\d{2})/(\d{2})/(\d{4})', s)
        if m:
            return '%s-%s-%s' % (m.group(3), m.group(2), m.group(1))
        return None

    def h_vendor_invoice(self, d):
        self.purchase(d, d.g('Expense Label'))

    def h_supplier_invoice(self, d):
        cat = d.g('Expense Category')
        if not cat:
            if (d.g('Invoice Number') or '').startswith('MAT') and 'Raw Materials Inventory' in self.aset:
                cat = 'Raw Materials Inventory'
            else:
                cat = self.inv_acct()
        if cat == 'Inventory':
            cat = self.inv_acct()
        self.purchase(d, cat)

    def purchase(self, d, account):
        num_ = d.g('Invoice Number')
        if num_ in self.withdrawn:
            return
        self.check_invoice(d)
        account = account or self.acct('Office Supplies Expense')
        if account not in self.aset:
            # try matching
            for a in self.allowed:
                if a.lower() == account.lower():
                    account = a
        refs = [d.id]
        grn = self.ref.get(d.g('Goods Receipt Ref') or '')
        if grn is not None and grn.type == 'goods_receipt_note':
            refs = [grn.id, d.id]
        sub = d.n('Subtotal')
        tot = d.n('Total')
        tax = d.n('Tax Amount') or 0.0
        base = sub if sub is not None else (tot - tax if tot is not None else None)
        cur = d.g('Currency')
        if cur and cur != self.func:
            fx = self.fx_notice(num_)
            if fx is not None:
                refs = [d.id, fx.id]
                rate, famt, src = fx.n('Exchange Rate'), fx.n('Functional Amount'), fx.n('Source Amount')
                if src is not None and rate is not None and self.neq(src * rate, famt, 0.011):
                    self.flag('exchange_rate_mismatch')
                if src is not None and self.neq(src, tot, 0.011):
                    self.flag('exchange_rate_mismatch')
                tot = base = famt
                tax = 0.0
                self.booked[num_] = famt
                self.add(refs, account, 'Accounts Payable', base)
                return
        notices = self.find_type('tax_regime_notice')
        for x in notices:
            if d.n('Tax Amount') and not self.neq(x.n('Jurisdiction Tax Amount'), d.n('Tax Amount'), 0.011) \
                    and 'TAX' in (d.g('Goods Receipt Ref') or '') + (num_ or ''):
                refs = [x.id, d.id]
        if 'TAX' in (num_ or '') and notices:
            self.check_jurisdiction(d, notices)
        tl = self.tax_lines(d, 'purchase')
        emb = sum(v for a, v in tl if a is None)
        self.add(refs, account, 'Accounts Payable', r2(base + emb))
        for a, v in tl:
            if a is not None:
                self.add(refs, a, 'Accounts Payable', v)
        self.booked[num_] = tot

    def check_jurisdiction(self, d, notices):
        tax = d.n('Tax Amount')
        match = [x for x in notices if not self.neq(x.n('Jurisdiction Tax Amount'), tax, 0.011)]
        if not match:
            self.flag('jurisdiction_tax_mismatch')
            return
        x = match[0]
        if x.n('Tax Rate') is not None and d.n('Tax Rate') is not None and self.neq(x.n('Tax Rate'), d.n('Tax Rate'), 0.001):
            self.flag('jurisdiction_tax_mismatch')
        t = x.g('Treatment') or ''
        if 'CGST' in t and d.n('IGST Amount'):
            self.flag('jurisdiction_tax_mismatch')
        if 'IGST' in t and d.n('CGST Amount'):
            self.flag('jurisdiction_tax_mismatch')
        cj, pj = x.g('Company Jurisdiction'), x.g('Counterparty Jurisdiction')
        if cj and pj and 'same-state' in t and cj != pj:
            self.flag('jurisdiction_tax_mismatch')
        if cj and pj and 'different-state' in t and cj == pj:
            self.flag('jurisdiction_tax_mismatch')

    def h_utilities_statement(self, d):
        amts = [num(it.get('Amount')) for it in d.items if it.get('Amount')]
        if amts and self.neq(sum(amts), d.n('Total'), 0.02):
            self.flag('invoice_total_mismatch')
        self.add([d.id], self.acct('Utilities Expense'), 'Accounts Payable', d.n('Total'))

    def h_expense_receipt(self, d):
        acc = None
        for it in d.items:
            desc = it.get('Description', '')
            for a in self.allowed:
                if desc == a:
                    acc = a
            if acc:
                break
        if not acc:
            acc = self.acct('Office Supplies Expense')
        amts = [num(it.get('Amount')) for it in d.items if it.get('Amount')]
        if amts and self.neq(sum(amts), d.n('Total'), 0.02):
            self.flag('invoice_total_mismatch')
        self.add([d.id], acc, 'Cash', d.n('Total'))
        self.receipt_acct[d.g('Receipt Number')] = acc

    def h_payment_advice(self, d):
        pf = (d.g('Payment For') or '').lower()
        amt = d.n('Amount')
        if d.items and any('Allocated Amount' in it for it in d.items):
            tot = 0.0
            for it in d.items:
                a = num(it.get('Allocated Amount'))
                if a is None:
                    continue
                tot += a
            if self.neq(tot, amt, 0.011):
                self.flag('payment_allocation_mismatch')
            customer = 'supplier' not in pf
            for it in d.items:
                a = num(it.get('Allocated Amount'))
                tgt = self.ref.get(it.get('Reference', ''))
                refs = [d.id] + ([tgt.id] if tgt else [])
                if customer:
                    self.add(refs, 'Cash', 'Accounts Receivable', a)
                else:
                    self.add(refs, 'Accounts Payable', 'Cash', a)
            return
        refn = d.g('Reference') or ''
        tgt = self.ref.get(refn)
        refs = [d.id] + ([tgt.id] if tgt else [])
        if 'foreign' in pf:
            src, rate = d.n('Source Amount'), d.n('Exchange Rate')
            famt = d.n('Functional Amount')
            fxd = d.n('FX Difference')
            if src is not None and rate is not None:
                if self.neq(src * rate, amt, 0.011) or self.neq(src * rate, famt, 0.011) or self.neq(amt, famt, 0.011):
                    self.flag('fx_settlement_mismatch')
            booked = self.booked_amount(refn)
            if booked is not None and fxd is not None and self.neq(abs(booked - amt), abs(fxd), 0.011):
                self.flag('fx_settlement_mismatch')
            if booked is None:
                booked = amt
            if 'receivable' in pf:
                self.add(refs, 'Cash', 'Accounts Receivable', amt)
                diff = r2(booked - amt)
                if diff > 0:
                    self.add(refs, self.acct('Foreign Exchange Loss'), 'Accounts Receivable', diff)
                elif diff < 0:
                    self.add(refs, 'Accounts Receivable', self.acct('Foreign Exchange Gain'), -diff)
            else:
                self.add(refs, 'Accounts Payable', 'Cash', amt)
                diff = r2(booked - amt)
                if diff > 0:
                    self.add(refs, 'Accounts Payable', self.acct('Foreign Exchange Gain'), diff)
                elif diff < 0:
                    self.add(refs, self.acct('Foreign Exchange Loss'), 'Accounts Payable', -diff)
            self.fx_settled.add(refn)
            return
        if 'supplier' in pf or 'payable' in pf:
            self.add(refs, 'Accounts Payable', 'Cash', amt)
        else:
            self.add(refs, 'Cash', 'Accounts Receivable', amt)

    def booked_amount(self, refn):
        if refn in self.booked:
            return self.booked[refn]
        fx = self.fx_notice(refn)
        if fx:
            return fx.n('Functional Amount')
        return None

    def h_payroll_summary(self, d):
        g, t = d.n('Gross Pay'), d.n('Employer Tax')
        self.add([d.id], self.acct('Salaries Expense'), 'Cash', g)
        self.add([d.id], self.acct('Payroll Tax Expense'), 'Cash', t)

    def h_loan_statement(self, d):
        op, dr, pp, ip, en = (d.n(k) for k in ('Opening Principal', 'Draw Amount', 'Principal Paid', 'Interest Paid', 'Ending Principal'))
        self.add([d.id], 'Cash', self.acct('Loans Payable'), dr)
        self.add([d.id], self.acct('Loans Payable'), 'Cash', pp)
        self.add([d.id], self.acct('Interest Expense'), 'Cash', ip)

    def asset_account(self, name, tag=None):
        n = (name or '').lower()
        tag = tag or ''
        if 'OPEN-FUR' in tag or 'furniture' in n:
            return self.fixed_acct('Furniture')
        if 'OPEN-STO' in tag or 'fixture' in n:
            return self.fixed_acct('Store Fixtures')
        if 'OPEN-VEH' in tag or 'van' in n.split() or 'vehicle' in n or 'truck' in n:
            return self.fixed_acct('Vehicles')
        return self.fixed_acct('Equipment')

    def h_equipment_invoice(self, d):
        acc = self.asset_account(d.g('Asset Name'))
        self.tag_acct[d.g('Asset Tag')] = acc
        tot, paid, fin = d.n('Total'), d.n('Paid Cash'), d.n('Financed Amount')
        if tot is not None and paid is not None and fin is not None and self.neq(paid + fin, tot):
            self.flag('invoice_total_mismatch')
        self.add([d.id], acc, 'Cash', paid)
        self.add([d.id], acc, self.acct('Notes Payable'), fin)

    def h_depreciation_schedule(self, d):
        self.add([d.id], self.acct('Depreciation Expense'), 'Accumulated Depreciation',
                 d.n('Current Period Charge') if d.n('Current Period Charge') is not None else d.n('Current Charge'))

    def h_fixed_asset_rollforward(self, d):
        op, ad, dp, en = d.n('Opening Balance'), d.n('Additions'), d.n('Disposals'), d.n('Ending Balance')
        if None not in (op, ad, dp, en) and self.neq(op + ad - dp, en):
            self.flag('schedule_rollforward_mismatch')
        self.add([d.id], self.acct('Depreciation Expense'), 'Accumulated Depreciation', d.n('Current Charge'))

    def h_rent_notice(self, d):
        self.prepaid[d.g('Notice Number')] = ('Prepaid Rent', 'Rent Expense', d)
        self.add([d.id], self.acct('Prepaid Rent'), 'Cash', d.n('Total'))

    def h_insurance_notice(self, d):
        self.prepaid[d.g('Notice Number')] = ('Prepaid Insurance', 'Insurance Expense', d)
        self.add([d.id], self.acct('Prepaid Insurance'), 'Cash', d.n('Total Premium') or d.n('Total'))

    def h_service_period_memo(self, d):
        ref = d.g('Reference') or ''
        amt = d.n('Recognized Amount')
        src = self.ref.get(ref)
        if src is not None and src.type in ('rent_notice', 'insurance_notice'):
            if src.type == 'rent_notice':
                self.add([src.id, d.id], self.acct('Rent Expense'), 'Prepaid Rent', amt)
            else:
                self.add([src.id, d.id], self.acct('Insurance Expense'), 'Prepaid Insurance', amt)
            return
        m = re.search(r'Accrue unpaid ([a-z ]+?) expense', d.flat, re.I)
        if m:
            acc = None
            for a in self.allowed:
                if a.lower() == (m.group(1).strip() + ' expense').lower():
                    acc = a
            acc = acc or self.acct('Office Supplies Expense')
            self.add([d.id], acc, self.acct('Accrued Expenses'), amt)
            return
        subj = (d.g('Subject') or '').lower()
        if 'rent' in subj:
            self.add([d.id], self.acct('Rent Expense'), 'Prepaid Rent', amt)
        elif 'insurance' in subj:
            self.add([d.id], self.acct('Insurance Expense'), 'Prepaid Insurance', amt)

    def h_revenue_recognition_schedule(self, d):
        op, ad, rl, en = (d.n(k) for k in ('Opening Deferred', 'Added Deferred', 'Released This Period', 'Ending Deferred'))
        if None not in (op, ad, rl, en) and self.neq(op + ad - rl, en):
            self.flag('schedule_rollforward_mismatch')
        inv = self.ref.get(d.g('Contract Reference') or '')
        refs = [d.id] + ([inv.id] if inv else [])
        self.add(refs, self.acct('Unearned Revenue'), self.acct('Service Revenue', 'Sales Revenue'), rl)

    def h_performance_obligation_schedule(self, d):
        tp, tssp, alloc_tot, rel, endd = (d.n(k) for k in ('Transaction Price', 'Total SSP', 'Allocation Total',
                                                             'Released This Period', 'Ending Deferred'))
        obs = [it for it in d.items if 'Obligation' in it]
        s_ssp = sum(num(it.get('Ssp Amount')) or 0 for it in obs)
        s_alloc = sum(num(it.get('Allocated Transaction Price')) or 0 for it in obs)
        s_rel = sum(num(it.get('Released This Period')) or 0 for it in obs)
        if obs:
            if self.neq(s_ssp, tssp, 0.02) or self.neq(s_alloc, tp, 0.02) or self.neq(alloc_tot, tp, 0.02):
                self.flag('ssp_allocation_mismatch')
            for it in obs:
                ssp = num(it.get('Ssp Amount'))
                al = num(it.get('Allocated Transaction Price'))
                if tssp and ssp is not None and al is not None and tp is not None and self.neq(tp * ssp / tssp, al, 0.02):
                    self.flag('ssp_allocation_mismatch')
            if self.neq(s_rel, rel, 0.02):
                self.flag('performance_obligation_release_mismatch')
            if tp is not None and endd is not None and rel is not None and self.neq(tp - rel, endd, 0.02):
                self.flag('performance_obligation_release_mismatch')
        # rate card consistency
        ctr = d.g('Contract Reference')
        for rc in self.find_type('ssp_rate_card'):
            if rc.g('Contract Reference') == ctr:
                if self.neq(rc.n('Total SSP'), tssp, 0.02):
                    self.flag('ssp_allocation_mismatch')
                rcm = {it.get('Obligation'): num(it.get('Ssp Amount')) for it in rc.items if 'Obligation' in it}
                for it in obs:
                    o = it.get('Obligation')
                    if o in rcm and self.neq(rcm[o], num(it.get('Ssp Amount')), 0.02):
                        self.flag('ssp_allocation_mismatch')
        acc_memos = [x for x in self.find_type('implementation_acceptance_memo') if x.g('Contract Reference') == ctr]
        for it in obs:
            o = (it.get('Obligation') or '')
            r = num(it.get('Released This Period'))
            pat = (it.get('Release Pattern') or '').lower()
            if 'acceptance' in pat:
                if acc_memos:
                    m = acc_memos[0]
                    if self.neq(m.n('Accepted Amount'), num(it.get('Allocated Transaction Price')), 0.02):
                        self.flag('performance_obligation_release_mismatch')
                    if r is not None and self.neq(r, m.n('Accepted Amount'), 0.02):
                        self.flag('performance_obligation_release_mismatch')
                    self.add([m.id, d.id], self.acct('Unearned Revenue'), self.acct('Service Revenue'), r)
                else:
                    if r:
                        self.flag('performance_obligation_release_mismatch')
            else:
                mm = re.search(r'over (\d+) months', pat)
                al = num(it.get('Allocated Transaction Price'))
                self.add([d.id], self.acct('Unearned Revenue'), self.acct('Service Revenue'), r)

    def h_rent_roll(self, d):
        amts = [num(it.get('Amount')) for it in d.items if it.get('Amount')]
        if amts and self.neq(sum(amts), d.n('Total Rent'), 0.02):
            self.flag('invoice_total_mismatch')
        self.add([d.id], 'Accounts Receivable', self.acct('Rental Revenue', 'Service Revenue'), d.n('Total Rent'))

    def h_security_deposit_notice(self, d):
        nn = d.g('Notice Number') or ''
        amt = d.n('Amount')
        if nn.startswith('DEPREF') or 'Refund' in d.text:
            m = re.search(r'deposit (DEP-\d+)', d.text)
            orig = self.ref.get(m.group(1)) if m else None
            self.add([d.id] + ([orig.id] if orig else []), self.acct('Security Deposits Payable'), 'Cash', amt)
        else:
            self.add([d.id], 'Cash', self.acct('Security Deposits Payable'), amt)

    def h_patient_invoice(self, d):
        g, p, i = d.n('Gross Charge'), d.n('Patient Due'), d.n('Insurer Due')
        if None not in (g, p, i) and self.neq(p + i, g):
            self.flag('invoice_total_mismatch')
        self.add([d.id], 'Accounts Receivable', self.acct('Service Revenue'), g)

    def h_insurer_remittance(self, d):
        inv = self.ref.get(d.g('Claim Reference') or '')
        self.add([d.id] + ([inv.id] if inv else []), 'Cash', 'Accounts Receivable', d.n('Paid Amount'))

    def h_copay_receipt(self, d):
        inv = self.ref.get(d.g('Reference Invoice') or '')
        self.add([d.id] + ([inv.id] if inv else []), 'Cash', 'Accounts Receivable', d.n('Amount'))

    def h_sales_summary(self, d):
        net, tax, cogs = d.n('Net Sales'), d.n('Tax Amount') or 0.0, d.n('COGS Amount')
        cash, card = d.n('Cash Sales') or 0.0, d.n('Card Sales') or 0.0
        gross, ret = d.n('Gross Sales'), d.n('Returns')
        if gross is not None and ret is not None and net is not None and self.neq(gross - ret, net):
            self.flag('invoice_total_mismatch')
        if net is not None and self.neq(net + tax, cash + card, 0.02):
            self.flag('tax_total_mismatch')
        refs = [d.id]
        for b in self.find_type('pos_batch_report'):
            if not self.neq(b.n('Batch Total'), card, 0.011) and card:
                refs = [d.id, b.id]
        tot = cash + card
        rev = self.acct('Sales Revenue')
        if tot:
            cash_rev = r2(net * cash / tot)
            cash_tax = r2(tax * cash / tot)
        else:
            cash_rev, cash_tax = net, tax
        self.add(refs, 'Cash', rev, cash_rev)
        self.add(refs, self.acct('Card Settlement Clearing'), rev, r2(net - cash_rev))
        self.add(refs, 'Cost of Goods Sold', self.inv_acct(), cogs)
        tacc = self.acct('Sales Tax Payable')
        self.add(refs, 'Cash', tacc, cash_tax)
        self.add(refs, self.acct('Card Settlement Clearing'), tacc, r2(tax - cash_tax))

    def h_pos_batch_report(self, d):
        bt, fee, exp = d.n('Batch Total'), d.n('Fee Amount'), d.n('Expected Deposit')
        if None not in (bt, fee, exp) and self.neq(bt - fee, exp):
            self.flag('bank_closing_mismatch')

    def h_card_settlement_report(self, d):
        g, fee, net = d.n('Gross Amount'), d.n('Fees'), d.n('Net Deposit')
        refs = [d.id]
        for b in self.find_type('pos_batch_report'):
            if not self.neq(b.n('Batch Total'), g, 0.011):
                refs = [d.id, b.id]
        clr = self.acct('Card Settlement Clearing')
        self.add(refs, 'Cash', clr, net)
        self.add(refs, self.acct('Maintenance Expense', 'Office Supplies Expense'), clr, fee)

    def h_return_note(self, d):
        self.add([d.id], self.acct('Sales Revenue'), 'Cash', d.n('Amount'))

    def h_inventory_adjustment_note(self, d):
        sh = self.ref.get(d.g('Reference Sheet') or '')
        refs = ([sh.id] if sh else []) + [d.id]
        self.add(refs, self.acct('Inventory Shrinkage Expense'), self.inv_acct(), d.n('Amount'))

    def h_scrap_report(self, d):
        lot = d.g('Batch Or Lot') or ''
        acc = self.acct('Finished Goods Inventory', 'Inventory') if 'FG' in lot else self.inv_acct()
        if 'RM' in lot:
            acc = self.acct('Raw Materials Inventory', 'Inventory')
        ob = [x.id for x in self.docs if x.type == 'opening_trial_balance'][:1]
        self.add([d.id] + ob, self.acct('Inventory Shrinkage Expense'), acc, d.n('Write Down'))

    def h_inventory_rollforward(self, d):
        op, ad, us, wd, en = (d.n(k) for k in ('Opening Balance', 'Additions', 'Usage Or Sales', 'Write Down', 'Ending Balance'))
        if None not in (op, ad, us, en) and self.neq(op + ad - us - (wd or 0), en):
            self.flag('inventory_rollforward_mismatch')
        if wd and not self.find_type('inventory_adjustment_note'):
            rolls = sorted(self.find_type('inventory_rollforward'), key=lambda x: x.g('Rollforward ID') or '')
            sheets = sorted(self.find_type('stock_count_sheet'), key=lambda x: x.g('Sheet ID') or '')
            i = rolls.index(d)
            refs = ([sheets[i].id] if i < len(sheets) else []) + [d.id]
            self.add(refs, self.acct('Inventory Shrinkage Expense'), self.inv_acct(), wd)

    def h_credit_memo(self, d):
        reason = (d.g('Reason') or '').lower()
        inv = self.ref.get(d.g('Reference') or '')
        amt = d.n('Amount')
        if 'bad debt' in reason:
            ag = [x.id for x in self.find_type('ar_aging_summary')]
            self.add(ag[:1] + [d.id] + ([inv.id] if inv else []), self.acct('Bad Debt Expense'), 'Accounts Receivable', amt)
        else:
            self.add([d.id] + ([inv.id] if inv else []), self.rev_acct(), 'Accounts Receivable', amt)

    def h_ar_aging_summary(self, d):
        s = 0.0
        for it in d.items:
            s += (num(it.get('Current')) or 0) + (num(it.get('Past Due')) or 0)
        if d.items and self.neq(s, d.n('Total Open'), 0.02):
            self.flag('statement_balance_mismatch')

    def h_vendor_statement(self, d):
        s = sum(num(it.get('Amount')) or 0 for it in d.items)
        if d.items and self.neq(s, d.n('Closing Balance'), 0.02):
            self.flag('statement_balance_mismatch')

    def h_bank_statement(self, d):
        op, cl = d.n('Opening Balance'), d.n('Closing Balance')
        s = sum(num(it.get('Amount')) or 0 for it in d.items)
        if op is not None and cl is not None and self.neq(op + s, cl):
            self.flag('bank_closing_mismatch')

    def h_material_requisition_slip(self, d):
        b = self.ref.get(d.g('Batch ID') or '')
        src = None
        for x in self.find_type('supplier_invoice'):
            if any(it.get('Description') == d.g('Material') for it in x.items):
                if src is None or (x.g('Invoice Number') or '') < (src.g('Invoice Number') or ''):
                    src = x
        refs = [d.id] + ([b.id] if b else []) + ([src.id] if src else [])
        self.add(refs, self.acct('Work In Process'), self.acct('Raw Materials Inventory'), d.n('Issue Value'))

    def h_direct_labor_record(self, d):
        b = self.batch_sheet(d.g('Batch ID'))
        self.add([d.id] + ([b.id] if b else []), self.acct('Work In Process'), 'Cash', d.n('Labor Cash Paid') or d.n('Labor Value'))

    def h_overhead_accrual_memo(self, d):
        b = self.batch_sheet(d.g('Batch ID'))
        self.add([d.id] + ([b.id] if b else []), self.acct('Work In Process'), self.acct('Accrued Expenses'),
                 d.n('Accrued Overhead') or d.n('Overhead Value'))

    def h_finished_goods_transfer_note(self, d):
        b = self.batch_sheet(d.g('Batch ID'))
        self.add([d.id] + ([b.id] if b else []), self.acct('Finished Goods Inventory'), self.acct('Work In Process'),
                 d.n('Transfer Value'))

    def batch_sheet(self, bid):
        for x in self.find_type('production_batch_sheet'):
            if x.g('Batch ID') == bid:
                return x
        return None

    def h_transfer_advice(self, d):
        fa = d.g('From Account') or 'Cash'
        ta = d.g('To Account') or 'Reserve Cash'
        amt = d.n('Amount')
        ref = d.g('Reference') or d.g('Transfer Number') or ''
        found = []
        for b in self.find_type('bank_statement'):
            for it in b.items:
                if ref and ref in (it.get('Description') or ''):
                    found.append(num(it.get('Amount')))
        for v in found:
            if v is not None and self.neq(abs(v), amt):
                self.flag('transfer_mismatch')
        self.add([d.id], self.acct(ta), self.acct(fa), amt)

    def h_reclassification_memo(self, d):
        fa, ta, amt = d.g('From Account'), d.g('To Account'), d.n('Amount')
        orig = self.ref.get(d.g('Original Reference') or '')
        if orig is not None:
            tot = orig.n('Total')
            if tot is not None and amt is not None and self.neq(amt, tot):
                self.flag('reclassification_support_mismatch')
            oacc = self.receipt_acct.get(d.g('Original Reference'))
            if oacc and fa and oacc != fa:
                self.flag('reclassification_support_mismatch')
        self.add([d.id] + ([orig.id] if orig else []), ta, fa, amt)

    def h_lease_agreement(self, d):
        rou, liab = d.n('ROU Asset Amount'), d.n('Lease Liability Amount')
        self.add([d.id], self.acct('Right-of-Use Asset'), self.acct('Lease Liability'), liab)

    def h_lease_amortization_schedule(self, d):
        op, pay, it, pr, en, am = (d.n(k) for k in ('Opening Liability Balance', 'Payment Amount', 'Interest Amount',
                                                     'Principal Amount', 'Ending Liability Balance', 'ROU Amortization Amount'))
        if None not in (op, pr, en) and self.neq(op - pr, en):
            self.flag('lease_schedule_mismatch')
        if None not in (pay, it, pr) and self.neq(it + pr, pay):
            self.flag('lease_schedule_mismatch')
        ag = self.ref.get(d.g('Agreement Number') or '')
        pn = [x for x in self.find_type('lease_payment_notice') if x.g('Agreement Number') == d.g('Agreement Number')]
        for x in (pn if pay else []):
            if self.neq(x.n('Interest Amount'), it) or self.neq(x.n('Principal Amount'), pr) or self.neq(x.n('Payment Amount'), pay):
                self.flag('lease_schedule_mismatch')
        refs = ([ag.id] if ag else []) + [d.id]
        prefs = refs + [x.id for x in pn]
        if pn and pay:
            self.add(prefs, self.acct('Lease Liability'), 'Cash', pr)
            self.add(prefs, self.acct('Lease Interest Expense', 'Interest Expense'), 'Cash', it)
        self.lease_paid.add(d.g('Agreement Number'))
        self.add(refs, self.acct('Lease Amortization Expense'), self.acct('Right-of-Use Asset'), am)

    def h_lease_payment_notice(self, d):
        pass  # handled with schedule (or in finalize)

    def h_lease_modification_notice(self, d):
        old, new, delta, rou = (d.n(k) for k in ('Old Liability Balance', 'Remeasured Liability Balance',
                                                 'Liability Remeasurement Delta Amount', 'ROU Asset Adjustment Amount'))
        if None not in (old, new, delta) and self.neq(new - old, delta):
            self.flag('lease_remeasurement_mismatch')
        if None not in (delta, rou) and self.neq(delta, rou):
            self.flag('lease_remeasurement_mismatch')
        ag = self.ref.get(d.g('Agreement Number') or '')
        self.add([d.id] + ([ag.id] if ag else []), self.acct('Right-of-Use Asset'), self.acct('Lease Liability'), delta)

    def h_asset_disposal_notice(self, d):
        cost, ad, nbv, pr, gl = (d.n(k) for k in ('Original Cost', 'Accumulated Depreciation', 'Net Book Value',
                                                  'Proceeds Amount', 'Gain Loss Amount'))
        typ = (d.g('Gain Loss Type') or '').lower()
        if None not in (cost, ad, nbv) and self.neq(cost - ad, nbv):
            self.flag('asset_disposal_mismatch')
        if None not in (pr, nbv, gl):
            calc = pr - nbv
            if self.neq(abs(calc), gl) or (calc > 0.005 and typ == 'loss') or (calc < -0.005 and typ == 'gain'):
                self.flag('asset_disposal_mismatch')
        tag = d.g('Asset Tag') or ''
        adv = None
        for x in self.find_type('sale_proceeds_advice'):
            if x.g('Asset Tag') == tag:
                adv = x
                if self.neq(x.n('Proceeds Amount'), pr):
                    self.flag('asset_disposal_mismatch')
        acc = self.tag_acct.get(tag) or self.asset_account(d.g('Asset Name'), tag)
        refs = [d.id] + ([adv.id] if adv else [])
        self.add(refs, 'Cash', acc, pr)
        self.add(refs, 'Accumulated Depreciation', acc, ad)
        if typ == 'loss':
            self.add(refs, self.acct('Loss on Disposal'), acc, gl)
        else:
            self.add(refs, acc, self.acct('Gain on Disposal'), gl)

    def h_tax_depreciation_schedule(self, d):
        b, t, diff, rate = (d.n(k) for k in ('Book Depreciation Amount', 'Tax Depreciation Amount',
                                             'Temporary Difference Amount', 'Tax Rate'))
        if None not in (b, t, diff) and self.neq(t - b, diff):
            self.flag('deferred_tax_rollforward_mismatch')

    def h_deferred_tax_memo(self, d):
        op, mv, en, ex = (d.n(k) for k in ('Opening Deferred Tax Liability', 'Current Period Deferred Tax Movement',
                                           'Deferred Tax Liability Ending', 'Deferred Tax Expense Amount'))
        if None not in (op, mv, en) and self.neq(op + mv, en):
            self.flag('deferred_tax_rollforward_mismatch')
        if None not in (mv, ex) and self.neq(mv, ex):
            self.flag('deferred_tax_rollforward_mismatch')
        tag = d.g('Asset Tag')
        sch = None
        for x in self.find_type('tax_depreciation_schedule'):
            if x.g('Asset Tag') == tag:
                diff, rate = x.n('Temporary Difference Amount'), x.n('Tax Rate')
                if diff is not None and rate is not None and mv is not None and not self.neq(diff * rate / 100.0, mv, 0.011):
                    sch = x
        if sch is None:
            cands = [x for x in self.find_type('tax_depreciation_schedule') if x.g('Asset Tag') == tag]
            if cands:
                # schedule exists but does not match the movement
                if len(cands) == len([y for y in self.find_type('deferred_tax_memo') if y.g('Asset Tag') == tag]):
                    self.flag('deferred_tax_rollforward_mismatch')
                sch = cands[0]
        refs = ([sch.id] if sch else []) + [d.id]
        self.add(refs, self.acct('Deferred Tax Expense'), self.acct('Deferred Tax Liability'), mv)

    def h_exchange_rate_notice(self, d):
        src, rate, fa = d.n('Source Amount'), d.n('Exchange Rate'), d.n('Functional Amount')
        if None not in (src, rate, fa) and self.neq(src * rate, fa, 0.011):
            self.flag('exchange_rate_mismatch')

    def h_fx_remeasurement_memo(self, d):
        src, bk, cr, rm, df = (d.n(k) for k in ('Source Amount', 'Booked Amount', 'Closing Rate', 'Remeasured Amount',
                                                'Difference Amount'))
        if None not in (src, cr, rm) and self.neq(src * cr, rm, 0.011):
            self.flag('remeasurement_mismatch')
        if None not in (bk, rm, df) and self.neq(abs(bk - rm), abs(df), 0.011):
            self.flag('remeasurement_mismatch')
        ref = d.g('Reference') or ''
        inv = self.ref.get(ref)
        fx = self.fx_notice(ref)
        refs = [d.id] + ([inv.id] if inv else []) + ([fx.id] if fx else [])
        if bk is None or rm is None:
            return
        diff = r2(bk - rm)
        payable = 'BILL' in ref or (inv is not None and inv.type in ('vendor_invoice', 'supplier_invoice'))
        if payable:
            if diff > 0:
                self.add(refs, 'Accounts Payable', self.acct('Foreign Exchange Gain'), diff)
            else:
                self.add(refs, self.acct('Foreign Exchange Loss'), 'Accounts Payable', -diff)
        else:
            if diff > 0:
                self.add(refs, self.acct('Foreign Exchange Loss'), 'Accounts Receivable', diff)
            else:
                self.add(refs, 'Accounts Receivable', self.acct('Foreign Exchange Gain'), -diff)

    def h_secondary_copy(self, d):
        src = d.g('Source Reference')
        orig = self.ref.get(src or '')
        if orig is not None and self.neq(orig.n('Total'), d.n('Total'), 0.011):
            self.flag('duplicate_reference_conflict')

    # ---------------- main
    def solve(self):
        self.booked = {}
        self.fx_settled = set()
        self.tag_acct = {}
        self.prepaid = {}
        self.receipt_acct = {}
        self.lease_paid = set()
        # duplicate invoice numbers with conflicting totals (not withdrawn)
        seen = {}
        for d in self.docs:
            if d.type in ('customer_invoice', 'vendor_invoice', 'supplier_invoice'):
                k = d.g('Invoice Number')
                if k in self.withdrawn:
                    continue
                if k in seen and self.neq(seen[k], d.n('Total')):
                    self.flag('duplicate_reference_conflict')
                seen[k] = d.n('Total')
        order = ['equipment_invoice', 'customer_invoice', 'vendor_invoice', 'supplier_invoice', 'expense_receipt']
        docs = sorted(self.docs, key=lambda x: (order.index(x.type) if x.type in order else 99, x.id))
        for d in docs:
            h = getattr(self, 'h_' + d.type, None)
            if h:
                h(d)
        # lease payments with no schedule
        for x in self.find_type('lease_payment_notice'):
            if x.g('Agreement Number') not in self.lease_paid:
                ag = self.ref.get(x.g('Agreement Number') or '')
                refs = ([ag.id] if ag else []) + [x.id]
                self.add(refs, self.acct('Lease Liability'), 'Cash', x.n('Principal Amount'))
                self.add(refs, self.acct('Lease Interest Expense', 'Interest Expense'), 'Cash', x.n('Interest Amount'))
        if self.codes:
            return {'has_inconsistency': True, 'inconsistency_codes': self.codes,
                    'inconsistency_notes': ['Detected: ' + c for c in self.codes], 'entries': [],
                    'balance_sheet': {'assets': {}, 'liabilities': {}, 'equity': {}}}
        self.entries.sort(key=lambda e: e['doc_refs'][0] if e['doc_refs'] else '')
        return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [],
                'entries': self.entries, 'balance_sheet': self.balance_sheet()}

    def section(self, a):
        if any(w in a for w in ('Expense', 'Revenue', 'Gain', 'Loss', 'Cost of')) and a != 'Unearned Revenue':
            return None
        if a in ASSET_HINT:
            return 'assets'
        if a in LIAB_HINT:
            return 'liabilities'
        if a in EQUITY_HINT:
            return 'equity'
        if any(w in a for w in ('Payable', 'Liability', 'Unearned', 'Accrued')):
            return 'liabilities'
        if any(w in a for w in ('Receivable', 'Inventory', 'Prepaid', 'Cash', 'Asset')):
            return 'assets'
        if any(w in a for w in ('Capital', 'Equity')):
            return 'equity'
        return None  # income statement

    def balance_sheet(self):
        ob = self.rec.get('opening_balance', {})
        bal = defaultdict(float)
        sec = {}
        orderk = []
        for s in ('assets', 'liabilities', 'equity'):
            for k, v in ob.get(s, {}).items():
                sign = 1 if s == 'assets' else -1
                bal[k] += sign * v
                sec[k] = s
                orderk.append(k)
        for e in self.entries:
            bal[e['debit_account']] += e['amount']
            bal[e['credit_account']] -= e['amount']
        ni = 0.0
        out = {'assets': {}, 'liabilities': {}, 'equity': {}}
        for k in list(bal.keys()):
            s = sec.get(k) or self.section(k)
            if s is None:
                ni += bal[k]
                continue
            sec[k] = s
            if k not in orderk:
                orderk.append(k)
        bal['Retained Earnings'] += ni  # debit-positive: net income reduces (credit)
        sec['Retained Earnings'] = 'equity'
        if 'Retained Earnings' not in orderk:
            orderk.append('Retained Earnings')
        for k in orderk:
            s = sec[k]
            v = bal[k] if s == 'assets' else -bal[k]
            v = r2(v)
            in_ob = k in ob.get(s, {})
            if abs(v) < 0.005:
                continue
            out[s][k] = v + 0.0
        return out


def solve(rec):
    try:
        return Solver(rec).solve()
    except Exception as ex:  # never crash: return opening balance
        ob = rec.get('opening_balance', {})
        return {'has_inconsistency': False, 'inconsistency_codes': [], 'inconsistency_notes': [], 'entries': [],
                'balance_sheet': {s: dict(ob.get(s, {})) for s in ('assets', 'liabilities', 'equity')}}


def main():
    inp, outp = sys.argv[1], sys.argv[2]
    res = {}
    with open(inp) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            res[rec['record_id']] = solve(rec)
    with open(outp, 'w') as fh:
        json.dump(res, fh, indent=1)


if __name__ == '__main__':
    main()
