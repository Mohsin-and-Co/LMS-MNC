from odoo import http
from odoo.http import request
from odoo import fields
import logging
import traceback
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

class SchoolWebsite(http.Controller):

    def _handle_access(self, model_name):
        try:
            request.env[model_name].sudo().check_access_rights('create')
            return True
        except AccessError as e:
            _logger.error("Access rights error for model %s: %s", model_name, str(e))
            return False

    @http.route(['/school/enroll'], type='http', auth='public', website=True, methods=['GET'])
    def enrollment_form(self, **kw):
        try:
            if not self._handle_access('school.student'):
                return request.render('website.403')

            classes = request.env['school.class'].sudo().search([])
            _logger.info("Found %d classes for enrollment form", len(classes))
            message = request.session.pop('enrollment_success', None)
            return request.render('education_school_management.student_enrollment_form', {
                'classes': classes,
                'message': message
            })
        except Exception as e:
            _logger.error("Error in enrollment form: %s\n%s", str(e), traceback.format_exc())
            return request.render('website.http_error', {'status_code': 500})

    @http.route(['/school/enroll'], type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def submit_enrollment(self, **post):
        try:
            _logger.info("Starting student enrollment with data: %s", post)
            
            if not self._handle_access('school.student'):
                _logger.error("Access denied for student creation")
                return request.render('website.403')

            if not post:
                _logger.warning("No data received in enrollment form")
                return request.redirect('/school/enroll')

            # Validate required fields
            required_fields = ['name', 'date_of_birth', 'gender', 'parent_name', 'class_id']
            missing_fields = [field for field in required_fields if not post.get(field)]
            if missing_fields:
                _logger.warning("Missing required fields: %s", missing_fields)
                return request.render('website.http_error', {
                    'status_code': 'Error',
                    'status_message': f'The following fields are required: {", ".join(missing_fields)}'
                })

            try:
                # Prepare student values
                vals = {
                    'name': post.get('name').strip(),
                    'date_of_birth': post.get('date_of_birth'),
                    'gender': post.get('gender'),
                    'address': post.get('address', '').strip(),
                    'phone': post.get('phone', '').strip(),
                    'email': post.get('email', '').strip(),
                    'parent_name': post.get('parent_name').strip(),
                    'parent_phone': post.get('parent_phone', '').strip(),
                    'parent_email': post.get('parent_email', '').strip(),
                    'state': 'draft'
                }

                if post.get('class_id'):
                    try:
                        vals['class_id'] = int(post.get('class_id'))
                    except (ValueError, TypeError) as e:
                        _logger.error("Invalid class_id value: %s", post.get('class_id'))
                        raise ValidationError("Invalid class selected")

                _logger.info("Attempting to create student with values: %s", vals)
                
                # Create student record using create method
                Student = request.env['school.student'].sudo()
                new_student = Student.create(vals)
                _logger.info("Student created successfully with ID: %s, Roll Number: %s", 
                            new_student.id, new_student.roll_number)

                # Verify creation
                if not new_student.exists():
                    _logger.error("Student creation verification failed")
                    raise ValidationError("Student creation failed - record not found after creation")

                success_message = f"Student {new_student.name} enrolled successfully! Roll Number: {new_student.roll_number}"
                request.session['enrollment_success'] = success_message
                _logger.info("Enrollment success: %s", success_message)
                
                return request.render('education_school_management.enrollment_success', {
                    'message': success_message
                })

            except (ValueError, ValidationError) as e:
                _logger.error("Validation error in enrollment: %s\n%s", str(e), traceback.format_exc())
                return request.render('website.http_error', {
                    'status_code': 'Error',
                    'status_message': str(e)
                })

        except Exception as e:
            _logger.error("Error in enrollment submission: %s\n%s", str(e), traceback.format_exc())
            return request.render('website.http_error', {
                'status_code': 'Error',
                'status_message': 'There was an error processing your enrollment. Please try again.'
            })

    @http.route(['/school/enrollment/success'], type='http', auth='public', website=True)
    def enrollment_success(self, **kw):
        message = request.session.get('enrollment_success', 'Enrollment completed successfully!')
        return request.render('education_school_management.enrollment_success', {
            'message': message
        })

    # -------- /school/scan: Public QR scan page --------
    @http.route(['/school/scan'], type='http', auth='public', website=True, methods=['GET'])
    def school_scan_page(self, **kw):
        """Public page to scan QR for attendance - waha se scan hona chahiye."""
        return request.render('education_school_management.school_scan_page')

    @http.route(['/school/scan/submit'], type='http', auth='public', methods=['POST'], csrf=False)
    def school_scan_submit(self, **post):
        """Submit scanned QR code and create attendance. Called from /school/scan page (JSON body or form)."""
        import json
        qr_code = date_val = None
        if request.httprequest.content_type and 'application/json' in request.httprequest.content_type:
            try:
                body = request.httprequest.get_data(as_text=True)
                data = json.loads(body) if body else {}
                qr_code = data.get('qr_code') or data.get('params', {}).get('qr_code')
                date_val = data.get('date') or data.get('params', {}).get('date')
            except Exception:
                pass
        if qr_code is None:
            qr_code = post.get('qr_code')
        if date_val is None:
            date_val = post.get('date')
        if not qr_code or not str(qr_code).strip():
            return request.make_response(json.dumps({'success': False, 'message': 'QR code is required.'}),
                headers=[('Content-Type', 'application/json')])
        qr_code = str(qr_code).strip().upper()
        from datetime import datetime
        if not date_val:
            date_val = fields.Date.today()
        else:
            try:
                if isinstance(date_val, str):
                    date_val = datetime.strptime(date_val[:10], '%Y-%m-%d').date()
            except Exception:
                date_val = fields.Date.today()
        
        # Handle STAFF QR codes
        if qr_code.startswith('STAFF_'):
            employee_id = qr_code.replace('STAFF_', '').strip()
            Teacher = request.env['school.teacher'].sudo()
            teacher = Teacher.search([('employee_id', '=', employee_id)], limit=1)
            if not teacher:
                return request.make_response(json.dumps({'success': False, 'message': f'Staff not found for employee ID: {employee_id}'}),
                    headers=[('Content-Type', 'application/json')])
            StaffAttendance = request.env['school.staff.attendance'].sudo()
            existing = StaffAttendance.search([
                ('staff_id', '=', teacher.id),
                ('date', '=', date_val)
            ], limit=1)
            if existing:
                # Update check-in/check-out if exists
                if not existing.check_in:
                    existing.write({'check_in': fields.Datetime.now(), 'state': 'confirmed'})
                    msg = f'Check-in recorded for {teacher.name}'
                elif not existing.check_out:
                    existing.write({'check_out': fields.Datetime.now(), 'state': 'confirmed'})
                    msg = f'Check-out recorded for {teacher.name}'
                else:
                    return request.make_response(json.dumps({'success': False, 'message': f'Attendance for {teacher.name} on {date_val} already completed.'}),
                        headers=[('Content-Type', 'application/json')])
                attendance_record = existing
            else:
                # Create new staff attendance
                attendance_record = StaffAttendance.create({
                    'staff_id': teacher.id,
                    'date': date_val,
                    'check_in': fields.Datetime.now(),
                    'status': 'present',
                    'state': 'confirmed',
                    'remark': 'Scanned via /school/scan'
                })
                msg = f'Check-in recorded for {teacher.name}'
            
            # Handle attendance recordset
            if isinstance(attendance_record, list) and len(attendance_record) > 0:
                att_name = attendance_record[0].name if hasattr(attendance_record[0], 'name') else str(attendance_record[0].id)
            elif hasattr(attendance_record, 'name'):
                att_name = attendance_record.name
            else:
                att_name = 'N/A'
            return request.make_response(json.dumps({'success': True, 'message': msg, 'ref': att_name}),
                headers=[('Content-Type', 'application/json')])
        
        # Handle STUDENT QR codes
        if not qr_code.startswith('STUDENT_'):
            return request.make_response(json.dumps({'success': False, 'message': 'Invalid QR code format. Must start with STUDENT_ or STAFF_'}),
                headers=[('Content-Type', 'application/json')])
        admission_number = qr_code.replace('STUDENT_', '').strip()
        Student = request.env['school.student'].sudo()
        student = Student.search([('admission_number', '=', admission_number)], limit=1)
        if not student:
            return request.make_response(json.dumps({'success': False, 'message': f'Student not found for admission number: {admission_number}'}),
                headers=[('Content-Type', 'application/json')])
        if student.state != 'admitted':
            return request.make_response(json.dumps({'success': False, 'message': f'Student {student.name} is not admitted.'}),
                headers=[('Content-Type', 'application/json')])
        Attendance = request.env['school.attendance'].sudo()
        existing = Attendance.search([
            ('student_id', '=', student.id),
            ('date', '=', date_val)
        ], limit=1)
        if existing:
            return request.make_response(json.dumps({'success': False, 'message': f'Attendance for {student.name} on {date_val} already exists.'}),
                headers=[('Content-Type', 'application/json')])
        attendance = Attendance.create({
            'student_id': student.id,
            'date': date_val,
            'status': 'present',
            'state': 'confirmed',
            'remark': 'Scanned via /school/scan'
        })
        # Handle attendance recordset (create() may return list or recordset)
        if isinstance(attendance, list) and len(attendance) > 0:
            attendance_record = attendance[0]
            attendance_name = attendance_record.name if hasattr(attendance_record, 'name') else str(attendance_record.id)
        elif hasattr(attendance, 'name'):
            attendance_name = attendance.name
        elif hasattr(attendance, '__iter__') and len(attendance) > 0:
            attendance_name = attendance[0].name if hasattr(attendance[0], 'name') else str(attendance[0].id)
        else:
            attendance_name = 'N/A'
        return request.make_response(json.dumps({'success': True, 'message': f'Attendance recorded for {student.name}', 'ref': attendance_name}),
            headers=[('Content-Type', 'application/json')])

    # -------- Result portal: show relative result per student only --------
    @http.route(['/school/my/results', '/my/student/results'], type='http', auth='user', website=True)
    def portal_my_results(self, **kw):
        """Portal page: show results only for students related to current user (by parent_email or student.partner_id)."""
        import logging
        _logger = logging.getLogger(__name__)
        partner = request.env.user.partner_id
        email = (partner.email or '').strip().lower()
        phone = (partner.phone or '').strip()
        
        # Search students by multiple criteria (OR conditions)
        domain = []
        conditions = []
        
        if email:
            conditions.append(('parent_email', '=ilike', email))
        if phone:
            conditions.append(('parent_phone', '=', phone))
        conditions.append(('partner_id', '=', partner.id))
        # Also check if student's roll_number matches user login (for student portal users)
        if request.env.user.login:
            conditions.append(('roll_number', '=', request.env.user.login))
        
        # Build OR domain: ['|', '|', condition1, condition2, condition3] for 3+ conditions
        if len(conditions) > 1:
            domain = ['|'] * (len(conditions) - 1) + conditions
        elif len(conditions) == 1:
            domain = conditions
        else:
            domain = []
        
        students = request.env['school.student'].sudo().search(domain) if domain else request.env['school.student'].sudo().browse([])
        _logger.info(f"Portal user {request.env.user.name} (email: {email}, partner_id: {partner.id}) - Found {len(students)} students")
        
        if not students:
            # Try to find by exact email match
            if email:
                students = request.env['school.student'].sudo().search([
                    ('parent_email', '=', email)
                ])
                _logger.info(f"Trying exact email match - Found {len(students)} students")
        
        results = request.env['school.result'].sudo().search([
            ('student_id', 'in', students.ids)
        ], order='date desc, id desc') if students else request.env['school.result'].sudo().browse([])
        
        _logger.info(f"Found {len(results)} results for {len(students)} students")
        
        return request.render('education_school_management.portal_my_results', {
            'results': results,
            'students': students,
            'user_email': email,
            'user_partner_id': partner.id,
        })