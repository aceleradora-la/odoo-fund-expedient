# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FundExpedient(models.Model):
    _name = "fund.expedient"
    _inherit = ["fund.expedient", "tier.validation"]
    _state_from = ["draft", "in_progress", "to_approve"]
    _state_to = ["approved"]
    _cancel_state = "cancel"
    _tier_validation_manual_config = False
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
    can_restart_validation_stage = fields.Boolean(
        string="Puede reiniciar validación (etapa)",
        compute="_compute_can_restart_validation_stage",
    )

    # --- Validación por etapa (tier definitions aplicables × reviews con stage_id) ---

    def _get_applicable_tier_definitions(self):
        """Definiciones cuyo dominio/condiciones aplican al expediente en su estado actual."""
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
        # evaluate_tier devuelve subconjunto de self; vacío si el dominio no aplica.
        return tiers.filtered(lambda t: bool(self.evaluate_tier(t)))

    def _missing_tier_reviews_for_current_stage(self):
        """Definiciones aplicables sin línea de revisión para la etapa actual."""
        self.ensure_one()
        applicable = self._get_applicable_tier_definitions()
        missing = self.env["tier.definition"]
        for td in applicable:
            has_row = self.review_ids.filtered(
                lambda r, d=td: r.definition_id == d and r.stage_id == self.stage_id
            )
            if not has_row:
                missing |= td
        return missing

    def _is_current_stage_tier_complete(self):
        """Todas las definiciones aplicables tienen review aprobada en la etapa actual."""
        self.ensure_one()
        applicable = self._get_applicable_tier_definitions()
        if not applicable:
            return True
        for td in applicable:
            stage_rev = self.review_ids.filtered(
                lambda r, d=td: r.definition_id == d and r.stage_id == self.stage_id
            )
            if not stage_rev or any(r.status != "approved" for r in stage_rev):
                return False
        return True

    @api.depends(
        "review_ids",
        "review_ids.status",
        "review_ids.stage_id",
        "review_ids.definition_id",
        "stage_id",
        "state",
    )
    def _compute_need_validation(self):
        """Puede solicitar validación si faltan reviews de la etapa actual para defs. aplicables."""
        for rec in self:
            if isinstance(rec.id, models.NewId):
                rec.need_validation = False
                continue
            if not rec._check_state_from_condition():
                rec.need_validation = False
                continue
            rec.need_validation = bool(rec._missing_tier_reviews_for_current_stage())

    @api.depends(
        "review_ids",
        "review_ids.status",
        "review_ids.stage_id",
        "stage_id",
    )
    def _compute_validation_status(self):
        """Estado de validación solo según reviews de la etapa actual."""
        validated_states = self._validated_states()
        rejected_states = self._rejected_states()
        for item in self:
            reviews = item._current_stage_reviews()
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
        """Secuencias de aprobación solo en la etapa actual."""
        self.ensure_one()
        all_reviews = self._current_stage_reviews().filtered(
            lambda r: r.status in ("waiting", "pending")
        )
        my_reviews = all_reviews.filtered(lambda r: user in r.reviewer_ids)
        sequences = my_reviews.filtered(lambda r: not r.approve_sequence).mapped("sequence")
        approve_sequences = my_reviews.filtered("approve_sequence").mapped("sequence")
        if approve_sequences:
            my_sequence = min(approve_sequences)
            min_sequence = min(all_reviews.mapped("sequence"))
            if my_sequence <= min_sequence:
                sequences.append(my_sequence)
        return sequences

    def validate_tier(self):
        self.ensure_one()
        sequences = self._get_sequences_to_approve(self.env.user)
        reviews = self._current_stage_reviews().filtered(
            lambda x: x.sequence in sequences or x.approve_sequence_bypass
        )
        if self.has_comment:
            user_reviews = reviews.filtered(
                lambda r: r.status == "pending" and (self.env.user in r.reviewer_ids)
            )
            return self._add_comment("validate", user_reviews)
        self._validate_tier(reviews)
        self._update_counter({"review_deleted": True})

    def reject_tier(self):
        self.ensure_one()
        sequences = self._get_sequences_to_approve(self.env.user)
        reviews = self._current_stage_reviews().filtered(lambda x: x.sequence in sequences)
        if self.has_comment:
            return self._add_comment("reject", reviews)
        self._rejected_tier(reviews)
        self._update_counter({"review_deleted": True})

    def _validate_tier(self, tiers=False):
        """Igual que base_tier_validation pero notificaciones solo sobre la etapa actual."""
        self.ensure_one()
        tier_reviews = tiers or self._current_stage_reviews()
        waiting_reviews = tier_reviews.filtered(
            lambda r: r.status == "waiting"
            or r.approve_sequence_bypass
            and self.env.user in r.reviewer_ids
        )
        if waiting_reviews:
            waiting_reviews.write({"status": "pending"})
        user_reviews = tier_reviews.filtered(
            lambda r: r.status == "pending" and (self.env.user in r.reviewer_ids)
        )
        user_reviews.write(
            {
                "status": "approved",
                "done_by": self.env.user.id,
                "reviewed_date": fields.Datetime.now(),
            }
        )
        reviews_to_notify = user_reviews.filtered(lambda r: r.definition_id.notify_on_accepted)
        stage_reviews = self._current_stage_reviews()
        if tier_reviews and any(review.approve_sequence for review in tier_reviews):
            reviews_to_notify = stage_reviews.filtered(
                lambda r: r.status in ("waiting", "pending") and r.definition_id.notify_on_accepted
            )
            if reviews_to_notify and any(review.approve_sequence for review in reviews_to_notify):
                reviews_to_notify = reviews_to_notify.filtered(lambda x: x.approve_sequence)[:1]
        if reviews_to_notify:
            subscribe = "message_subscribe"
            if hasattr(self, subscribe):
                getattr(self, subscribe)(
                    partner_ids=reviews_to_notify.mapped("reviewer_ids").mapped("partner_id").ids,
                    subtype_ids=self.env.ref(self._get_accepted_notification_subtype()).ids,
                )
            for review in reviews_to_notify:
                rec = self.env[review.model].browse(review.res_id)
                rec._notify_accepted_reviews()

    def _rejected_tier(self, tiers=False):
        """Igual que base_tier_validation pero notificaciones solo sobre la etapa actual."""
        self.ensure_one()
        tier_reviews = tiers or self._current_stage_reviews()
        user_reviews = tier_reviews.filtered(
            lambda r: r.status in ("waiting", "pending") and self.env.user in r.reviewer_ids
        )
        user_reviews.write(
            {
                "status": "rejected",
                "done_by": self.env.user.id,
                "reviewed_date": fields.Datetime.now(),
            }
        )
        reviews_to_notify = user_reviews.filtered(lambda r: r.definition_id.notify_on_rejected)
        stage_reviews = self._current_stage_reviews()
        if tier_reviews and any(review.approve_sequence for review in tier_reviews):
            reviews_to_notify = stage_reviews.filtered(
                lambda r: r.status == "pending" and r.definition_id.notify_on_rejected
            )
            if reviews_to_notify and any(review.approve_sequence for review in reviews_to_notify):
                reviews_to_notify = reviews_to_notify.filtered(lambda x: x.approve_sequence)[:1]
        if reviews_to_notify:
            subscribe = "message_subscribe"
            if hasattr(self, subscribe):
                getattr(self, subscribe)(
                    partner_ids=reviews_to_notify.mapped("reviewer_ids").mapped("partner_id").ids,
                    subtype_ids=self.env.ref(self._get_rejected_notification_subtype()).ids,
                )
            for review in reviews_to_notify:
                rec = self.env[review.model].browse(review.res_id)
                rec._notify_rejected_review()

    def _notify_accepted_reviews_body(self):
        has_comment = self._current_stage_reviews().filtered(
            lambda r: (self.env.user in r.reviewer_ids) and r.comment
        )
        if has_comment:
            comment = has_comment.mapped("comment")[0]
            return self.env._("A review was accepted. (%s)", comment)
        return self.env._("A review was accepted")

    def _notify_rejected_review_body(self):
        has_comment = self._current_stage_reviews().filtered(
            lambda r: (self.env.user in r.reviewer_ids) and r.comment
        )
        if has_comment:
            comment = has_comment.mapped("comment")[0]
            return self.env._(
                "A review was rejected by %(user)s. (%(comment)s)",
                user=self.env.user.name,
                comment=comment,
            )
        return self.env._("A review was rejected by %s.", self.env.user.name)

    @api.depends("review_ids", "review_ids.status", "review_ids.stage_id", "stage_id")
    def _compute_reviewer_ids(self):
        for rec in self:
            rec.reviewer_ids = (
                rec._current_stage_reviews()
                .filtered(lambda r: r.status in ("waiting", "pending"))
                .mapped("reviewer_ids")
            )

    @api.depends_context("uid")
    @api.depends("review_ids.status", "review_ids.stage_id", "stage_id")
    def _compute_has_comment(self):
        for rec in self:
            has_comment = rec._current_stage_reviews().filtered(
                lambda r: r.status in ("waiting", "pending") and self.env.user in r.reviewer_ids
            ).mapped("has_comment")
            rec.has_comment = True in has_comment

    @api.depends("review_ids.status", "review_ids.stage_id", "stage_id")
    def _compute_next_review(self):
        for rec in self:
            review = rec._current_stage_reviews().sorted("sequence").filtered(
                lambda x: x.status == "pending"
            )[:1]
            rec.next_review = review and self.env._("Next: %s", review.name or "") or ""

    @api.depends("review_ids.status", "review_ids.stage_id", "stage_id")
    def _compute_can_restart_validation_stage(self):
        for rec in self:
            stage_reviews = rec.review_ids.filtered(lambda r: r.stage_id.id == rec.stage_id.id)
            rec.can_restart_validation_stage = bool(
                stage_reviews
                and any(
                    r.status in ("waiting", "pending", "rejected", "approved") for r in stage_reviews
                )
            )

    @api.depends(
        "review_ids.status",
        "review_ids.stage_id",
        "stage_id",
        "state",
    )
    def _compute_stage_validation(self):
        for rec in self:
            stage_reviews = rec.review_ids.filtered(lambda r: r.stage_id.id == rec.stage_id.id)
            rec.has_stage_reviews = bool(stage_reviews)
            if not stage_reviews:
                rec.stage_validation_status = "no"
                continue
            statuses = set(stage_reviews.mapped("status"))
            if "rejected" in statuses:
                rec.stage_validation_status = "rejected"
            elif rec._is_current_stage_tier_complete():
                rec.stage_validation_status = "validated"
            elif "pending" in statuses:
                rec.stage_validation_status = "pending"
            elif "waiting" in statuses:
                rec.stage_validation_status = "waiting"
            else:
                rec.stage_validation_status = "no"

    def _current_stage_reviews(self):
        """Reviews asociadas a la etapa actual (para validación por etapa)."""
        self.ensure_one()
        if not self.stage_id:
            return self.env["tier.review"]
        return self.review_ids.filtered(lambda r: r.stage_id.id == self.stage_id.id)

    def _prepare_tier_review_vals(self, definition, sequence):
        """Inyectar etapa actual en la review para auditoría por etapa."""
        vals = super()._prepare_tier_review_vals(definition, sequence)
        vals["stage_id"] = self.stage_id.id
        return vals

    def request_validation(self):
        """Crea solo las reviews faltantes para la etapa actual (respeta orden y secuencia)."""
        tr_obj = self.env["tier.review"]
        vals_list = []
        for rec in self:
            if not rec._check_state_from_condition():
                continue
            missing = rec._missing_tier_reviews_for_current_stage()
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
            existing = rec._current_stage_reviews()
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
        """Reiniciar solo la validación de la etapa actual (mantiene historial de otras etapas)."""
        for rec in self:
            rec._current_stage_reviews().sudo().unlink()
        self.review_ids._compute_can_review()
        return True

    def action_next_stage(self):
        """No permitir pasar a la siguiente etapa hasta que la validación esté finalizada."""
        for rec in self:
            if not rec.can_edit_in_stage:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual pueden pasar a la siguiente."
                    )
                )
            stage_reviews = rec._current_stage_reviews()
            if any(r.status in ("waiting", "pending", "rejected") for r in stage_reviews):
                raise UserError(
                    _(
                        "No puede pasar a la siguiente etapa hasta que la validación "
                        "de la etapa actual esté finalizada."
                    )
                )
            applicable = rec._get_applicable_tier_definitions()
            if applicable and not rec._is_current_stage_tier_complete():
                if rec._missing_tier_reviews_for_current_stage():
                    rec.request_validation()
                raise UserError(
                    _(
                        "No puede pasar a la siguiente etapa hasta que la validación "
                        "esté finalizada. Solicite la validación y espere su aprobación."
                    )
                )
        for rec, stages in self._get_allowed_stages():
            if not rec.stage_id or not stages:
                continue
            current_index = stages.ids.index(rec.stage_id.id) if rec.stage_id.id in stages.ids else -1
            if current_index == -1 or current_index + 1 >= len(stages):
                continue
            target = stages[current_index + 1]
            rec.with_context(skip_validation_check=True).write({"stage_id": target.id})
        return True

    def action_previous_stage(self):
        """Permitir volver de etapa usando skip_validation_check para no bloquear por tier validation."""
        for rec in self:
            if not rec.can_edit_in_stage:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual pueden volver a la etapa anterior."
                    )
                )
            stage_reviews = rec._current_stage_reviews()
            if any(r.status in ("waiting", "pending", "rejected") for r in stage_reviews):
                raise UserError(
                    _(
                        "No puede volver de etapa hasta que la validación de la etapa "
                        "actual esté finalizada."
                    )
                )
        for rec, stages in self._get_allowed_stages():
            if not rec.stage_id or not stages:
                continue
            current_index = stages.ids.index(rec.stage_id.id) if rec.stage_id.id in stages.ids else -1
            if current_index <= 0:
                continue
            target = stages[current_index - 1]
            rec.with_context(skip_validation_check=True).write({"stage_id": target.id})
        return True
