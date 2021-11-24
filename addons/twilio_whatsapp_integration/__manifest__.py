# -*- coding: utf-8 -*-
##########################################################################
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
##########################################################################
{
    "name":  "Twilio Whatsapp Integration",
    "summary":  "Send whatsapp notifications using twilio sms gateway.",
    "category":  "Marketing",
    "version":  "1.0.0",
    "sequence":  1,
    "license":  "Other proprietary",
    "author":  "Webkul Software Pvt. Ltd.",
    "website":  "https://store.webkul.com/Odoo.html",
    "description":  """Twilio communication
Twilio Whatsapp Communicatio
Whatsapp Integration
Whatsapp SMS Integration
Twilio Whatsapp SMS Integration
Odoo Twilio SMS Gateway
Use Twilio in odoo
Twilio communication
Bulk SMS send
Send Bulk SMS
Twilio odoo
Twilio SMS alert
Integrate SMS Gateways with Odoo
Odoo SMS Notification
Send Text Messages to mobile
Integrate SMS Gateways with Odoo
SMS Gateway
SMS Notification
Notify with Odoo SMS 
Mobile message send
Send Mobile messages
Mobile notifications to customers
Mobile Notifications to Users
How to get SMS notification in Odoo
module to get SMS notification in Odoo
SMS Notification app in Odoo
Notify SMS in Odoo
Add SMS notification feature to your Odoo
Mobile SMS feature
How Odoo can help to get SMS notification,
Odoo SMS OTP Authentication,
Marketplace SMS
Plivo SMS Gateway
Clicksend SMS Gateway
Skebby SMS Gateway
Mobily SMS Gateway
MSG91 SMS Gateway
Netelip SMS Gateway""",
    "depends":  [
        'sms_notification',
    ],
    "data":  [
        'views/twilio_config_view.xml',
        'views/res_config.xml'
    ],
    "images":  ['static/description/Banner.png'],
    "application":  True,
    "installable":  True,
    "auto_install":  False,
    "price":  50,
    "currency":  "USD",
    "pre_init_hook":  "pre_init_check",
    "external_dependencies": {
        'python': ['twilio', 'urllib3'],
    },
}
