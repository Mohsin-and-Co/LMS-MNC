from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class SchoolClass(models.Model):
    _name = 'school.class'
    _description = 'School Class'
    _order = 'name'

    name = fields.Char(string='Class Name', required=True)
    code = fields.Char(string='Class Code', required=True)
    capacity = fields.Integer(string='Class Capacity', default=30)
    active = fields.Boolean(default=True)
    student_ids = fields.One2many('school.student', 'class_id', string='Students')
    student_count = fields.Integer(compute='_compute_student_count', string='Number of Students')

    @api.depends('student_ids')
    def _compute_student_count(self):
        for record in self:
            record.student_count = len(record.student_ids)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Class code must be unique!')
    ] 
    subject_ids = fields.Many2many(
        'school.subject',
        string="Subjects",
        help="Subjects assigned to this class."
    )