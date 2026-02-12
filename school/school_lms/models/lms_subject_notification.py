# -*- coding: utf-8 -*-
from odoo import models, fields


class LmsSubjectNotification(models.Model):
    _name = 'lms.subject.notification'
    _description = 'LMS Subject Notification (shown on LMS per subject)'
    _order = 'date desc, sequence, id desc'

    name = fields.Char(string='Title', required=True)
    subject_id = fields.Many2one('school.subject', string='Subject', required=True, ondelete='cascade')
    message = fields.Html(string='Message')
    date = fields.Date(string='Date', default=fields.Date.context_today)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
