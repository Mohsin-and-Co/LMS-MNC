from odoo import models, fields, api, _
import logging
from datetime import datetime, time

_logger = logging.getLogger(__name__)

class StaffHead(models.Model):
    _name = 'school.staff.head'
    _description = 'Staff Head'

    name = fields.Char(string='Name', required=True)
    phone = fields.Char(string='Phone', required=True)
    email = fields.Char(string='Email')
    active = fields.Boolean(string='Active', default=True)
    
    # Fixed time for summary
    summary_time = fields.Float(string='Summary Time', required=True, default=18.0,
                                help='Time in 24-hour format (e.g., 18.0 for 6:00 PM)')
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        ondelete='restrict',
        help="Related partner for messaging."
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('partner_id') and vals.get('name'):
                partner = self.env['res.partner'].create({
                    'name': vals['name'],
                    'phone': vals.get('phone'),
                    'email': vals.get('email'),
                    'is_company': False,
                })
                vals['partner_id'] = partner.id
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals or 'phone' in vals or 'email' in vals:
            for rec in self:
                if rec.partner_id:
                    partner_vals = {}
                    if 'name' in vals:
                        partner_vals['name'] = vals['name']
                    if 'phone' in vals:
                        partner_vals['phone'] = vals['phone']
                    if 'email' in vals:
                        partner_vals['email'] = vals['email']
                    if partner_vals:
                        rec.partner_id.write(partner_vals)
        return super().write(vals)
    
    def send_daily_summary(self):
        """Send daily attendance summary to staff head"""
        for head in self:
            try:
                today = fields.Date.today()
                
                # Get all staff attendance for today
                staff_attendances = self.env['school.staff.attendance'].search([
                    ('date', '=', today),
                    ('state', '=', 'confirmed')
                ])
                
                if not staff_attendances:
                    _logger.info(f"No attendance records found for {today}")
                    return
                
                # Prepare summary message
                message = f"Daily Staff Attendance Summary\n"
                message += f"Date: {today}\n"
                message += f"Total Records: {len(staff_attendances)}\n\n"
                
                present_count = len(staff_attendances.filtered(lambda a: a.status == 'present'))
                absent_count = len(staff_attendances.filtered(lambda a: a.status == 'absent'))
                late_count = len(staff_attendances.filtered(lambda a: a.status == 'late'))
                
                message += f"Present: {present_count}\n"
                message += f"Absent: {absent_count}\n"
                message += f"Late: {late_count}\n\n"
                
                message += "Details:\n"
                for att in staff_attendances:
                    message += f"- {att.staff_id.name}: {att.status.upper()}"
                    if att.check_in:
                        # Convert to user timezone
                        check_in_tz = fields.Datetime.context_timestamp(self, att.check_in)
                        check_in_ampm = check_in_tz.strftime('%I:%M %p')
                        message += f" (In: {check_in_ampm})"
                    if att.check_out:
                        # Convert to user timezone
                        check_out_tz = fields.Datetime.context_timestamp(self, att.check_out)
                        check_out_ampm = check_out_tz.strftime('%I:%M %p')
                        message += f" (Out: {check_out_ampm})"
                    message += "\n"
                
                # Send WhatsApp message
                if head.phone:
                    head._send_whatsapp_message(head.phone, message)
                    
            except Exception as e:
                _logger.error(f"Error sending summary to {head.name}: {str(e)}")
    
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
    
    @api.model
    def send_daily_summary_cron(self):
        """Method called by cron to send daily summary to all active staff heads"""
        active_heads = self.search([('active', '=', True)])
        for head in active_heads:
            # Check if current time matches summary time
            current_time = datetime.now().time()
            summary_hour = int(head.summary_time)
            summary_minute = int((head.summary_time % 1) * 60)
            summary_time_obj = time(summary_hour, summary_minute)
            
            # Calculate time difference in minutes
            current_minutes = current_time.hour * 60 + current_time.minute
            summary_minutes = summary_time_obj.hour * 60 + summary_time_obj.minute
            time_diff = abs(current_minutes - summary_minutes)
            
            # Send if time matches (within 1 hour window)
            if time_diff <= 60:  # Within 1 hour window
                head.send_daily_summary()
