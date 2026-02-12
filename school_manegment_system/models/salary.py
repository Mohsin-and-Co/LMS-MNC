from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SchoolSalary(models.Model):
    _name = "school.salary"
    _description = "School Salary"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Salary Reference",
        required=True,
        readonly=True,
        default="New"
    )
    teacher_id = fields.Many2one(
        "school.teacher",
        string="Teacher",
        required=True
    )
    month = fields.Selection([
        ('january', 'January'),
        ('february', 'February'),
        ('march', 'March'),
        ('april', 'April'),
        ('may', 'May'),
        ('june', 'June'),
        ('july', 'July'),
        ('august', 'August'),
        ('september', 'September'),
        ('october', 'October'),
        ('november', 'November'),
        ('december', 'December'),
    ], string="Month", required=True)
    year = fields.Integer(string="Year", required=True)

    basic_salary = fields.Float(string="Basic Salary")
    allowance = fields.Float(string="Allowance")
    deduction = fields.Float(string="Deduction")
    net_salary = fields.Float(
        string="Net Salary",
        compute="_compute_net_salary",
        store=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ], string="Status", default="draft", tracking=True)

    payment_date = fields.Date(string="Payment Date", readonly=True)
    invoice_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)

    # -----------------------------
    # Compute Net Salary
    # -----------------------------
    @api.depends("basic_salary", "allowance", "deduction")
    def _compute_net_salary(self):
        for rec in self:
            rec.net_salary = (rec.basic_salary + rec.allowance) - rec.deduction

    # -----------------------------
    # Sequence Generation
    # -----------------------------
    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("school.salary") or "New"
        return super().create(vals)

    # -----------------------------
    # Workflow Actions
    # -----------------------------
    def action_confirm(self):
        """Confirm salary and create accounting entry"""
        for rec in self:
            if rec.state != 'draft':
                continue

            # Fetch accounts from config parameters
            expense_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
                'school.salary_expense_account_id', 0
            ))
            payable_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
                'school.salary_payable_account_id', 0
            ))

            expense_account = self.env['account.account'].browse(expense_account_id)
            payable_account = self.env['account.account'].browse(payable_account_id)

            if not expense_account.exists() or not payable_account.exists():
                raise UserError(_("Please set the Salary Expense and Payable accounts in Settings."))

            # Select a journal
            journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
            if not journal:
                raise UserError(_("Please create at least one General Journal for salary entries."))

            # Create Journal Entry
            move_vals = {
                'date': fields.Date.today(),
                'ref': rec.name,
                'journal_id': journal.id,
                'line_ids': [
                    (0, 0, {
                        'name': rec.name,
                        'account_id': expense_account.id,
                        'debit': rec.net_salary,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'name': rec.name,
                        'account_id': payable_account.id,
                        'debit': 0.0,
                        'credit': rec.net_salary,
                    }),
                ]
            }
            move = self.env['account.move'].create(move_vals)

            # ✅ Odoo 17 uses action_post()
            move.action_post()

            rec.invoice_id = move.id
            rec.state = 'pending'

    def action_pay(self):
        for rec in self:
            if rec.state == 'pending':
                rec.state = 'paid'
                rec.payment_date = fields.Date.today()

    def action_overdue(self):
        for rec in self:
            if rec.state == 'pending':
                rec.state = 'overdue'

    # -----------------------------
    # Print Salary Report
    # -----------------------------
    def action_print_salary(self):
        try:
            return self.env.ref(
                'school_manegment_system.action_report_school_salary'
            ).report_action(self)
        except ValueError:
            raise UserError(_("Salary Report template missing. Check XML definition."))
