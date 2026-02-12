from odoo import http
from odoo.http import request
 
class SchoolWebsite(http.Controller):
    @http.route(['/school'], type='http', auth='public', website=True)
    def school_homepage(self, **kw):
        return request.render('school_manegment_system.school_homepage') 