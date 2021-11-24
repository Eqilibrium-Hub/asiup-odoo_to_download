from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import requests
import json
import base64
import hashlib


class ProductTemplate(models.Model):
    _inherit = "product.template"

    shopbase_store_ids = fields.One2many('product.store', 'product_id', string='Shopbase Store')
    product_store_count = fields.Integer(string='Number of Shopbase Product', compute='_compute_product_store')
    compare_price = fields.Float(string='Compare Price')

    @api.depends("shopbase_store_ids")
    def _compute_product_store(self):
        for product in self:
            product.product_store_count = len(product.shopbase_store_ids)

    def action_view_shopbase_product(self):
        self.ensure_one()
        shopbase_product_ids = self.shopbase_store_ids.ids
        action = {
            'name': _('Shopbase Product of %s', self.name),
            'res_model': 'product.store',
            'type': 'ir.actions.act_window',
            'context': {'default_product_id': self.id},
            'domain': [('id', 'in', shopbase_product_ids)],
            'view_mode': 'tree,form',
        }
        return action

    # def open_update_product_price_wizard(self):
    #     self.ensure_one()
    #
    #     action_obj = self.env.ref('asiup_shopbase_integration.action_update_product_price_wizard')
    #     action = action_obj.read([])[0]
    #     context = dict(self._context)
    #     context['default_product_id'] = self.id
    #     action['context'] = context
    #     return action


class ProductProduct(models.Model):
    _inherit = "product.product"

    shopbase_variant_ids = fields.One2many('product.variant.store', 'product_variant_id', string='Shopbase Variants')
    variant_store_count = fields.Integer(string='Number of Shopbase Variant', compute='_compute_variant_store')
    attribute_variant_lst = fields.Char(string='Attribute', compute='compute_attribute_variant_lst', store=True)
    product_label = fields.Char(related="product_tmpl_id.product_label", store=True, string="Label")

    def compute_attribute_variant_lst(self):
        for rec in self:
            rec.attribute_variant_lst = rec.product_template_attribute_value_ids._get_combination_name()

    def name_get(self):
        name_lst = super(ProductProduct, self).name_get()
        return [(name[0], name[1][name[1].find("]") + 1:].strip()) for name in name_lst]

    @api.depends("shopbase_variant_ids")
    def _compute_variant_store(self):
        for product in self:
            product.variant_store_count = len(product.shopbase_variant_ids)

    def action_view_shopbase_variant(self):
        self.ensure_one()
        shopbase_variant_ids = self.shopbase_variant_ids.ids
        action = {
            'name': _('Shopbase Variant of %s', self.name),
            'res_model': 'product.variant.store',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', shopbase_variant_ids)],
            'view_mode': 'tree,form',
        }
        return action

    def _get_product_sku(self):
        res = super(ProductProduct, self)._get_product_sku()
        for rec in self:
            if not rec.product_sku:
                continue
            for variant in rec.shopbase_variant_ids:
                if variant.variant_sku == rec.product_sku:
                    continue
                variant.write({'variant_sku': rec.product_sku})
        return res


class ProductProductStore(models.Model):
    _name = "product.store"
    _rec_name = "product_id"
    _description = "Product Store"

    product_id = fields.Many2one('product.template', string='Product', ondelete='cascade')
    product_variant_ids = fields.One2many('product.variant.store', 'product_store_id', string="Product Variant")
    product_name = fields.Char(related='product_id.name', string='Product Name')

    shopbase_store_id = fields.Many2one('store.shopbase', string='Store', ondelete='cascade')
    shopbase_product_id = fields.Char(string='Shopbase Product ID', readonly=True, copy=False)
    shopbase_product_page = fields.Char(string='Product Page', readonly=True, copy=False)
    shopbase_inventory = fields.Integer(string='Inventory', readonly=True, copy=False)
    continue_selling_over_stock = fields.Boolean(readonly=True, copy=False)
    is_connect_to_shopbase = fields.Boolean(string='Connect Shopbase', readonly=True, copy=False)
    sync_from_shopbase = fields.Boolean(default=False, readonly=True)

    shopbase_image_url = fields.Char(string='Image URL')
    shopbase_image_id = fields.Char(string='Image ID')
    shopbase_image_ids = fields.One2many("product.variant.image.store", "shopbase_template_id")

    _sql_constraints = [
        ("shopbase_product_id_uniq", "unique(shopbase_product_id)", "Shopbase product ID must be unique")
    ]

    def action_view_product_shopbase_web(self):
        shopbase_url = self.shopbase_store_id.shopbase_url + f'/admin/products/{self.shopbase_product_id}'
        return {
            "url": shopbase_url,
            "type": "ir.actions.act_url"
        }

    def _auto_create_product_variant_store(self):
        """
            Create list variant of product when select product template from model connect product shopbase
        """
        valid_product_sku = all([product.product_sku for product in self.product_id.product_variant_ids])
        if not self.sync_from_shopbase and not valid_product_sku:
            raise ValidationError(_('Can"t create shopbase product because There exists product without sku!'))
        vals = [(0, 0, {
            'product_store_id': self.id,
            'product_variant_id': line.id,
            'variant_sku': line.product_sku,
            'lst_price': line.lst_price,
            'compare_price': line.compare_price,
            'sync_from_shopbase': True,
            'shopbase_image_ids': [(0, 0, {
                'shopbase_template_id': self.id,
                'odoo_image_id': rec.id}) for rec in line.ept_image_ids]
        }) for line in self.product_id.product_variant_ids]
        self.product_variant_ids = vals

    @api.model
    def create(self, vals):
        res = super(ProductProductStore, self).create(vals)
        res._auto_create_product_variant_store()
        if not vals.get("sync_from_shopbase"):
            res.with_delay(description='Sync new product to shopbase').sync_new_product_to_shopbase()
        return res

    def process_update_product_variant_image(self):
        for rec in self.product_variant_ids:
            if not rec.shopbase_store_id:
                continue
            if not rec.shopbase_variant_id:
                continue
            image_id = rec.get_image_id()
            if not image_id:
                continue
            vals = {"image_id": image_id}
            rec.sync_update_variant_to_shopbase(rec.shopbase_store_id, rec.shopbase_variant_id, vals)

    def _get_product_option(self):
        """
            Get option of product template when sync new product to shopbase
        """
        options = []
        for line in self.product_id.attribute_line_ids:
            attr = dict()
            attr['name'] = line.attribute_id.name
            attr['values'] = [value.name for value in line.value_ids]
            options.append(attr)
        return options

    def _get_product_variants(self):
        """
            Get variant data of product data when sync new product to shopbase
        """
        list_variant = []
        for line in self.product_variant_ids:
            variant = dict()
            variant['title'] = line.product_variant_id.name or ''
            variant['sku'] = line.variant_sku or ''
            variant['price'] = line.lst_price or ''
            variant['compare_at_price'] = line.compare_price or ''
            position = 1
            for option in line.product_variant_id.product_template_attribute_value_ids:
                variant[f'option{position}'] = option.product_attribute_value_id.name
                position += 1
            list_variant.append(variant)
        return list_variant

    def get_product_data(self):
        """
            Get product data for sync product to shopbase
        """
        data = dict()
        data_detail = dict()
        data_detail['title'] = self.product_id.name or ''
        data_detail['product_type'] = self.product_id.categ_id.name or ''
        data_detail['options'] = self._get_product_option()
        data_detail['tags'] = ','.join([line.name for line in self.product_id.tag_ids]) if self.product_id.tag_ids else ''
        data_detail['body_html'] = self.product_id.description_sale or ''
        data_detail['variants'] = self._get_product_variants()
        data['product'] = data_detail
        return data

    def process_sync_product_to_shopbase_result(self, data):
        """
            After sync product, write shopbase variant id to odoo
        """
        data = data.get("product", {})
        vals = dict()
        vals['shopbase_product_id'] = data.get("id")
        vals['is_connect_to_shopbase'] = True
        self.write(vals)
        variants = data.get("variants", [])
        for variant in variants:
            variant_id = self.product_variant_ids.filtered(lambda t: t.variant_sku == variant.get("sku"))
            if not variant_id:
                continue
            variant_id.write({'shopbase_variant_id': variant.get("id"), 'is_connect_to_shopbase': True})

    def sync_new_product_to_shopbase(self):
        """
            Sync product to shopbase when create new product in odoo.
        """
        shopbase_url, headers = self.shopbase_store_id.get_shopbase_connect_info()
        auth = self.shopbase_store_id.get_authen()
        data = self.get_product_data()
        data = json.dumps(data)
        url = f'{shopbase_url}/admin/products.json'
        try:
            res = requests.post(url, data=data, auth=auth, headers=headers)
            if res.status_code == 200:
                content = res.json()
                self.process_sync_product_to_shopbase_result(content)
                self.process_update_product_variant_image()
            else:
                error_msg = res.content.decode('utf-8') if res.content \
                    else 'Sync new product to shopbase fail with no result!'
                raise ValidationError(_(error_msg))

        except Exception as error_msg:
            raise ValidationError(_(error_msg))

    @api.model
    def sync_product_from_shopbase(self):
        """
            Sync product from shopbase for all store with cron
        """
        shopbase_store = self.env['store.shopbase'].search([])
        if not shopbase_store:
            return False
        for store in shopbase_store:
            self.with_delay(description='Sync product from shopbase for a store').sync_product_from_a_shopbase(store)
        return True

    def sync_product_from_a_shopbase(self, store):
        shopbase_url, headers = store.get_shopbase_connect_info()
        auth = store.get_authen()
        url = f'{shopbase_url}/admin/products.json'
        try:
            res = requests.get(url, auth=auth, headers=headers)
            if res.status_code == 200:
                content = res.json()
                self.process_sync_product(content, store)
            else:
                error_msg = res.content.decode('utf-8') if res.content \
                    else 'Sync customers from shopbase fail with no result!'
                raise ValidationError(_(error_msg))

        except Exception as error_msg:
            raise ValidationError(_(error_msg))

    def create_new_product_attribute(self, options):
        """
            Create new product attribute when sync product from shopbase
        """
        attribute_obj = self.env['product.attribute']
        attribute_dict = {}
        for option in options:
            option_name = option.get("name")
            values = option.get("values")
            already_exist_attribute = attribute_obj.search([('name', '=', option_name)], limit=1)
            if already_exist_attribute:
                already_exist_attribute_name = [line.name for line in already_exist_attribute.value_ids]
                for value in values:
                    value = value
                    if value not in already_exist_attribute_name:
                        self.env['product.attribute.value'].create({
                            'attribute_id': already_exist_attribute.id,
                            'name': value,
                        })
                values_ids = already_exist_attribute.value_ids.filtered(lambda t: t.name in [line for line in values])
                attribute_dict.update({already_exist_attribute: values_ids})
                continue
            new_attribute = attribute_obj.create({
                'name': option_name,
                'value_ids': [(0, 0, {'name': line}) for line in values]
            })
            values_ids = new_attribute.value_ids.filtered(lambda t: t.name in [line for line in values])
            attribute_dict.update({new_attribute: values_ids})

        return attribute_dict

    def process_create_new_product(self, product):
        """
            Create new product template if not exit in odoo when sync from shopbase
        """
        product_name = product.get("title")
        options = product.get("options")
        tags = product.get("tags").split(",")
        body_html = product.get("body_html")
        attribute_dict = self.create_new_product_attribute(options)
        new_product = self.env['product.template'].create({
            'name': product_name,
            'tag_ids': [(0, 0, {'name': tag}) for tag in tags if tag != ''],
            'description_sale': body_html,
            'attribute_line_ids': [(
                0, 0, {'attribute_id': line.id, 'value_ids': attribute_dict[line].ids}) for line in attribute_dict]
        })
        return new_product

    def get_product_image(self, images):
        image_dict = dict()
        for image in images:
            image_id = image.get("id")
            if not image_id:
                continue
            image_dict.update({image_id: image})
        return image_dict

    def process_mapping_variant(self, options, variants, images):
        """
            Create product variant and mapping shopbase id when sync product from shopbase
        """
        product_images = self.get_product_image(images)
        product_attribute_value_obj = self.env['product.template.attribute.value']
        for variant in variants:
            list_attribute = False
            count = 1
            for option in options:
                attribute = variant.get(f'option{count}')
                count += 1
                if not attribute:
                    continue
                product_attribute_value_id = product_attribute_value_obj.search([
                    ('product_attribute_value_id.name', '=', attribute), ('product_tmpl_id', '=', self.product_id.id)])
                if not product_attribute_value_id:
                    continue
                if not list_attribute:
                    list_attribute = product_attribute_value_id
                    continue
                list_attribute += product_attribute_value_id

            if not list_attribute:
                continue
            variant_id = self.product_id.product_variant_ids.filtered(
                lambda p: p.product_template_attribute_value_ids == list_attribute)

            if not variant_id:
                continue
            variant_store = self.product_variant_ids.filtered(lambda p: p.product_variant_id.id == variant_id.id)
            vals = {
                'shopbase_variant_id': variant.get("id"),
                'is_connect_to_shopbase': True,
                'variant_sku': variant.get("sku"),
                'lst_price': variant.get("price")}
            variant_store.with_context(not_sync=True).write(vals)
            image_id = variant.get("image_id")
            image = product_images.get(image_id)
            product_store = self
            self.update_product_images(image, product_store, variant_store)

    def sync_a_product_from_shopbase(self, product, store):
        """
            Process data when sync product from shopbase
        """
        shopbase_product_id = product.get("id")
        store_product_id = self.env['product.store'].search([('shopbase_product_id', '=', shopbase_product_id)])
        if store_product_id:
            return True
        product_name = product.get("title")
        product_id = self.env['product.template'].search([('name', 'ilike', product_name)], limit=1)
        if product_id:
            return True
        new_product = self.process_create_new_product(product)
        if not new_product:
            return False

        vals = {
            'product_id': new_product.id,
            'shopbase_store_id': store.id,
            'shopbase_product_id': shopbase_product_id,
            'sync_from_shopbase': True,
            'is_connect_to_shopbase': True}
        product_store = self.env['product.store'].create(vals)

        variants = product.get("variants")
        options = product.get("options")
        product_images = product.get("images")
        product_store.process_mapping_variant(options, variants, product_images)

    def get_existing_images(self, shopbase_template=False, shopbase_product=False):
        existing_common_images = {}
        if shopbase_product:
            images = shopbase_product.product_variant_id.ept_image_ids
        else:
            images = shopbase_template.product_id.ept_image_ids

        for odoo_image in images:
            if not odoo_image.image:
                continue
            key = hashlib.md5(odoo_image.image).hexdigest()
            if not key:
                continue
            existing_common_images.update({key: odoo_image.id})
        return existing_common_images

    def find_or_create_common_product_image(self, shopbase_template, image, url, shopbase_product):
        shopbase_product_image_obj = self.env["product.variant.image.store"]
        common_product_image_obj = common_product_image = self.env["common.product.image.ept"]

        domain = []
        vals = {"name": shopbase_template.product_id.name, "template_id": shopbase_template.product_id.id, "image": image, "url": url}

        if shopbase_product:
            if not shopbase_product.product_variant_id.image_1920:
                shopbase_product.product_variant_id.image_1920 = image
                common_product_image = shopbase_product.product_variant_id.ept_image_ids.filtered(
                    lambda x: x.image == shopbase_product.product_variant_id.image_1920)
            else:
                vals.update({"product_id": shopbase_product.product_variant_id.id})
            domain.append(("shopbase_variant_id", "=", shopbase_product.id))

        if not shopbase_product and not shopbase_template.product_id.image_1920:
            shopbase_template.product_id.image_1920 = image
            common_product_image = shopbase_template.product_id.ept_image_ids.filtered(
                lambda x: x.image == shopbase_template.product_id.image_1920)
        elif not common_product_image:
            common_product_image = common_product_image_obj.create(vals)

        domain += [("shopbase_template_id", "=", shopbase_template.id), ("odoo_image_id", "=", common_product_image.id)]
        shopbase_product_image = shopbase_product_image_obj.search(domain)
        return shopbase_product_image

    def update_shopbase_variant_image(self, variant_image, product_store, product_variant_store):
        if not variant_image:
            return
        shopbase_product_image_obj = self.env["product.variant.image.store"]
        image_id = variant_image.get("id")
        url = variant_image.get('src')
        existing_common_variant_images = self.get_existing_images(product_store, product_variant_store)

        shopbase_product_image = shopbase_product_image_obj.search([("shopbase_variant_id", "=", product_variant_store.id),
                                                                    ("shopbase_image_id", "=", image_id)])
        if not shopbase_product_image:
            try:
                response = requests.get(url, stream=True, verify=True, timeout=10)
                if response.status_code == 200:
                    image = base64.b64encode(response.content)
                    key = hashlib.md5(image).hexdigest()
                    if key in existing_common_variant_images.keys():
                        shopbase_product_image = shopbase_product_image_obj.create({
                            "shopbase_template_id": product_store.id,
                            "shopbase_variant_id": product_variant_store.id,
                            "shopbase_image_id": image_id,
                            "odoo_image_id": existing_common_variant_images[key]})
                    else:
                        shopbase_product_image = self.find_or_create_common_product_image(product_store, image, url,
                                                                                          product_variant_store)
                        if shopbase_product_image:
                            shopbase_product_image.shopbase_image_id = image_id
            except Exception:
                pass
        return shopbase_product_image

    @api.model
    def update_product_images(self, product_images, product_store, product_variant_store):
        if not product_images:
            return
        shopbase_product_image_obj = need_to_remove = self.env["product.variant.image.store"]
        shopbase_product_image = self.update_shopbase_variant_image(product_images, product_store, product_variant_store)
        all_shopbase_product_images = shopbase_product_image_obj.search([("shopbase_template_id", "=", product_store.id),
                                                                         ("shopbase_variant_id", "=", product_variant_store.id)])
        need_to_remove += (all_shopbase_product_images - shopbase_product_image)
        need_to_remove.unlink()

    def process_sync_product(self, data, store):
        list_product = data.get("products")
        for product in list_product:
            self.sync_a_product_from_shopbase(product, store)


class ProductVariantStore(models.Model):
    _name = "product.variant.store"
    _rec_name = "product_variant_id"
    _description = "Product Variant Store"

    product_store_id = fields.Many2one('product.store', string='Product Store', ondelete='cascade')
    product_variant_id = fields.Many2one('product.product', string='Variant', ondelete='cascade')
    lst_price = fields.Float(string=u'Retail Price')
    compare_price = fields.Float(string='Compare Price')
    variant_sku = fields.Char(string='Variant SKU')
    shopbase_store_id = fields.Many2one(related='product_store_id.shopbase_store_id', string='Shopbase Store', store=True)
    shopbase_variant_id = fields.Char(string='Shopbase variant ID', readonly=True, copy=False)
    is_connect_to_shopbase = fields.Boolean(string='Connect Shopbase', readonly=True, copy=False)
    sync_from_shopbase = fields.Boolean(default=False, readonly=True)
    shopbase_image_ids = fields.One2many("product.variant.image.store", "shopbase_variant_id")

    _sql_constraints = [
        ("shopbase_variant_id_uniq", "unique(shopbase_variant_id)", "Shopbase variant ID must be unique")
    ]

    def get_image_id(self):
        if not self.shopbase_image_ids:
            return False
        image = self.shopbase_image_ids[0]
        if image.shopbase_image_id:
            return image.shopbase_image_id
        image.sync_new_image_to_shopbase(self.shopbase_store_id)
        return image.shopbase_image_id

    def _get_variant_option(self):
        option = []
        for attribute in self.product_variant_id.product_template_attribute_value_ids:
            option.append(attribute.product_attribute_value_id.name)
        return option

    def get_variant_data(self):
        """
            Get variant data for sync variant to shopbase
        """
        image_id = self.get_image_id()
        data = dict()
        data_detail = dict()
        data_detail['title'] = self.product_variant_id.name or ''
        data_detail['product_id'] = int(self.product_store_id.shopbase_product_id)
        data_detail['sku'] = self.variant_sku or ''
        data_detail['price'] = self.product_variant_id.lst_price
        if image_id:
            data_detail['image_id'] = int(image_id)
        options = self._get_variant_option()
        count = 1
        for option in options:
            data_detail[f'option{count}'] = option
            count += 1
        data['variant'] = data_detail
        return data

    def process_sync_variant_to_shopbase_result(self, content):
        variant = content.get("variant", {})
        variant_id = variant.get("id")
        self.write({
            'shopbase_variant_id': variant_id,
            'is_connect_to_shopbase': True})

    def sync_new_variant_to_shopbase(self):
        """
            Sync new variant from odoo to shopbase
        """
        shopbase_url, headers = self.shopbase_store_id.get_shopbase_connect_info()
        auth = self.shopbase_store_id.get_authen()
        if not self.product_store_id.shopbase_product_id:
            return False
        data = self.get_variant_data()
        data = json.dumps(data)
        url = f'{shopbase_url}/admin/products/{self.product_store_id.shopbase_product_id}/variants.json'
        try:
            res = requests.post(url, data=data, auth=auth, headers=headers)
            if res.status_code == 200:
                content = res.json()
                self.process_sync_variant_to_shopbase_result(content)
            else:
                return False

        except Exception as error_msg:
            raise ValidationError(_(error_msg))

    def sync_update_variant_to_shopbase(self, store_id, shopbase_variant_id, vals):
        """
            Update data of variant when change price or sku
        """
        shopbase_url, headers = store_id.get_shopbase_connect_info()
        auth = store_id.get_authen()
        data = vals
        data = json.dumps(data)
        url = f'{shopbase_url}/admin/variants/{shopbase_variant_id}.json'
        try:
            res = requests.put(url, data=data, auth=auth, headers=headers)
            if res.status_code == 200:
                return True
            else:
                return False

        except Exception as error_msg:
            raise ValidationError(_(error_msg))

    def process_update_variant_to_shopbase(self, values):
        if not self.shopbase_store_id or not self.shopbase_variant_id:
            return False
        shopbase_product_id = self.product_store_id.shopbase_product_id
        if not shopbase_product_id:
            return False
        variant = {}
        if values.get("lst_price"):
            variant['price'] = values.get("lst_price")
        if values.get("variant_sku"):
            variant['sku'] = values.get("variant_sku")
        if values.get("compare_price"):
            variant['compare_at_price'] = values.get("compare_price")
        if not variant:
            return False
        variant.update({'product_id': int(shopbase_product_id)})
        vals = {"variant": variant}
        self.with_delay(description='Update variant info to shopbase').sync_update_variant_to_shopbase(self.shopbase_store_id,
                                                                                                       self.shopbase_variant_id, vals)

    def write(self, values):
        res = super(ProductVariantStore, self).write(values)
        if self._context.get("not_sync"):
            return res
        if not values.get("lst_price") and not values.get("variant_sku"):
            return res
        for rec in self:
            rec.process_update_variant_to_shopbase(values)
        return res

    @api.model
    def create(self, vals):
        res = super(ProductVariantStore, self).create(vals)
        if not vals.get("sync_from_shopbase"):
            res.with_delay(description='Sync new variant to shopbase').sync_new_variant_to_shopbase()
        return res


class ProductVariantImageStore(models.Model):
    _name = "product.variant.image.store"
    _description = "Product Variant Image Store"
    _order = "sequence, id"

    odoo_image_id = fields.Many2one("common.product.image.ept", ondelete="cascade")
    shopbase_variant_id = fields.Many2one("product.variant.store")
    shopbase_template_id = fields.Many2one("product.store")
    url = fields.Char(related="odoo_image_id.url", help="External URL of image")
    image = fields.Image(related="odoo_image_id.image")
    sequence = fields.Integer(help="Sequence of images.", index=True, default=10)
    image_mime_type = fields.Char(help="This field is used to set image mime type.")

    image_url = fields.Char(string='Image URL')
    shopbase_image_id = fields.Char(string='Image ID in Shopbase')

    def sync_new_image_to_shopbase(self, store_id):
        """
            Sync new variant image to shopbase
        """
        if not self.shopbase_variant_id.shopbase_variant_id:
            return False
        shopbase_url, headers = store_id.get_shopbase_connect_info()
        auth = store_id.get_authen()
        data = {
            'image': {
                'attachment': self.image.decode("utf-8", "ignore"),
                'filename': f"{self.id}.png",
                'variant_ids': [int(self.shopbase_variant_id.shopbase_variant_id)],
            }
        }
        data = json.dumps(data)
        url = f'{shopbase_url}/admin/products/{self.shopbase_template_id.shopbase_product_id}/images.json'
        try:
            res = requests.post(url, data=data, auth=auth, headers=headers)
            if res.status_code == 200:
                content = res.json()
                image_id = content.get("image", {}).get("id")
                self.write({
                    'shopbase_image_id': image_id,
                })
            else:
                return False

        except Exception as error_msg:
            raise ValidationError(_(error_msg))
