# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TierValidationFundMixin(models.AbstractModel):
    """Mixin reutilizable: tier validation acotada por contexto (etapa o fase SG)."""

    _name = "fund.tier.validation.mixin"
    _description = "Tier validation por contexto (fundación)"

    stage_validation_status = fields.Selection(
        selection=[
            ("no", "Without validation"),
            ("waiting", "Waiting"),
            ("pending", "Pending"),
            ("rejected", "Rejected"),
            ("validated", "Validated"),
        ],
        compute="_compute_stage_validation",
        store=False,
    )
    has_stage_reviews = fields.Boolean(
        compute="_compute_stage_validation",
        store=False,
    )
    tier_stage_locked = fields.Boolean(
        string="Bloqueado por validación (contexto)",
        compute="_compute_tier_stage_locked",
        store=False,
    )
    can_restart_validation_stage = fields.Boolean(
        compute="_compute_can_restart_validation_stage",
    )

    def _tier_context_value(self):
        """Valor de contexto actual (recordset stage o string fase)."""
        self.ensure_one()
        return False

    def _tier_context_domain(self, value):
        """Dominio para filtrar reviews del contexto actual."""
        field = self._tier_review_context_field()
        if not field or value is False:
            return []
        if hasattr(value, "id"):
            return [(field, "=", value.id)]
        return [(field, "=", value)]

    def _tier_review_context_field(self):
        return "stage_id"

    def _current_context_reviews(self):
        self.ensure_one()
        ctx = self._tier_context_value()
        field = self._tier_review_context_field()
        if not field:
            return self.env["tier.review"]

        def _matches_context(review):
            value = getattr(review, field)
            if hasattr(ctx, "id"):
                return value and value.id == ctx.id
            return value == ctx

        return self.review_ids.filtered(
            lambda r: _matches_context(r)
            or (
                not getattr(r, field)
                and r.status in ("waiting", "pending", "approved", "forwarded")
            )
        )

    def _get_applicable_tier_definitions(self):
        self.ensure_one()
        if isinstance(self.id, models.NewId):
            return self.env["tier.definition"]
        td_obj = self.env["tier.definition"].with_context(active_test=True)
        tiers = td_obj.search(
            [
                ("model", "=", self._name),
                ("company_id", "in", [False] + self._get_company().ids),
            ],
            order="sequence desc",
        )
        return tiers.filtered(lambda t: bool(self.evaluate_tier(t)))

    def _missing_tier_reviews_for_context(self):
        self.ensure_one()
        applicable = self._get_applicable_tier_definitions()
        missing = self.env["tier.definition"]
        for td in applicable:
            has_row = self._current_context_reviews().filtered(
                lambda r, d=td: r.definition_id == d
            )
            if not has_row:
                missing |= td
        return missing

    def _is_context_tier_complete(self):
        self.ensure_one()
        applicable = self._get_applicable_tier_definitions()
        if not applicable:
            return True
        context_reviews = self._current_context_reviews()
        review_model = self.env["tier.review"]
        return all(
            review_model._definition_reviews_resolved(td, context_reviews)
            for td in applicable
        )

    @api.depends("has_stage_reviews", "stage_validation_status")
    def _compute_tier_stage_locked(self):
        for rec in self:
            rec.tier_stage_locked = bool(rec.has_stage_reviews) and rec.stage_validation_status in (
                "waiting",
                "pending",
                "rejected",
                "validated",
            )

    def _get_tier_validation_readonly_domain(self):
        return "tier_stage_locked"

    @api.depends(
        "review_ids",
        "review_ids.status",
        "review_ids.stage_id",
        "review_ids.spend_phase",
        "review_ids.definition_id",
    )
    def _compute_need_validation(self):
        for rec in self:
            if isinstance(rec.id, models.NewId):
                rec.need_validation = False
                continue
            if not rec._check_state_from_condition():
                rec.need_validation = False
                continue
            rec.need_validation = bool(rec._missing_tier_reviews_for_context())

    def _tier_validation_check_write_allowed(self, vals):
        for rec in self:
            if rec._context.get("skip_validation_check"):
                continue
            if not rec.tier_stage_locked:
                continue
            if not rec._check_allow_write_under_validation(vals):
                allowed_fields, not_allowed_fields = rec._get_fields_to_write_validation(
                    vals, rec._get_under_validation_exceptions
                )
                raise ValidationError(
                    rec.env._(
                        "You are not allowed to write those fields under validation.\n"
                        "- %(not_allowed_fields_str)s\n\n"
                        "Only those fields can be modified:\n- %(allowed_fields_str)s",
                        not_allowed_fields_str="\n- ".join(not_allowed_fields),
                        allowed_fields_str="\n- ".join(allowed_fields),
                    )
                )

    @api.depends(
        "review_ids",
        "review_ids.status",
        "review_ids.stage_id",
        "review_ids.spend_phase",
    )
    def _compute_validation_status(self):
        validated_states = self._validated_states()
        rejected_states = self._rejected_states()
        for item in self:
            reviews = item._current_context_reviews()
            any_rejected = any(reviews.filtered(lambda x: x.status in rejected_states))
            any_pending = any(reviews.filtered(lambda x: x.status == "pending"))
            any_waiting = any(reviews.filtered(lambda x: x.status == "waiting"))
            if reviews and all(x.status in validated_states for x in reviews):
                item.validation_status = "validated"
            elif any_rejected:
                item.validation_status = "rejected"
            elif any_pending:
                item.validation_status = "pending"
            elif any_waiting:
                item.validation_status = "waiting"
            else:
                item.validation_status = "no"

    def _get_sequences_to_approve(self, user):
        self.ensure_one()
        all_reviews = self._current_context_reviews().filtered(
            lambda r: r.status in ("waiting", "pending")
        )
        my_reviews = all_reviews.filtered(lambda r: user.id in r.reviewer_ids.ids)
        sequences = my_reviews.filtered(lambda r: not r.approve_sequence).mapped("sequence")
        approve_sequences = my_reviews.filtered("approve_sequence").mapped("sequence")
        if approve_sequences:
            my_sequence = min(approve_sequences)
            min_sequence = min(all_reviews.mapped("sequence"))
            if my_sequence <= min_sequence:
                sequences.append(my_sequence)
        return sequences

    @api.depends_context("uid")
    @api.depends(
        "review_ids",
        "review_ids.status",
        "review_ids.stage_id",
        "review_ids.spend_phase",
        "review_ids.reviewer_ids",
    )
    def _compute_can_review(self):
        for rec in self:
            rec.can_review = bool(rec._get_sequences_to_approve(self.env.user))

    def _prepare_tier_review_vals(self, definition, sequence):
        vals = super()._prepare_tier_review_vals(definition, sequence)
        ctx = self._tier_context_value()
        field = self._tier_review_context_field()
        if field == "stage_id" and hasattr(ctx, "id"):
            vals["stage_id"] = ctx.id
        elif field == "spend_phase":
            vals["spend_phase"] = ctx
        return vals

    def request_validation(self):
        tr_obj = self.env["tier.review"]
        vals_list = []
        for rec in self:
            if not rec._check_state_from_condition():
                continue
            missing = rec._missing_tier_reviews_for_context()
            if not missing:
                continue
            td_obj = self.env["tier.definition"]
            tier_definitions = td_obj.search(
                [
                    ("model", "=", rec._name),
                    ("company_id", "in", [False] + rec._get_company().ids),
                ],
                order="sequence desc",
            )
            existing = rec._current_context_reviews()
            max_seq = max(existing.mapped("sequence"), default=0)
            sequence = max_seq
            for td in tier_definitions:
                if td not in missing:
                    continue
                sequence += 1
                vals_list.append(rec._prepare_tier_review_vals(td, sequence))
        if not vals_list:
            return tr_obj.browse()
        created_trs = tr_obj.create(vals_list)
        if any(self.mapped("can_review")):
            self._update_counter({"review_created": True})
        self._notify_review_requested(created_trs)
        return created_trs

    def restart_validation(self):
        """Reiniciar la validación: solo quien opera la etapa del expediente.

        Reiniciar borra las revisiones del contexto, así que equivale a dar de
        baja lo actuado: es una acción del circuito del expediente, no de
        cualquiera con acceso de lectura al registro.
        """
        for rec in self:
            if not rec.expedient_stage_editable:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual del expediente "
                        "pueden reiniciar la validación."
                    )
                )
        for rec in self:
            rec._current_context_reviews().sudo().unlink()
        self.review_ids._compute_can_review()
        return True

    @api.depends("review_ids", "review_ids.status", "review_ids.stage_id", "review_ids.spend_phase")
    def _compute_stage_validation(self):
        for rec in self:
            reviews = rec._current_context_reviews()
            rec.has_stage_reviews = bool(reviews)
            if not reviews:
                rec.stage_validation_status = "no"
                continue
            statuses = set(reviews.mapped("status"))
            if "rejected" in statuses:
                rec.stage_validation_status = "rejected"
            elif rec._is_context_tier_complete():
                rec.stage_validation_status = "validated"
            elif "pending" in statuses:
                rec.stage_validation_status = "pending"
            elif "waiting" in statuses:
                rec.stage_validation_status = "waiting"
            else:
                rec.stage_validation_status = "no"

    @api.depends("review_ids.status", "review_ids.stage_id", "review_ids.spend_phase")
    def _compute_can_restart_validation_stage(self):
        for rec in self:
            reviews = rec._current_context_reviews()
            rec.can_restart_validation_stage = bool(
                reviews
                and any(r.status in ("waiting", "pending", "rejected", "approved") for r in reviews)
            )

    def validate_tier(self):
        self.ensure_one()
        sequences = self._get_sequences_to_approve(self.env.user)
        reviews = self._current_context_reviews().filtered(
            lambda x: x.sequence in sequences or x.approve_sequence_bypass
        )
        if self.has_comment:
            user_reviews = reviews.filtered(
                lambda r: r.status == "pending" and (self.env.user in r.reviewer_ids)
            )
            return self._add_comment("validate", user_reviews)
        self._validate_tier(reviews)
        self._update_counter({"review_deleted": True})
        self._on_context_tier_validated()

    def _on_context_tier_validated(self):
        """Hook: acciones al completar validación del contexto actual."""

    # ------------------------------------------------------------------
    # Acciones para los botones EMBEBIDOS en el formulario del expediente
    #
    # La Solicitud, la Disposición y la Resolución se abren como diálogo desde
    # el expediente. Al aprobar o solicitar aprobación desde ahí, el cliente
    # recarga el registro del diálogo pero NO el expediente padre, así que sus
    # carteles y botones (quién lo tiene, requisitos pendientes, siguiente
    # etapa) quedaban con datos viejos hasta reabrir el expediente.
    #
    # Estos envoltorios existen solo para devolver una recarga del cliente. No
    # se cambia el retorno de `request_validation` / `restart_validation`
    # porque el portal los reutiliza y espera su valor original.
    # ------------------------------------------------------------------

    def _tier_ui_result(self, result):
        """Respeta la acción devuelta (p. ej. wizard de comentario) o recarga."""
        if isinstance(result, dict) and result.get("type"):
            return result
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_tier_request_validation(self):
        return self._tier_ui_result(self.request_validation())

    def action_tier_validate(self):
        return self._tier_ui_result(self.validate_tier())

    def action_tier_reject(self):
        return self._tier_ui_result(self.reject_tier())

    def action_tier_restart_validation(self):
        return self._tier_ui_result(self.restart_validation())

    def reject_tier(self):
        self.ensure_one()
        sequences = self._get_sequences_to_approve(self.env.user)
        reviews = self._current_context_reviews().filtered(lambda x: x.sequence in sequences)
        if self.has_comment:
            return self._add_comment("reject", reviews)
        self._rejected_tier(reviews)
        self._update_counter({"review_deleted": True})

    @api.depends("review_ids", "review_ids.status", "review_ids.stage_id", "review_ids.spend_phase")
    def _compute_reviewer_ids(self):
        for rec in self:
            rec.reviewer_ids = (
                rec._current_context_reviews()
                .filtered(lambda r: r.status in ("waiting", "pending"))
                .mapped("reviewer_ids")
            )

    @api.depends_context("uid")
    @api.depends("review_ids.status", "review_ids.stage_id", "review_ids.spend_phase")
    def _compute_has_comment(self):
        for rec in self:
            has_comment = rec._current_context_reviews().filtered(
                lambda r: r.status in ("waiting", "pending") and self.env.user in r.reviewer_ids
            ).mapped("has_comment")
            rec.has_comment = True in has_comment

    @api.depends("review_ids.status", "review_ids.stage_id", "review_ids.spend_phase")
    def _compute_next_review(self):
        for rec in self:
            review = rec._current_context_reviews().sorted("sequence").filtered(
                lambda x: x.status == "pending"
            )[:1]
            rec.next_review = review and self.env._("Next: %s", review.name or "") or ""
