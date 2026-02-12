# -*- coding: utf-8 -*-
from odoo import models, fields, api
import base64


class LmsSubjectMaterial(models.Model):
    _name = 'lms.subject.material'
    _description = 'LMS Subject Material (Documents, Videos, Updates)'
    _order = 'sequence, publish_date desc, id desc'

    name = fields.Char(string='Title', required=True)
    subject_id = fields.Many2one('school.subject', string='Subject', required=True, ondelete='cascade')
    material_type = fields.Selection([
        ('document', 'Document'),
        ('image', 'Pictures/Images'),
        ('video', 'Video'),
    ], string='Type', required=True, default='document')
    description = fields.Html(string='Description')
    # Direct file upload: user selects file in form; we create ir.attachment
    file_upload = fields.Binary(string='Upload File', attachment=False, copy=False,
                               help='Select file for Document/Image/Update. Will appear on LMS.')
    file_name = fields.Char(string='File Name', copy=False)
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Attached File',
        ondelete='set null',
        copy=False,
        readonly=True,
        help='Created from Upload File. Shown on LMS for students.'
    )
    attachment_filename = fields.Char(
        string='File Name',
        related='attachment_id.name',
        readonly=True
    )
    url = fields.Char(string='Video URL (optional)', help='Optional external link for video. You can also upload a video file above.')
    publish_date = fields.Date(string='Publish Date', default=fields.Date.context_today)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        files = []
        clean_list = []
        for vals in vals_list:
            v = dict(vals)
            files.append((v.pop('file_upload', None), v.pop('file_name', None)))
            v.pop('attachment_id', None)
            clean_list.append(v)
        records = super().create(clean_list)
        for rec, (file_upload, file_name) in zip(records, files):
            if file_upload and file_name:
                rec._create_attachment_from_upload(file_upload, file_name)
            elif rec.attachment_id:
                rec._link_attachment_to_material()
        return records

    def write(self, vals):
        file_upload = vals.pop('file_upload', None)
        file_name = vals.pop('file_name', None)
        res = super().write(vals)
        if file_upload and file_name:
            for rec in self:
                rec._create_attachment_from_upload(file_upload, file_name)
        elif 'attachment_id' in vals or (file_upload is not None and not file_upload):
            for rec in self:
                if rec.attachment_id:
                    rec._link_attachment_to_material()
        return res

    def _create_attachment_from_upload(self, file_upload, file_name):
        self.ensure_one()
        Attachment = self.env['ir.attachment'].sudo()
        if self.attachment_id:
            self.attachment_id.sudo().unlink()
        att = Attachment.create({
            'name': file_name or 'material',
            'res_model': self._name,
            'res_id': self.id,
            'datas': file_upload,
            'type': 'binary',
        })
        self.sudo().write({'attachment_id': att.id})

    def _link_attachment_to_material(self):
        """Ensure attachment is linked to this material so it is served correctly on LMS."""
        self.ensure_one()
        if self.attachment_id and (self.attachment_id.res_model != self._name or self.attachment_id.res_id != self.id):
            self.attachment_id.sudo().write({
                'res_model': self._name,
                'res_id': self.id,
            })

    def _get_video_embed_url(self):
        """Convert watch URL to embed URL for same-page iframe (YouTube, Vimeo, or return as-is)."""
        if not self:
            return ''
        self.ensure_one()
        url = (self.url or '').strip()
        if not url:
            return ''
        import re
        # YouTube: watch?v=XXX or youtu.be/XXX
        m = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)', url)
        if m:
            return 'https://www.youtube.com/embed/%s' % m.group(1)
        m = re.search(r'vimeo\.com/(?:video/)?(\d+)', url)
        if m:
            return 'https://player.vimeo.com/video/%s' % m.group(1)
        return url

    def action_open_attachment(self):
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=1' % self.attachment_id.id,
                'target': 'new',
            }
        return False
