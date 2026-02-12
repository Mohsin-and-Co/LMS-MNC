from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class QRScannerWizard(models.TransientModel):
    _name = 'school.qr.scanner.wizard'
    _description = 'QR Code Scanner Wizard for Student Attendance'

    # Kept for compatibility: old views/cache may trigger onchange('input_method')
    input_method = fields.Selection(
        [('manual', 'Manual')],
        string='Input Method',
        default='manual',
        required=True,
    )

    qr_code = fields.Char(string='QR Code', required=True, help="Enter QR code (STUDENT_XXXXX)")
    student_id = fields.Many2one('school.student', string='Student', readonly=True)
    student_name = fields.Char(string='Student Name', readonly=True)
    class_id = fields.Many2one('school.class', string='Class', readonly=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    status = fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late')
    ], string='Status', default='present', required=True)
    remark = fields.Text(string='Remarks')
    message = fields.Text(string='Message', readonly=True)
    attendance_id = fields.Many2one('school.attendance', string='Attendance Record', readonly=True)
    
    @api.onchange('qr_code')
    def _onchange_qr_code(self):
        """Auto-detect student from QR code"""
        if not self.qr_code:
            self.student_id = False
            self.student_name = False
            self.class_id = False
            self.message = False
            return

        # Normalize QR code
        qr_code = self.qr_code.strip().upper()
        
        # Check if it starts with STUDENT_
        if not qr_code.startswith('STUDENT_'):
            self.student_id = False
            self.student_name = False
            self.class_id = False
            self.message = _('Invalid QR code format. Must start with STUDENT_')
            return

        # Extract admission number
        admission_number = qr_code.replace('STUDENT_', '').strip()
        
        # Search for student
        student = self.env['school.student'].search([
            ('admission_number', '=', admission_number)
        ], limit=1)

        if not student:
            self.student_id = False
            self.student_name = False
            self.class_id = False
            self.message = _('Student not found with admission number: %s') % admission_number
            return

        # Check if student is admitted
        if student.state != 'admitted':
            self.student_id = False
            self.student_name = False
            self.class_id = False
            self.message = _('Student %s is not admitted. Current status: %s') % (student.name, student.state)
            return

        # Set student information
        self.student_id = student.id
        self.student_name = student.name
        self.class_id = student.class_id.id if student.class_id else False
        self.message = _('Student found: %s (Class: %s)') % (
            student.name,
            student.class_id.name if student.class_id else 'N/A'
        )

    def action_scan_and_create_attendance(self):
        """Process QR code and create attendance"""
        if not self.qr_code:
            raise ValidationError(_('Please enter QR code.'))

        # Normalize QR code
        qr_code = self.qr_code.strip().upper()
        
        if not qr_code.startswith('STUDENT_'):
            raise ValidationError(_('Invalid QR code format. Must start with STUDENT_'))

        # Extract admission number
        admission_number = qr_code.replace('STUDENT_', '').strip()
        
        # Search for student
        student = self.env['school.student'].search([
            ('admission_number', '=', admission_number)
        ], limit=1)

        if not student:
            raise ValidationError(_('Student not found with admission number: %s') % admission_number)

        # Check if student is admitted
        if student.state != 'admitted':
            raise ValidationError(_('Student %s is not admitted. Current status: %s') % (student.name, student.state))

        # Check if attendance already exists for this date
        existing_attendance = self.env['school.attendance'].search([
            ('student_id', '=', student.id),
            ('date', '=', self.date)
        ], limit=1)

        if existing_attendance:
            raise ValidationError(_('Attendance for %s on %s already exists!') % (student.name, self.date))

        # Create attendance record
        attendance_vals = {
            'student_id': student.id,
            'date': self.date,
            'status': self.status,
            'remark': self.remark,
            'state': 'confirmed'  # Auto-confirm when created via QR scan
        }

        attendance = self.env['school.attendance'].create(attendance_vals)
        self.attendance_id = attendance.id

        # WhatsApp notification is sent by attendance.create() when state='confirmed'
        try:
            if attendance.state == 'confirmed':
                attendance._send_whatsapp_notification(attendance)
                _logger.info(f"WhatsApp notification triggered for attendance {attendance.id}")
        except Exception as e:
            _logger.error(f"Error sending WhatsApp notification: {str(e)}")
        
        # Update message
        self.message = _('✅ Attendance created successfully for %s on %s\nStatus: %s') % (
            student.name,
            self.date,
            self.status.upper()
        )

        # Return notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Attendance recorded successfully for %s') % student.name,
                'type': 'success',
                'sticky': False,
            }
        }
