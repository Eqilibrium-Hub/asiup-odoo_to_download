from odoo import api, fields, models, _


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    is_att_set = fields.Boolean(string='Is Attribute Set')
    attribute_set_id = fields.Many2one('product.attribute.set', string="Attribute Set")
    code = fields.Char(string='Code')

    @api.onchange('attribute_set_id')
    def _onchange_attribute_set_id(self):
        if self.attribute_set_id:
            self.name = self.attribute_set_id.name

    def write(self, vals):
        res = super(ProductAttributeValue, self).write(vals)
        if vals.get('attribute_set_id'):
            attribute_set = self.env['product.attribute.set'].browse(vals.get('attribute_set_id'))
            attribute_set.with_delay().search_variant_with_attribute()
        return res


class ProductAttributeSet(models.Model):
    _name = "product.attribute.set"
    _description = "Product Attribute Set"

    name = fields.Char(string='Set Name', required=True)
    product_attribute_id = fields.Many2one('product.attribute', string='Product Attribute', required=True)
    attribute_value_ids = fields.Many2many('product.attribute.value', string='Product Attribute Value')

    @api.model
    def create(self, vals):
        res = super(ProductAttributeSet, self).create(vals)
        res.add_set_to_attribute_value()
        return res

    def search_variant_with_attribute(self):
        product_attribute_obj = self.env['product.template.attribute.value']
        product_attribute_ids = product_attribute_obj.search([
            ('attribute_id', '=', self.product_attribute_id.id),
            '|', '|',
            ('product_attribute_value_id.name', '=', self.name),
            ('product_attribute_value_id.name', '=', self.name.lower()),
            ('product_attribute_value_id.name', '=', self.name.upper())])
        product_variant = self.env['product.product'].browse([line for rec in product_attribute_ids
                                                              for line in rec.ptav_product_variant_ids.ids])
        for variant in product_variant:
            variant.update_product_from_set()
        return True

    def add_set_to_attribute_value(self):
        attribute_value_obj = self.env['product.attribute.value']
        if not self.product_attribute_id or not self.attribute_value_ids:
            return False
        already_attribute_value = attribute_value_obj.search([
            ('attribute_id', '=', self.product_attribute_id.id), ('name', '=', self.name)])
        if already_attribute_value:
            return False
        attribute_value_obj.create({
            'attribute_id': self.product_attribute_id.id,
            'name': self.name,
            'attribute_set_id': self.id,
            'is_att_set': True})
        
    def write(self, vals):
        res = super(ProductAttributeSet, self).write(vals)
        if not vals.get("name"):
            return res
        for rec in self:
            attribute_value_ids = rec.env['product.attribute.value'].search([('attribute_set_id', '=', rec.id)])
            attribute_value_ids.write({'name': vals.get("name")})
        return res
