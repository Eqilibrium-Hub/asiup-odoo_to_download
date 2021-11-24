# -*- coding: utf-8 -*-
##############################################################################
#
# Odoo, Open Source Management Solution
# Copyright (C) 2016 Webkul Software Pvt. Ltd.
# Author : www.webkul.com
#
##############################################################################

from . import models


def pre_init_check(cr):
    from odoo.service import common
    from odoo.exceptions import Warning
    version_info = common.exp_version()
    server_serie = version_info.get('server_serie')
    if server_serie != '14.0':
        raise Warning(
            'Module support Odoo series 14.0 found {}.'.format(server_serie))
    return True
