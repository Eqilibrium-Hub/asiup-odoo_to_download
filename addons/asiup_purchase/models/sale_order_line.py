from odoo import models, fields, api, _
import random
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    quotation_detail = fields.Many2one('supplier.price.list', string='Quotation')

    def confirm_supplier_product_cost(self):
        order_line_ids = self.search([('id', 'in', self._context.get('active_ids'))])
        for order_line_id in order_line_ids:
            if order_line_id.quote_status == 'draft':
                order_line_id.quote_status = 'confirm'

    def set_price_lst_notfound(self):
        self.write({
            'product_cost': 0,
            'price_unit': 0
        })

    def select_supplier_wizard_form(self):
        form_view_id = self.env.ref("asiup_purchase.quotation_message_wizard").id
        order_line_ids = self._context.get('active_ids')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Supplier',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'quotation.message.wizard',
            'views': [(form_view_id, 'form')],
            'target': 'new',
            'context': {'default_order_line_ids': order_line_ids}
        }


class QuotationMessageWizard(models.TransientModel):
    _name = "quotation.message.wizard"

    supplier = fields.Many2one('res.partner', string='Supplier')
    order_line_ids = fields.Many2many('sale.order.line')

    def mapping_order_line_supplier(self):
        self.order_line_ids.supplier = self.supplier.id
        self.order_line_ids.quote_status = 'draft'
        for order_line in self.order_line_ids:
            if not order_line.ffm_date:
                order_line.set_price_lst_notfound()
                continue
            supplier_price = order_line.product_id.supplier_price_list.filtered(
                lambda r: r.supplier == self.supplier and r.date_version <= order_line.ffm_date)
            if not supplier_price:
                order_line.set_price_lst_notfound()
                continue
            supplier_price.sorted(key=lambda x: (x.date_version, x.quotation_id.id))
            order_line.write({
                'quotation_detail': supplier_price[0],
                'product_cost': supplier_price[0].price * order_line.product_uom_qty,
                'price_unit': supplier_price[0].price,
            })
