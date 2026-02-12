from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    salary_expense_account_id = fields.Many2one(
        'account.account',
        string="Salary Expense Account",
        config_parameter="school.salary_expense_account_id",
        domain=[('account_type','=','expense')],
    )
    salary_payable_account_id = fields.Many2one(
        'account.account',
        string="Salary Payable Account",
        config_parameter="school.salary_payable_account_id",
        domain=[('account_type','=','liability')],
    )
