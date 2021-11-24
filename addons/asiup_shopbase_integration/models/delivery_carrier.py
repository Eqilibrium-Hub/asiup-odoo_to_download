# -*- coding: utf-8 -*-
from odoo import models, fields


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    shopbase_code = fields.Char(help="Shopbase Delivery Code")
