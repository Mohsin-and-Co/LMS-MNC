{
    'name': 'School Management System',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Comprehensive solution to manage school operations and academics',
    'description': """
School Management System
========================
A complete school management application for Odoo.

Features:
---------
* Student Management  
* Class & Subject Management  
* Attendance Tracking  
* Fee Management & Accounting Integration  
* SMS Notifications  
* Exam & Result Management  
* Teacher & Timetable Management  
* Access Control for Sale Order Lines  
* Third-Party Integration  
""",
    'author': 'EBITDA SOLUTIONS LLP',
    'website': 'https://ebitdasolutions.com',
    'license': 'LGPL-3',
    'maintainers': ['EBITDA SOLUTIONS LLP'],
    'price': 38.59,
    'currency': 'USD',
    'depends': [
        'base',
        'mail',
        'sms',
        'website',
        'sale',
        'hr',
        'account',
    ],
    'data': [
        # Security & Access
        'security/sale_security.xml',
        'security/school_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/sequences.xml',
        'data/cron_data.xml',

        # Views - Actions first, then menus
        'views/class_views.xml',  # Load first to define root menu
        'views/student_views.xml',
        'views/attendance_views.xml',
        'views/fee_views.xml',
        'views/school_subject_views.xml',
        'views/bank.xml',
        'views/exam.xml',
        'views/teacher.xml',
        'views/timetable.xml',
        'views/school_result_form.xml',
        'views/staff_attendance_views.xml',
        'views/staff_head_views.xml',
        'views/result_wizard_views.xml',
        'views/attendance_wizard_views.xml',
        'views/attendance_settings_views.xml',
        'views/qr_scanner_wizard_views.xml',
        'views/school_qr_scan_result.xml',
        'views/library_views.xml',
        'views/portal.xml',
        'views/website_templates.xml',
        'views/res_config_settings_views.xml',
        # 'views/salary.xml',
        # 'views/salary_setting.xml',

        # Reports
        'reports/student_report_template.xml',
        'reports/school_result_report.xml',
        'reports/school_fee_report.xml',
        'reports/timetable.xml',
        'reports/salary_report.xml',
        'reports/library_report.xml',
        'reports/card_reports.xml',
    ],
    'images': [
        'static/description/banner.png'
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
