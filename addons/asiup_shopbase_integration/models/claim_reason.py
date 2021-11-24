from odoo import models, fields, api, _
from random import randint


class ClaimReason(models.Model):
    _name = 'asiup.claim.reason'

    name = fields.Char('Reason')


class ProductShippingProblem(models.Model):
    _name = 'asiup.product.shipping.problem'

    def _get_default_color(self):
        return 9

    color = fields.Integer(string="Color", default=_get_default_color)
    name = fields.Char()
