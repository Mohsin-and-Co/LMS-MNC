from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Library Book'
    _rec_name = 'title'
    _order = 'title'

    title = fields.Char(string='Title', required=True, index=True)
    isbn = fields.Char(string='ISBN', help='International Standard Book Number')
    author = fields.Char(string='Author', required=True, index=True)
    publisher = fields.Char(string='Publisher')
    edition = fields.Char(string='Edition')
    category_id = fields.Many2one('library.book.category', string='Category', required=True)
    total_copies = fields.Integer(string='Total Copies', required=True, default=1)
    available_copies = fields.Integer(string='Available Copies', compute='_compute_available_copies', store=True)
    price = fields.Float(string='Price')
    purchase_date = fields.Date(string='Purchase Date')
    location = fields.Char(string='Location/Shelf', help='Physical location in library')
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    
    # Issue statistics
    issue_count = fields.Integer(string='Total Issues', compute='_compute_issue_stats')
    current_issues = fields.Integer(string='Currently Issued', compute='_compute_issue_stats')
    
    @api.depends('total_copies', 'current_issues')
    def _compute_available_copies(self):
        for book in self:
            book.available_copies = book.total_copies - book.current_issues
    
    def _compute_issue_stats(self):
        for book in self:
            issues = self.env['library.book.issue'].search([
                ('book_id', '=', book.id)
            ])
            book.issue_count = len(issues)
            current = issues.filtered(lambda i: i.state == 'issued')
            book.current_issues = len(current)
    
    @api.constrains('total_copies')
    def _check_total_copies(self):
        for book in self:
            if book.total_copies < 1:
                raise ValidationError(_("Total copies must be at least 1."))
            if book.total_copies < book.current_issues:
                raise ValidationError(_("Total copies cannot be less than currently issued copies."))
    
    def action_view_issues(self):
        """View all issues for this book"""
        self.ensure_one()
        return {
            'name': _('Book Issues'),
            'type': 'ir.actions.act_window',
            'res_model': 'library.book.issue',
            'view_mode': 'list,form',
            'domain': [('book_id', '=', self.id)],
            'context': {'default_book_id': self.id},
        }

class LibraryBookCategory(models.Model):
    _name = 'library.book.category'
    _description = 'Book Category'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Category Name', required=True, index=True)
    code = fields.Char(string='Code', help='Category code for quick reference')
    description = fields.Text(string='Description')
    book_count = fields.Integer(string='Books', compute='_compute_book_count')
    active = fields.Boolean(string='Active', default=True)
    
    def _compute_book_count(self):
        for category in self:
            category.book_count = self.env['library.book'].search_count([
                ('category_id', '=', category.id),
                ('active', '=', True)
            ])
