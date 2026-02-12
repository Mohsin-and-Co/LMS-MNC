from odoo import models, fields, api, _
import logging
from datetime import datetime
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False
    _logger.warning("pytz library not available. Timezone features will be limited.")

_logger = logging.getLogger(__name__)

class SchoolAttendanceSettings(models.TransientModel):
    _name = 'school.attendance.settings'
    _description = 'School Attendance Settings'

    # Attendance WhatsApp Settings
    attendance_auto_send_enable = fields.Boolean(
        string="Enable Auto Send Attendance Messages",
        default=True,
        help="Automatically send WhatsApp messages when attendance is scanned via QR code"
    )
    attendance_staff_message_enable = fields.Boolean(
        string="Enable Staff Attendance WhatsApp Messages",
        default=False,
        help="Enable automatic WhatsApp messages when staff attendance is scanned"
    )
    attendance_classwise_message_enable = fields.Boolean(
        string="Enable Classwise Attendance WhatsApp Messages",
        default=False,
        help="Enable automatic WhatsApp messages when student attendance is scanned"
    )
    
    # Student Attendance to Teacher Settings
    student_attendance_teacher_enable = fields.Boolean(
        string="Enable Student Attendance Message to Teacher",
        default=False,
        help="Send student attendance messages to class teacher"
    )
    student_attendance_teacher_time = fields.Float(
        string="Teacher Message Send Time",
        default=9.0,
        help="Time to send student attendance messages to teacher (24 hour format, e.g., 9.0 for 9:00 AM)"
    )
    
    # Classwise Summary Settings
    classwise_summary_enable = fields.Boolean(
        string="Enable Classwise Summary",
        default=False,
        help="Enable daily classwise attendance summary"
    )
    class_teacher_id = fields.Many2one(
        'school.teacher',
        string="Default Class Teacher",
        help="Default class teacher to receive classwise summary (can be overridden per class)"
    )
    summary_send_time = fields.Float(
        string="Summary Send Time",
        help="Time to send daily classwise summary (24 hour format, e.g., 17.5 for 5:30 PM)"
    )
    
    # Staff Attendance Settings
    staff_attendance_group_phone = fields.Char(
        string="Staff Attendance Group Phone Number",
        help="Phone number for staff attendance group messages (one-by-one messages will be sent to this number)"
    )
    
    # Student Attendance Settings
    student_attendance_classwise_enable = fields.Boolean(
        string="Enable Classwise Student Attendance Messages",
        default=False,
        help="Enable classwise summary messages for student attendance"
    )
    
    # Attendance Time Settings
    attendance_start_time = fields.Float(
        string="Attendance Start Time",
        default=8.0,
        help="Start time for attendance (24 hour format, e.g., 8.0 for 8:00 AM)"
    )
    attendance_end_time = fields.Float(
        string="Attendance End Time",
        default=17.0,
        help="End time for attendance (24 hour format, e.g., 17.0 for 5:00 PM)"
    )
    
    # Auto-send Messages for Absent/Leave Students
    auto_send_absent_leave_enable = fields.Boolean(
        string="Enable Auto-send Messages for Absent/Leave Students",
        default=False,
        help="Automatically send messages for absent/leave students after attendance end time"
    )
    
    # Timezone Settings
    timezone = fields.Selection(
        '_get_timezones',
        string="Timezone",
        default='Asia/Karachi',
        help="Select timezone for attendance timestamps"
    )
    
    @api.model
    def _get_timezones(self):
        """Get list of timezones"""
        if not PYTZ_AVAILABLE:
            return [('UTC', 'UTC')]
        timezones = []
        for tz in pytz.all_timezones:
            timezones.append((tz, tz))
        return timezones
    
    @api.model
    def get_values(self):
        """Load existing values from ir.config_parameter"""
        res = {}
        ICPSudo = self.env['ir.config_parameter'].sudo()
        res.update({
            'attendance_auto_send_enable': ICPSudo.get_param('school.attendance_auto_send_enable', 'True') == 'True',
            'attendance_staff_message_enable': ICPSudo.get_param('school.attendance_staff_message_enable', 'False') == 'True',
            'attendance_classwise_message_enable': ICPSudo.get_param('school.attendance_classwise_message_enable', 'False') == 'True',
            'student_attendance_teacher_enable': ICPSudo.get_param('school.student_attendance_teacher_enable', 'False') == 'True',
            'student_attendance_teacher_time': float(ICPSudo.get_param('school.student_attendance_teacher_time', default=9.0)),
            'classwise_summary_enable': ICPSudo.get_param('school.classwise_summary_enable', 'False') == 'True',
            'class_teacher_id': int(ICPSudo.get_param('school.attendance_class_teacher_id', default=0)) or False,
            'summary_send_time': float(ICPSudo.get_param('school.attendance_summary_send_time', default=17.5)),
            'staff_attendance_group_phone': ICPSudo.get_param('school.staff_attendance_group_phone', default=''),
            'student_attendance_classwise_enable': ICPSudo.get_param('school.student_attendance_classwise_enable', 'False') == 'True',
            'attendance_start_time': float(ICPSudo.get_param('school.attendance_start_time', default=8.0)),
            'attendance_end_time': float(ICPSudo.get_param('school.attendance_end_time', default=17.0)),
            'auto_send_absent_leave_enable': ICPSudo.get_param('school.auto_send_absent_leave_enable', 'False') == 'True',
            'timezone': ICPSudo.get_param('school.attendance_timezone', default='Asia/Karachi'),
        })
        return res

    def set_values(self):
        """Save values in ir.config_parameter"""
        ICPSudo = self.env['ir.config_parameter'].sudo()
        ICPSudo.set_param('school.attendance_auto_send_enable', str(self.attendance_auto_send_enable))
        ICPSudo.set_param('school.attendance_staff_message_enable', str(self.attendance_staff_message_enable))
        ICPSudo.set_param('school.attendance_classwise_message_enable', str(self.attendance_classwise_message_enable))
        ICPSudo.set_param('school.student_attendance_teacher_enable', str(self.student_attendance_teacher_enable))
        ICPSudo.set_param('school.student_attendance_teacher_time', str(self.student_attendance_teacher_time))
        ICPSudo.set_param('school.classwise_summary_enable', str(self.classwise_summary_enable))
        ICPSudo.set_param('school.attendance_class_teacher_id', str(self.class_teacher_id.id) if self.class_teacher_id else '')
        ICPSudo.set_param('school.attendance_summary_send_time', str(self.summary_send_time))
        ICPSudo.set_param('school.staff_attendance_group_phone', str(self.staff_attendance_group_phone or ''))
        ICPSudo.set_param('school.student_attendance_classwise_enable', str(self.student_attendance_classwise_enable))
        ICPSudo.set_param('school.attendance_start_time', str(self.attendance_start_time))
        ICPSudo.set_param('school.attendance_end_time', str(self.attendance_end_time))
        ICPSudo.set_param('school.auto_send_absent_leave_enable', str(self.auto_send_absent_leave_enable))
        ICPSudo.set_param('school.attendance_timezone', str(self.timezone))
