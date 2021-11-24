# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError, UserError
from odoo import models, fields, api, _
from datetime import datetime


class PurchaseQuotation(models.Model):
    _name = 'purchase.quotation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Asiup Quotation'
    _rec_name = 'name'
    _order = 'id desc,name'

    name = fields.Char(default='Draft')
    supplier = fields.Many2one('res.partner', string='Supplier')
    product_label = fields.Many2one('asiup.product.label', string='Label')
    date_version = fields.Datetime(string='Date Version', default=fields.Datetime.now())
    pack_price_ids = fields.One2many('purchase.price.line', 'quotation_id', string='Set Price')
    state = fields.Selection([('draft', u'Draft'), ('confirm', u'Confirm'),
                              ('cancel', u'Cancel')], default='draft', string='Status', readonly=True,
                             tracking=True, copy=False)
    note = fields.Char(string='Note')

    def action_confirm(self):
        self.ensure_one()
        self.name = self.product_label.name + ' - ' + self.supplier.name + ' - ' + self.date_version.strftime('%Y-%m-%d %H:%M')
        self.state = 'confirm'
        self.create_suppler_price_list()

    def create_suppler_price_list(self):
        price_obj = self.env['supplier.price.list']
        for line in self.pack_price_ids:
            for sku_id in line.sku_ids:
                product = self.env['product.product'].search([('product_sku', '=', sku_id.name)])
                price_obj.create({
                    'quotation_id': self.id,
                    'price': product.price,
                    'product_id': product.id,
                    'name': product.product_label + ' - ' + self.supplier.name + ' - ' + self.date_version.strftime('%Y-%m-%d %H:%M')
                })

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancel'

    # def unlink(self):
    #     for record in self:
    #         if record.state != 'draft':
    #             raise ValidationError(_('Only delete record is Draft!'))
    #     return super(PurchaseQuotation, self).unlink()


class PurchasePackPrice(models.Model):
    _name = 'purchase.price.line'
    _description = 'Purchase Set Line'

    sku_ids = fields.Many2many('product.sku', string='SKU', require=True)
    price = fields.Float(string='Price', require=True)
    quotation_id = fields.Many2one('purchase.quotation', string='Quotation')

    @api.onchange('sku_ids')
    def domain_product_select(self):
        sku_ids = self.env['product.sku'].search([('product_label', '=', self.quotation_id.product_label.name)])
        return {'domain': {'sku_ids': [('id', 'in', sku_ids.ids)]}}


class SupplierPriceLine(models.Model):
    _name = 'supplier.price.list'
    _description = 'Purchase Price Listing'
    _rec_name = 'name'

    supplier = fields.Many2one('res.partner', string='Supplier', related='quotation_id.supplier', store=True)
    price = fields.Float(string='Price')
    quotation_id = fields.Many2one('purchase.quotation', string='Quotation', ondelete="cascade")
    date_version = fields.Datetime(string='Date Version', related='quotation_id.date_version', store=True)
    product_id = fields.Many2one('product.product', string='Product Variant')
    name = fields.Char(string='Name')
