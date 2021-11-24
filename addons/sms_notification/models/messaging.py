# -*- coding: utf-8 -*-
##########################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2017-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
##########################################################################

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


def send_message_sms(self, partner_id=False, condition=''):
    """Code to send sms to customer."""
    if not (condition):
        return
    sms_template_objs = self.env["wk.sms.template"].search(
        [('condition', '=', condition), ('globally_access', '=', False)])
    if not sms_template_objs:
        return False
    for sms_template_obj in sms_template_objs:
        mobile = sms_template_obj._get_partner_mobile(partner_id)
        if mobile:
            sms_template_obj.send_sms_using_template(
                mobile, sms_template_obj, obj=self)
