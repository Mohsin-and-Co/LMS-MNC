# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LmsSupportIssue(models.Model):
    _name = 'lms.support.issue'
    _description = 'LMS Support Issue (submitted by student on portal)'
    _order = 'create_date desc, id desc'

    student_id = fields.Many2one('school.student', string='Student', required=True, ondelete='cascade')
    student_name = fields.Char(string='Student Name', related='student_id.name', readonly=True, store=True)
    class_id = fields.Many2one('school.class', string='Class', related='student_id.class_id', readonly=True, store=True)
    class_display = fields.Char(string='Class', related='student_id.class_display', readonly=True, store=True)
    roll_number = fields.Char(string='Roll Number', related='student_id.roll_number', readonly=True, store=True)

    complaint_type = fields.Selection([
        ('academic', 'Academic Issue'),
        ('fee', 'Fee / Payment Issue'),
        ('portal', 'Online Portal / IT Issue'),
        ('classroom', 'Classroom or Facilities Issue'),
        ('administration', 'Administration / Office Issue'),
        ('others', 'Others'),
    ], string='Complaint Type', required=True, default='others')
    description = fields.Html(string='Description', required=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], string='Status', default='open', required=True)
    create_date = fields.Datetime(string='Submitted', readonly=True)

    def action_mark_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_mark_done(self):
        self.write({'state': 'done'})
