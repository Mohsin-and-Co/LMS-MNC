from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
from datetime import datetime
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

_logger = logging.getLogger(__name__)

class StaffAttendance(models.Model):
    _name = 'school.staff.attendance'
    _description = 'Staff Attendance'
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    staff_id = fields.Many2one('school.teacher', string='Staff', required=True)
    check_in = fields.Datetime(string='Check In')
    check_out = fields.Datetime(string='Check Out')
    status = fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late')
    ], string='Status', required=True, default='present')
    remark = fields.Text(string='Remarks')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed')
    ], string='Stage', default='draft')

    _sql_constraints = [
        ('unique_staff_date', 'unique(staff_id, date)', 'Attendance for this staff on this date already exists!'),
    ]

    # ================= Create =================
    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            records = []
            for val in vals:
                records.append(self._create_single(val))
            return records
        return self._create_single(vals)

    def _create_single(self, vals):
        if vals.get('staff_id') and vals.get('date'):
            existing = self.search([
                ('staff_id', '=', vals['staff_id']),
                ('date', '=', vals['date'])
            ], limit=1)
            if existing:
                raise ValidationError(_('Attendance for this staff on this date already exists!'))
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('school.staff.attendance') or _('New')
        record = super(StaffAttendance, self).create(vals)
        if record.state == 'confirmed':
            self._send_whatsapp_notification(record)
        return record

    # ================= Write =================
    def write(self, vals):
        for rec in self:
            if isinstance(vals, dict):
                if ('name' not in vals or vals.get('name') == _('New')) and rec.name == _('New'):
                    vals['name'] = self.env['ir.sequence'].next_by_code('school.staff.attendance') or _('New')
        if 'staff_id' in vals or 'date' in vals:
            for rec in self:
                staff_id = vals.get('staff_id', rec.staff_id.id) if isinstance(vals, dict) else rec.staff_id.id
                date = vals.get('date', rec.date) if isinstance(vals, dict) else rec.date
                existing = self.search([
                    ('staff_id', '=', staff_id),
                    ('date', '=', date),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_('Attendance for this staff on this date already exists!'))
        result = super(StaffAttendance, self).write(vals)
        if 'state' in vals and vals['state'] == 'confirmed':
            for rec in self:
                if rec.state == 'confirmed':
                    self._send_whatsapp_notification(rec)
        return result

    # ================= Confirm =================
    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_("Only draft attendance can be confirmed."))
            record.write({'state': 'confirmed'})
            self._send_whatsapp_notification(record)

    # ================= WhatsApp =================
    def _send_whatsapp_notification(self, attendance):
        """Send WhatsApp notification for staff attendance"""
        try:
            # Check if auto send is enabled
            auto_send = self.env['ir.config_parameter'].sudo().get_param(
                'school.attendance_auto_send_enable', 'True'
            )
            if auto_send != 'True':
                return
            
            # Send to staff head phone (main recipient for staff attendance)
            staff_heads = self.env['school.staff.head'].sudo().search([('active', '=', True)])
            staff_head_phones = []
            for head in staff_heads:
                if head.phone:
                    staff_head_phones.append(head.phone)
            
            # Send to staff member's phone if enabled
            staff_message_enable = self.env['ir.config_parameter'].sudo().get_param(
                'school.attendance_staff_message_enable', 'False'
            )
            staff_phone = None
            if staff_message_enable == 'True':
                staff_phone = attendance.staff_id.phone if attendance.staff_id and attendance.staff_id.phone else False

            current_time = fields.Datetime.now()
            # Convert to user timezone
            current_time_tz = fields.Datetime.context_timestamp(self, current_time)
            current_time_str = current_time_tz.strftime('%Y-%m-%d %I:%M:%S %p')
            message = ""

            if attendance.check_in and not attendance.check_out:
                message = f"✅ QR Code Scanned - Staff Check-In\n\n"
                message += f"👤 Staff Name: {attendance.staff_id.name}\n"
                message += f"🆔 Employee ID: {attendance.staff_id.employee_id}\n"
                message += f"📅 Date: {attendance.date}\n"
                # Convert check_in to user timezone
                check_in_tz = fields.Datetime.context_timestamp(self, attendance.check_in)
                check_in_ampm = check_in_tz.strftime('%I:%M:%S %p')
                message += f"⏰ Check-In Time: {check_in_ampm}\n"
                message += f"✅ Status: {attendance.status.upper()}\n"
            elif attendance.check_out:
                message = f"✅ QR Code Scanned - Staff Check-Out\n\n"
                message += f"👤 Staff Name: {attendance.staff_id.name}\n"
                message += f"🆔 Employee ID: {attendance.staff_id.employee_id}\n"
                message += f"📅 Date: {attendance.date}\n"
                if attendance.check_in:
                    # Convert check_in to user timezone
                    check_in_tz = fields.Datetime.context_timestamp(self, attendance.check_in)
                    check_in_ampm = check_in_tz.strftime('%I:%M:%S %p')
                    message += f"⏰ Check-In: {check_in_ampm}\n"
                # Convert check_out to user timezone
                check_out_tz = fields.Datetime.context_timestamp(self, attendance.check_out)
                check_out_ampm = check_out_tz.strftime('%I:%M:%S %p')
                message += f"⏰ Check-Out Time: {check_out_ampm}\n"
                message += f"✅ Status: {attendance.status.upper()}\n"
            else:
                message = f"✅ QR Code Scanned - Staff Attendance\n\n"
                message += f"👤 Staff Name: {attendance.staff_id.name}\n"
                message += f"🆔 Employee ID: {attendance.staff_id.employee_id}\n"
                message += f"📅 Date: {attendance.date}\n"
                message += f"✅ Status: {attendance.status.upper()}\n"
                time_ampm = current_time_tz.strftime('%I:%M:%S %p')
                message += f"⏰ Time: {time_ampm}\n"

            # Send to all active staff heads (main recipients)
            for head_phone in staff_head_phones:
                if head_phone and message:
                    self._send_whatsapp_message(head_phone, message)
                    _logger.info(f"Sent staff attendance message to staff head phone: {head_phone}")
            
            # Send to staff member if enabled
            if staff_phone and message:
                self._send_whatsapp_message(staff_phone, message)
            
            # Send to staff attendance group if enabled (one-by-one messages)
            staff_group_phone = self.env['ir.config_parameter'].sudo().get_param(
                'school.staff_attendance_group_phone', ''
            )
            if staff_group_phone and staff_message_enable == 'True' and message:
                # Send one-by-one message to group number
                self._send_whatsapp_message(staff_group_phone, message)
                
        except Exception as e:
            _logger.error(f"Failed to send WhatsApp notification: {str(e)}")

    def _send_whatsapp_message(self, phone, message):
        """Send WhatsApp message"""
        try:
            if not phone or not message:
                _logger.warning(f"Cannot send WhatsApp: phone={phone}, message={bool(message)}")
                return
            
            # Check if whatsapp.message model exists
            if 'whatsapp.message' in self.env:
                try:
                    # Try different common field names for message content
                    create_vals = {'phone': phone}
                    whatsapp_model = self.env['whatsapp.message']
                    model_fields = whatsapp_model._fields
                    
                    # Try common field names
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
                            _logger.info(f"WhatsApp message record created using 'body' field")
                    
                    # Try to trigger send
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
