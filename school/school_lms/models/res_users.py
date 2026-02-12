# -*- coding: utf-8 -*-
from odoo import models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _lms_verify_password(self, plain_password):
        """
        Verify that plain_password matches this user's stored password.
        Uses Odoo's same crypt context as login. Returns True if match.
        """
        self.ensure_one()
        if not plain_password:
            return False
        try:
            # Get stored hash from DB (password field is not readable via ORM)
            self.env.cr.execute(
                "SELECT password FROM res_users WHERE id = %s",
                (self.id,)
            )
            row = self.env.cr.fetchone()
            if not row or not row[0]:
                return False
            stored_hash = row[0]
            # Use same crypt context as Odoo login
            ctx = self._crypt_context()
            return ctx.verify(plain_password, stored_hash)
        except Exception:
            return False
