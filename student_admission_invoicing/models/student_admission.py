from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class StudentAdmission(models.Model):
    _name = "student.admission"
    _description = "Student Admission"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Admission Reference",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
    )
    student_name = fields.Char(string="Student Name", required=True, tracking=True)
    date_of_birth = fields.Date(string="Date of Birth", required=True)
    gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")],
        string="Gender",
        required=True,
    )
    phone = fields.Char(string="Phone")
    email = fields.Char(string="Email")
    address = fields.Text(string="Address")

    parent_name = fields.Char(string="Parent/Guardian Name", required=True)
    parent_phone = fields.Char(string="Parent/Guardian Phone")
    parent_email = fields.Char(string="Parent/Guardian Email")
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        help="Customer used for invoicing. Auto-created on save when empty.",
        tracking=True,
    )

    student_id = fields.Many2one(
        "school.student",
        string="Linked Student",
        readonly=True,
        copy=False,
    )
    service_product_id = fields.Many2one(
        "product.product",
        string="Fee Service Product",
        required=True,
        domain=[("type", "=", "service")],
        help="Select fee product from Inventory/Products. Only service products are allowed.",
        tracking=True,
    )
    fee_amount = fields.Monetary(
        string="Fee Amount",
        currency_field="currency_id",
        compute="_compute_fee_amount",
        store=True,
    )
    discount_type = fields.Selection(
        [("none", "No Discount"), ("percent", "Percentage"), ("fixed", "Fixed Amount")],
        string="Discount Type",
        default="none",
        required=True,
        tracking=True,
    )
    discount_value = fields.Float(string="Discount Value", tracking=True)
    discount_amount = fields.Monetary(
        string="Discount Amount",
        currency_field="currency_id",
        compute="_compute_discount_amount",
        store=True,
    )
    total_amount = fields.Monetary(
        string="Net Fee",
        currency_field="currency_id",
        compute="_compute_total_amount",
        store=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        readonly=True,
        copy=False,
    )
    invoice_state = fields.Selection(
        related="invoice_id.state",
        string="Invoice State",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("admitted", "Admitted"),
            ("approved", "Invoice Approved"),
        ],
        default="draft",
        tracking=True,
    )
    admission_date = fields.Date(string="Admission Date", readonly=True)

    @api.depends("service_product_id", "service_product_id.list_price")
    def _compute_fee_amount(self):
        for rec in self:
            rec.fee_amount = rec.service_product_id.list_price if rec.service_product_id else 0.0

    @api.depends("fee_amount", "discount_type", "discount_value")
    def _compute_discount_amount(self):
        for rec in self:
            if rec.discount_type == "percent":
                rec.discount_amount = rec.fee_amount * (rec.discount_value / 100.0)
            elif rec.discount_type == "fixed":
                rec.discount_amount = rec.discount_value
            else:
                rec.discount_amount = 0.0

    @api.depends("fee_amount", "discount_amount")
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = rec.fee_amount - rec.discount_amount

    @api.constrains("discount_type", "discount_value", "fee_amount")
    def _check_discount(self):
        for rec in self:
            if rec.discount_type == "percent" and (rec.discount_value < 0 or rec.discount_value > 100):
                raise ValidationError(_("Percentage discount must be between 0 and 100."))
            if rec.discount_type == "fixed" and rec.discount_value < 0:
                raise ValidationError(_("Fixed discount cannot be negative."))
            if rec.total_amount < 0:
                raise ValidationError(_("Discount cannot be greater than fee amount."))

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = seq.next_by_code("student.admission") or _("New")
        records = super().create(vals_list)
        for rec in records:
            rec._ensure_partner()
            rec._ensure_student()
            rec._create_invoice_if_needed()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if not rec.partner_id:
                rec._ensure_partner()
            if not rec.student_id:
                rec._ensure_student()
            if rec.invoice_id and rec.invoice_id.state == "draft":
                rec._sync_draft_invoice()
            elif not rec.invoice_id:
                rec._create_invoice_if_needed()
        return res

    def _ensure_partner(self):
        self.ensure_one()
        if not self.partner_id:
            partner = self.env["res.partner"].create(
                {
                    "name": self.parent_name or self.student_name,
                    "phone": self.parent_phone or self.phone,
                    "email": self.parent_email or self.email,
                    "street": self.address or "",
                    "is_company": False,
                }
            )
            self.partner_id = partner.id

    def _ensure_student(self):
        self.ensure_one()
        if self.student_id:
            return
        student = self.env["school.student"].create(
            {
                "name": self.student_name,
                "date_of_birth": self.date_of_birth,
                "gender": self.gender,
                "phone": self.phone,
                "email": self.email,
                "address": self.address,
                "parent_name": self.parent_name,
                "parent_phone": self.parent_phone,
                "parent_email": self.parent_email,
                "partner_id": self.partner_id.id,
            }
        )
        self.student_id = student.id
        self.state = "admitted"
        self.admission_date = fields.Date.today()

    def _prepare_invoice_line_vals(self):
        self.ensure_one()
        line_vals = {
            "product_id": self.service_product_id.id,
            "name": self.service_product_id.display_name,
            "quantity": 1.0,
            "price_unit": self.fee_amount,
        }
        if self.discount_type == "percent":
            line_vals["discount"] = self.discount_value
        return line_vals

    def _create_invoice_if_needed(self):
        self.ensure_one()
        if self.invoice_id:
            return
        if not self.partner_id:
            raise UserError(_("A customer is required to create invoice."))
        if not self.service_product_id:
            raise UserError(_("Please select a service product to create invoice."))

        invoice_vals = {
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": fields.Date.today(),
            "invoice_origin": self.name,
            "invoice_payment_term_id": False,
            "invoice_line_ids": [(0, 0, self._prepare_invoice_line_vals())],
        }
        invoice = self.env["account.move"].create(invoice_vals)

        if self.discount_type == "fixed" and self.discount_amount:
            discount_line_vals = {
                "name": _("Discount"),
                "quantity": 1.0,
                "price_unit": -abs(self.discount_amount),
            }
            income_account = (
                self.service_product_id.property_account_income_id
                or self.service_product_id.categ_id.property_account_income_categ_id
            )
            if income_account:
                discount_line_vals["account_id"] = income_account.id
            invoice.write({"invoice_line_ids": [(0, 0, discount_line_vals)]})

        self.invoice_id = invoice.id

    def _sync_draft_invoice(self):
        self.ensure_one()
        if not self.invoice_id or self.invoice_id.state != "draft":
            return
        if len(self.invoice_id.invoice_line_ids) >= 1:
            main_line = self.invoice_id.invoice_line_ids[0]
            main_line.write(self._prepare_invoice_line_vals())

        other_lines = self.invoice_id.invoice_line_ids[1:]
        if other_lines:
            other_lines.unlink()

        if self.discount_type == "fixed" and self.discount_amount:
            discount_line_vals = {
                "name": _("Discount"),
                "quantity": 1.0,
                "price_unit": -abs(self.discount_amount),
            }
            income_account = (
                self.service_product_id.property_account_income_id
                or self.service_product_id.categ_id.property_account_income_categ_id
            )
            if income_account:
                discount_line_vals["account_id"] = income_account.id
            self.invoice_id.write({"invoice_line_ids": [(0, 0, discount_line_vals)]})

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice linked to this admission."))
        return {
            "name": _("Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
            "target": "current",
        }

    def action_approve_invoice(self):
        for rec in self:
            if not rec.invoice_id:
                raise UserError(_("No invoice found for this admission."))
            if rec.invoice_id.state == "cancel":
                raise UserError(_("Cannot approve a cancelled invoice."))
            if rec.invoice_id.state == "draft":
                rec.invoice_id.action_post()
            rec.state = "approved"
