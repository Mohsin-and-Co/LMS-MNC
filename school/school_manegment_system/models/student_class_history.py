from odoo import models, fields, api, _
from datetime import datetime

class StudentClassHistory(models.Model):
    _name = 'school.student.class.history'
    _description = 'Student Class History'
    _order = 'start_date desc, id desc'

    student_id = fields.Many2one('school.student', string='Student', required=True, ondelete='cascade')
    class_id = fields.Many2one('school.class', string='Class', required=True)
    class_name = fields.Char(string='Class Name', related='class_id.name', store=True, readonly=True)
    class_section = fields.Char(string='Section', related='class_id.section', store=True, readonly=True)
    class_year = fields.Char(string='Academic Year', related='class_id.year', store=True, readonly=True)
    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.today)
    end_date = fields.Date(string='End Date', help='Leave empty if this is the current class')
    is_current = fields.Boolean(string='Current Class', compute='_compute_is_current', store=True)
    notes = fields.Text(string='Notes', help='Additional notes about this class change')
    
    @api.depends('end_date', 'student_id.class_id')
    def _compute_is_current(self):
        for rec in self:
            rec.is_current = (
                not rec.end_date and 
                rec.student_id.class_id.id == rec.class_id.id
            )
