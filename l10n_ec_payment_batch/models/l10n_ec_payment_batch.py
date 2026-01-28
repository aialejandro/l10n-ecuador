# -*- coding: utf-8 -*-

import base64

from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang


class L10nEcPaymentBatch(models.Model):
    _name = 'l10n_ec.payment.batch'
    _description = 'Payment Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Batch Name', required=True, default='/', help='Name of the payment batch')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        tracking=True
    )
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', 'Currency', related='company_id.currency_id', readonly=True)
    
    batch_date = fields.Date('Batch Date', required=True, default=fields.Date.context_today)
    partner_type = fields.Selection([('customer', 'Customer'), ('supplier', 'Supplier')], required=True, default='supplier')
    payment_method_line_id = fields.Many2one(
        'account.payment.method.line',
        'Payment Method',
        required=True,
        domain="[('payment_method_id.payment_type', '=', 'outbound' if partner_type == 'supplier' else 'inbound')]"
    )
    partner_ids = fields.Many2many('res.partner', string='Partners')
    
    line_ids = fields.One2many('l10n_ec.payment.batch.line', 'batch_id', 'Batch Lines')
    total_amount = fields.Monetary('Total Amount', compute='_compute_total', currency_field='currency_id', readonly=True)
    has_own_checks = fields.Boolean(
        string='Has Own Checks',
        compute='_compute_has_own_checks',
        store=True,
        help='Technical field to control check columns visibility.'
    )
    
    @api.depends('line_ids.amount', 'line_ids.reconcile_line_ids', 'line_ids.reconcile_line_ids.amount')
    def _compute_total(self):
        for record in self:
            record.total_amount = sum(record.line_ids.mapped('amount'))
    
    @api.onchange('partner_type')
    def _onchange_partner_type(self):
        """Clear payment_method_line_id when partner_type changes"""
        self.payment_method_line_id = False

    @api.depends('payment_method_line_id.payment_method_id.code')
    def _compute_has_own_checks(self):
        for record in self:
            record.has_own_checks = record.payment_method_line_id.payment_method_id.code == 'own_checks' if record.payment_method_line_id else False

    def action_confirm(self):
        for batch in self:
            batch._l10n_ec_create_payments()
        self.write({'state': 'confirmed'})
        
    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals.get('name') == '/':
            partner_type = vals.get('partner_type') or self.env.context.get('default_partner_type') or 'supplier'
            sequence_code = 'l10n_ec.payment.batch.customer' if partner_type == 'customer' else 'l10n_ec.payment.batch.supplier'
            vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or '/'
        return super().create(vals)

    def action_download_txt(self):
        self.ensure_one()
        payment_method_line = self.payment_method_line_id
        if not payment_method_line or not payment_method_line.journal_id:
            raise ValidationError(_('Please select a payment method with a journal.'))

        bank_account = payment_method_line.journal_id.bank_account_id
        if not bank_account:
            raise ValidationError(_('The selected journal has no bank account.'))

        bic_value = (bank_account.bank_bic or '').strip()
        if bic_value != '10':
            raise ValidationError(_('The bank account BIC must be 10 to download this TXT file.'))

        if not self.line_ids:
            raise ValidationError(_('Please add at least one batch line.'))

        currency_name = self.currency_id.name or ''
        account_number = bank_account.acc_number or ''
        company_name = self.company_id.name or ''

        lines = []
        for index, line in enumerate(self.line_ids.sorted('id'), start=1):
            partner = line.partner_id
            partner_vat = partner.vat or ''
            partner_name = partner.name or ''
            columns = [
                'PA',
                str(index),
                currency_name,
                account_number,
                company_name,
                'C',
                partner_vat,
                partner_name,
            ]
            lines.append('|'.join(columns))

        content = '\n'.join(lines) + '\n'
        filename = f"payment_batch_{self.id}.txt"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(content.encode('utf-8')),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'text/plain',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=1',
            'target': 'self',
        }
    
    def action_update_lines(self):
        """Add lines for partners that don't already have one"""
        for record in self:
            # Get the list of partners that already have a line
            existing_partner_ids = record.line_ids.mapped('partner_id').ids
            
            # Find partners that need a line added
            partners_to_add = record.partner_ids.filtered(lambda p: p.id not in existing_partner_ids)
            
            # Create a line for each missing partner
            for partner in partners_to_add:
                self.env['l10n_ec.payment.batch.line'].create({
                    'batch_id': record.id,
                    'partner_id': partner.id,
                    'amount': 0.0,
                })

    def _l10n_ec_create_payments(self):
        for batch in self:
            if not batch.line_ids:
                raise ValidationError(_('Please add at least one batch line.'))
            lines_to_pay = batch.line_ids.filtered(lambda l: l.amount > 0 and not l.payment_id)
            if not lines_to_pay:
                continue
            for line in lines_to_pay:
                payment_vals = line._l10n_ec_prepare_payment_vals()
                payment = self.env['account.payment']\
                    .with_context(l10n_ec_skip_check_reserve=True)\
                    .create(payment_vals)
                line.payment_id = payment
                payment.action_post()
                line._l10n_ec_reconcile_payment(payment)


class L10nEcPaymentBatchLine(models.Model):
    _name = 'l10n_ec.payment.batch.line'
    _description = 'Payment Batch Line'

    batch_id = fields.Many2one('l10n_ec.payment.batch', 'Payment Batch', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', 'Partner', required=True, default=lambda self: self._default_partner_id())
    payment_method_line_id = fields.Many2one('account.payment.method.line', 'Payment Method', related='batch_id.payment_method_line_id', readonly=False)

    is_own_checks = fields.Boolean(
        string='Own Checks Method',
        compute='_compute_is_own_checks',
        store=True,
        help='Indicates this line uses the own checks payment method.'
    )

    check_number = fields.Char(
        string='Check Number',
        copy=False,
        help='Check number reserved for this payment line when using own checks.'
    )
    check_beneficiary = fields.Char(
        string='Check Beneficiary',
        help='Beneficiary to print on the check.'
    )
    check_payment_date = fields.Date(
        string='Check Payment Date',
        help='Payment date to print on the check.'
    )
    
    currency_id = fields.Many2one('res.currency', 'Currency', related='batch_id.currency_id', readonly=True)
    amount = fields.Monetary(
        'Amount',
        compute='_compute_amount',
        currency_field='currency_id',
        store=True,
        readonly=True,
        default=0.0,
    )
    
    reconcile_line_ids = fields.One2many('l10n_ec.payment.batch.line.reconcile', 'batch_line_id', 'Reconcile Lines')

    payment_id = fields.Many2one('account.payment', 'Payment', readonly=True, copy=False)
    payment_state = fields.Selection(related='payment_id.state', string='Payment Status', readonly=True)
    
    full_residual = fields.Monetary('Full Residual', compute='_compute_residuals', currency_field='currency_id', readonly=True)
    
    display_name = fields.Char(compute='_compute_display_name', readonly=True)
    tag_color = fields.Integer(compute='_compute_tag_color', readonly=True)
    
    @api.depends('amount')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Line') if not rec.id else _('Line #%s') % rec.id

    @api.onchange('batch_id')
    def _onchange_batch_id_set_partner(self):
        if not self.partner_id and self.batch_id and len(self.batch_id.partner_ids) == 1:
            self.partner_id = self.batch_id.partner_ids.id

    @api.onchange('partner_id')
    def _onchange_partner_id_set_beneficiary(self):
        for rec in self:
            if rec.is_own_checks and rec.partner_id and not rec.check_beneficiary:
                rec.check_beneficiary = rec.partner_id.name

    @api.onchange('payment_method_line_id')
    def _onchange_payment_method_line_id_set_check_defaults(self):
        for rec in self:
            rec.is_own_checks = bool(rec.payment_method_line_id and rec.payment_method_line_id.payment_method_id.code == 'own_checks')
            if rec.is_own_checks:
                bank_account = rec._l10n_ec_get_bank_account()
                if bank_account and not rec.check_number:
                    taken_numbers = rec._l10n_ec_get_taken_numbers(exclude_current=True)
                    peek = bank_account._l10n_ec_peek_next_check_number(taken_numbers)
                    if peek:
                        rec.check_number = peek
                if not rec.check_beneficiary and rec.partner_id:
                    rec.check_beneficiary = rec.partner_id.name
                if not rec.check_payment_date:
                    rec.check_payment_date = rec.batch_id.batch_date or fields.Date.context_today(rec)

    @api.model
    def _default_partner_id(self):
        if self.env.context.get('default_partner_id'):
            return self.env.context.get('default_partner_id')
        batch_id = self.env.context.get('default_batch_id')
        if batch_id:
            batch = self.env['l10n_ec.payment.batch'].browse(batch_id)
            if len(batch.partner_ids) == 1:
                return batch.partner_ids.id
        return False

    @api.model
    def create(self, vals):
        if not vals.get('partner_id') and vals.get('batch_id'):
            batch = self.env['l10n_ec.payment.batch'].browse(vals['batch_id'])
            if len(batch.partner_ids) == 1:
                vals['partner_id'] = batch.partner_ids.id
        vals = self._l10n_ec_prepare_check_fields(vals)
        return super().create(vals)

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        batch_id = defaults.get('batch_id') or self.env.context.get('default_batch_id')
        batch = self.env['l10n_ec.payment.batch'].browse(batch_id) if batch_id else False

        if 'check_payment_date' in fields_list and not defaults.get('check_payment_date'):
            defaults['check_payment_date'] = (batch.batch_date if batch else False) or fields.Date.context_today(self)

        if 'check_beneficiary' in fields_list and not defaults.get('check_beneficiary'):
            partner_id = defaults.get('partner_id') or self.env.context.get('default_partner_id')
            if partner_id:
                defaults['check_beneficiary'] = self.env['res.partner'].browse(partner_id).name

        if 'check_number' in fields_list and not defaults.get('check_number'):
            payment_method_line = self._l10n_ec_get_payment_method_line(defaults, batch)
            if payment_method_line and payment_method_line.payment_method_id.code == 'own_checks':
                bank_account = payment_method_line.journal_id.bank_account_id
                if bank_account:
                    taken_numbers = self._l10n_ec_get_taken_numbers(batch=batch)
                    defaults['check_number'] = bank_account._l10n_ec_peek_next_check_number(taken_numbers)

        return defaults

    @api.depends('reconcile_line_ids')
    def _compute_tag_color(self):
        for rec in self:
            rec.tag_color = 2 if rec.reconcile_line_ids else 0

    @api.depends('payment_method_line_id.payment_method_id.code')
    def _compute_is_own_checks(self):
        for rec in self:
            code = rec.payment_method_line_id.payment_method_id.code if rec.payment_method_line_id else False
            rec.is_own_checks = code == 'own_checks'

    @api.depends('reconcile_line_ids', 'reconcile_line_ids.move_line_id')
    def _compute_residuals(self):
        for rec in self:
            # Sum the residuals from all reconcile lines
            rec.full_residual = sum(line.move_line_id.amount_residual_currency for line in rec.reconcile_line_ids if line.move_line_id)

    @api.depends('reconcile_line_ids', 'reconcile_line_ids.amount')
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(rec.reconcile_line_ids.mapped('amount'))

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_('Amount to pay cannot be negative.'))

    def _l10n_ec_get_payment_method_line(self, defaults, batch):
        payment_method_line = False
        if defaults.get('payment_method_line_id'):
            payment_method_line = self.env['account.payment.method.line'].browse(defaults['payment_method_line_id'])
        elif batch:
            payment_method_line = batch.payment_method_line_id
        elif self.env.context.get('default_payment_method_line_id'):
            payment_method_line = self.env['account.payment.method.line'].browse(self.env.context.get('default_payment_method_line_id'))
        return payment_method_line

    def _l10n_ec_get_bank_account(self):
        self.ensure_one()
        payment_method_line = self.payment_method_line_id or (self.batch_id.payment_method_line_id if self.batch_id else False)
        journal = payment_method_line.journal_id if payment_method_line else False
        return journal.bank_account_id if journal else self.env['res.partner.bank']

    def _l10n_ec_get_taken_numbers(self, batch=None, exclude_current=False):
        batch = batch or (self.batch_id if self else False)
        if not batch:
            return []
        lines = batch.line_ids
        if exclude_current and self:
            current_ids = self.ids
            lines = lines.filtered(lambda l: l.id not in current_ids)
        return [num for num in lines.mapped('check_number') if num]

    def _l10n_ec_prepare_check_fields(self, vals):
        vals = dict(vals)
        batch = self.env['l10n_ec.payment.batch'].browse(vals.get('batch_id')) if vals.get('batch_id') else False

        # Determine payment method line and whether it uses own checks
        payment_method_line_id = vals.get('payment_method_line_id')
        if not payment_method_line_id and batch:
            payment_method_line_id = batch.payment_method_line_id.id
            vals['payment_method_line_id'] = payment_method_line_id
        payment_method_line = self.env['account.payment.method.line'].browse(payment_method_line_id) if payment_method_line_id else False
        is_own_checks = payment_method_line and payment_method_line.payment_method_id.code == 'own_checks'

        if is_own_checks:
            bank_account = payment_method_line.journal_id.bank_account_id
            if bank_account:
                manual_number = vals.get('check_number')
                if manual_number:
                    vals['check_number'] = str(manual_number).zfill(8) if str(manual_number).isdigit() else manual_number
                else:
                    taken_numbers = self._l10n_ec_get_taken_numbers(batch=batch)
                    vals['check_number'] = bank_account._l10n_ec_peek_next_check_number(taken_numbers)
            if not vals.get('check_beneficiary') and vals.get('partner_id'):
                vals['check_beneficiary'] = self.env['res.partner'].browse(vals['partner_id']).name
            if not vals.get('check_payment_date'):
                vals['check_payment_date'] = (batch.batch_date if batch else False) or fields.Date.context_today(self)

        return vals

    def action_open_reconcile_wizard(self):
        self.ensure_one()
        partner = self.partner_id
        batch = self.batch_id

        account_types = ['asset_receivable'] if batch.partner_type == 'customer' else ['liability_payable']
        domain = [
            ('partner_id', '=', partner.id),
            ('move_id.state', '=', 'posted'),
            ('account_id.account_type', 'in', account_types),
            ('amount_residual', '!=', 0),
            ('company_id', '=', batch.company_id.id),
        ]
        move_lines = self.env['account.move.line'].search(domain)

        existing_amounts = {line.move_line_id.id: line.amount for line in self.reconcile_line_ids}
        wizard_lines = []
        for move_line in move_lines:
            amount = existing_amounts.get(move_line.id, 0.0)
            wizard_lines.append((0, 0, {
                'move_line_id': move_line.id,
                'selected': move_line.id in existing_amounts,
                'amount': amount,
            }))

        wizard = self.env['l10n_ec.payment.batch.reconcile.wizard'].create({
            'batch_line_id': self.id,
            'line_ids': wizard_lines,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_ec.payment.batch.reconcile.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _l10n_ec_prepare_payment_vals(self):
        self.ensure_one()
        batch = self.batch_id
        if not batch.payment_method_line_id:
            raise ValidationError(_('Please select a payment method on the batch.'))
        journal = batch.payment_method_line_id.journal_id
        if not journal:
            raise ValidationError(_('The selected payment method has no journal assigned.'))

        payment_type = 'outbound' if batch.partner_type == 'supplier' else 'inbound'
        vals = {
            'payment_type': payment_type,
            'partner_type': batch.partner_type,
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'currency_id': batch.currency_id.id,
            'company_id': batch.company_id.id,
            'journal_id': journal.id,
            'payment_method_line_id': batch.payment_method_line_id.id,
            'date': batch.batch_date or fields.Date.context_today(self),
            'memo': batch.name,
            'l10n_ec_payment_batch_id': batch.id,
        }

        if self.is_own_checks:
            if not self.check_number:
                raise ValidationError(_('Please set a check number for partner %s.') % self.partner_id.display_name)
            check_number = str(self.check_number).zfill(8) if str(self.check_number).isdigit() else self.check_number
            payment_date = self.check_payment_date or batch.batch_date or fields.Date.context_today(self)
            vals['l10n_latam_new_check_ids'] = [Command.create({
                'name': check_number,
                'amount': self.amount,
                'payment_date': payment_date,
                'beneficiary': self.check_beneficiary or self.partner_id.name,
            })]
        return vals

    def _l10n_ec_reconcile_payment(self, payment):
        self.ensure_one()
        if not self.reconcile_line_ids:
            return

        liquidity_lines, counterpart_lines, writeoff_lines = payment._seek_for_lines()
        counterpart_lines = counterpart_lines.filtered(lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable'))
        if not counterpart_lines:
            raise ValidationError(_('No counterpart line found to reconcile payment %s.') % payment.display_name)

        company_currency = payment.company_id.currency_id
        for rec_line in self.reconcile_line_ids:
            move_line = rec_line.move_line_id
            amount = rec_line.amount
            if amount <= 0:
                continue
            payment_line = counterpart_lines.filtered(lambda l: l.account_id == move_line.account_id)[:1]
            if not payment_line:
                raise ValidationError(_(
                    'Payment %s cannot be reconciled with line %s because accounts do not match.'
                ) % (payment.display_name, move_line.display_name))

            debit_line = move_line if move_line.balance > 0 else payment_line
            credit_line = payment_line if move_line.balance > 0 else move_line

            debit_amount_currency = 0.0
            credit_amount_currency = 0.0
            if debit_line.currency_id:
                if debit_line.currency_id == company_currency:
                    debit_amount_currency = amount
                else:
                    debit_amount_currency = company_currency._convert(
                        amount, debit_line.currency_id, payment.company_id, payment.date
                    )
            if credit_line.currency_id:
                if credit_line.currency_id == company_currency:
                    credit_amount_currency = amount
                else:
                    credit_amount_currency = company_currency._convert(
                        amount, credit_line.currency_id, payment.company_id, payment.date
                    )

            self.env['account.partial.reconcile'].create({
                'debit_move_id': debit_line.id,
                'credit_move_id': credit_line.id,
                'amount': amount,
                'debit_amount_currency': abs(debit_amount_currency),
                'credit_amount_currency': abs(credit_amount_currency),
            })


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    l10n_ec_payment_batch_id = fields.Many2one(
        'l10n_ec.payment.batch',
        'Payment Batch',
        ondelete='set null'
    )


class L10nEcPaymentBatchLineReconcile(models.Model):
    _name = 'l10n_ec.payment.batch.line.reconcile'
    _description = 'Payment Batch Line Reconciliation'
    _rec_name = 'display_name'

    batch_line_id = fields.Many2one('l10n_ec.payment.batch.line', 'Batch Line', required=True, ondelete='cascade')
    batch_id = fields.Many2one('l10n_ec.payment.batch', 'Batch', related='batch_line_id.batch_id', readonly=True)
    move_line_id = fields.Many2one('account.move.line', 'Invoice Line', required=True)
    move_id = fields.Many2one('account.move', 'Invoice', related='move_line_id.move_id')
    
    currency_id = fields.Many2one('res.currency', 'Currency', related='batch_line_id.currency_id', readonly=True)
    amount = fields.Monetary('Amount to Pay', currency_field='currency_id')

    display_name = fields.Char(compute='_compute_display_name', store=True)
    
    allocated_in_batch = fields.Monetary('Allocated in Batch', compute='_compute_allocations', currency_field='currency_id', readonly=True)
    available_residual = fields.Monetary('Available Residual', compute='_compute_allocations', currency_field='currency_id', readonly=True)

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, rec.display_name))
        return result

    @api.depends('move_line_id', 'amount', 'currency_id')
    def _compute_display_name(self):
        for rec in self:
            move_name = rec.move_line_id.name or rec.move_line_id.move_id.name or _('Move Line')
            if rec.currency_id:
                amount_display = formatLang(self.env, rec.amount, currency_obj=rec.currency_id)
            else:
                amount_display = str(rec.amount)
            rec.display_name = f"{move_name}: {amount_display}"
    
    @api.depends('move_line_id', 'batch_id')
    def _compute_allocations(self):
        for rec in self:
            if rec.move_line_id:
                # Find all other batch lines in the same batch that have this move_line allocated
                other_allocations = self.search([
                    ('batch_id', '=', rec.batch_id.id),
                    ('move_line_id', '=', rec.move_line_id.id),
                    ('id', '!=', rec.id),
                ])
                rec.allocated_in_batch = sum(other_allocations.mapped('amount'))
                rec.available_residual = abs(rec.move_line_id.amount_residual_currency) - rec.allocated_in_batch
            else:
                rec.allocated_in_batch = 0
                rec.available_residual = 0
