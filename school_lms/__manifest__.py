# -*- coding: utf-8 -*-
{
    'name': 'Student LMS',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Student Learning Management System – portal with subjects, teachers, materials, fee, timetable, results',
    'description': """
Student LMS for Odoo 19
=======================
- Navbar: student name, photo; click opens menu: Change Password, Logout
- Sidebar: Home, Fee, Calendar, Time Table, Result, Support, Logout
- Home: all subjects with teacher name and photo; click subject → teacher detail on top, then documents/videos/updates
- Change password: current password, new password, save
- Each student sees only their own data (by partner_id / roll_number)
    """,
    'author': 'Abdul Wahid ',
    'website': '',
    'depends': ['education_school_management', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'views/lms_subject_material_views.xml',
        'views/lms_student_document_views.xml',
        'views/lms_support_views.xml',
        'views/lms_support_issue_views.xml',
        'views/lms_subject_notification_views.xml',
        'views/lms_calendar_event_views.xml',
        'views/lms_layout_inherit.xml',
        'views/lms_templates.xml',
        'views/portal.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
