# -*- coding: utf-8 -*-
from odoo import models, fields


class LmsCalendarEvent(models.Model):
    _name = 'lms.calendar.event'
    _description = 'LMS Academic Calendar Event'
    _order = 'date desc, sequence, id desc'

    name = fields.Char(string='Event Title', required=True)
    date = fields.Date(string='Date', required=True)
    description = fields.Text(string='Description')
    event_type = fields.Selection([
        ('holiday', 'Holiday'),
        ('exam', 'Exam'),
        ('event', 'Event'),
        ('other', 'Other'),
    ], string='Type', default='event')
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        help='Leave empty to show for all countries. Set to show only for students in this country.'
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
