from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class LibraryBookIssue(models.Model):
    _name = 'library.book.issue'
    _description = 'Library Book Issue'
    _rec_name = 'name'
    _order = 'issue_date desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    student_id = fields.Many2one('school.student', string='Student', required=True, index=True)
    book_id = fields.Many2one('library.book', string='Book', required=True, index=True)
    category_id = fields.Many2one('library.book.category', string='Category', related='book_id.category_id', store=True, readonly=True)
    issue_date = fields.Date(string='Issue Date', required=True, default=fields.Date.context_today)
    due_date = fields.Date(string='Due Date', required=True)
    return_date = fields.Date(string='Return Date', readonly=True)
    state = fields.Selection([
        ('issued', 'Issued'),
        ('returned', 'Returned'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged')
    ], string='Status', default='issued', required=True)
    
    # Fine calculation
    fine_amount = fields.Float(string='Fine Amount', compute='_compute_fine', store=True)
    fine_per_day = fields.Float(string='Fine Per Day', default=10.0, help='Fine amount per day after due date')
    days_overdue = fields.Integer(string='Days Overdue', compute='_compute_fine', store=True)
    
    # Additional info
    issue_by = fields.Many2one('res.users', string='Issued By', default=lambda self: self.env.user, readonly=True)
    return_by = fields.Many2one('res.users', string='Returned By', readonly=True)
    remark = fields.Text(string='Remarks')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('library.book.issue') or _('New')
        return super().create(vals_list)
    
    @api.depends('due_date', 'return_date', 'state', 'fine_per_day')
    def _compute_fine(self):
        today = fields.Date.today()
        for issue in self:
            if issue.state == 'returned' and issue.return_date:
                # Calculate based on return date
                if issue.return_date > issue.due_date:
                    days = (issue.return_date - issue.due_date).days
                    issue.days_overdue = days
                    issue.fine_amount = days * issue.fine_per_day
                else:
                    issue.days_overdue = 0
                    issue.fine_amount = 0.0
            elif issue.state == 'issued':
                # Calculate based on today
                if today > issue.due_date:
                    days = (today - issue.due_date).days
                    issue.days_overdue = days
                    issue.fine_amount = days * issue.fine_per_day
                else:
                    issue.days_overdue = 0
                    issue.fine_amount = 0.0
            else:
                issue.days_overdue = 0
                issue.fine_amount = 0.0
    
    @api.onchange('issue_date', 'book_id')
    def _onchange_issue_date(self):
        """Set default due date (usually 7 or 14 days from issue date)"""
        if self.issue_date and not self.due_date:
            # Default: 14 days from issue date
            self.due_date = self.issue_date + timedelta(days=14)
    
    @api.constrains('issue_date', 'due_date')
    def _check_dates(self):
        for issue in self:
            if issue.due_date and issue.issue_date:
                if issue.due_date < issue.issue_date:
                    raise ValidationError(_("Due date cannot be before issue date."))
    
    @api.constrains('book_id', 'state')
    def _check_book_availability(self):
        for issue in self:
            if issue.state == 'issued':
                # Check if book has available copies
                if issue.book_id.available_copies < 1:
                    raise ValidationError(_("No available copies of '%s'. Available: %d") % 
                                        (issue.book_id.title, issue.book_id.available_copies))
    
    def action_return(self):
        """Return the book"""
        for record in self:
            if record.state != 'issued':
                raise ValidationError(_("Only issued books can be returned."))
            
            record.write({
                'state': 'returned',
                'return_date': fields.Date.today(),
                'return_by': self.env.user.id
            })
            _logger.info(f"Book '{record.book_id.title}' returned by student {record.student_id.name}")
    
    def action_mark_lost(self):
        """Mark book as lost"""
        for record in self:
            if record.state != 'issued':
                raise ValidationError(_("Only issued books can be marked as lost."))
            
            record.write({
                'state': 'lost',
                'return_date': fields.Date.today(),
                'return_by': self.env.user.id
            })
            # Reduce total copies by 1
            record.book_id.write({'total_copies': record.book_id.total_copies - 1})
            _logger.info(f"Book '{record.book_id.title}' marked as lost for student {record.student_id.name}")
    
    def action_mark_damaged(self):
        """Mark book as damaged"""
        for record in self:
            if record.state != 'issued':
                raise ValidationError(_("Only issued books can be marked as damaged."))
            
            record.write({
                'state': 'damaged',
                'return_date': fields.Date.today(),
                'return_by': self.env.user.id
            })
            _logger.info(f"Book '{record.book_id.title}' marked as damaged for student {record.student_id.name}")
