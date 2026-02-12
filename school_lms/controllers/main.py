# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging
import base64

_logger = logging.getLogger(__name__)


def _get_current_student():
    """Return the student record linked to current user (partner_id, parent_email, or roll_number as login)."""
    env = request.env
    user = env.user
    if not user or user._is_public():
        return env['school.student'].browse([])
    partner = user.partner_id
    email = (partner.email or '').strip().lower()
    login = (user.login or '').strip()
    domain = [
        '|', '|', '|',
        ('partner_id', '=', partner.id),
        ('parent_email', '=ilike', email),
        ('parent_phone', '=', partner.phone or ''),
        ('roll_number', '=', login),
    ]
    return env['school.student'].sudo().search(domain, limit=1)


class StudentLmsController(http.Controller):

    def _allowed_material_types(self):
        return {'all', 'document', 'image', 'video', 'update'}  # update = legacy for image

    def _normalize_material_type(self, value):
        v = (value or '').strip().lower()
        return v if v in self._allowed_material_types() else 'all'

    def _get_subject_teacher(self, student, subject):
        """Return teacher for this subject in student's class from timetable."""
        if not student or not student.class_id or not subject:
            return request.env['school.teacher'].browse([])
        tt = request.env['school.timetable'].sudo().search([
            ('class_id', '=', student.class_id.id),
            ('subject_id', '=', subject.id),
        ], limit=1)
        return tt.teacher_id if tt else request.env['school.teacher'].browse([])

    @http.route('/school/lms', type='http', auth='user', website=True)
    def lms_root(self, **kw):
        return request.redirect('/school/lms/home')

    @http.route('/school/lms/home', type='http', auth='user', website=True)
    def lms_home(self, **kw):
        student = _get_current_student()
        if not student:
            return request.render('school_lms.lms_home', {
                'student': None,
                'page': 'home',
                'subjects_with_teachers': [],
                'subject_notifications': [],
                'error_message': 'No student record linked to your account. Please contact the school.',
            })
        subjects_with_teachers = []
        for subj in student.subject_ids:
            teacher = self._get_subject_teacher(student, subj)
            # Notifications for this subject only (for icon under teacher)
            subj_notifications = request.env['lms.subject.notification'].sudo().search([
                ('subject_id', '=', subj.id),
                ('active', '=', True),
            ], order='date desc, sequence, id desc', limit=5)
            subjects_with_teachers.append({
                'subject': subj,
                'teacher': teacher,
                'subject_notifications': subj_notifications,
            })
        # Latest subject notifications (all subjects) for top card
        subject_notification_ids = request.env['lms.subject.notification'].sudo().search([
            ('subject_id', 'in', student.subject_ids.ids),
            ('active', '=', True),
        ], order='date desc, sequence, id desc', limit=10)
        return request.render('school_lms.lms_home', {
            'student': student,
            'page': 'home',
            'subjects_with_teachers': subjects_with_teachers,
            'subject_notifications': subject_notification_ids,
        })

    @http.route('/school/lms/subject/<int:subject_id>', type='http', auth='user', website=True)
    def lms_subject_detail(self, subject_id, **kw):
        student = _get_current_student()
        if not student:
            return request.redirect('/school/lms/home')
        subject = request.env['school.subject'].sudo().browse(subject_id)
        if not subject.exists() or subject not in student.subject_ids:
            return request.redirect('/school/lms/home')
        teacher = self._get_subject_teacher(student, subject)
        selected_type = self._normalize_material_type(kw.get('type'))
        domain = [
            ('subject_id', '=', subject_id),
            ('active', '=', True),
        ]
        if selected_type != 'all':
            if selected_type == 'image':
                domain.append(('material_type', 'in', ['image', 'update']))
            else:
                domain.append(('material_type', '=', selected_type))
        materials = request.env['lms.subject.material'].sudo().search(domain, order='sequence, publish_date desc, id desc')

        # Notifications: latest materials for this subject (always unfiltered)
        notifications = request.env['lms.subject.material'].sudo().search([
            ('subject_id', '=', subject_id),
            ('active', '=', True),
        ], order='publish_date desc, id desc', limit=8)
        # Subject notifications (announcements per subject)
        subject_notifications = request.env['lms.subject.notification'].sudo().search([
            ('subject_id', '=', subject_id),
            ('active', '=', True),
        ], order='date desc, sequence, id desc', limit=10)

        # Counts for tabs
        all_for_counts = request.env['lms.subject.material'].sudo().search([
            ('subject_id', '=', subject_id),
            ('active', '=', True),
        ])
        type_counts = {
            'all': len(all_for_counts),
            'document': len(all_for_counts.filtered(lambda r: r.material_type == 'document')),
            'image': len(all_for_counts.filtered(lambda r: r.material_type == 'image')),
            'video': len(all_for_counts.filtered(lambda r: r.material_type == 'video')),
            'update': len(all_for_counts.filtered(lambda r: r.material_type == 'update')),
        }
        return request.render('school_lms.lms_subject_detail', {
            'student': student,
            'page': 'subject',
            'subject': subject,
            'teacher': teacher,
            'materials': materials,
            'selected_type': selected_type,
            'type_counts': type_counts,
            'notifications': notifications,
            'subject_notifications': subject_notifications,
        })

    @http.route('/school/lms/materials', type='http', auth='user', website=True)
    def lms_materials(self, **kw):
        """Materials are shown only when opening a subject; redirect to home."""
        return request.redirect('/school/lms/home')

    @http.route('/school/lms/fee', type='http', auth='user', website=True)
    def lms_fee(self, **kw):
        student = _get_current_student()
        fees = request.env['school.fee'].sudo().browse([])
        if student:
            fees = request.env['school.fee'].sudo().search([
                ('student_id', '=', student.id),
            ], order='due_date desc')
        return request.render('school_lms.lms_fee', {
            'student': student,
            'page': 'fee',
            'fees': fees,
        })

    @http.route('/school/lms/calendar', type='http', auth='user', website=True)
    def lms_calendar(self, year=None, month=None, **kw):
        from datetime import date
        student = _get_current_student()
        today = date.today()
        try:
            y = int(year) if year else today.year
            m = int(month) if month else today.month
        except (TypeError, ValueError):
            y, m = today.year, today.month
        domain = [('active', '=', True)]
        if student and student.partner_id and student.partner_id.country_id:
            domain.append('|')
            domain.append(('country_id', '=', False))
            domain.append(('country_id', '=', student.partner_id.country_id.id))
        else:
            domain.append(('country_id', '=', False))
        events = request.env['lms.calendar.event'].sudo().search(
            domain, order='date asc, sequence, id asc'
        )
        # Build month grid: 6 rows x 7 cols; each cell = (day_number, events_on_that_day)
        import calendar as cal
        cal_obj = cal.Calendar(cal.MONDAY)
        flat_days = list(cal_obj.itermonthdays(y, m))
        while len(flat_days) < 42:
            flat_days.append(0)
        flat_days = flat_days[:42]
        events_by_date = {}
        for ev in events:
            d = ev.date
            if d and d.year == y and d.month == m:
                key = d.day
                events_by_date.setdefault(key, []).append(ev)
        # rows = list of 6 rows, each row = list of 7 (day_num, events_list)
        calendar_rows = []
        for row_idx in range(6):
            row = []
            for col_idx in range(7):
                idx = row_idx * 7 + col_idx
                day_num = flat_days[idx] if idx < len(flat_days) else 0
                day_events = events_by_date.get(day_num, []) if day_num else []
                is_today = day_num and y == today.year and m == today.month and day_num == today.day
                row.append({'day': day_num, 'events': day_events, 'is_today': is_today})
            calendar_rows.append(row)
        weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        from datetime import date as date_type
        month_name = date_type(y, m, 1).strftime('%B %Y')
        return request.render('school_lms.lms_calendar', {
            'student': student,
            'page': 'calendar',
            'events': events,
            'year': y,
            'month': m,
            'month_name': month_name,
            'calendar_rows': calendar_rows,
            'weekdays': weekdays,
            'today': today,
        })

    @http.route('/school/lms/timetable', type='http', auth='user', website=True)
    def lms_timetable(self, **kw):
        student = _get_current_student()
        slots = request.env['school.timetable'].sudo().browse([])
        if student and student.class_id:
            slots = request.env['school.timetable'].sudo().search([
                ('class_id', '=', student.class_id.id),
            ], order='day_of_week, start_time')
        return request.render('school_lms.lms_timetable', {
            'student': student,
            'page': 'timetable',
            'slots': slots,
        })

    @http.route('/school/lms/result', type='http', auth='user', website=True)
    def lms_result(self, **kw):
        student = _get_current_student()
        results = request.env['school.result'].sudo().browse([])
        if student:
            results = request.env['school.result'].sudo().search([
                ('student_id', '=', student.id),
            ], order='date desc, id desc')
        return request.render('school_lms.lms_result', {
            'student': student,
            'page': 'result',
            'results': results,
        })

    @http.route('/school/lms/support', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def lms_support(self, **post):
        student = _get_current_student()
        support_items = request.env['lms.support'].sudo().search([
            ('active', '=', True),
        ], order='sequence, date desc, id desc')
        error = None
        complaint_types = ('academic', 'fee', 'portal', 'classroom', 'administration', 'others')
        if request.httprequest.method == 'POST':
            subject_id = post.get('subject_id')
            complaint_type = (post.get('complaint_type') or 'others').strip()
            if complaint_type not in complaint_types:
                complaint_type = 'others'
            description = (post.get('description') or '').strip()
            try:
                subject_id = int(subject_id) if subject_id else 0
            except (TypeError, ValueError):
                subject_id = 0
            if not student:
                error = 'Please log in as a student to submit an issue.'
            elif not description:
                error = 'Please enter a description of your issue.'
            else:
                vals = {
                    'student_id': student.id,
                    'complaint_type': complaint_type,
                    'description': description,
                }
                if subject_id and student and subject_id in student.subject_ids.ids:
                    vals['subject_id'] = subject_id
                request.env['lms.support.issue'].sudo().create(vals)
                return request.redirect('/school/lms/support?submitted=1')
        my_issues = request.env['lms.support.issue'].sudo().browse([])
        if student:
            my_issues = request.env['lms.support.issue'].sudo().search([
                ('student_id', '=', student.id),
            ], order='create_date desc')
        complaint_type_labels = dict(
            request.env['lms.support.issue']._fields['complaint_type']._description_selection(request.env)
        )
        return request.render('school_lms.lms_support', {
            'student': student,
            'page': 'support',
            'support_items': support_items,
            'my_issues': my_issues,
            'subjects': student.subject_ids if student else request.env['school.subject'].sudo().browse([]),
            'complaint_type_labels': complaint_type_labels,
            'error': error,
            'submitted': post.get('submitted') == '1',
        })

    @http.route('/school/lms/upload', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def lms_upload(self, **post):
        """Student document upload: form and list of my uploads."""
        student = _get_current_student()
        if not student:
            return request.redirect('/school/lms/home')
        error = None
        if request.httprequest.method == 'POST':
            title = (post.get('title') or '').strip()
            subject_id = post.get('subject_id')
            try:
                subject_id = int(subject_id) if subject_id else 0
            except (TypeError, ValueError):
                subject_id = 0
            if not title:
                error = 'Please enter a title.'
            elif not subject_id or subject_id not in student.subject_ids.ids:
                error = 'Please select a valid subject.'
            else:
                file_storage = request.httprequest.files.get('file')
                if not file_storage or not file_storage.filename:
                    error = 'Please select a file to upload.'
                else:
                    Attachment = request.env['ir.attachment'].sudo()
                    doc = request.env['lms.student.document'].sudo()
                    doc_rec = doc.create({
                        'name': title,
                        'student_id': student.id,
                        'subject_id': subject_id,
                        'attachment_id': False,
                    })
                    att = Attachment.create({
                        'name': file_storage.filename,
                        'res_model': 'lms.student.document',
                        'res_id': doc_rec.id,
                        'datas': base64.b64encode(file_storage.read()),
                        'type': 'binary',
                    })
                    doc_rec.write({'attachment_id': att.id})
                    return request.redirect('/school/lms/upload?uploaded=1')
        my_uploads = request.env['lms.student.document'].sudo().search([
            ('student_id', '=', student.id),
        ], order='create_date desc')
        return request.render('school_lms.lms_upload', {
            'student': student,
            'page': 'upload',
            'subjects': student.subject_ids,
            'my_uploads': my_uploads,
            'error': error,
            'uploaded': post.get('uploaded') == '1',
        })

    @http.route('/school/lms/upload/download/<int:doc_id>', type='http', auth='user', website=False)
    def lms_upload_download(self, doc_id, **kw):
        """Serve student's own upload for download (portal users)."""
        student = _get_current_student()
        if not student:
            return request.not_found()
        doc = request.env['lms.student.document'].sudo().browse(doc_id)
        if not doc.exists() or doc.student_id.id != student.id or not doc.attachment_id:
            return request.not_found()
        att = doc.attachment_id
        if not att.datas:
            return request.not_found()
        return request.make_response(
            base64.b64decode(att.datas),
            headers=[
                ('Content-Type', att.mimetype or 'application/octet-stream'),
                ('Content-Disposition', 'attachment; filename="%s"' % (att.name or 'download')),
            ],
        )

    @http.route('/school/lms/change-password', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def lms_change_password(self, **post):
        student = _get_current_student()
        if request.httprequest.method == 'POST':
            current = (post.get('current_password') or '').strip()
            new_pwd = (post.get('new_password') or '').strip()
            confirm = (post.get('confirm_password') or '').strip()
            if not current or not new_pwd or new_pwd != confirm:
                return request.render('school_lms.lms_change_password', {
                    'student': student,
                    'page': 'change_password',
                    'error': 'Please fill all fields and ensure new password matches confirmation.',
                })
            user = request.env.user
            if not user or not user.exists() or user._is_public():
                return request.render('school_lms.lms_change_password', {
                    'student': student,
                    'page': 'change_password',
                    'error': 'Session invalid. Please log in again.',
                })
            # Verify current password using same hash as Odoo login (works in Odoo 19)
            if not user.sudo()._lms_verify_password(current):
                return request.render('school_lms.lms_change_password', {
                    'student': student,
                    'page': 'change_password',
                    'error': 'Current password is incorrect.',
                })
            try:
                user.sudo().with_context(no_reset_password=True).write({'password': new_pwd})
            except Exception:
                return request.render('school_lms.lms_change_password', {
                    'student': student,
                    'page': 'change_password',
                    'error': 'Could not update password. Try a stronger password.',
                })
            return request.redirect('/school/lms/home?pwd=updated')
        return request.render('school_lms.lms_change_password', {
            'student': student,
            'page': 'change_password',
            'error': None,
        })

    @http.route('/school/lms/forgot-password', type='http', auth='public', website=True, methods=['GET', 'POST'], csrf=True)
    def lms_forgot_password(self, **post):
        """Request password reset: enter login/email, send reset link by email."""
        if request.httprequest.method == 'POST':
            login = (post.get('login') or '').strip().lower()
            if not login:
                return request.render('school_lms.lms_forgot_password', {
                    'error': 'Please enter your email or login.',
                })
            user = request.env['res.users'].sudo().search([('login', '=', login)], limit=1)
            if not user:
                user = request.env['res.users'].sudo().search([('login', 'ilike', login)], limit=1)
            if user:
                try:
                    user.action_reset_password()
                    return request.render('school_lms.lms_forgot_password', {
                        'success': 'If an account exists for this email, you will receive a password reset link.',
                    })
                except Exception:
                    pass
            return request.render('school_lms.lms_forgot_password', {
                'error': 'Could not send reset link. Contact your school admin.',
            })
        return request.render('school_lms.lms_forgot_password', {
            'error': None,
            'success': None,
        })


    @http.route('/school/lms/photo/student/<int:student_id>', type='http', auth='user', website=False)
    def lms_student_photo(self, student_id, **kw):
        """Serve student photo so portal users can see it (bypass ACLs)."""
        student = _get_current_student()
        if not student or student.id != student_id:
            return request.not_found()
        rec = request.env['school.student'].sudo().browse(student_id)
        if not rec.exists() or not rec.photo:
            return request.not_found()
        return request.make_response(
            base64.b64decode(rec.photo),
            headers=[
                ('Content-Type', 'image/png'),
                ('Content-Disposition', 'inline; filename="student_%s.png"' % student_id),
            ],
        )

    @http.route('/school/lms/photo/teacher/<int:teacher_id>', type='http', auth='user', website=False)
    def lms_teacher_photo(self, teacher_id, **kw):
        """Serve teacher photo for LMS (bypass ACLs)."""
        rec = request.env['school.teacher'].sudo().browse(teacher_id)
        if not rec.exists() or not rec.photo:
            return request.not_found()
        return request.make_response(
            base64.b64decode(rec.photo),
            headers=[
                ('Content-Type', 'image/png'),
                ('Content-Disposition', 'inline; filename="teacher_%s.png"' % teacher_id),
            ],
        )

    @http.route('/school/lms/material/download/<int:material_id>', type='http', auth='user', website=False)
    def lms_material_download(self, material_id, **kw):
        """Serve material attachment for download (portal users)."""
        student = _get_current_student()
        if not student:
            return request.not_found()
        mat = request.env['lms.subject.material'].sudo().browse(material_id)
        if not mat.exists() or not mat.attachment_id or mat.subject_id not in student.subject_ids:
            return request.not_found()
        att = mat.attachment_id
        if not att.datas:
            return request.not_found()
        return request.make_response(
            base64.b64decode(att.datas),
            headers=[
                ('Content-Type', att.mimetype or 'application/octet-stream'),
                ('Content-Disposition', 'attachment; filename="%s"' % (att.name or 'download')),
            ],
        )

    @http.route('/school/lms/material/view/<int:material_id>', type='http', auth='user', website=False)
    def lms_material_view(self, material_id, **kw):
        """Serve material attachment inline (for iframe/view in same page)."""
        student = _get_current_student()
        if not student:
            return request.not_found()
        mat = request.env['lms.subject.material'].sudo().browse(material_id)
        if not mat.exists() or not mat.attachment_id or mat.subject_id not in student.subject_ids:
            return request.not_found()
        att = mat.attachment_id
        if not att.datas:
            return request.not_found()
        return request.make_response(
            base64.b64decode(att.datas),
            headers=[
                ('Content-Type', att.mimetype or 'application/octet-stream'),
                ('Content-Disposition', 'inline; filename="%s"' % (att.name or 'view')),
            ],
        )
