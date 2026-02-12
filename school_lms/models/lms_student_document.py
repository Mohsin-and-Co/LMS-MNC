# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LmsStudentDocument(models.Model):
    _name = 'lms.student.document'
    _description = 'LMS Student Document (uploaded by student on LMS or by teacher/admin in backend)'
    _order = 'create_date desc'

    name = fields.Char(string='Title', required=True)
    student_id = fields.Many2one('school.student', string='Student', required=True, ondelete='cascade')
    subject_id = fields.Many2one('school.subject', string='Subject', required=True, ondelete='cascade')
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='File',
        ondelete='cascade',
        copy=False,
        help='Uploaded file. Shown on student LMS Upload page.'
    )
    create_date = fields.Datetime(string='Uploaded', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.attachment_id:
                rec._link_attachment()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'attachment_id' in vals:
            for rec in self:
                if rec.attachment_id:
                    rec._link_attachment()
        return res

    def _link_attachment(self):
        """Ensure attachment is linked to this document (res_model, res_id)."""
        self.ensure_one()
        if self.attachment_id and (
            self.attachment_id.res_model != self._name or self.attachment_id.res_id != self.id
        ):
            self.attachment_id.sudo().write({
                'res_model': self._name,
                'res_id': self.id,
            })
