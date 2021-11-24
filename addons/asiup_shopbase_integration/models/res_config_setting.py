# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, tools
import requests
import json
from odoo.exceptions import UserError


class InheritResCompany(models.Model):
    _inherit = 'res.company'

    trackingmore_api_key = fields.Char('Trackingmore API Key')
    api_key_17track = fields.Char('17Track API Key')
    url_17track_register = fields.Char('Url 17Track Register')
    url_trackingmore_register = fields.Char('Url TrackingMore Register')
    max_amount = fields.Float(string='Order Max Amount', default=150)
    day_of_duplicate = fields.Integer(string='Day Of Duplicate', default=2)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    trackingmore_api_key = fields.Char('Trackingmore API Key')
    api_key_17track = fields.Char('17Track API Key')
    url_17track_register = fields.Char('Url 17Track Register')
    url_trackingmore_register = fields.Char('Url TrackingMore Register')
    max_amount = fields.Float(string='Order Max Amount')
    day_of_duplicate = fields.Integer(string='Day Of Duplicate')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        company = self.env.user.company_id
        res['trackingmore_api_key'] = company.trackingmore_api_key or ''
        res['api_key_17track'] = company.api_key_17track or ''
        res['url_17track_register'] = company.url_17track_register or ''
        res['url_trackingmore_register'] = company.url_trackingmore_register or ''
        res['max_amount'] = company.max_amount or ''
        res['day_of_duplicate'] = company.day_of_duplicate or ''
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        company = self.env.user.company_id
        company.sudo().write({
            'trackingmore_api_key': self.trackingmore_api_key or '',
            'api_key_17track': self.api_key_17track or '',
            'url_trackingmore_register': self.url_trackingmore_register or '',
            'url_17track_register': self.url_17track_register or '',
            'max_amount': self.max_amount or '',
            'day_of_duplicate': self.day_of_duplicate or ''
        })
        if self.url_17track_register and self.api_key_17track:
            self.check_apikey_17track()

    def check_apikey_17track(self):
        headers = {
            "Content-Type": "application/json",
            "17token": self.api_key_17track}
        response = requests.post(self.url_17track_register, headers=headers,
                                 data=json.dumps([{}])).json()
        if response.get('code') != 0:
            raise UserError(_('API Key not valid'))
