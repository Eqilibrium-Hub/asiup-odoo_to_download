from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from random import randint


class ProductCategory(models.Model):
    _inherit = "product.category"

    product_category_code = fields.Char(string='Code')
    active = fields.Boolean(string='Active', default=True, compute='_compute_active_product_category', store=True)
    parent_id = fields.Many2one('product.category', 'Parent Category', index=True, ondelete='cascade',
                                domain="['!',('id', 'child_of', 1)]")

    def _compute_active_product_category(self):
        for category in self:
            if category.id in self.env['product.category'].search([('id', 'child_of', 1)]).ids:
                category.active = False
            else:
                category.active = True


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def default_get(self, fields):
        res = super(ProductTemplate, self).default_get(fields)
        res['type'] = 'product'
        return res

    product_label = fields.Char(string='Label', compute='compute_product_label', store=True)
    product_template_code = fields.Char(string='Code')
    product_category_code = fields.Char(related='categ_id.product_category_code')
    tag_ids = fields.Many2many('product.tags', string='Tags')
    taxes_id = fields.Many2many('account.tax', 'product_taxes_rel', 'prod_id', 'tax_id',
                                help="Default taxes used when selling the product.", string='Customer Taxes',
                                domain=[('type_tax_use', '=', 'sale')], default=None)
    description_sale = fields.Html()

    def compute_product_label(self):
        for product in self:
            if not product.name:
                product.product_label = False
                continue
            product.product_label = product.name.split('-')[0].split('–')[0].strip()

    def update_product_variant_of_set(self):
        for variant in self.product_variant_ids:
            if not variant.is_product_set:
                continue
            variant.update_product_from_set()

    def _create_variant_ids(self):
        res = super(ProductTemplate, self)._create_variant_ids()
        self.update_product_variant_of_set()
        return res


class ProductProduct(models.Model):
    _inherit = "product.product"

    is_product_set = fields.Boolean(string='Is Product Set', compute='_check_is_product_set')
    set_product_ids = fields.One2many('product.product.set', 'product_id', string='List Product')
    product_sku = fields.Char(string='SKU', compute='_get_product_sku', store=True)
    qty_per_sku = fields.Integer(string='Qty Per SKU', compute='_get_qty_product_per_sku', store=True)
    compare_price = fields.Float(string='Compare Price')

    _sql_constraints = [
        ("product_sku_uniq", "unique(product_sku)", "Product sku must be unique")
    ]

    def get_product_attribute_code(self):
        code = ''
        set_code = False
        for attribute_value in self.product_template_attribute_value_ids:
            attribute_code = attribute_value.product_attribute_value_id.code
            is_attribute_set = attribute_value.product_attribute_value_id.is_att_set
            if not attribute_code and not is_attribute_set:
                return False, False
            if not is_attribute_set:
                code += attribute_code
                continue
            attribute_value_ids = attribute_value.product_attribute_value_id.attribute_set_id.attribute_value_ids
            for attribute_value in attribute_value_ids:
                if not attribute_value.code:
                    return False, False
                code += attribute_value.code
            if not set_code:
                set_code = 'S' + str(len(attribute_value_ids.ids)) if not set_code else set_code
        return code, set_code or 'S1'

    @api.depends("set_product_ids")
    def _get_qty_product_per_sku(self):
        for product in self:
            if product.is_product_set:
                product.qty_per_sku = len(product.set_product_ids)
            else:
                product.qty_per_sku = 1

    def get_product_code(self):
        product_category_code = self.product_tmpl_id.product_category_code or ''
        if not product_category_code:
            return False
        product_code = self.product_tmpl_id.product_template_code or ''
        if not product_code:
            return False
        code, set_code = self.get_product_attribute_code()
        if not code or not set_code:
            return False
        return (product_category_code + product_code + code + set_code).replace(' ', '')

    @api.depends("product_tmpl_id.product_template_code", "product_tmpl_id.product_category_code",
                 "product_template_attribute_value_ids.product_attribute_value_id.code",
                 "product_template_attribute_value_ids.product_attribute_value_id.attribute_set_id",
                 "product_template_attribute_value_ids.product_attribute_value_id.attribute_set_id.attribute_value_ids",
                 "type", "default_code")
    def _get_product_sku(self):
        for product in self:
            product_code = product.get_product_code()
            default_code = product.default_code
            product.product_sku = product_code or default_code or False
            if product_code:
                product.default_code = product_code

    def _check_is_product_set_line(self):
        if not self.product_template_attribute_value_ids:
            return False
        if any([line.product_attribute_value_id.is_att_set for line in self.product_template_attribute_value_ids]):
            return True
        return False

    @api.depends("product_template_attribute_value_ids",
                 "product_template_attribute_value_ids.product_attribute_value_id",
                 "product_template_attribute_value_ids.product_attribute_value_id.is_att_set")
    def _check_is_product_set(self):
        for rec in self:
            rec.is_product_set = rec._check_is_product_set_line()

    def update_product_from_set(self):
        """
        Combine each attribute in the set list with the attribute list that is not a set together to
        find the corresponding product.
        """
        product = self.product_tmpl_id.product_variant_ids.filtered(lambda t: not t.is_product_set)
        list_product_of_set = []
        attr_not_set, attr_is_set = self.get_list_attr_value()
        if not attr_not_set or not attr_is_set:
            return False
        for line in attr_is_set:
            product_of_set = attr_not_set + line
            product_id = product.filtered(lambda p: p.product_template_attribute_value_ids == product_of_set)
            if not product_id:
                continue
            list_product_of_set.append(product_id)
        self.create_product_variant_of_set_rel(list_product_of_set)

    def create_product_variant_of_set_rel(self, list_product_of_set):
        if not list_product_of_set:
            return False

        self.set_product_ids.unlink()
        for rec in list_product_of_set:
            self.env['product.product.set'].create({
                'product_id': self.id,
                'root_product_id': rec.id
            })

    def get_list_attr_value(self):
        """
        Categorize attributes from the product's attribute list into 2 types: set and not set.
        Return one recordset of product not set and one list of product is set.
        """
        product_att_obj = self.env['product.template.attribute.value']
        attr_not_set = False
        attr_is_set = []
        for attr in self.product_template_attribute_value_ids:
            attr_set = attr.product_attribute_value_id.attribute_set_id
            if not attr_set:
                product_att_id = product_att_obj.search([('product_tmpl_id', '=', self.product_tmpl_id.id),
                                                         ('product_attribute_value_id', '=',
                                                          attr.product_attribute_value_id.id),
                                                         ('attribute_id', '=', attr.attribute_id.id)])
                if product_att_id:
                    attr_not_set = product_att_id if not attr_not_set else attr_not_set + product_att_id
                continue

            for line in attr_set.attribute_value_ids:
                product_att_id = product_att_obj.search([('product_tmpl_id', '=', self.product_tmpl_id.id),
                                                         ('product_attribute_value_id', '=', line.id),
                                                         ('attribute_id', '=', attr_set.product_attribute_id.id)])
                if product_att_id:
                    attr_is_set.append(product_att_id)
        return attr_not_set, attr_is_set


class ProductProductSet(models.Model):
    _name = "product.product.set"
    _description = "Product Set"

    product_id = fields.Many2one('product.product', string='Product')
    root_product_id = fields.Many2one('product.product', string='Root Product')
    product_sku = fields.Char(related='product_id.product_sku', string='Product SKU')


class ProductTags(models.Model):
    _name = 'product.tags'
    _description = 'Product Tags'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string="Tag Name", required="1")
    color = fields.Integer(string="Color Index", default=_get_default_color)
    active = fields.Boolean(default=True)
