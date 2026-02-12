from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ResultWhatsAppWizard(models.TransientModel):
    _name = 'school.result.whatsapp.wizard'
    _description = 'Result WhatsApp Wizard'
    _rec_name = 'class_id'

    class_id = fields.Many2one('school.class', string='Class', required=True)
    exam_id = fields.Many2one('school.exam', string='Exam', required=True)
    
    def action_send_whatsapp(self):
        """Send result WhatsApp messages to all students in the class"""
        if not self.class_id or not self.exam_id:
            raise ValidationError(_("Please select both Class and Exam."))
        
        students = self.env['school.student'].search([
            ('class_id', '=', self.class_id.id),
            ('state', '=', 'admitted')
        ])
        
        if not students:
            raise ValidationError(_("No students found in this class."))
        
        sent_count = 0
        failed_count = 0
        
        for student in students:
            try:
                # Get student's result for this exam
                result = self.env['school.result'].search([
                    ('student_id', '=', student.id),
                    ('exam_id', '=', self.exam_id.id),
                    ('class_id', '=', self.class_id.id)
                ], limit=1)
                
                if not result:
                    _logger.warning(f"No result found for student {student.name} in exam {self.exam_id.name}")
                    failed_count += 1
                    continue
                
                # Prepare message
                message = f"Result Notification\n\n"
                message += f"Student: {student.name}\n"
                message += f"Roll Number: {student.roll_number}\n"
                message += f"Class: {self.class_id.name}\n"
                message += f"Exam: {self.exam_id.name}\n"
                message += f"Date: {result.date}\n\n"
                message += f"Total Marks: {result.total_marks}\n"
                message += f"Obtained Marks: {result.obtained_marks}\n"
                message += f"Percentage: {result.percentage:.2f}%\n"
                message += f"Grade: {result.grade}\n\n"
                
                message += "Subject-wise Marks:\n"
                for line in result.line_ids:
                    message += f"- {line.subject_id.name}: {line.obtained_marks}/{line.subject_id.max_marks}\n"
                
                # Send to parent phone (home number)
                phone = student.parent_phone if student.parent_phone else student.phone
                
                if phone:
                    self._send_whatsapp_message(phone, message)
                    sent_count += 1
                else:
                    _logger.warning(f"No phone number found for student {student.name}")
                    failed_count += 1
                    
            except Exception as e:
                _logger.error(f"Error sending WhatsApp to {student.name}: {str(e)}")
                failed_count += 1
        
        # Show summary message
        message = _("WhatsApp messages sent successfully!\n\n")
        message += _("Sent: %d\n") % sent_count
        message += _("Failed: %d") % failed_count
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('WhatsApp Messages'),
                'message': message,
                'type': 'success' if failed_count == 0 else 'warning',
                'sticky': False,
            }
        }
    
    def _send_whatsapp_message(self, phone, message):
        """Send WhatsApp message"""
        try:
            if not phone or not message:
                _logger.warning(f"Cannot send WhatsApp: phone={phone}, message={bool(message)}")
                return
            
            # Check if whatsapp.message model exists
            if 'whatsapp.message' in self.env:
                try:
                    create_vals = {'phone': phone}
                    whatsapp_model = self.env['whatsapp.message']
                    model_fields = whatsapp_model._fields
                    message_field = None
                    for field_name in ['message', 'body', 'text', 'content', 'message_text', 'message_body', 'msg_body', 'msg_text']:
                        if field_name in model_fields:
                            message_field = field_name
                            break
                    if message_field:
                        create_vals[message_field] = message
                        whatsapp_record = self.env['whatsapp.message'].sudo().create(create_vals)
                        _logger.info(f"WhatsApp message record created: ID={whatsapp_record.id}, Phone={phone}, Field={message_field}")
                    else:
                        try:
                            whatsapp_record = self.env['whatsapp.message'].sudo().create({'phone': phone, 'message': message})
                        except Exception:
                            whatsapp_record = self.env['whatsapp.message'].sudo().create({'phone': phone, 'body': message})
                    try:
                        if hasattr(whatsapp_record, 'action_send'):
                            whatsapp_record.action_send()
                            # Reload record to get updated state
                            whatsapp_record = self.env['whatsapp.message'].sudo().browse(whatsapp_record.id)
                            if whatsapp_record.state == 'sent':
                                _logger.info(f"WhatsApp message sent successfully: ID={whatsapp_record.id}, Phone={phone}")
                            elif whatsapp_record.state == 'failed':
                                _logger.error(f"WhatsApp message failed: ID={whatsapp_record.id}, Phone={phone}, Error={whatsapp_record.error or 'Unknown error'}")
                        elif hasattr(whatsapp_record, 'send'):
                            whatsapp_record.send()
                        elif hasattr(whatsapp_record, 'action_send_message'):
                            whatsapp_record.action_send_message()
                    except Exception as send_error:
                        _logger.error(f"Error calling action_send() for WhatsApp message ID={whatsapp_record.id}: {str(send_error)}")
                        import traceback
                        _logger.error(traceback.format_exc())
                    return whatsapp_record
                except Exception as e:
                    _logger.error(f"Error creating WhatsApp message record: {str(e)}")
                    import traceback
                    _logger.error(traceback.format_exc())
                    _logger.info(f"WhatsApp message to {phone}: {message}")
            else:
                _logger.warning(f"WhatsApp module not found. Message would be: Phone={phone}, Message={message[:50]}...")
                _logger.info(f"WhatsApp message to {phone}: {message}")
        except Exception as e:
            _logger.error(f"Error sending WhatsApp message to {phone}: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
