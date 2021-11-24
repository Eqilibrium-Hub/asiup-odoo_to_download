from odoo import models, fields, api, _
from datetime import datetime, timedelta
from itertools import groupby
from operator import itemgetter


class SupplierInvoice(models.Model):
    _name = 'asiup.supplier.invoice'

    supplier = fields.Many2one('res.partner', string='Supplier', domain="[('supplier_rank', '=', 1)]")
    ffm_date = fields.Date(string='Date', default=fields.Datetime.now())
    type = fields.Selection([('debit', 'Debit'), ('credit', 'Credit')], string='Type')
    amount = fields.Float(string='Amount')
    description = fields.Text(string='Description')
    state = fields.Selection([('draft', u'Draft'), ('confirm', u'Confirm'),('cancel', u'Cancel'),
                              ], default='draft', string='Status', readonly=True,
                             tracking=True, copy=False)
    # ('cancel', u'Cancel'), ('paid', u'Paid')
    note = fields.Text(string='Note')
    paid_date = fields.Datetime(string='Pay Date')

    def action_confirm_invoice(self):
        self.state = 'confirm'

    def action_paid_invoice(self):
        self.state = 'paid'

    def action_cancel_invoice(self):
        self.state = 'cancel'


class SupplierDebitReport(models.TransientModel):
    _name = 'report.supplier.debit.wizard'

    name = fields.Char()
    supplier_ids = fields.Many2many('res.partner', string='Supplier', domain="[('supplier_rank','=',1)]")
    from_date = fields.Datetime(string='From Date')
    to_date = fields.Datetime(string='To Date')
    state = fields.Many2many('supplier.invoice.status', string='Status')
    debit = fields.Float('Debit')
    credit = fields.Float('Credit')
    debt = fields.Float('Debt')
    report_line_detail = fields.One2many('report.supplier.debit.line', 'report_id')
    is_report_generate = fields.Boolean(default=False, compute='compute_is_report_generate')

    def compute_is_report_generate(self):
        for rec in self:
            rec.get_report()

    def create_record_form_open_view(self):
        today = datetime.now()
        start = today
        day_start = datetime(year=start.year, month=start.month, day=1, hour=0, second=0)
        day_end = today
        status_list = ['confirm']
        ids = self.env['supplier.invoice.status'].search([('name', 'in', status_list)]).ids
        status = [(6, 0, ids)]
        record_id = self.create({'state': status,
                                 'from_date': day_start,
                                 'to_date': day_end})
        return record_id

    def get_report(self):
        old_report = self.search([('id', '!=', self.id)])
        old_report.unlink()
        self.report_line_detail.unlink()
        total_debit, total_credit, total_debt = 0, 0, 0
        cost_detail_by_supplier = []
        order_line_obj = self.env['sale.order.line']
        invoice_obj = self.env['asiup.supplier.invoice']
        res_partner_obj = self.env['res.partner']
        domain = [('ffm_date', '>=', self.from_date), ('ffm_date', '<=', self.to_date)]
        domain = []
        if self.supplier_ids:
            domain.append(('supplier', 'in', self.supplier_ids.ids))
        debit_invoice_domain = domain + [('type', '=', 'debit')]
        credit_invoice_domain = domain + [('type', '=', 'credit')]
        if self.state:
            debit_invoice_domain.append(('state', 'in', [i.name for i in self.state]))
            credit_invoice_domain.append(('state', 'in', [i.name for i in self.state]))
        order_line_group_ids = order_line_obj.read_group(domain, fields=['product_cost'], groupby='supplier', lazy=False, orderby='product_cost')
        invoice_debit_group_ids = invoice_obj.read_group(debit_invoice_domain, fields=['amount'], groupby='supplier', lazy=False, orderby='amount')
        invoice_credit_group_ids = invoice_obj.read_group(credit_invoice_domain, fields=['amount'], groupby='supplier', lazy=False, orderby='amount')
        for order_line in order_line_group_ids:
            if not order_line.get('supplier'):
                continue
            cost = order_line.get('product_cost') or 0.0
            supplier_id = order_line.get('supplier')[0]
            cost_detail_by_supplier.append({'supplier_id': supplier_id,
                                            'cost': cost,
                                            'type': 'debit'})
        for invoice_debit in invoice_debit_group_ids:
            if not invoice_debit.get('supplier'):
                continue
            cost = invoice_debit.get('amount') or 0.0
            supplier_id = invoice_debit.get('supplier')[0]
            cost_detail_by_supplier.append({'supplier_id': supplier_id,
                                            'cost': cost,
                                            'type': 'debit'})
        for invoice_credit in invoice_credit_group_ids:
            if not invoice_credit.get('supplier'):
                continue
            cost = invoice_credit.get('amount') or 0.0
            supplier_id = invoice_credit.get('supplier')[0]
            cost_detail_by_supplier.append({'supplier_id': supplier_id,
                                            'cost': cost,
                                            'type': 'credit'})

        cost_detail_by_supplier = sorted(cost_detail_by_supplier, key=itemgetter('supplier_id'))
        for supplier, cost_lst in groupby(cost_detail_by_supplier, key=itemgetter('supplier_id')):
            supplier_id = res_partner_obj.search([('id', '=', supplier)])
            debit, credit, debt = 0, 0, 0
            for cost in cost_lst:
                if cost.get('type') == 'debit':
                    debit += cost.get('cost')
                else:
                    credit += cost.get('cost')
            if supplier_id:
                debt = abs(credit - debit)
                self.report_line_detail.create({
                    'supplier': supplier_id.id,
                    'debit': debit,
                    'credit': credit,
                    'debt': debt,
                    'report_id': self.id,
                })
            total_debit += debit
            total_credit += credit
            total_debt += debt

        self.debit = total_debit
        self.credit = total_credit
        self.debt = total_debt
        self.is_report_generate = True

    def get_report_supplier_debit(self):
        view_id = self.env.ref('asiup_report_xlsx.report_supplier_debit_report_wizard').id
        record = self.create_record_form_open_view()
        record.write({
            'name': u'Công nợ'
        })
        record.get_report()
        return {
            'name': 'Supplier',
            'view_type': 'form',
            'views': [(view_id, 'form')],
            'res_model': 'report.supplier.debit.wizard',
            'view_id': view_id,
            'type': 'ir.actions.act_window',
            'res_id': record.id,
        }


class SupplierDetailDebit(models.TransientModel):
    _name = 'report.supplier.debit.line'

    report_id = fields.Many2one('report.supplier.debit.wizard', ondelete="cascade")
    supplier = fields.Many2one('res.partner', string='Supplier')
    debit = fields.Float('Debit')
    credit = fields.Float('Credit')
    debt = fields.Float('Debt')


class SupplierInvoiceStatus(models.Model):
    _name = 'supplier.invoice.status'

    name = fields.Char()

    def init(self):
        status_list = ['draft', 'confirm', 'cancel', 'paid']
        for status in status_list:
            st = self.search([('name', '=', status)])
            if st:
                continue
            self.create({
                'name': status,
            })
