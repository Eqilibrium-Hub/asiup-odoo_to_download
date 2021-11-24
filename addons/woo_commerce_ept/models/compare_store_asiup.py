from odoo import fields, models, api, _


class OrderStatus(models.Model):
    _name = "order.status"
    _description = "Order Status"
    _rec_name = 'name'
    _order = 'id'

    name = fields.Char('Status')
    code = fields.Char('Code')

    def init(self):
        order_status = [('pending_payment', u'Pending Payment'),
                        ('processing', u'Processing'),
                        ('on_hold', u'On Hold'),
                        ('pending', u'Pending'),
                        ('cancelled', u'Cancelled'),
                        ('partially_cancelled', u'Partially Cancelled'),
                        ('failed', u'Failed'),
                        ('delivered', u'Delivered'),
                        ('reship', u'Reship'),
                        ('partially_reship', u'Partially Reship')]
        if self.env['order.status'].search([]):
            self.env['order.status'].search([]).unlink()
        for status in order_status:
            self.env['order.status'].create({
                'name': status[1],
                'code': status[0],
            })


class ProductLabel(models.Model):
    _name = "asiup.product.label"

    name = fields.Char()

    def init(self):
        product_tmpl = self.env['product.template']
        product_label = self.env['asiup.product.label'].search([])
        if product_label:
            product_label.unlink()
        for product in product_tmpl.search([('type', '=', 'product')]):
            name = product.name.split('-')[0].split('–')[0].strip()
            exist_label = product_label.search([('name', '=', name)])
            if exist_label:
                continue
            self.create({
                'name': name
            })


class AsiupStoreDomain(models.Model):
    _name = "store.domain"
    _description = "Store Domain"
    _rec_name = 'primary_domain'

    primary_domain = fields.Char(string='Store', store=True)
    woo_store_id = fields.Many2one('woo.instance.ept', string='Woo Store')
    shopbase_store_id = fields.Many2one('store.shopbase', string='Shopbase Store')

    def init(self):
        domain = self.env['store.domain'].search([])
        if domain:
            domain.unlink()
        for store in list(self.env['woo.instance.ept'].search([])) + list(self.env['store.shopbase'].search([])):
            self.env['store.domain'].create({
                'primary_domain': store.primary_domain,
                'woo_store_id': store.id if store._name == 'woo.instance.ept' else False,
                'shopbase_store_id': store.id if store._name == 'store.shopbase' else False
            })

    @api.depends('woo_store_id.primary_domain', 'shopbase_store_id.primary_domain')
    def _compute_name_store_domain(self):
        for rec in self:
            rec.primary_domain = rec.woo_store_id.primary_domain if rec.woo_store_id else rec.shopbase_store_id.primary_domain


class WooInstanceEpt(models.Model):
    _inherit = "woo.instance.ept"

    def create(self, vals):
        res = super(WooInstanceEpt, self).create(vals)
        self.env['store.domain'].create({
            'woo_store_id': res.id
        })
        return res


class StoreShopbase(models.Model):
    _inherit = 'store.shopbase'

    def create(self, vals):
        res = super(StoreShopbase, self).create(vals)
        self.env['store.domain'].create({
            'shopbase_store_id': res.id
        })
        return res
