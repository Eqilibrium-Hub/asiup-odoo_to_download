# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import timedelta, datetime, date


class OrderlineStoreWizard(models.TransientModel):
    _name = "report.order.line.store.wizard"
    _description = "Wizard report order line by store"
    _rec_name = "name"

    name = fields.Char()
    date_start = fields.Datetime(string='From Date', required=True)
    date_end = fields.Datetime(string='To Date', required=True)
    revenue_total = fields.Float(string='Revenue', digits=(22, 2))
    order_total = fields.Integer(string='Total Order')
    report_line_detail = fields.One2many('report.store.order.line', 'report_id', string='Line')
    is_report_generate = fields.Boolean(default=False, compute='compute_is_report_generate')
    order_status = fields.Many2many('order.status', 'report_order_order_status_rel', 'report_id', 'status_id', string='Order Status')
    is_product_report = fields.Boolean(string='Product Dashboard', default=False)
    product_ids = fields.Many2many('asiup.product.label', string='Product')
    product_count_total = fields.Integer(string='Total Product')
    report_line_product_detail = fields.One2many('report.product.order.line', 'report_id', string='Line')
    store_ids = fields.Many2many('store.domain', string='Store')
    aov = fields.Float(string='AOV', digits=(22, 2), default=0)

    def create_record_form_open_view(self):
        today = datetime.now() - timedelta(hours=8)
        start = today - timedelta(days=1)
        daystart = datetime(year=start.year, month=start.month,
                            day=start.day, hour=17, second=0)
        dayend = datetime(year=today.year, month=today.month,
                          day=today.day, hour=16, minute=59, second=59)
        status_list = ['processing', 'on_hold', 'delivered', 'pending_payment', 'pending']
        ids = self.env['order.status'].search([('code', 'in', status_list)]).ids
        order_status = [(6, 0, ids)]
        record = self.create({'order_status': order_status,
                              'date_start': daystart,
                              'date_end': dayend})
        return record

    def compute_is_report_generate(self):
        for rec in self:
            rec.get_report_store()

    def get_report_store(self):
        # if report has product in filter, will take revenue by order line
        self.report_line_detail.unlink()
        self.report_line_product_detail.unlink()
        domain_order = [('date_order', '>=', self.date_start), ('date_order', '<=', self.date_end)]
        if self.store_ids:
            domain_order.append(('primary_domain', 'in', [store.primary_domain for store in self.store_ids]))
        if self.order_status:
            domain_order.append(('order_status', 'in', [x.code for x in self.order_status]))
        if not self.is_product_report:
            if not self.product_ids:
                order_group_ids = self.env['sale.order'].read_group(domain_order, fields=['amount_total', 'id'], groupby=['primary_domain'],
                                                                    lazy=False)
                total_revenue, total_order = self.get_report_order_by_store(order_group_ids)
            else:
                order_ids = self.env['sale.order'].search(domain_order)
                domain_order_line = [('product_label', 'in', [x.name for x in self.product_ids]), ('order_id', 'in', order_ids.ids),
                                     ('is_extra_line', '=', False)]

                order_line_group_ids = self.env['sale.order.line'].read_group(domain_order_line, fields=['price_subtotal', 'product_uom_qty'],
                                                                              groupby='primary_domain', lazy=False)

                total_revenue, total_order, total_product = self.get_report_product_by_store(order_line_group_ids)
        else:
            order_ids = self.env['sale.order'].search(domain_order)
            if not self.product_ids:
                order_line_domain = [('order_id', 'in', order_ids.ids), ('is_extra_line', '=', False)]
            else:
                order_line_domain = [('product_label', 'in', [x.name for x in self.product_ids]), ('order_id', 'in', order_ids.ids),
                                     ('is_extra_line', '=', False)]
            order_line_group_ids = self.env['sale.order.line'].read_group(order_line_domain, fields=['price_subtotal'], groupby='product_label',
                                                                          lazy=False, orderby='price_subtotal')
            total_revenue, total_order = self.get_report_product(order_line_group_ids)

        self.is_report_generate = True
        self.revenue_total = total_revenue
        self.order_total = total_order
        if total_order > 0:
            self.aov = total_revenue / total_order

    def get_report_product(self, order_line_group_ids):
        total_revenue, total_order = 0, 0
        for line_group_id in order_line_group_ids:
            order_line_count = line_group_id.get('__count')
            revenue = line_group_id.get('price_subtotal')
            order_count = line_group_id.get('__count')
            if not line_group_id.get('product_label'):
                continue
            aov = 0
            if order_line_count > 0:
                aov = revenue / order_line_count
            self.report_line_product_detail.create({
                'product_label': line_group_id.get('product_label'),
                'revenue': revenue,
                'report_id': self.id,
                'order_count': order_count,
                'aov': aov,
            })
            total_revenue += line_group_id.get('price_subtotal')
            total_order += line_group_id.get('__count')
        return total_revenue, total_order

    def get_report_product_by_store(self, order_line_group_ids):
        total_product, total_revenue, total_order = 0, 0, 0
        for product_group in order_line_group_ids:
            store = product_group.get('primary_domain')
            order_count = product_group.get('__count')
            product_count = product_group.get('product_uom_qty')
            revenue = product_group.get('price_subtotal')
            aov = 0
            if order_count > 0:
                aov = revenue / order_count
            self.report_line_detail.create({
                'store': store,
                'revenue': revenue,
                'report_id': self.id,
                'order_count': order_count,
                'aov': aov,
            })
            total_revenue += revenue
            total_order += order_count
            total_product += product_count

        return total_revenue, total_order, total_product

    def get_report_order_by_store(self, order_group_ids):
        total_order, total_revenue = 0, 0
        for order_group in order_group_ids:
            domain = order_group.get('primary_domain')
            order_count = order_group.get('__count')
            revenue = order_group.get('amount_total')
            aov = 0
            if order_count > 0:
                aov = revenue / order_count
            self.report_line_detail.create({
                'store': domain,
                'order_count': order_count,
                'revenue': revenue,
                'report_id': self.id,
                'aov': aov,
            })
            total_revenue += revenue
            total_order += order_count
        return total_revenue, total_order

    def get_form_view_store_dashboard_report(self):
        view_id = self.env.ref('asiup_report_xlsx.sale_order_line_store_report_wizard').id
        record = self.create_record_form_open_view()
        record.name = 'DashBoard'
        record.get_report_store()
        return {
            'name': 'Store',
            'view_type': 'form',
            'views': [(view_id, 'form')],
            'res_model': 'report.order.line.store.wizard',
            'view_id': view_id,
            'type': 'ir.actions.act_window',
            'res_id': record.id,
        }

    def get_form_view_product_dashboard_report(self):
        view_id = self.env.ref('asiup_report_xlsx.sale_order_line_store_report_wizard').id
        record = self.create_record_form_open_view()
        record.write({
            'is_product_report': True,
            'name': 'DashBoard'
        })
        record.get_report_store()
        return {
            'name': 'Product',
            'view_type': 'form',
            'views': [(view_id, 'form')],
            'res_model': 'report.order.line.store.wizard',
            'view_id': view_id,
            'type': 'ir.actions.act_window',
            'res_id': record.id,
        }


class OrderStoreLine(models.TransientModel):
    _name = "report.store.order.line"
    _description = "Wizard to describe order by store"
    _order = 'revenue desc'

    report_id = fields.Many2one('report.order.line.store.wizard', ondelete="cascade")
    store_woo = fields.Many2one('woo.instance.ept')
    store_shopbase = fields.Many2one('store.shopbase')
    store = fields.Char(string='Store')
    order_count = fields.Integer(string='Total Order')
    revenue = fields.Float(string='Revenue', digits=(22, 2))
    product_count = fields.Integer(string='Total Product')
    aov = fields.Float(string='AOV', digits=(22, 2))


class OrderLineProductLine(models.TransientModel):
    _name = "report.product.order.line"
    _description = "Wizard to describe product by order"
    _order = 'revenue desc'

    report_id = fields.Many2one('report.order.line.store.wizard', ondelete="cascade")
    store = fields.Char('Store')
    order_count = fields.Float('Total Order')
    revenue = fields.Float(string='Revenue', digits=(22, 2))
    product_count = fields.Integer(string='Total Product')
    product_label = fields.Char(string='Product')
    aov = fields.Float(string='AOV', digits=(22, 2))
