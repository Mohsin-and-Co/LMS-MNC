from odoo import models, fields

class SchoolBank(models.Model):
    _name = 'school.bank'
    _description = 'Bank Details'

    name = fields.Char(string="Bank Name", required=True)
    account_number = fields.Char(string="Bank Account Number", required=True)
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        domain="[('type', 'in', ('bank', 'cash'))]",
        help="Journal used for payments related to this bank."
    )

class SchoolTeacherBank(models.Model):
    _name = "school.teacher.bank"
    _description = "Teacher Bank Information"

    teacher_id = fields.Many2one('school.teacher', string="Teacher", required=True)
    bank_id = fields.Many2one('school.bank', string="Bank", required=True)
    account_number = fields.Char(string="Account Number", required=True)
