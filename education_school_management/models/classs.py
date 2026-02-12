from odoo import models, fields, api

class SchoolClass(models.Model):
    _name = 'school.class'
    _description = 'School Class'
    _order = 'year desc, name, section'

    name = fields.Char(string='Class Name', required=True)

    section = fields.Char(string='Section', help='Class section (e.g., A, B, C)')
    year = fields.Char(string='Academic Year', required=True, 
                      help='Academic year for this class (e.g., 2024-2025, 2025-2026)')
    capacity = fields.Integer(string='Capacity', default=30)
    active = fields.Boolean(default=True)
    student_ids = fields.One2many('school.student', 'class_id', string='Students')
    student_count = fields.Integer(compute='_compute_student_count', string='Number of Students')
    subject_ids = fields.One2many('school.subject', 'class_id', string='Subjects')
    result_ids = fields.One2many('school.result', 'class_id', string='Results')
    description = fields.Text(string='Description') 
    timetable_ids = fields.One2many("school.timetable", "class_id", string="Timetable")
    class_teacher_id = fields.Many2one('school.teacher', string='Class Teacher')
    class_attendance_phone = fields.Char(
        string='Class Attendance Phone Number',
        help="Phone number for classwise attendance summary messages"
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        help="Analytic account for this class's fees."
    )
    
    # Display field combining name, section, and year
    display_name_full = fields.Char(string='Class Display', compute='_compute_display_name_full', store=True)
    
    @api.depends('name', 'section', 'year')
    def _compute_display_name_full(self):
        for rec in self:
            parts = [rec.name or '']
            if rec.section:
                parts.append(rec.section)
            if rec.year:
                parts.append(rec.year)
            rec.display_name_full = ' - '.join(filter(None, parts))
    
    @api.depends('student_ids')
    def _compute_student_count(self):
        for record in self:
            record.student_count = len(record.student_ids)
    
    _sql_constraints = [
        ('code_year_uniq', 'unique(code, year)', 'Class code must be unique per academic year!')
    ]

    def action_print_timetable(self):
        """Print the timetable report as PDF"""
        return self.env.ref('education_school_management.action_report_class_timetable').report_action(self)
   