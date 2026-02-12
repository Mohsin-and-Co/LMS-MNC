from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, datetime
import logging

_logger = logging.getLogger(__name__)

class AttendanceWhatsAppWizard(models.TransientModel):
    _name = 'school.attendance.whatsapp.wizard'
    _description = 'Attendance WhatsApp Wizard'

    class_id = fields.Many2one('school.class', string='Class', required=False, 
                               help='Required for classwise attendance, not needed for staff attendance')
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    send_to_parents = fields.Boolean(string='Send to Parents', default=True, 
                                     help='Send attendance summary to student parents')
    send_to_class_teacher = fields.Boolean(string='Send to Class Teacher', default=True,
                                          help='Send attendance summary to class teacher')
    
    name = fields.Char(string='Name', compute='_compute_name', store=False)
    
    @api.depends('class_id', 'date')
    def _compute_name(self):
        for rec in self:
            if rec.class_id:
                rec.name = f"{rec.class_id.name} - {rec.date}"
            else:
                rec.name = f"Staff Attendance - {rec.date}"
    
    def action_send_classwise_attendance(self):
        """Send class-wise attendance summary via WhatsApp"""
        if not self.class_id:
            raise ValidationError(_("Please select a Class."))
        
        # Get all students in the class
        students = self.env['school.student'].search([
            ('class_id', '=', self.class_id.id),
            ('state', '=', 'admitted')
        ])
        
        if not students:
            raise ValidationError(_("No students found in this class."))
        
        # Get attendance records for the selected date
        attendances = self.env['school.attendance'].search([
            ('student_id', 'in', students.ids),
            ('date', '=', self.date),
            ('state', '=', 'confirmed')
        ])
        
        # Calculate statistics
        total_students = len(students)
        present_count = len(attendances.filtered(lambda a: a.status == 'present'))
        absent_count = total_students - present_count
        late_count = len(attendances.filtered(lambda a: a.status == 'late'))
        
        sent_count = 0
        failed_count = 0
        
        # Send to class teacher if enabled
        if self.send_to_class_teacher and self.class_id.class_teacher_id and self.class_id.class_teacher_id.phone:
            try:
                teacher_message = f"📊 Class Attendance Summary\n\n"
                teacher_message += f"🏫 Class: {self.class_id.name}\n"
                teacher_message += f"📅 Date: {self.date}\n\n"
                teacher_message += f"📊 Statistics:\n"
                teacher_message += f"✅ Present: {present_count}\n"
                teacher_message += f"❌ Absent: {absent_count}\n"
                teacher_message += f"⏰ Late: {late_count}\n"
                teacher_message += f"👥 Total: {total_students}\n\n"
                
                teacher_message += "📋 Present Students:\n"
                for att in attendances.filtered(lambda a: a.status == 'present'):
                    teacher_message += f"✅ {att.student_id.name} (Roll: {att.student_id.roll_number or 'N/A'})\n"
                
                if absent_count > 0:
                    teacher_message += "\n❌ Absent Students:\n"
                    present_student_ids = attendances.filtered(lambda a: a.status == 'present').mapped('student_id.id')
                    absent_students = students.filtered(lambda s: s.id not in present_student_ids)
                    for student in absent_students:
                        teacher_message += f"❌ {student.name} (Roll: {student.roll_number or 'N/A'})\n"
                
                self._send_whatsapp_message(self.class_id.class_teacher_id.phone, teacher_message)
                sent_count += 1
            except Exception as e:
                _logger.error(f"Error sending WhatsApp to class teacher: {str(e)}")
                failed_count += 1
        
        # Send individual messages to parents if enabled
        if self.send_to_parents:
            for student in students:
                try:
                    # Get student's attendance for the date
                    student_attendance = attendances.filtered(lambda a: a.student_id.id == student.id)
                    
                    if student_attendance:
                        att = student_attendance[0]
                        message = f"📊 Daily Attendance Summary\n\n"
                        message += f"Dear {student.parent_name or 'Parent'},\n\n"
                        message += f"👤 Student: {student.name}\n"
                        message += f"📋 Roll No: {student.roll_number or 'N/A'}\n"
                        message += f"🏫 Class: {self.class_id.name}\n"
                        message += f"📅 Date: {self.date}\n"
                        message += f"✅ Status: {att.status.upper()}\n"
                        if att.remark:
                            message += f"📝 Remark: {att.remark}\n"
                    else:
                        # Absent student
                        message = f"📊 Daily Attendance Summary\n\n"
                        message += f"Dear {student.parent_name or 'Parent'},\n\n"
                        message += f"👤 Student: {student.name}\n"
                        message += f"📋 Roll No: {student.roll_number or 'N/A'}\n"
                        message += f"🏫 Class: {self.class_id.name}\n"
                        message += f"📅 Date: {self.date}\n"
                        message += f"❌ Status: ABSENT\n"
                        message += f"\n📊 Class Summary:\n"
                        message += f"✅ Present: {present_count}/{total_students}\n"
                        message += f"❌ Absent: {absent_count}/{total_students}\n"
                    
                    # Send to parent phone (prefer parent_phone, fallback to phone)
                    phone = student.parent_phone if student.parent_phone else student.phone
                    
                    if phone:
                        self._send_whatsapp_message(phone, message)
                        sent_count += 1
                    else:
                        _logger.warning(f"No phone number found for student {student.name}")
                        failed_count += 1
                        
                except Exception as e:
                    _logger.error(f"Error sending WhatsApp to {student.name}: {str(e)}")
                    failed_count += 1
        
        # Show summary message
        result_message = _("Attendance WhatsApp messages sent!\n\n")
        result_message += _("Sent: %d\n") % sent_count
        result_message += _("Failed: %d") % failed_count
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Attendance WhatsApp Messages'),
                'message': result_message,
                'type': 'success' if failed_count == 0 else 'warning',
                'sticky': False,
            }
        }
    
    def action_send_staff_attendance(self):
        """Send staff attendance messages"""
        if not self.date:
            raise ValidationError(_("Please select a Date."))
        
        # Get all staff attendance for the date
        staff_attendances = self.env['school.staff.attendance'].search([
            ('date', '=', self.date),
            ('state', '=', 'confirmed')
        ])
        
        if not staff_attendances:
            raise ValidationError(_("No staff attendance found for this date."))
        
        sent_count = 0
        failed_count = 0
        
        # Send message to each staff member
        for attendance in staff_attendances:
            try:
                staff = attendance.staff_id
                if not staff.phone:
                    _logger.warning(f"No phone number found for staff {staff.name}")
                    failed_count += 1
                    continue
                
                message = f"📊 Staff Attendance Summary\n\n"
                message += f"👤 Staff: {staff.name}\n"
                message += f"🆔 Employee ID: {staff.employee_id or 'N/A'}\n"
                message += f"📅 Date: {self.date}\n"
                message += f"✅ Status: {attendance.status.upper()}\n"
                
                if attendance.check_in:
                    # Convert to user timezone
                    check_in_tz = fields.Datetime.context_timestamp(self, attendance.check_in)
                    check_in_ampm = check_in_tz.strftime('%I:%M:%S %p')
                    message += f"⏰ Check-In: {check_in_ampm}\n"
                if attendance.check_out:
                    # Convert to user timezone
                    check_out_tz = fields.Datetime.context_timestamp(self, attendance.check_out)
                    check_out_ampm = check_out_tz.strftime('%I:%M:%S %p')
                    message += f"⏰ Check-Out: {check_out_ampm}\n"
                
                if attendance.remark:
                    message += f"📝 Remark: {attendance.remark}\n"
                
                self._send_whatsapp_message(staff.phone, message)
                sent_count += 1
                
            except Exception as e:
                _logger.error(f"Error sending WhatsApp to staff {attendance.staff_id.name}: {str(e)}")
                failed_count += 1
        
        # Show summary message
        result_message = _("Staff Attendance WhatsApp messages sent!\n\n")
        result_message += _("Sent: %d\n") % sent_count
        result_message += _("Failed: %d") % failed_count
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Staff Attendance WhatsApp Messages'),
                'message': result_message,
                'type': 'success' if failed_count == 0 else 'warning',
                'sticky': False,
            }
        }
    
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
    def send_daily_classwise_summary(self):
        """Send daily classwise summary at configured time - called by cron"""
        try:
            # Check if classwise summary is enabled
            classwise_summary_enable = self.env['ir.config_parameter'].sudo().get_param(
                'school.classwise_summary_enable', 'False'
            )
            
            if classwise_summary_enable != 'True':
                _logger.info("Classwise summary is disabled, skipping...")
                return
            
            # Check if it's time to send (within 1 hour window)
            summary_send_time = float(self.env['ir.config_parameter'].sudo().get_param(
                'school.attendance_summary_send_time', default=17.5))
            
            current_time = fields.Datetime.now()
            current_hour = current_time.hour + (current_time.minute / 60.0)
            
            # Check if current hour matches the configured time (within 1 hour)
            if abs(current_hour - summary_send_time) > 1.0:
                _logger.debug(f"Not time to send summary yet. Current: {current_hour}, Configured: {summary_send_time}")
                return
            
            today = fields.Date.today()
            
            # Get all classes
            classes = self.env['school.class'].search([('active', '=', True)])
            
            for class_obj in classes:
                try:
                    # Get class teacher (prefer class's class_teacher_id, fallback to settings)
                    class_teacher = class_obj.class_teacher_id
                    if not class_teacher:
                        default_teacher_id = int(self.env['ir.config_parameter'].sudo().get_param(
                            'school.attendance_class_teacher_id', default=0) or 0)
                        if default_teacher_id:
                            class_teacher = self.env['school.teacher'].browse(default_teacher_id)
                    
                    if not class_teacher or not class_teacher.phone:
                        _logger.warning(f"No class teacher or phone for class {class_obj.name}, skipping...")
                        continue
                    
                    # Get all students in the class
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
                    
                    # Calculate statistics
                    total_students = len(students)
                    present_count = len(attendances.filtered(lambda a: a.status == 'present'))
                    absent_count = total_students - present_count
                    late_count = len(attendances.filtered(lambda a: a.status == 'late'))
                    
                    # Prepare summary message
                    message = f"📊 Daily Classwise Attendance Summary\n\n"
                    message += f"🏫 Class: {class_obj.name}\n"
                    message += f"📅 Date: {today}\n\n"
                    message += f"📊 Statistics:\n"
                    message += f"✅ Present: {present_count}\n"
                    message += f"❌ Absent: {absent_count}\n"
                    message += f"⏰ Late: {late_count}\n"
                    message += f"👥 Total: {total_students}\n\n"
                    
                    message += "📋 Present Students:\n"
                    for att in attendances.filtered(lambda a: a.status == 'present'):
                        message += f"✅ {att.student_id.name} (Roll: {att.student_id.roll_number or 'N/A'})\n"
                    
                    if absent_count > 0:
                        message += "\n❌ Absent Students:\n"
                        present_student_ids = attendances.filtered(lambda a: a.status == 'present').mapped('student_id.id')
                        absent_students = students.filtered(lambda s: s.id not in present_student_ids)
                        for student in absent_students:
                            message += f"❌ {student.name} (Roll: {student.roll_number or 'N/A'})\n"
                    
                    # Send to class teacher
                    self._send_whatsapp_message(class_teacher.phone, message)
                    _logger.info(f"Sent daily summary for class {class_obj.name} to {class_teacher.name}")
                    
                except Exception as e:
                    _logger.error(f"Error sending daily summary for class {class_obj.name}: {str(e)}")
                    
        except Exception as e:
            _logger.error(f"Error in send_daily_classwise_summary: {str(e)}")
