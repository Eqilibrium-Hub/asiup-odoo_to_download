# -*- coding: utf-8 -*-
import ast
import requests
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_shopbase_customer = fields.Boolean(string="Is Shopbase Customer?", default=False)
    shopbase_store_id = fields.Many2one("store.shopbase", string="Shopbase Store")
    shopbase_customer_id = fields.Char(readonly=True, string='Shopbase Customer ID')
    property_account_receivable_id = fields.Many2one('account.account', company_dependent=True,
                                                     string="Account Receivable",
                                                     domain="[('internal_type', '=', 'receivable'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                     help="This account will be used instead of the default one as the receivable account for the current partner",
                                                     required=False)

    property_account_payable_id = fields.Many2one('account.account', company_dependent=True,
                                                  string="Account Payable",
                                                  domain="[('internal_type', '=', 'payable'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
                                                  help="This account will be used instead of the default one as the payable account for the current partner",
                                                  required=False)
    # is_edit_display_name = fields.Boolean(compute='compute_edit_display_name', store=True)

    def search_shopbase_partner(self, shopbase_customer_id, shopbase_store_id):
        partner_id = self.search([("shopbase_customer_id", "=", shopbase_customer_id),
                                  ("shopbase_store_id", "=", shopbase_store_id)], limit=1)
        if partner_id:
            return partner_id
        return False

    # def compute_edit_display_name(self):
    #     for rec in self:
    #         rec.write({
    #             'name': rec.name,
    #             'is_edit_display_name' : True
    #         })

    def _get_name(self):
        name = super(ResPartner, self)._get_name()
        return name

    def create_or_update_state(self, country_code, state_name_or_code, zip_code, country_obj=False):
        """
        Modified the below method to set state from the api of zippopotam.
        """
        if not country_obj:
            country = self.get_country(country_code)
        else:
            country = country_obj
        state = self.env['res.country.state'].search(['|', ('name', '=ilike', state_name_or_code),
                                                      ('code', '=ilike', state_name_or_code),
                                                      ('country_id', '=', country.id)], limit=1)

        if not state and zip_code:
            state = self.get_state_from_api(country_code, zip_code, country)
        return state

    def get_country(self, country_name_or_code):
        country = self.env['res.country'].search(['|', ('code', '=ilike', country_name_or_code),
                                                  ('name', '=ilike', country_name_or_code)], limit=1)
        return country

    def get_state_from_api(self, country_code, zip_code, country):
        """
        This method tries to find state from country and zip code from zippopotam api.
        @param country_code: Code of country.
        @param zip_code: Zip code.
        @param country: Record of Country.
        @return: Record of state if found, otherwise object.
        """
        state_obj = state = self.env['res.country.state']
        country_obj = self.env['res.country']
        try:
            url = 'https://api.zippopotam.us/' + country_code + '/' + zip_code.split('-')[0]
            response = requests.get(url)
            response = ast.literal_eval(response.content.decode('utf-8'))
        except:
            return state_obj
        if response:
            if not country:
                self.get_country(response.get('country abbreviation'))
            if not country:
                self.get_country(response.get('country'))
            if not country:
                country = country_obj.create({
                    'name': response.get('country'),
                    'code': response.get('country abbreviation')})

            state = state_obj.search(['|', ('name', '=', response.get('places')[0].get('state')),
                                      ('code', '=', response.get('places')[0].get('state abbreviation')),
                                      ('country_id', '=', country.id)], limit=1)
            if not state:
                state = state_obj.create({
                    'name': response.get('places')[0].get('state'),
                    'code': response.get('places')[0].get('state abbreviation'),
                    'country_id': country.id})
        return state

    def shopbase_prepare_partner_vals(self, vals):
        """
        This method used to prepare a partner vals.
        @param : self,vals
        @return: partner_vals
        """
        partner_obj = self.env["res.partner"]

        first_name = vals.get("first_name")
        last_name = vals.get("last_name")
        name = f"{first_name} {last_name}"

        zipcode = vals.get("zip")
        state_code = vals.get("province_code")
        country_code = vals.get("country_code")
        country = partner_obj.get_country(country_code)

        state = partner_obj.create_or_update_state(country_code, state_code, zipcode, country)

        partner_vals = {
            "email": vals.get("email") or False,
            "name": name,
            "phone": vals.get("phone"),
            "street": vals.get("address1"),
            "street2": vals.get("address2"),
            "city": vals.get("city"),
            "zip": zipcode,
            "state_id": state and state.id or False,
            "country_id": country and country.id or False,
            "is_company": False
        }
        return partner_vals

    def search_partner_by_email(self, email):
        partner = self.search([('email', '=ilike', email)], limit=1)
        return partner

    def shopbase_create_contact_partner(self, vals, store):
        """
        This method is used to create a contact type customer.
        """
        partner_obj = self.env["res.partner"]
        shopbase_store_id = store.id
        shopbase_customer_id = vals.get("id", False)
        first_name = vals.get("first_name", "")
        last_name = vals.get("last_name", "")
        email = vals.get("email", "")

        if not first_name and not last_name and not email:
            return False

        name = ""
        if first_name:
            name = f"{first_name}"
        if last_name:
            name += f"{last_name}" if name else f"{last_name}"
        if not name and email:
            name = email

        partner = self.search_shopbase_partner(shopbase_customer_id, shopbase_store_id)
        if partner:
            return partner
        if email:
            partner = partner_obj.search_partner_by_email(email)
            if partner:
                partner.write({
                    "is_shopbase_customer": True,
                    "shopbase_customer_id": shopbase_customer_id,
                    "shopbase_store_id": shopbase_store_id})
                return partner

        partner_vals = dict()
        if vals.get("default_address"):
            partner_vals = self.shopbase_prepare_partner_vals(vals.get("default_address", {}))
        partner_vals.update({
            "name": name,
            "email": email,
            "customer_rank": 1,
            "is_shopbase_customer": True,
            "type": "contact",
            "shopbase_customer_id": shopbase_customer_id,
            "shopbase_store_id": shopbase_store_id})
        partner = partner_obj.create(partner_vals)
        return partner

    def _find_partner(self, vals, key_list=[], extra_domain=[]):
        """
        This function find the partner based on domain.
        This function map the keys of the key_list with the dictionary and create domain and
        if you have given the extra_domain, then it will merge with _domain (i.e _domain = _domain + extra_domain).
        @requires: vals, key_list
        @param vals: i.e {'name': 'emipro', 'street': 'address', 'street2': 'address', 'email': 'test@test.com'...}
        @param key_list: i.e ['name', 'street', 'street2', 'email',...]
        @param extra_domain: This domain for you can pass your own custom domain.
        i.e [('name', '!=', 'test')...]
        @return: partner object or False
        """
        if key_list and vals:
            _domain = [] + extra_domain
            for key in key_list:
                if not vals.get(key):
                    continue
                if (key in vals) and isinstance(vals.get(key), str):
                    _domain.append((key, '=ilike', vals.get(key)))
                else:
                    _domain.append((key, '=', vals.get(key)))
            partner = self.search(_domain, limit=1) if _domain else False
            return partner
        return False

    @api.model
    def shopbase_create_or_update_address(self, shopbase_customer_data, parent_partner, partner_type="contact"):
        """
        Creates or updates existing partner from Shopbase customer's data.
        """
        partner_obj = self.env["res.partner"]

        first_name = shopbase_customer_data.get("first_name")
        last_name = shopbase_customer_data.get("last_name")

        if not first_name and not last_name:
            return False

        company_name = shopbase_customer_data.get("company")
        partner_vals = self.shopbase_prepare_partner_vals(shopbase_customer_data)
        address_key_list = ["name", "street", "street2", "city", "zip", "phone", "state_id", "country_id"]

        if company_name:
            address_key_list.append("company_name")
            partner_vals.update({"company_name": company_name})

        partner = self._find_partner(partner_vals, address_key_list,
                                     [("parent_id", "=", parent_partner.id), ("type", "=", partner_type)])

        if not partner:
            partner = self._find_partner(partner_vals, address_key_list, [("parent_id", "=", parent_partner.id)])
        if not partner:
            partner = self._find_partner(partner_vals, address_key_list)

            if partner and not partner.child_ids and partner_type == 'invoice':
                partner.write({"type": partner_type})
        if partner:
            return partner

        partner_vals.update({"type": partner_type, "parent_id": parent_partner.id})
        partner = partner_obj.create(partner_vals)

        company_name and partner.write({"company_name": company_name})
        return partner

    def create_or_update_customer(self, vals, store):
        partner = vals.get("customer") and self.shopbase_create_contact_partner(vals.get("customer"), store)
        if not partner:
            return False, False, False

        if partner.parent_id:
            partner = partner.parent_id

        invoice_address = vals.get("billing_address") and self.shopbase_create_or_update_address(
            vals.get("billing_address"), partner, "invoice") or partner

        delivery_address = vals.get("shipping_address") and self.shopbase_create_or_update_address(
            vals.get("shipping_address"), partner, "delivery") or partner

        if not partner and invoice_address and delivery_address:
            partner = invoice_address
        if not partner and not delivery_address and invoice_address:
            partner = invoice_address
            delivery_address = invoice_address
        if not partner and not invoice_address and delivery_address:
            partner = delivery_address
            invoice_address = delivery_address

        return partner, delivery_address, invoice_address

    @api.model
    def create(self, vals):
        res = super(ResPartner, self).create(vals)
        res._onchange_country_id()
        return res


class ExtendAddressShipping(models.Model):
    _name = 'asiup.extend.address.shipping'

    zip = fields.Char('Zip')
    city = fields.Char('City')
    state_id = fields.Many2one('res.country.state')
    country_id = fields.Many2one('res.country')
