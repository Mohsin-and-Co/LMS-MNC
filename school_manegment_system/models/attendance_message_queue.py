from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class AttendanceMessageQueue(models.Model):
    _name = 'school.attendance.message.queue'
    _description = 'Attendance Message Queue'
    _order = 'send_time desc'

    attendance_id = fields.Many2one('school.attendance', string='Student Attendance', required=True, ondelete='cascade')
    teacher_id = fields.Many2one('school.teacher', string='Teacher', required=True)
    phone = fields.Char(string='Phone', required=True)
    message = fields.Text(string='Message', required=True)
    send_time = fields.Datetime(string='Send Time', required=True)
    sent = fields.Boolean(string='Sent', default=False)
    sent_at = fields.Datetime(string='Sent At', readonly=True)
    
    @api.model
    def send_pending_messages(self):
        """Send pending messages that are due - called by cron"""
        try:
            now = fields.Datetime.now()
            pending_messages = self.search([
                ('sent', '=', False),
                ('send_time', '<=', now)
            ])
            
            sent_count = 0
            for msg in pending_messages:
                try:
                    self._send_whatsapp_message(msg.phone, msg.message)
                    msg.write({
                        'sent': True,
                        'sent_at': now
                    })
                    sent_count += 1
                except Exception as e:
                    _logger.error(f"Error sending queued message {msg.id}: {str(e)}")
            
            _logger.info(f"Sent {sent_count} queued attendance messages")
            return sent_count
            
        except Exception as e:
            _logger.error(f"Error in send_pending_messages: {str(e)}")
            return 0
    
    def _send_whatsapp_message(self, phone, message):
        """Send WhatsApp message"""
        try:
            if not phone or not message:
                _logger.warning(f"Cannot send WhatsApp: phone={phone}, message={bool(message)}")
                return
            
            # Check if whatsapp.message model exists
            if 'whatsapp.message' in self.env:
                try:
                    create_vals = {'phone': phone}
                    whatsapp_model = self.env['whatsapp.message']
                    model_fields = whatsapp_model._fields
                    message_field = None
                    for field_name in ['message', 'body', 'text', 'content', 'message_text', 'message_body', 'msg_body', 'msg_text']:
                        if field_name in model_fields:
                            message_field = field_name
                            break
                    if message_field:
                        create_vals[message_field] = message
                        whatsapp_record = self.env['whatsapp.message'].sudo().create(create_vals)
                        _logger.info(f"WhatsApp message record created: ID={whatsapp_record.id}, Phone={phone}, Field={message_field}")
                    else:
                        try:
                            whatsapp_record = self.env['whatsapp.message'].sudo().create({'phone': phone, 'message': message})
                        except Exception:
                            whatsapp_record = self.env['whatsapp.message'].sudo().create({'phone': phone, 'body': message})
                    try:
                        if hasattr(whatsapp_record, 'action_send'):
                            whatsapp_record.action_send()
                            # Reload record to get updated state
                            whatsapp_record = self.env['whatsapp.message'].sudo().browse(whatsapp_record.id)
                            if whatsapp_record.state == 'sent':
                                _logger.info(f"WhatsApp message sent successfully: ID={whatsapp_record.id}, Phone={phone}")
                            elif whatsapp_record.state == 'failed':
                                _logger.error(f"WhatsApp message failed: ID={whatsapp_record.id}, Phone={phone}, Error={whatsapp_record.error or 'Unknown error'}")
                        elif hasattr(whatsapp_record, 'send'):
                            whatsapp_record.send()
                        elif hasattr(whatsapp_record, 'action_send_message'):
                            whatsapp_record.action_send_message()
                    except Exception as send_error:
                        _logger.error(f"Error calling action_send() for WhatsApp message ID={whatsapp_record.id}: {str(send_error)}")
                        import traceback
                        _logger.error(traceback.format_exc())
                    return whatsapp_record
                except Exception as e:
                    _logger.error(f"Error creating WhatsApp message record: {str(e)}")
                    import traceback
                    _logger.error(traceback.format_exc())
                    _logger.info(f"WhatsApp message to {phone}: {message}")
            else:
                _logger.warning(f"WhatsApp module not found. Message would be: Phone={phone}, Message={message[:50]}...")
                _logger.info(f"WhatsApp message to {phone}: {message}")
        except Exception as e:
            _logger.error(f"Error sending WhatsApp message to {phone}: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
