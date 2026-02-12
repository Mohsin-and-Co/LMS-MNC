from odoo import models, fields, api

class SchoolSalarySettings(models.TransientModel):
    _name = "school.salary.settings"
    _description = "School Salary Settings"

    salary_expense_account_id = fields.Many2one(
        'account.account', string="Salary Expense Account",
        required=True,
        help="Select the account used for Salary Expenses"
    )
    salary_payable_account_id = fields.Many2one(
        'account.account', string="Salary Payable Account",
        required=True,
        help="Select the account used for Salary Payables"
    )

    @api.model
    def get_values(self):
        """ Load existing values from ir.config_parameter """
        res = super(SchoolSalarySettings, self).get_values() if hasattr(super(), 'get_values') else {}
        ICPSudo = self.env['ir.config_parameter'].sudo()
        res.update({
            'salary_expense_account_id': int(ICPSudo.get_param('school.salary_expense_account_id', default=0)),
            'salary_payable_account_id': int(ICPSudo.get_param('school.salary_payable_account_id', default=0)),
        })
        return res

    def set_values(self):
        """ Save values in ir.config_parameter """
        ICPSudo = self.env['ir.config_parameter'].sudo()
        ICPSudo.set_param('school.salary_expense_account_id', self.salary_expense_account_id.id)
        ICPSudo.set_param('school.salary_payable_account_id', self.salary_payable_account_id.id)
