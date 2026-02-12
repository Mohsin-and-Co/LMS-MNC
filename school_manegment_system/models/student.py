from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import traceback
import io
import base64

_logger = logging.getLogger(__name__)

# Try to import qrcode, make it optional
try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    _logger.warning("qrcode library not available. QR code generation will be disabled.")

class Student(models.Model):
    _name = 'school.student'
    _description = 'Student'

    name = fields.Char(string='Name', required=True)
    roll_number = fields.Char(string="Roll Number", copy=False)
    admission_number = fields.Char(string="Admission Number", readonly=True, copy=False)
    date_of_birth = fields.Date(string='Date of Birth', required=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender', required=True)
    blood_group = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'), ('b+', 'B+'), ('b-', 'B-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'), ('o+', 'O+'), ('o-', 'O-')
    ], string='Blood Group')
    address = fields.Text(string='Address')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    photo = fields.Binary(string='Photo', help='Student photo for ID card')
    parent_name = fields.Char(string='Parent/Guardian Name', required=True)
    parent_phone = fields.Char(string='Parent/Guardian Phone')
    parent_email = fields.Char(string='Parent/Guardian Email')
    partner_id = fields.Many2one('res.partner', string='Portal Account',
        help='Link parent/guardian portal user to view this student\'s results and info')
    class_id = fields.Many2one('school.class', string='Current Class')
    class_history_ids = fields.One2many('school.student.class.history', 'student_id', string='Class History')
    class_display = fields.Char(string='Class Info', compute='_compute_class_display', store=False,
                               help='Displays: Class Name - Section - Year')
    # Related field to show all classes student has been in (from history)
    all_class_ids = fields.Many2many('school.class', 
                                     compute='_compute_all_class_ids',
                                     string='All Classes',
                                     help='All classes this student has been enrolled in')
    subject_ids = fields.Many2many('school.subject', string="Subjects", help="Auto assigned based on class")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('admitted', 'Admitted'),
        ('left', 'Left')
    ], string='Status', default='draft')
    admission_date = fields.Date(string='Admission Date')
    leaving_date = fields.Date(string='Leaving Date')
    attendance_ids = fields.One2many('school.attendance', 'student_id', string='Attendance History')
    fee_ids = fields.One2many('school.fee', 'student_id', string='Fee History')
    attendance_count = fields.Integer(compute='_compute_attendance_count', string='Attendance Count')
    fee_count = fields.Integer(compute='_compute_fee_count', string='Fee Count')
    total_fee_amount = fields.Float(compute='_compute_fee_amounts', string='Total Fee Amount')
    paid_fee_amount = fields.Float(compute='_compute_fee_amounts', string='Paid Fee Amount')
    pending_fee_amount = fields.Float(compute='_compute_fee_amounts', string='Pending Fee Amount')
    
    # QR Code fields
    qr_code = fields.Char(string='QR Code', compute='_compute_qr_code', store=True)
    qr_code_image = fields.Binary(string='QR Code Image', compute='_compute_qr_code_image', store=False)
    qr_code_url = fields.Char(string='QR Code URL', compute='_compute_qr_code_url', store=False)

    partner_id = fields.Many2one(
        'res.partner',
        string='Student Partner',
        ondelete='restrict',
        help="Related partner for invoicing. Auto-created if not set."
    )

    # -----------------------
    # Automatic Partner Creation
    # -----------------------
    @api.model_create_multi
    def create(self, vals_list):
        IrSequence = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            # Generate admission_number if not provided
            if not vals.get('admission_number'):
                vals['admission_number'] = IrSequence.next_by_code('school.student')
            # Generate roll number if not provided
            if not vals.get('roll_number'):
                vals['roll_number'] = IrSequence.next_by_code('school.student.roll')
            # Create partner if not exists
            if not vals.get('partner_id') and vals.get('name'):
                partner = self.env['res.partner'].create({
                    'name': vals['name'],
                    'is_company': False,
                })
                vals['partner_id'] = partner.id
        records = super().create(vals_list)
        # Force QR code computation by accessing the fields
        # This ensures computed fields are triggered immediately
        for record in records:
            if record.admission_number:
                # Access computed fields to trigger computation
                _ = record.qr_code
                _ = record.qr_code_image
                _ = record.qr_code_url
                _logger.info(f"Student {record.name} created with admission number: {record.admission_number}, QR code: {record.qr_code}")
            else:
                _logger.warning(f"Student {record.name} created without admission number!")
        
        return records
    
    def _recompute_qr_code(self):
        """Recompute QR code and related fields - invalidate cache to trigger computed fields"""
        for record in self:
            if record.admission_number:
                # Invalidate cache to trigger @api.depends computation
                record.invalidate_recordset(['qr_code', 'qr_code_image', 'qr_code_url'])
                # Access fields to trigger computation
                _ = record.qr_code
                _ = record.qr_code_image
                _ = record.qr_code_url
                _logger.info(f"Recomputed QR code for student {record.name}: {record.qr_code}")

    # Update partner name if student name changes
    def write(self, vals):
        result = super().write(vals)
        if 'name' in vals:
            for rec in self:
                if rec.partner_id and not rec.partner_id.is_company:
                    rec.partner_id.write({'name': vals['name']})
        
        # QR code will be automatically recomputed by @api.depends('admission_number')
        # No need to manually recompute
        return result

    # -----------------------
    # Computed Fields
    # -----------------------
    @api.depends('attendance_ids')
    def _compute_attendance_count(self):
        for record in self:
            record.attendance_count = len(record.attendance_ids)

    @api.depends('fee_ids')
    def _compute_fee_count(self):
        for record in self:
            record.fee_count = len(record.fee_ids)

    @api.depends('fee_ids', 'fee_ids.amount', 'fee_ids.state')
    def _compute_fee_amounts(self):
        for record in self:
            record.total_fee_amount = sum(record.fee_ids.mapped('amount'))
            record.paid_fee_amount = sum(record.fee_ids.filtered(lambda f: f.state == 'paid').mapped('amount'))
            record.pending_fee_amount = sum(record.fee_ids.filtered(lambda f: f.state in ['pending', 'overdue']).mapped('amount'))

    # -----------------------
    # Actions
    # -----------------------
    def action_admit(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_("Only draft students can be admitted."))
            record.state = 'admitted'
            record.admission_date = fields.Date.today()
            
            # QR code will be automatically computed by @api.depends('admission_number')
            # Just invalidate cache to ensure it's computed
            if record.admission_number:
                record.invalidate_recordset(['qr_code', 'qr_code_image', 'qr_code_url'])
                _logger.info(f"Student {record.name} admitted, QR code will be auto-generated")

    def action_leave(self):
        for record in self:
            if record.state != 'admitted':
                raise ValidationError(_("Only admitted students can leave."))
            record.state = 'left'
            record.leaving_date = fields.Date.today()

    def action_test(self):
        """Button method to test the action"""
        for record in self:
            _logger.info("Test button clicked for student: %s", record.name)
    
    def action_regenerate_qr_code(self):
        """Manually regenerate QR code for student"""
        IrSequence = self.env['ir.sequence'].sudo()
        for record in self:
            # Ensure admission_number exists
            if not record.admission_number:
                record.admission_number = IrSequence.next_by_code('school.student')
            
            # Invalidate cache and recompute
            record.invalidate_recordset(['qr_code', 'qr_code_image', 'qr_code_url'])
            
            # Access fields to trigger computation
            qr_code = record.qr_code
            qr_image = record.qr_code_image
            qr_url = record.qr_code_url
            
            _logger.info(f"Regenerated QR code for student {record.name}: QR={qr_code}, Image={bool(qr_image)}, URL={qr_url}")
        
        # Show notification and reload
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('QR code regenerated successfully!'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def generate_qr_codes_for_all(self):
        """Generate QR codes for all students who don't have one"""
        IrSequence = self.env['ir.sequence'].sudo()
        students_without_qr = self.search([
            '|',
            ('qr_code', '=', False),
            ('admission_number', '=', False)
        ])
        
        count = 0
        for student in students_without_qr:
            try:
                if not student.admission_number:
                    student.admission_number = IrSequence.next_by_code('school.student')
                
                # Recompute QR code
                student._recompute_qr_code()
                count += 1
            except Exception as e:
                _logger.error(f"Error generating QR code for student {student.name}: {str(e)}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('QR Code Generation'),
                'message': _('Generated QR codes for %d students') % count,
                'type': 'success',
                'sticky': False,
            }
        }
    @api.depends('class_id.name', 'class_id.section', 'class_id.year')
    def _compute_class_display(self):
        for rec in self:
            if rec.class_id:
                parts = [rec.class_id.name or '']
                if rec.class_id.section:
                    parts.append(rec.class_id.section)
                if rec.class_id.year:
                    parts.append(rec.class_id.year)
                rec.class_display = ' - '.join(filter(None, parts))
            else:
                rec.class_display = ''
    
    @api.depends('class_history_ids.class_id')
    def _compute_all_class_ids(self):
        for rec in self:
            # Get unique classes from history
            classes = rec.class_history_ids.mapped('class_id')
            rec.all_class_ids = classes
    
    @api.onchange('class_id')
    def _onchange_class_id(self):
        if self.class_id:
            self.subject_ids = self.class_id.subject_ids
        else:
            self.subject_ids = [(5, 0, 0)]
    
    def write(self, vals):
        """Track class changes in history"""
        if 'class_id' in vals:
            for rec in self:
                old_class_id = rec.class_id.id if rec.class_id else False
                new_class_id = vals.get('class_id')
                
                # If class is changing
                if old_class_id != new_class_id and old_class_id:
                    # End the previous class history record
                    previous_history = self.env['school.student.class.history'].search([
                        ('student_id', '=', rec.id),
                        ('class_id', '=', old_class_id),
                        ('end_date', '=', False)
                    ], limit=1)
                    if previous_history:
                        previous_history.write({'end_date': fields.Date.today()})
                
                # Create new class history record if new class is set
                if new_class_id:
                    self.env['school.student.class.history'].create({
                        'student_id': rec.id,
                        'class_id': new_class_id,
                        'start_date': fields.Date.today(),
                    })
        
        return super().write(vals)
    
    def action_open_qr_scanner(self):
        """Open QR scanner wizard"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'QR Code Scanner',
            'res_model': 'school.qr.scanner.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_qr_code': self.qr_code if self.qr_code else False,
            }
        }
    
    def action_print_id_card(self):
        """Print Student ID Card"""
        return self.env.ref('school_manegment_system.action_report_student_card').report_action(self)
    
    # QR Code Methods
    @api.depends('admission_number')
    def _compute_qr_code(self):
        for record in self:
            if record.admission_number:
                qr_value = f"STUDENT_{record.admission_number}"
                record.qr_code = qr_value
                _logger.info(f"Computed QR code for student {record.name}: {qr_value}")
            else:
                record.qr_code = False
    
    @api.depends('qr_code')
    def _compute_qr_code_image(self):
        for record in self:
            if record.qr_code and QRCODE_AVAILABLE:
                try:
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(record.qr_code)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    # Binary field needs base64 encoded string
                    record.qr_code_image = base64.b64encode(buffer.getvalue())
                    _logger.info(f"Generated QR code image for student {record.name}")
                except Exception as e:
                    _logger.error(f"Error generating QR code for student {record.name}: {str(e)}")
                    record.qr_code_image = False
            else:
                if not QRCODE_AVAILABLE:
                    _logger.warning(f"QR code library not available for student {record.name}")
                record.qr_code_image = False
    
    @api.depends('qr_code')
    def _compute_qr_code_url(self):
        for record in self:
            if record.qr_code:
                # QR code URL is no longer needed for website scanning
                # Keep it for reference but don't use website route
                record.qr_code_url = f"QR Code: {record.qr_code}"
            else:
                record.qr_code_url = False