from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class Attendance(models.Model):
    _name = 'school.attendance'
    _description = 'Student Attendance'
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    student_id = fields.Many2one('school.student', string='Student', required=True,
                                 domain="[('state', '=', 'admitted')]")
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
        ('unique_student_date', 'unique(student_id, date)', 'Attendance for this student on this date already exists!'),
    ]

    # ================= Create =================
    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            ids = []
            for val in vals:
                ids.append(self._create_single(val).id)
            return self.browse(ids)
        return self._create_single(vals)

    def _create_single(self, vals):
        if vals.get('student_id') and vals.get('date'):
            existing = self.search([
                ('student_id', '=', vals['student_id']),
                ('date', '=', vals['date'])
            ], limit=1)
            if existing:
                raise ValidationError(_('Attendance is already set for this student on this date!'))
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('school.attendance') or _('New')
        record = super(Attendance, self).create(vals)
        if record.state == 'confirmed':
            self._send_whatsapp_notification(record)
        return record

    # ================= Write =================
    def write(self, vals):
        for rec in self:
            if isinstance(vals, dict):
                if ('name' not in vals or vals.get('name') == _('New')) and rec.name == _('New'):
                    vals['name'] = self.env['ir.sequence'].next_by_code('school.attendance') or _('New')
        if 'student_id' in vals or 'date' in vals:
            for rec in self:
                student_id = vals.get('student_id', rec.student_id.id) if isinstance(vals, dict) else rec.student_id.id
                date = vals.get('date', rec.date) if isinstance(vals, dict) else rec.date
                existing = self.search([
                    ('student_id', '=', student_id),
                    ('date', '=', date),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_('Attendance is already set for this student on this date!'))
        result = super(Attendance, self).write(vals)
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
        """Send WhatsApp notification for student attendance"""
        try:
            # Check if auto send is enabled
            auto_send = self.env['ir.config_parameter'].sudo().get_param(
                'school.attendance_auto_send_enable', 'True'
            )
            if auto_send != 'True':
                return
            
            # Check if classwise message is enabled
            classwise_enable = self.env['ir.config_parameter'].sudo().get_param(
                'school.attendance_classwise_message_enable', 'False'
            )
            
            student = attendance.student_id
            class_obj = student.class_id if student.class_id else False
            classwise_summary_enable = self.env['ir.config_parameter'].sudo().get_param(
                'school.student_attendance_classwise_enable', 'False'
            )

            # Check if student attendance teacher message is enabled
            teacher_message_enable = self.env['ir.config_parameter'].sudo().get_param(
                'school.student_attendance_teacher_enable', 'False'
            )
            
            # Send to class teacher if enabled (at configured time or queue it)
            if teacher_message_enable == 'True' and class_obj and class_obj.class_teacher_id and class_obj.class_teacher_id.phone:
                # Get configured send time
                teacher_send_time_float = float(self.env['ir.config_parameter'].sudo().get_param(
                    'school.student_attendance_teacher_time', default=9.0))
                
                # Prepare message
                current_time = fields.Datetime.now()
                message = f"✅ QR Code Scanned - Student Attendance\n\n"
                message += f"👤 Student Name: {student.name}\n"
                message += f"📋 Roll Number: {student.roll_number}\n"
                message += f"🏫 Class: {class_obj.name}\n"
                message += f"📅 Date: {attendance.date}\n"
                message += f"✅ Status: {attendance.status.upper()}\n"
                # Convert to user timezone and format
                user_tz = self.env.user.tz or 'UTC'
                scan_time_tz = fields.Datetime.context_timestamp(self, current_time)
                scan_time_ampm = scan_time_tz.strftime('%I:%M:%S %p')
                message += f"⏰ Scan Time: {scan_time_ampm}\n"
                if attendance.remark:
                    message += f"📝 Remark: {attendance.remark}\n"
                
                # Calculate send time (today at configured hour)
                send_date = attendance.date
                send_hour = int(teacher_send_time_float)
                send_minute = int((teacher_send_time_float - send_hour) * 60)
                send_time = fields.Datetime.now().replace(
                    year=send_date.year,
                    month=send_date.month,
                    day=send_date.day,
                    hour=send_hour,
                    minute=send_minute,
                    second=0,
                    microsecond=0
                )
                
                # If send time has passed, schedule for next day
                if send_time < current_time:
                    from datetime import timedelta
                    send_time = send_time + timedelta(days=1)
                
                # Queue the message
                self.env['school.attendance.message.queue'].create({
                    'attendance_id': attendance.id,
                    'teacher_id': class_obj.class_teacher_id.id,
                    'phone': class_obj.class_teacher_id.phone,
                    'message': message,
                    'send_time': send_time,
                })
                _logger.info(f"Queued student attendance message for teacher {class_obj.class_teacher_id.name} to send at {send_time}")

            # Send instant message to class number on each scan (class ke attendance sath sath)
            # Always send if class_attendance_phone is set (class ke attendance sath sath whatsapp per jani chahiye)
            if class_obj and class_obj.class_attendance_phone:
                # Convert to user timezone and format
                now_dt = fields.Datetime.now()
                now_tz = fields.Datetime.context_timestamp(self, now_dt)
                time_ampm = now_tz.strftime('%I:%M:%S %p')
                instant_msg = (
                    f"✅ Attendance: {student.name} - {attendance.status.upper()} - {attendance.date}\n"
                    f"🏫 Class: {class_obj.name}\n"
                    f"⏰ {time_ampm}"
                )
                self._send_whatsapp_message(class_obj.class_attendance_phone, instant_msg)
                _logger.info(f"Sent instant attendance message to class {class_obj.name} phone: {class_obj.class_attendance_phone}")
            
            # Send to parent if enabled
            if classwise_enable == 'True' and student.parent_phone:
                message = f"✅ QR Code Scanned - Attendance Notification\n\n"
                message += f"Dear {student.parent_name},\n\n"
                message += f"👤 Student: {student.name}\n"
                message += f"📋 Roll No: {student.roll_number}\n"
                message += f"🏫 Class: {class_obj.name if class_obj else 'N/A'}\n"
                message += f"📅 Date: {attendance.date}\n"
                message += f"✅ Status: {attendance.status.upper()}\n"
                # Convert to user timezone and format
                now_dt = fields.Datetime.now()
                now_tz = fields.Datetime.context_timestamp(self, now_dt)
                time_ampm = now_tz.strftime('%I:%M:%S %p')
                message += f"⏰ Time: {time_ampm}\n"
                if attendance.remark:
                    message += f"📝 Remark: {attendance.remark}\n"

                self._send_whatsapp_message(student.parent_phone, message)
            
            # Send class-wise summary to class phone number if enabled (in addition to instant per-scan above)
            if classwise_summary_enable == 'True' and class_obj and class_obj.class_attendance_phone:
                # Get all students in the class
                class_students = self.env['school.student'].search([
                    ('class_id', '=', class_obj.id),
                    ('state', '=', 'admitted')
                ])
                
                # Get attendance records for today
                today_attendances = self.env['school.attendance'].search([
                    ('student_id', 'in', class_students.ids),
                    ('date', '=', attendance.date),
                    ('state', '=', 'confirmed')
                ])
                
                # Calculate statistics
                total_students = len(class_students)
                present_count = len(today_attendances.filtered(lambda a: a.status == 'present'))
                absent_count = total_students - present_count
                late_count = len(today_attendances.filtered(lambda a: a.status == 'late'))
                
                # Prepare class-wise summary message
                summary_message = f"📊 Classwise Attendance Summary\n\n"
                summary_message += f"🏫 Class: {class_obj.name}\n"
                summary_message += f"📅 Date: {attendance.date}\n\n"
                summary_message += f"📊 Statistics:\n"
                summary_message += f"✅ Present: {present_count}\n"
                summary_message += f"❌ Absent: {absent_count}\n"
                summary_message += f"⏰ Late: {late_count}\n"
                summary_message += f"👥 Total: {total_students}\n"
                
                # Send to class phone number
                self._send_whatsapp_message(class_obj.class_attendance_phone, summary_message)

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
                    # Common field names: message, body, text, content, message_text, message_body
                    create_vals = {'phone': phone}
                    
                    # Try to get model fields to find correct field name
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
                        # Fallback: try with 'message' first, then 'body'
                        try:
                            whatsapp_record = self.env['whatsapp.message'].sudo().create({
                                'phone': phone,
                                'message': message,
                            })
                            _logger.info(f"WhatsApp message record created: ID={whatsapp_record.id}, Phone={phone}")
                        except Exception:
                            # Try with 'body' field
                            whatsapp_record = self.env['whatsapp.message'].sudo().create({
                                'phone': phone,
                                'body': message,
                            })
                            _logger.info(f"WhatsApp message record created: ID={whatsapp_record.id}, Phone={phone} (using 'body' field)")
                    
                    # Try to trigger send if there's a send method
                    try:
                        if hasattr(whatsapp_record, 'action_send'):
                            whatsapp_record.action_send()
                            # Refresh to get updated state
                            # Reload record to get updated state
                            whatsapp_record = self.env['whatsapp.message'].sudo().browse(whatsapp_record.id)
                            if whatsapp_record.state == 'sent':
                                _logger.info(f"WhatsApp message sent successfully: ID={whatsapp_record.id}, Phone={phone}")
                            elif whatsapp_record.state == 'failed':
                                _logger.error(f"WhatsApp message failed: ID={whatsapp_record.id}, Phone={phone}, Error={whatsapp_record.error or 'Unknown error'}")
                            else:
                                _logger.warning(f"WhatsApp message state: {whatsapp_record.state} for ID={whatsapp_record.id}, Phone={phone}")
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
    def send_absent_leave_messages(self):
        """Send messages for absent/leave students after attendance end time - called by cron"""
        try:
            # Check if auto-send is enabled
            auto_send_enable = self.env['ir.config_parameter'].sudo().get_param(
                'school.auto_send_absent_leave_enable', 'False'
            )
            if auto_send_enable != 'True':
                return
            
            # Get attendance end time
            end_time_float = float(self.env['ir.config_parameter'].sudo().get_param(
                'school.attendance_end_time', default=17.0))
            
            # Check if current time is after end time
            current_time = fields.Datetime.now()
            current_hour = current_time.hour + (current_time.minute / 60.0)
            
            # Only send if current time is after end time (within 1 hour window)
            if current_hour < end_time_float or (current_hour - end_time_float) > 1.0:
                return
            
            today = fields.Date.today()
            
            # Get all classes
            classes = self.env['school.class'].search([('active', '=', True)])
            
            for class_obj in classes:
                try:
                    # Get all admitted students in the class
                    students = self.env['school.student'].search([
                        ('class_id', '=', class_obj.id),
                        ('state', '=', 'admitted')
                    ])
                    
                    if not students:
                        continue
                    
                    # Get attendance records for today
                    attendances = self.env['school.attendance'].search([
                        ('student_id', 'in', students.ids),
                        ('date', '=', today),
                        ('state', '=', 'confirmed')
                    ])
                    
                    # Find absent/leave students
                    present_student_ids = attendances.filtered(
                        lambda a: a.status in ['present', 'late']
                    ).mapped('student_id.id')
                    absent_students = students.filtered(lambda s: s.id not in present_student_ids)
                    
                    # Send messages for absent students
                    for student in absent_students:
                        if student.parent_phone:
                            message = f"❌ Absent Student Notification\n\n"
                            message += f"Dear {student.parent_name or 'Parent'},\n\n"
                            message += f"👤 Student: {student.name}\n"
                            message += f"📋 Roll No: {student.roll_number or 'N/A'}\n"
                            message += f"🏫 Class: {class_obj.name}\n"
                            message += f"📅 Date: {today}\n"
                            message += f"❌ Status: ABSENT\n"
                            message += f"\nPlease contact the school if there's any issue."
                            
                            self._send_whatsapp_message(student.parent_phone, message)
                            _logger.info(f"Sent absent notification for {student.name} to {student.parent_phone}")
                    
                    # Also send to class phone if configured
                    if class_obj.class_attendance_phone and absent_students:
                        absent_count = len(absent_students)
                        absent_names = '\n'.join([f"❌ {s.name} (Roll: {s.roll_number or 'N/A'})" for s in absent_students])
                        
                        summary_message = f"❌ Absent Students Notification\n\n"
                        summary_message += f"🏫 Class: {class_obj.name}\n"
                        summary_message += f"📅 Date: {today}\n"
                        summary_message += f"❌ Total Absent: {absent_count}\n\n"
                        summary_message += f"Absent Students:\n{absent_names}"
                        
                        self._send_whatsapp_message(class_obj.class_attendance_phone, summary_message)
                        
                except Exception as e:
                    _logger.error(f"Error sending absent messages for class {class_obj.name}: {str(e)}")
                    
        except Exception as e:
            _logger.error(f"Error in send_absent_leave_messages: {str(e)}")