from odoo import models, fields

class SchoolExam(models.Model):
    _name = 'school.exam'
    _description = 'School Exam'

    name = fields.Char(string='Exam Name', required=True)