from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class Fee(models.Model):
    _name = 'school.fee'
    _description = 'School Fee'
    _order = 'due_date desc, id desc'

    name = fields.Char(
        string='Fee Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    roll_number = fields.Char(string="Roll Number", required=True)
    student_id = fields.Many2one('school.student', string="Student", store=True, required=True)
    class_id = fields.Many2one('school.class', string="Class", store=True)

    fee_type = fields.Selection([
        ('tuition', 'Tuition Fee'),
        ('transport', 'Transport Fee'),
        ('library', 'Library Fee'),
        ('other', 'Other')
    ], string='Fee Type', required=True)
    amount = fields.Float(string='Amount', required=True)
    due_date = fields.Date(string='Due Date', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    ], string='Status', default='draft')
    payment_date = fields.Date(string='Payment Date')
    payment_reference = fields.Char(string='Payment Reference')
    bank_id = fields.Many2one('school.bank', string="Bank")

    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True)
    invoice_state = fields.Selection(related='invoice_id.state', string='Invoice State', store=True, readonly=True)

    # -------------------------------
    # Onchange
    # -------------------------------
    @api.onchange('roll_number')
    def _onchange_roll_number(self):
        """Auto-fill student and class when roll number entered"""
        if not self.roll_number:
            self.student_id = False
            self.class_id = False
            return

        student = self.env['school.student'].search(
            [('roll_number', '=', self.roll_number)], limit=1
        )
        if student:
            self.student_id = student.id
            self.class_id = student.class_id.id if student.class_id else False
        else:
            self.student_id = False
            self.class_id = False

    # -------------------------------
    # Create override
    # -------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        # Assign sequence for each record
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('school.fee') or _('New')

        records = super(Fee, self).create(vals_list)

        # Create invoices per record
        for record in records:
            if record.amount > 0:
                if not record.student_id.partner_id:
                    raise UserError(
                        _("Student '%s' does not have a linked Customer (Partner).")
                        % record.student_id.name
                    )

                invoice_vals = {
                    'move_type': 'out_invoice',
                    'partner_id': record.student_id.partner_id.id,
                    'invoice_date': fields.Date.today(),
                    'invoice_origin': record.name,
                    'ref': record.name,
                    'invoice_line_ids': [
                        (0, 0, {
                            'name': f"{record.fee_type.title()} Fee for {record.student_id.name}",
                            'quantity': 1,
                            'price_unit': record.amount,
                        }),
                    ],
                }

                invoice = self.env['account.move'].create(invoice_vals)
                record.invoice_id = invoice.id
                record.state = 'paid'

        return records
    # -------------------------------
    # Workflow Actions
    # -------------------------------
    def action_confirm(self):
        for rec in self:
            rec.state = 'pending'

    def action_pay(self):
        for rec in self:
            rec.state = 'paid'
            rec.payment_date = fields.Date.today()

    def action_overdue(self):
        for rec in self:
            rec.state = 'overdue'

    # -------------------------------
    # Report Action
    # -------------------------------
    def action_print_fee(self):
        """ Trigger PDF Fee Report """
        try:
            return self.env.ref(
                'school_manegment_system.action_report_school_fee'
            ).report_action(self)
        except ValueError:
            raise UserError(_("The Fee Report template is missing. Please check if 'action_report_school_fee' is defined in XML."))
