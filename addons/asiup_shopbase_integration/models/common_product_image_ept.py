# -*- coding: utf-8 -*-

import base64

from odoo import models, api
from odoo.tools.mimetypes import guess_mimetype


class ProductImageEpt(models.Model):
    _inherit = "common.product.image.ept"

    @api.model
    def create(self, vals):
        result = super(ProductImageEpt, self).create(vals)
        shopbase_product_product_obj = self.env["product.variant.store"]
        shopbase_product_template_obj = self.env["product.store"]
        shopbase_product_image_obj = self.env["product.variant.image.store"]
        shopbase_product_image_vals = {"odoo_image_id": result.id}

        if vals.get("product_id", False):
            shopbase_variants = shopbase_product_product_obj.search_read([("product_variant_id", "=", vals.get("product_id"))],
                                                               ["id", "product_store_id"])
            mimetype = guess_mimetype(base64.b64decode(result.image))
            sequence = 1
            for shopbase_variant in shopbase_variants:
                variant_gallery_images = shopbase_product_product_obj.browse(shopbase_variant["id"]).shopbase_image_ids
                for variant_gallery_image in variant_gallery_images:
                    variant_gallery_image.write({"sequence": sequence})
                    sequence = sequence + 1
                shopbase_product_image_vals.update(
                    {"shopbase_variant_id": shopbase_variant["id"], "shopbase_template_id": shopbase_variant["product_store_id"][0],
                     "image_mime_type": mimetype, "sequence": 0})
                shopbase_product_image_obj.create(shopbase_product_image_vals)

        elif vals.get("template_id", False):
            shopbase_templates = shopbase_product_template_obj.search_read(
                [("product_id", "=", vals.get("template_id"))], ["id"])
            mimetype = guess_mimetype(base64.b64decode(result.image))
            for shopbase_template in shopbase_templates:
                existing_gallery_images = shopbase_product_template_obj.browse(
                    shopbase_template["id"]).shopbase_image_ids.filtered(lambda x: not x.shopbase_variant_id)
                sequence = 1
                for existing_gallery_image in existing_gallery_images:
                    existing_gallery_image.write({"sequence": sequence})
                    sequence = sequence + 1
                shopbase_product_image_vals.update({"shopbase_template_id": shopbase_template["id"], "sequence": 0,
                                               "image_mime_type": mimetype})
                shopbase_product_image_obj.create(shopbase_product_image_vals)

        return result

    def write(self, vals):
        result = super(ProductImageEpt, self).write(vals)
        shopbase_product_images = self.env["product.variant.image.store"]
        shopbase_product_product_obj = self.env["product.variant.store"]
        for record in self:
            shopbase_product_images += shopbase_product_images.search([("odoo_image_id", "=", record.id)])
        if shopbase_product_images:
            if not vals.get("product_id", ""):
                shopbase_product_images.write({"shopbase_variant_id": False})
            elif vals.get("product_id", ""):
                for shopbase_product_image in shopbase_product_images:
                    shopbase_variant = shopbase_product_product_obj.search_read(
                        [("product_variant_id", "=", vals.get("product_id")),
                         ("product_store_id", "=", shopbase_product_image.shopbase_template_id.id)], ["id"])
                    if shopbase_variant:
                        shopbase_product_image.write({"shopbase_variant_id": shopbase_variant[0]["id"]})
        return result
