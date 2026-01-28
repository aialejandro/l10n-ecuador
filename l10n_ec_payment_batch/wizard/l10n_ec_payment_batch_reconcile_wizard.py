# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nEcPaymentBatchReconcileWizard(models.TransientModel):
    _name = 'l10n_ec.payment.batch.reconcile.wizard'
    _description = 'Select Invoices to Reconcile'

    batch_line_id = fields.Many2one(
        'l10n_ec.payment.batch.line',
        'Payment Line',
        required=True,
        ondelete='cascade'
    )
    
    batch_id = fields.Many2one(
        related='batch_line_id.batch_id'
    )
    
    partner_id = fields.Many2one(
        related='batch_line_id.partner_id',
        string='Partner'
    )
    
    partner_type = fields.Selection(
        related='batch_id.partner_type'
    )
    
    currency_id = fields.Many2one(
        related='batch_line_id.currency_id'
    )
    
    line_ids = fields.One2many(
        'l10n_ec.payment.batch.reconcile.wizard.line',
        'wizard_id',
        string='Invoice Lines'
    )
    
    total_selected = fields.Monetary(
        compute='_compute_total_selected',
        currency_field='currency_id',
        string='Total Selected'
    )
    
    @api.depends('line_ids.selected', 'line_ids.amount')
    def _compute_total_selected(self):
        for wizard in self:
            wizard.total_selected = sum(line.amount for line in wizard.line_ids if line.selected)

    def action_confirm(self):
        self.ensure_one()
        
        # Validate selected lines
        for line in self.line_ids.filtered('selected'):
            if line.amount <= 0:
                raise ValidationError(
                    _('Amount to pay must be greater than zero for invoice %s.') % line.move_id.name
                )
            
            if line.amount > line.available_residual:
                raise ValidationError(
                    _('Amount to pay (%(amount)s) exceeds available residual (%(available)s) for invoice %(invoice)s.') % {
                        'amount': line.amount,
                        'available': line.available_residual,
                        'invoice': line.move_id.name,
                    }
                )
        
        # Get selected move line IDs
        selected_move_line_ids = self.line_ids.filtered('selected').mapped('move_line_id').ids
        
        # Remove unselected allocations
        to_remove = self.batch_line_id.reconcile_line_ids.filtered(
            lambda r: r.move_line_id.id not in selected_move_line_ids
        )
        to_remove.unlink()
        
        # Create or update reconciliation lines
        for wiz_line in self.line_ids.filtered('selected'):
            existing = self.batch_line_id.reconcile_line_ids.filtered(
                lambda r: r.move_line_id.id == wiz_line.move_line_id.id
            )
            
            if existing:
                existing.write({'amount': wiz_line.amount})
            else:
                self.env['l10n_ec.payment.batch.line.reconcile'].create({
                    'batch_line_id': self.batch_line_id.id,
                    'move_line_id': wiz_line.move_line_id.id,
                    'amount': wiz_line.amount,
                })
        
        return {
            'type': 'ir.actions.act_window_close',
        }

    def action_select_all(self):
        for line in self.line_ids:
            if line.available_residual > 0:
                line.selected = True
                if line.amount == 0:
                    line.amount = line.available_residual
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_deselect_all(self):
        self.line_ids.write({
            'selected': False,
            'amount': 0,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class L10nEcPaymentBatchReconcileWizardLine(models.TransientModel):
    _name = 'l10n_ec.payment.batch.reconcile.wizard.line'
    _description = 'Invoice Line Selection'

    wizard_id = fields.Many2one(
        'l10n_ec.payment.batch.reconcile.wizard',
        required=True,
        ondelete='cascade'
    )
    
    batch_id = fields.Many2one(
        related='wizard_id.batch_id'
    )
    
    batch_line_id = fields.Many2one(
        related='wizard_id.batch_line_id'
    )
    
    selected = fields.Boolean('Select', default=False)
    
    move_line_id = fields.Many2one(
        'account.move.line',
        'Invoice Line',
        required=True
    )
    
    move_id = fields.Many2one(
        related='move_line_id.move_id',
        string='Invoice'
    )
    
    date_maturity = fields.Date(
        related='move_line_id.date_maturity',
        string='Due Date'
    )
    
    currency_id = fields.Many2one(
        related='move_line_id.currency_id'
    )
    
    full_residual = fields.Monetary(
        string='Full Residual',
        compute='_compute_residuals',
        currency_field='currency_id'
    )
    
    allocated_in_batch = fields.Monetary(
        string='Allocated in Batch',
        compute='_compute_residuals',
        currency_field='currency_id'
    )
    
    available_residual = fields.Monetary(
        string='Available',
        compute='_compute_residuals',
        currency_field='currency_id'
    )
    
    amount = fields.Monetary(
        string='Amount to Pay',
        currency_field='currency_id'
    )
    
    @api.depends('move_line_id', 'batch_id', 'batch_line_id')
    def _compute_residuals(self):
        for rec in self:
            if rec.move_line_id:
                rec.full_residual = abs(rec.move_line_id.amount_residual_currency)
                
                other_allocations = self.env['l10n_ec.payment.batch.line.reconcile'].search([
                    ('batch_id', '=', rec.batch_id.id),
                    ('move_line_id', '=', rec.move_line_id.id),
                    ('batch_line_id', '!=', rec.batch_line_id.id),
                ])
                rec.allocated_in_batch = sum(other_allocations.mapped('amount'))
                rec.available_residual = rec.full_residual - rec.allocated_in_batch
            else:
                rec.full_residual = 0
                rec.allocated_in_batch = 0
                rec.available_residual = 0

    @api.onchange('selected')
    def _onchange_selected(self):
        if self.selected and self.amount == 0:
            self.amount = self.available_residual
        elif not self.selected:
            self.amount = 0
