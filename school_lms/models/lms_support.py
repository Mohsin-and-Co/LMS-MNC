# -*- coding: utf-8 -*-
from odoo import models, fields


class LmsSupport(models.Model):
    _name = 'lms.support'
    _description = 'LMS Support (help / FAQ entries for students)'
    _order = 'sequence, date desc, id desc'

    name = fields.Char(string='Title', required=True)
    description = fields.Html(string='Description')
    date = fields.Date(string='Date', default=fields.Date.context_today)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
