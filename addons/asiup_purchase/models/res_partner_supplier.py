from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    capacity = fields.Integer(string='Capacity', default=0)
    sale_order_ffm_count = fields.Integer(string='SO Count', compute='_compute_capacity_order', store=True)
    # capacity_so_ffm = fields.Char(string='Supplier Capacity', compute='_compute_capacity_order', store=True)
    sale_order_line_ids = fields.One2many('sale.order.line', 'supplier')

    # @api.depends('sale_order_line_ids', 'sale_order_line_ids.product_uom_qty', 'capacity')
    # def _compute_capacity_order(self):
    #     for rec in self:
    #         rec.sale_order_ffm_count = len(self.env['sale.order.line'].search([('supplier', '=', rec.id)]).filtered(
    #             lambda r: r.fulfillment_status == 'ffm_sent'))
    #         if rec.capacity > 0:
    #             capacity_so_ffm = (rec.sale_order_ffm_count / rec.capacity) * 100
    #         else:
    #             capacity_so_ffm = 0
    #         rec.capacity_so_ffm = str(capacity_so_ffm) + '%'
