# -*- coding: utf-8 -*-
##############################################################################
#
# Odoo, Open Source Management Solution
# Copyright (C) 2016 Webkul Software Pvt. Ltd.
# Author : www.webkul.com
#
##############################################################################
import logging
_logger = logging.getLogger(__name__)
try:
    import twilio
    from twilio.rest import Client 
except Exception as e:
    _logger.error("#WKDEBUG-1  python  twilio library not installed .")

from odoo import models, fields, api, _
from urllib3.exceptions import HTTPError


def send_sms_using_twilio(body_sms, mob_no, from_mob=None, sms_gateway=None):
    '''
    This function is designed for sending sms using Twilio SMS API.

    :param body_sms: body of sms contains text
    :param mob_no: Here mob_no must be string having one or more number seprated by (,)
    :param from_mob: sender mobile number or id used in Twilio API
    :param sms_gateway: sms.mail.server config object for Twilio Credentials
    :return: response dictionary if sms successfully sent else empty dictionary
    '''
    if not sms_gateway or not body_sms or not mob_no:
        return {}
    if sms_gateway.gateway == "twilio":
        twilio_account_sid = sms_gateway.account_sid
        twilio_auth_token = sms_gateway.auth_token
        twilio_number = sms_gateway.twilio_number
        try:
            if twilio_account_sid and twilio_auth_token and twilio_number:
                response_dict = {}
                client = twilio.rest.Client(
                    twilio_account_sid, twilio_auth_token)
                for mobi_no in mob_no.split(','):
                    response = client.messages.create(
                        body=body_sms or "Blank Message",  # Your SMS Text Message
                        # Receivers' phone numbers with country code.
                        to=mobi_no,
                        from_=twilio_number  # The Sender's Twilio phone number with country code
                    )
                    response_dict.update({mobi_no: response})
                return response_dict
        except HTTPError as e:
            logging.info(
                '---------------Twilio HTTPError----------------------', exc_info=True)
            _logger.info(
                "---------------Twilio HTTPError While Sending SMS ----%r---------", e)
            return {"error":e.msg}
        except Exception as e:
            logging.info(
                '---------------Twilio Exception While Sending SMS ----------', exc_info=True)
            _logger.info(
                "---------------Twilio Exception While Sending SMS -----%r---------", e)
            return {"error":e.msg}
    return {}


def get_sms_status_for_twilio(data):
    if not data:
        return {}
    if data.get("twilio_sms_id") and data.get("client_account_sid") and data.get("client_auth_token"):
        try:
            # Message sms_id for which the details have to be retrieved
            client = twilio.rest.Client(
                data["client_account_sid"], data["client_auth_token"])
            check = client.messages(data.get("twilio_sms_id"))
            test = check.fetch()
            status = test.status
            return status
        except HTTPError as e:
            logging.info(
                '---------------Twilio HTTPError----------------------', exc_info=True)
            _logger.info(
                "---------------Twilio HTTPError For SMS History----%r---------", e)
            return {"error":e.msg}
        except Exception as e:
            logging.info(
                '---------------Twilio Exception While Sending SMS ----------', exc_info=True)
            _logger.info(
                "---------------Twilio Exception For SMS History-----%r---------", e)
            return {"error":e.msg}
    return {}


class SmsSms(models.Model):
    """SMS sending using Twilio SMS Gateway."""

    _inherit = "wk.sms.sms"
    _name = "wk.sms.sms"
    _description = "Twilio SMS"

    
    def send_sms_via_gateway(self, body_sms, mob_no, from_mob=None, sms_gateway=None):
        self.ensure_one()
        gateway_id = sms_gateway if sms_gateway else super(SmsSms, self).send_sms_via_gateway(
            body_sms, mob_no, from_mob=from_mob, sms_gateway=sms_gateway)
        if gateway_id:
            if gateway_id.gateway == 'twilio':
                twilio_account_sid = gateway_id.account_sid
                twilio_auth_token = gateway_id.auth_token
                twilio_number = gateway_id.twilio_number
                for element in mob_no:
                    for mobi_no in element.split(','):
                        response = send_sms_using_twilio(
                            body_sms, mobi_no, from_mob=from_mob, sms_gateway=gateway_id)
                        _logger.info("========%r",response)
                        for key in response.keys():
                            if key == mobi_no:
                                sms_report_obj = self.env["sms.report"].create(
                                    {'to': mobi_no, 'msg': body_sms, 'sms_sms_id': self.id, "auto_delete": self.auto_delete, 'sms_gateway_config_id': gateway_id.id})
                                vals = {'state': 'undelivered'}
                                if response[mobi_no].sid:
                                    sms_sid = response[mobi_no].sid
                                    vals['twilio_sms_id'] = sms_sid
                                    # Get SMS status
                                    msg_status = response[mobi_no].status
                                    if msg_status in ['sending', 'accepted', 'receiving']:
                                        vals['state'] = 'new'
                                    elif msg_status in ['sent','queued']:
                                        vals['state'] = 'sent'
                                    elif msg_status in ['delivered', 'received']:
                                        if sms_report_obj.auto_delete:
                                            sms_report_obj.unlink()
                                        else:
                                            vals['state'] = 'delivered'
                                else:
                                    errorMsg = response.get('error')
                                    gateway_id = self.set_error_message(gateway_id, errorMsg)
                                    vals['state'] = 'failed'
                                    vals['message'] = errorMsg
                                if sms_report_obj:
                                    sms_report_obj.write(vals)
                            else:
                                self.write({'state': 'error'})
                                errorMsg = response.get('error')
                                gateway_id = self.set_error_message(gateway_id, errorMsg)
                else:
                    self.write({'state': 'sent'})
            else:
                gateway_id = super(SmsSms, self).send_sms_via_gateway(
                    body_sms, mob_no, from_mob=from_mob, sms_gateway=sms_gateway)
        else:
            _logger.info(
                "----------------------------- SMS Gateway not found -------------------------")
        return gateway_id


class SmsReport(models.Model):
    """SMS report."""

    _inherit = "sms.report"

    twilio_sms_id = fields.Char("Twilio SMS ID")

    @api.model
    def cron_function_for_sms(self):
        _logger.info(
            "************** Cron Function For Twilio SMS ***********************")
        all_sms_report = self.search([('state', 'in', ('sent', 'new')),('sms_gateway','=','twilio')])
        for sms in all_sms_report:
            sms_sms_obj = sms.sms_sms_id
            if sms.twilio_sms_id:
                client_account_sid = sms.sms_gateway_config_id.account_sid
                client_auth_token = sms.sms_gateway_config_id.auth_token
                msg_status = get_sms_status_for_twilio(
                    {"twilio_sms_id": sms.twilio_sms_id, 'client_account_sid': client_account_sid, 'client_auth_token': client_auth_token})
                vals = {'state': 'undelivered', "status_hit_count": sms.status_hit_count + 1}
                if msg_status in ['sending', 'accepted', 'receiving']:
                    vals['state'] = 'new'
                elif msg_status in ['sent','queued']:
                    vals['state'] = 'sent'
                elif msg_status in ['delivered', 'received']:
                    if sms.auto_delete:
                        sms.unlink()
                        if sms_sms_obj.auto_delete and not sms_sms_obj.sms_report_ids:
                            sms_sms_obj.unlink()
                    else:
                        vals['state'] = 'delivered'
                if sms:
                    sms.write(vals)
            else:
                sms.send_now()
        super(SmsReport, self).cron_function_for_sms()
        return True

    
    def send_sms_via_gateway(self, body_sms, mob_no, from_mob=None, sms_gateway=None):
        self.ensure_one()
        gateway_id = sms_gateway if sms_gateway else super(SmsReport, self).send_sms_via_gateway(
            body_sms, mob_no, from_mob=from_mob, sms_gateway=sms_gateway)
        if gateway_id:
            if gateway_id.gateway == 'twilio':
                twilio_account_sid = gateway_id.account_sid
                twilio_auth_token = gateway_id.auth_token
                twilio_number = gateway_id.twilio_number
                if mob_no:
                    for element in mob_no:
                        count = 1
                        for mobi_no in element.split(','):
                            if count == 1:
                                self.to = mobi_no
                                rec = self
                            else:
                                rec = self.create(
                                    {'to': mobi_no, 'msg': body_sms, "auto_delete": self.auto_delete, 'sms_gateway_config_id': gateway_id.id})
                            response = send_sms_using_twilio(
                                body_sms, mobi_no, from_mob=from_mob, sms_gateway=gateway_id)
                            for key in response.keys():
                                if key == mobi_no:
                                    if response[mobi_no].sid:
                                        sms_sid = response[mobi_no].sid
                                        msg_status = response[mobi_no].status
                                        if msg_status in ['sending', 'accepted', 'receiving']:
                                            rec.write({'state': 'new', 'twilio_sms_id': sms_sid})
                                        elif msg_status in ['sent','queued']:
                                            rec.write({'state': 'sent', 'twilio_sms_id': sms_sid})
                                        elif msg_status in ['delivered', 'received']:
                                            if rec.auto_delete:
                                                rec.unlink()
                                            else:
                                                rec.write({'state': 'delivered', 'twilio_sms_id': sms_sid})
                                        else:
                                            rec.write({'state': 'undelivered', 'twilio_sms_id': sms_sid})
                                    else:
                                        rec.write(
                                            {'state': 'undelivered'})
                                else:
                                    errorMsg = response.get('error')
                                    gateway_id = rec.set_error_message(gateway_id, errorMsg)
                                    rec.write(
                                            {'state': 'failed','message':errorMsg})
                            count += 1
                else:
                    self.write({'state': 'sent'})
            else:
                gateway_id = super(SmsReport, self).send_sms_via_gateway(
                    body_sms, mob_no, from_mob=from_mob, sms_gateway=sms_gateway)
        return gateway_id
