# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
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
#################################################################################
{
  "name"                 :  "Twilio SMS Gateway",
  "summary"              :  """Send sms notifications using twilio sms gateway.""",
  "category"             :  "Marketing",
  "version"              :  "1.2.1",
  "sequence"             :  1,
  "author"               :  "Webkul Software Pvt. Ltd.",
  "license"              :  "Other proprietary",
  "website"              :  "https://store.webkul.com/Odoo-SMS-Twilio-Gateway.html",
  "description"          :  """http://webkul.com/blog/odoo-sms-twilio-gateway/""",
  "live_test_url"        :  "https://webkul.com/blog/odoo-sms-twilio-gateway/",
  "depends"              :  ['sms_notification'],
  "data"                 :  [
                             'views/twilio_config_view.xml',
                             'views/sms_report.xml',
                            ],
  "images"               :  ['static/description/Banner.png'],
  "application"          :  True,
  "installable"          :  True,
  "auto_install"         :  False,
  "price"                :  50,
  "currency"             :  "USD",
  "pre_init_hook"        :  "pre_init_check",
  "external_dependencies":  {'python': ['twilio', 'urllib3']},
}