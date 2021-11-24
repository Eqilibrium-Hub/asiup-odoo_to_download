from odoo import models, fields, api, _


class PurchaseProduct(models.Model):
    _inherit = 'product.product'

    supplier_price_list = fields.One2many('supplier.price.list', 'product_id', string='Supplier Price')

    def create(self, vals):
        res = super(PurchaseProduct, self).create(vals)
        sku_exist = self.env['product.sku'].search([('name', '=', res.product_sku)])
        if not sku_exist:
            self.env['product.sku'].create({
                'name': res.product_sku,
                'product_variant': res.id
            })
        return res


class ProductSKU(models.Model):
    _name = 'product.sku'

    name = fields.Char(string='SKU')
    product_variant = fields.Many2one('product.product')
    product_label = fields.Char(related='product_variant.product_label', store=True)

    def init(self):
        product_lst = self.env['product.product'].search([])
        for product in product_lst:
            sku_exist = self.search([('name', '=', product.product_sku)])
            if sku_exist:
                continue
            self.create({
                'name': product.product_sku,
                'product_variant': product.id,
            })
