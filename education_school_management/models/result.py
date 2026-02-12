from odoo import models, fields, api



class SchoolResult(models.Model):
    _name = 'school.result'
    _description = 'School Result'

    roll_number = fields.Char(string="Roll Number", required=True)
    student_id = fields.Many2one('school.student', string="Student", store=True)
    class_id = fields.Many2one('school.class', string="Class", store=True)
    date = fields.Date(string="Date", default=fields.Date.context_today)
    exam_id = fields.Many2one('school.exam', string="Exam")  
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    line_ids = fields.One2many(
        'school.result.line', 'result_id', string="Subjects", domain=[('active', '=', True)]
    )

    total_marks = fields.Integer(string="Total Marks", compute="_compute_totals", store=True)
    obtained_marks = fields.Integer(string="Total Obtained Marks", compute="_compute_totals", store=True)
    percentage = fields.Float(string="Percentage", compute="_compute_totals", store=True)
    grade = fields.Selection(
        [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('F', 'F')],
        string="Grade",
        compute="_compute_totals",
        store=True
    )
    subject_id = fields.Many2one('school.subject', string='Subject')

    @api.onchange('roll_number')
    def _onchange_roll_number(self):
        """Auto-fill student, class, and load subjects when roll number is entered"""
        if not self.roll_number:
            self.student_id = False
            self.class_id = False
            self.line_ids = [(5, 0, 0)]
            return

        student = self.env['school.student'].search([('roll_number', '=', self.roll_number)], limit=1)
        if not student:
            self.student_id = False
            self.class_id = False
            self.line_ids = [(5, 0, 0)]
            return

        self.student_id = student.id
        self.class_id = student.class_id.id if student.class_id else False

        # Load subjects of this student
        self.line_ids = [(5, 0, 0)]  # clear previous
        if student.subject_ids:
            self.line_ids = [(0, 0, {
                'subject_id': subject.id,
                'obtained_marks': 0
            }) for subject in student.subject_ids]

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-set student_id, class_id, and subjects on create"""
        # Handle both single dict and list of dicts (Odoo can pass either)
        if not isinstance(vals_list, list):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if isinstance(vals, dict) and vals.get('roll_number'):
                student = self.env['school.student'].search([('roll_number', '=', vals['roll_number'])], limit=1)
                if student:
                    vals['student_id'] = student.id
                    vals['class_id'] = student.class_id.id if student.class_id else False

                    # If no subjects passed, auto-load them
                    if not vals.get('line_ids') and student.subject_ids:
                        vals['line_ids'] = [(0, 0, {
                            'subject_id': subject.id,
                            'obtained_marks': 0
                        }) for subject in student.subject_ids]
        return super().create(vals_list)

    def write(self, vals):
        """Auto-set student_id, class_id, and subjects on update"""
        if vals.get('roll_number'):
            student = self.env['school.student'].search([('roll_number', '=', vals['roll_number'])], limit=1)
            if student:
                vals['student_id'] = student.id
                vals['class_id'] = student.class_id.id if student.class_id else False

                # Refresh subjects if not provided
                if not vals.get('line_ids') and student.subject_ids:
                    vals['line_ids'] = [(5, 0, 0)] + [(0, 0, {
                        'subject_id': subject.id,
                        'obtained_marks': 0
                    }) for subject in student.subject_ids]
        return super().write(vals)

    @api.depends('line_ids.obtained_marks', 'line_ids.subject_id.max_marks')
    def _compute_totals(self):
        for rec in self:
            obtained = sum(line.obtained_marks or 0 for line in rec.line_ids)
            rec.obtained_marks = obtained

            total = sum(line.subject_id.max_marks or 0 for line in rec.line_ids)
            rec.total_marks = total

            rec.percentage = (obtained / total * 100) if total else 0

            if rec.percentage >= 90:
                rec.grade = 'A'
            elif rec.percentage >= 75:
                rec.grade = 'B'
            elif rec.percentage >= 60:
                rec.grade = 'C'
            elif rec.percentage >= 50:
                rec.grade = 'D'
            else:
                rec.grade = 'F'

    def action_print_result(self):
        """Print the result report as PDF"""
        return self.env.ref('education_school_management.report_school_result').report_action(self)
    
    def action_print_result_preview(self):
        """Preview the result report in browser (HTML)"""
        return {
            'type': 'ir.actions.report',
            'report_name': 'education_school_management.report_school_result_template',
            'report_type': 'qweb-html',
            'data': {'ids': self.ids},
            'context': dict(self.env.context),
        }
    
    def action_send_result_whatsapp(self):
        """Open wizard to send result via WhatsApp"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Send Result via WhatsApp',
            'res_model': 'school.result.whatsapp.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_class_id': self.class_id.id if self.class_id else False,
                'default_exam_id': self.exam_id.id if self.exam_id else False,
            }
        }


class SchoolResultLine(models.Model):
    _name = 'school.result.line'
    _description = 'School Result Line'

    result_id = fields.Many2one('school.result', string="Result", ondelete="cascade")
    subject_id = fields.Many2one('school.subject', string="Subject", required=True)
    obtained_marks = fields.Integer(string="Obtained Marks", default=0)
    active = fields.Boolean(string="Active", default=True)
