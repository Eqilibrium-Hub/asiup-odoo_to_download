# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class UpdateProductPriceWizard(models.TransientModel):
    _name = "update.product.price.wizard"
    _description = 'Update Product Price Wizard'

    product_id = fields.Many2one('product.template', string='Product')
    is_update_all = fields.Boolean(string='Update All')
    product_page_ids = fields.Many2many('product.store', string='Apply For Product Page')
    variant_ids = fields.One2many('update.product.price.line', 'update_product_wizard_id', string='Variants')

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.variant_ids = False
        vals =[(0, 0, {
            'update_product_wizard_id': self.id,
            'variant_id': line.id,
            'variant_sku': line.product_sku,
            'lst_price': line.lst_price,
            'compare_price': self.product_id.compare_price
        }) for line in self.product_id.product_variant_ids]
        self.variant_ids = vals

    def update_product_price(self):
        if not self.is_update_all and not self.product_page_ids:
            raise ValueError("You must choose at least one store!")
        product_page_ids = self.product_page_ids
        if self.is_update_all:
            product_page_ids = self.env['product.store'].search([('product_id', '=', self.product_id.id)])
        product_variant_store_obj = self.env['product.variant.store']
        variant_store_ids = product_variant_store_obj.search([('product_store_id', 'in', product_page_ids.ids)])
        for variant in self.variant_ids:
            variant_ids = variant_store_ids.filtered(lambda p: p.product_variant_id.id == variant.variant_id.id)
            variant_ids.write({'lst_price': variant.lst_price, 'compare_price': variant.compare_price})


class UpdateProductPriceLine(models.TransientModel):
    _name = "update.product.price.line"
    _description = 'Update Product Price Line'

    update_product_wizard_id = fields.Many2one('update.product.price.wizard', string='Update Product Wizard')
    variant_id = fields.Many2one('product.product', string='Variant')
    variant_sku = fields.Char(related='variant_id.product_sku', string='SKU')
    product_template_attribute_value_ids = fields.Many2many(related='variant_id.product_template_attribute_value_ids',
                                                            string='Attribute Values')
    lst_price = fields.Float(string='Price')
    compare_price = fields.Float(string='Compare Price')