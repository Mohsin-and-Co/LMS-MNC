from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SchoolTimetable(models.Model):
    _name = 'school.timetable'
    _description = 'School Timetable'
    _order = "day_of_week, start_time"

    name = fields.Char(string="Name")
    class_id = fields.Many2one('school.class', string="Class", required=True)
    teacher_id = fields.Many2one('school.teacher', string="Teacher", required=True)
    subject_id = fields.Many2one('school.subject', string="Subject", required=True)
    day_of_week = fields.Selection([
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
    ], string="Day", required=True)
    start_time = fields.Float(string="Start Time", required=True, help="Use 24h format, e.g. 9.0 for 9:00 AM, 13.5 for 1:30 PM")
    end_time = fields.Float(string="End Time", required=True)
    start_time_display = fields.Char(string="Start Time", compute='_compute_time_display', store=False)
    end_time_display = fields.Char(string="End Time", compute='_compute_time_display', store=False)

    def _float_to_ampm(self, time_float):
        """Convert 24-hour float time to AM/PM format string"""
        if not time_float:
            return ''
        hours = int(time_float)
        minutes = int((time_float - hours) * 60)
        period = 'AM' if hours < 12 else 'PM'
        if hours == 0:
            display_hours = 12
        elif hours > 12:
            display_hours = hours - 12
        else:
            display_hours = hours
        return f"{display_hours}:{minutes:02d} {period}"

    @api.depends('start_time', 'end_time')
    def _compute_time_display(self):
        """Compute AM/PM formatted time strings"""
        for rec in self:
            rec.start_time_display = rec._float_to_ampm(rec.start_time)
            rec.end_time_display = rec._float_to_ampm(rec.end_time)

    def name_get(self):
        """Show subject + class + day in list views"""
        result = []
        for rec in self:
            start_str = rec._float_to_ampm(rec.start_time)
            end_str = rec._float_to_ampm(rec.end_time)
            name = f"[{rec.day_of_week.capitalize()} {start_str}-{end_str}] {rec.subject_id.name} ({rec.class_id.name})"
            result.append((rec.id, name))
        return result

    @api.constrains('start_time', 'end_time')
    def _check_time_validity(self):
        """Ensure valid time ranges"""
        for rec in self:
            if rec.start_time >= rec.end_time:
                raise ValidationError("End time must be greater than Start time.")
            if rec.start_time < 0 or rec.end_time > 24:
                raise ValidationError("Time must be between 0 and 24 (24h format).")

    @api.constrains('teacher_id', 'day_of_week', 'start_time', 'end_time')
    def _check_teacher_double_booking(self):
        """Prevent teacher from handling two classes at same time"""
        for rec in self:
            overlaps = self.env['school.timetable'].search([
                ('id', '!=', rec.id),
                ('teacher_id', '=', rec.teacher_id.id),
                ('day_of_week', '=', rec.day_of_week),
                ('start_time', '<', rec.end_time),
                ('end_time', '>', rec.start_time),
            ], limit=1)
            if overlaps:
                start_str = rec._float_to_ampm(rec.start_time)
                end_str = rec._float_to_ampm(rec.end_time)
                raise ValidationError(
                    f"Teacher {rec.teacher_id.name} already has a class "
                    f"on {rec.day_of_week.capitalize()} between {start_str} and {end_str}."
                )

    @api.constrains('class_id', 'day_of_week', 'start_time', 'end_time')
    def _check_class_double_booking(self):
        """Prevent one class from having two different teachers in same time slot"""
        for rec in self:
            overlaps = self.env['school.timetable'].search([
                ('id', '!=', rec.id),
                ('class_id', '=', rec.class_id.id),
                ('day_of_week', '=', rec.day_of_week),
                ('start_time', '<', rec.end_time),
                ('end_time', '>', rec.start_time),
            ], limit=1)
            if overlaps:
                start_str = rec._float_to_ampm(rec.start_time)
                end_str = rec._float_to_ampm(rec.end_time)
                raise ValidationError(
                    f"Class {rec.class_id.name} already has another subject scheduled "
                    f"on {rec.day_of_week.capitalize()} between {start_str} and {end_str}."
                )
    def action_print_timetable(self):
        """Print the timetable report as PDF"""
        return self.env.ref('education_school_management.action_report_class_timetable').report_action(self)
   