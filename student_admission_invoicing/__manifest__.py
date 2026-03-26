{
    "name": "Student Admission & Invoicing",
    "version": "19.0.1.0.0",
    "summary": "Admission form with automatic fee invoice posting workflow",
    "category": "Education",
    "author": "Custom",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "product",
        "account",
        "sale",
        "education_school_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/student_admission_sequence.xml",
        "views/student_admission_views.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
