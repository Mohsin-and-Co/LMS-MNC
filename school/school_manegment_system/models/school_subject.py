from odoo import models, fields

class SchoolSubject(models.Model):
    _name = 'school.subject'
    _description = 'School Subject'

    name = fields.Char(string="Subject Name", required=True)
    class_id = fields.Many2one('school.class', string="Class", required=True)
    max_marks = fields.Integer(string="Maximum Marks")
    description = fields.Text(string="Description")
