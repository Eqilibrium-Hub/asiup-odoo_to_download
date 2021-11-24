from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger("Update Price Woo")


class ExportProductPrice(models.TransientModel):
    _name = 'export.product.price.wizard'

    woo_store_ids = fields.Many2many('woo.instance.ept', string='Woo Store')
    shopbase_store_ids = fields.Many2many('store.shopbase', string='ShopBase Store')
    lst_price = fields.Float(string='Sale Price', required=True)
    compare_price = fields.Float(string='Compare Price', required=True)

    def update_product_variant_price(self, active_variant_ids):
        active_variant_ids.write({'lst_price': self.lst_price if self.lst_price else 0,
                                  'compare_price': self.compare_price if self.compare_price else 0})

    def update_shopbase_variants_price(self, active_variant_ids):
        product_variants = self.env['product.variant.store'].search(
            [('product_variant_id', 'in', active_variant_ids.ids), ('shopbase_store_id', 'in', self.shopbase_store_ids.ids)])
        if not product_variants:
            return False
        product_variants.write({
            'lst_price': self.lst_price,
            'compare_price': self.compare_price
        })

    def update_variant_price_to_store(self):
        if self.lst_price and self.compare_price and self.lst_price >= self.compare_price:
            raise ValidationError(_('Compare price must be greater than sale price!'))
        active_variant_ids = self.env['product.product'].search([('id', 'in', self._context.get('active_ids'))])
        self.update_product_variant_price(active_variant_ids)
        if self.shopbase_store_ids:
            self.update_shopbase_variants_price(active_variant_ids)
        if self.woo_store_ids:
            self.update_woo_variants_price(active_variant_ids)

    def update_woo_variants_price(self, active_variant_ids):
        woo_variant_obj = self.env['woo.product.product.ept']
        woo_variants = woo_variant_obj.search(
            [('product_id', 'in', active_variant_ids.ids), ('woo_instance_id', 'in', self.woo_store_ids.ids)])
        if not woo_variants:
            return False
        woo_variants.write({
            'regular_price': self.compare_price,
            'sale_price': self.lst_price,
        })
        woo_tmpl_ids = woo_variants.mapped(lambda x: x.woo_template_id)
        self.update_woo_product_price(woo_tmpl_ids.ids)

    def update_woo_product_price(self, woo_tmpl_ids):
        export_product_model = self.env['woo.process.import.export']
        export_product = export_product_model.with_context(process='export_products', active_ids=woo_tmpl_ids).create({
            'woo_basic_detail': True,
            'woo_is_set_image': True,
            'woo_is_set_price': True,
            'woo_publish': 'publish'
        })
        export_product.update_products()
