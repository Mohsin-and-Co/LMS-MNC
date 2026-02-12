from odoo import models, fields, api, _
import io
import base64
import logging

_logger = logging.getLogger(__name__)

# Try to import qrcode, make it optional
try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    _logger.warning("qrcode library not available. QR code generation will be disabled.")


class SchoolTeacher(models.Model):
    _name = "school.teacher"
    _description = "Teacher"

    # --------------------------------------------------
    # BASIC FIELDS
    # --------------------------------------------------
    name = fields.Char(string="Full Name", required=True)
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    photo = fields.Binary(string='Photo', help='Staff photo for ID card')
    subject_ids = fields.Many2many("school.subject", string="Subjects")
    hire_date = fields.Date(string="Hire Date")
    active = fields.Boolean(default=True)

    employee_id = fields.Char(
        string="Employee ID",
        readonly=True,
        copy=False
    )

    # --------------------------------------------------
    # HR EMPLOYEE LINK (NEW)
    # --------------------------------------------------
    hr_employee_id = fields.Many2one(
        'hr.employee',
        string='HR Employee',
        readonly=True,
        copy=False,
        ondelete='restrict'
    )

    # --------------------------------------------------
    # QR CODE
    # --------------------------------------------------
    qr_code = fields.Char(string='QR Code', compute='_compute_qr_code', store=True)
    qr_code_image = fields.Binary(string='QR Code Image', compute='_compute_qr_code_image')
    qr_code_url = fields.Char(string='QR Code URL', compute='_compute_qr_code_url')

    # --------------------------------------------------
    # ATTENDANCE
    # --------------------------------------------------
    attendance_ids = fields.One2many(
        'school.staff.attendance',
        'staff_id',
        string='Attendance History'
    )

    # --------------------------------------------------
    # PARTNER
    # --------------------------------------------------
    partner_id = fields.Many2one(
        'res.partner',
        string='Teacher Partner',
        ondelete='restrict',
        help="Related partner for invoicing. Auto-created if not set."
    )

    # --------------------------------------------------
    # CREATE
    # --------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        IrSequence = self.env['ir.sequence'].sudo()
        Partner = self.env['res.partner'].sudo()
        Employee = self.env['hr.employee'].sudo()

        for vals in vals_list:
            # ---------- Partner ----------
            if not vals.get('partner_id') and vals.get('name'):
                partner = Partner.create({
                    'name': vals['name'],
                    'email': vals.get('email'),
                    'phone': vals.get('phone'),
                    'is_company': False,
                })
                vals['partner_id'] = partner.id

            # ---------- Employee ID ----------
            if not vals.get('employee_id'):
                vals['employee_id'] = (
                    IrSequence.next_by_code('school.teacher.employee') or _('New')
                )

            # ---------- HR Employee ----------
            hr_employee = Employee.create({
                'name': vals.get('name'),
                'work_email': vals.get('email'),
                'work_phone': vals.get('phone'),
                'job_title': 'Teacher',
                'active': True,
            })
            vals['hr_employee_id'] = hr_employee.id

        return super().create(vals_list)

    # --------------------------------------------------
    # WRITE (SYNC)
    # --------------------------------------------------
    def write(self, vals):
        res = super().write(vals)

        for rec in self:
            # Sync partner
            if rec.partner_id:
                partner_vals = {}
                if 'name' in vals:
                    partner_vals['name'] = vals['name']
                if 'email' in vals:
                    partner_vals['email'] = vals['email']
                if 'phone' in vals:
                    partner_vals['phone'] = vals['phone']
                if partner_vals:
                    rec.partner_id.write(partner_vals)

            # Sync HR Employee
            if rec.hr_employee_id:
                emp_vals = {}
                if 'name' in vals:
                    emp_vals['name'] = vals['name']
                if 'email' in vals:
                    emp_vals['work_email'] = vals['email']
                if 'phone' in vals:
                    emp_vals['work_phone'] = vals['phone']
                if emp_vals:
                    rec.hr_employee_id.write(emp_vals)

        return res

    # --------------------------------------------------
    # QR CODE METHODS
    # --------------------------------------------------
    @api.depends('employee_id')
    def _compute_qr_code(self):
        for record in self:
            record.qr_code = (
                f"STAFF_{record.employee_id}"
                if record.employee_id else False
            )

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
                    record.qr_code_image = base64.b64encode(buffer.getvalue())
                except Exception as e:
                    _logger.error(
                        "QR generation error for %s: %s",
                        record.name, e
                    )
                    record.qr_code_image = False
            else:
                record.qr_code_image = False

    def _compute_qr_code_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            record.qr_code_url = (
                f"{base_url}/school/scan/{record.qr_code}"
                if record.qr_code else False
            )

    # --------------------------------------------------
    # ACTIONS
    # --------------------------------------------------
    def action_open_qr_scanner(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'QR Code Scanner',
            'res_model': 'school.qr.scanner.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_print_id_card(self):
        return self.env.ref(
            'education_school_management.action_report_staff_card'
        ).report_action(self)
