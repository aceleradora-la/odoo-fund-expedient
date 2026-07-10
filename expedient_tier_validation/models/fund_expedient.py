# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class FundExpedient(models.Model):
    _name = "fund.expedient"
    _inherit = ["fund.expedient", "fund.tier.approval.search.mixin", "tier.validation"]
    _state_from = ["draft", "in_progress", "purchases", "to_approve", "approved"]
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
    tier_stage_locked = fields.Boolean(
        string="Bloqueado por validación (etapa)",
        compute="_compute_tier_stage_locked",
        store=False,
        help=(
            "Indica si la etapa actual está bloqueada por el flujo de aprobaciones. "
            "Se usa para readonly y restricciones de escritura por etapa."
        ),
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

    def _current_stage_open_reviews(self):
        """Reviews de la etapa actual que bloquean escritura (waiting/pending)."""
        self.ensure_one()
        return self._current_stage_reviews().filtered(lambda r: r.status in ("waiting", "pending"))

    @api.depends("has_stage_reviews", "stage_validation_status")
    def _compute_tier_stage_locked(self):
        """Bloqueo por etapa: solo si ya se inició el flujo en la etapa (hay reviews)."""
        for rec in self:
            rec.tier_stage_locked = bool(rec.has_stage_reviews) and rec.stage_validation_status in (
                "waiting",
                "pending",
                "rejected",
                "validated",
            )

    def _get_tier_validation_readonly_domain(self):
        """Readonly dinámico de base_tier_validation, pero por etapa.

        Regla acordada:
        - Al entrar a una etapa (sin reviews de esa etapa): editable.
        - Una vez solicitado el flujo (waiting/pending) o cerrado (validated/rejected): readonly hasta cambiar de etapa.
        """
        return "tier_stage_locked"

    def _missing_tier_reviews_for_current_stage(self):
        """Definiciones aplicables sin línea de revisión para la etapa actual."""
        self.ensure_one()
        applicable = self._get_applicable_tier_definitions()
        missing = self.env["tier.definition"]
        for td in applicable:
            has_row = self._current_stage_reviews().filtered(
                lambda r, d=td: r.definition_id == d
            )
            if not has_row:
                missing |= td
        return missing

    def _is_current_stage_tier_complete(self):
        """Todas las definiciones aplicables están resueltas en la etapa actual."""
        self.ensure_one()
        applicable = self._get_applicable_tier_definitions()
        if not applicable:
            return True
        context_reviews = self._current_stage_reviews()
        review_model = self.env["tier.review"]
        return all(
            review_model._definition_reviews_resolved(td, context_reviews)
            for td in applicable
        )

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

    def _tier_validation_check_write_allowed(self, vals):
        """Tier validation por etapa.

        El mixin estándar bloquea escrituras si existen reviews en el registro, incluso si
        pertenecen a etapas anteriores. Para permitir edición según permisos de etapa y
        conservar auditoría histórica, sólo aplicamos el bloqueo cuando el flujo está
        iniciado/cerrado en la etapa actual.
        """
        for rec in self:
            if rec._context.get("skip_validation_check"):
                continue
            if not rec.tier_stage_locked:
                continue
            if not rec._check_allow_write_under_validation(vals):
                (
                    allowed_fields,
                    not_allowed_fields,
                ) = rec._get_fields_to_write_validation(
                    vals, rec._get_under_validation_exceptions
                )
                not_allowed_fields_str = "\n- ".join(not_allowed_fields)
                allowed_fields_str = "\n- ".join(allowed_fields)
                raise ValidationError(
                    rec.env._(
                        "You are not allowed to write those fields under validation.\n"
                        "- %(not_allowed_fields_str)s\n\n"
                        "Only those fields can be modified:\n- %(allowed_fields_str)s",
                        not_allowed_fields_str=not_allowed_fields_str,
                        allowed_fields_str=allowed_fields_str,
                    )
                )

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
        "stage_id",
        "review_ids",
        "review_ids.status",
        "review_ids.stage_id",
        "review_ids.reviewer_ids",
    )
    def _compute_can_review(self):
        """Debe recalcularse al cambiar etapa (el mixin base solo mira review_ids.status)."""
        for rec in self:
            rec.can_review = bool(rec._get_sequences_to_approve(self.env.user))

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
        self._try_auto_advance_stage_after_tier()

    def _tier_auto_advance_enabled(self):
        self.ensure_one()
        assign = self._current_stage_assign()
        return bool(assign and assign.auto_advance_on_tier_validated)

    def _try_auto_advance_stage_after_tier(self):
        """Avanza de etapa si la configuración del tipo/etapa lo permite y tier está completo."""
        if self.env.context.get("skip_auto_advance_stage"):
            return
        for rec in self:
            if not rec._tier_auto_advance_enabled():
                continue
            if not rec._get_applicable_tier_definitions():
                continue
            if not rec._is_current_stage_tier_complete():
                continue
            try:
                if rec.with_context(skip_auto_advance_stage=True)._auto_advance_to_next_stage():
                    continue
            except UserError as err:
                rec.message_post(
                    body=_(
                        "Validación de etapa completada. No se avanzó automáticamente "
                        "a la siguiente etapa: %s",
                        err,
                    ),
                    subtype_xmlid="mail.mt_note",
                )

    def _get_next_stage_target(self, *, require_can_edit=True):
        """Resuelve la etapa destino tras validar requisitos. False si no puede avanzar."""
        self.ensure_one()
        if require_can_edit and not self.can_edit_in_stage:
            raise UserError(
                _(
                    "Solo los usuarios asignados a la etapa actual pueden pasar a la siguiente."
                )
            )
        if self.stage_id.final_outcome:
            raise UserError(
                _(
                    "El expediente está cerrado como «%s»; no puede avanzar de etapa. "
                    "Solo puede cancelarse si corresponde."
                )
                % self.stage_id.name
            )
        self._check_spend_request_before_leave_stage()
        if not self.env.context.get("skip_document_check"):
            self._check_required_documents_before_leave_stage()
        stage_reviews = self._current_stage_reviews()
        if any(r.status in ("waiting", "pending", "rejected") for r in stage_reviews):
            raise UserError(
                _(
                    "No puede pasar a la siguiente etapa hasta que la validación "
                    "de la etapa actual esté finalizada."
                )
            )
        applicable = self._get_applicable_tier_definitions()
        if applicable and not self._is_current_stage_tier_complete():
            if self._missing_tier_reviews_for_current_stage():
                self.request_validation()
            raise UserError(
                _(
                    "No puede pasar a la siguiente etapa hasta que la validación "
                    "esté finalizada. Solicite la validación y espere su aprobación."
                )
            )
        for rec, stages in self._get_allowed_stages():
            if rec.id != self.id or not rec.stage_id or not stages:
                continue
            current_index = (
                stages.ids.index(rec.stage_id.id) if rec.stage_id.id in stages.ids else -1
            )
            if current_index == -1 or current_index + 1 >= len(stages):
                return False
            assign = rec._current_stage_assign()
            if assign and assign.is_final_stage:
                raise UserError(
                    _(
                        "Este expediente está en una etapa final del flujo. "
                        "No puede avanzar; solo cancelar el expediente si corresponde."
                    )
                )
            if assign and assign.require_notification:
                if not rec._notification_stage_satisfied():
                    if not rec._get_responded_rfq_partners():
                        raise UserError(
                            _(
                                "No hay oferentes con cotización respondida; "
                                "no se puede completar el requisito de notificación para salir de esta etapa."
                            )
                        )
                    raise UserError(
                        _(
                            "Debe notificar a todos los oferentes (correo registrado) antes de pasar de etapa. "
                            "Use el asistente 'Notificar oferentes'."
                        )
                    )
            if current_index == 0 and not (rec.amount_estimated and rec.amount_estimated > 0):
                raise UserError(
                    _(
                        "Debe cargar un monto estimado mayor a cero antes de "
                        "pasar de la primera etapa. Cárguelo manualmente en "
                        "«Total estimado» o detallándolo en las líneas."
                    )
                )
            return stages[current_index + 1]
        return False

    def _apply_next_stage(self, target):
        self.ensure_one()
        self.with_context(skip_validation_check=True).write({"stage_id": target.id})

    def _auto_advance_to_next_stage(self):
        """Avanza a la siguiente etapa tras tier validado (sin exigir can_edit_in_stage)."""
        self.ensure_one()
        target = self._get_next_stage_target(require_can_edit=False)
        if not target:
            return False
        old_stage = self.stage_id
        self._apply_next_stage(target)
        self.message_post(
            body=_(
                "Tras completar la validación de la etapa <b>%s</b>, el expediente "
                "avanzó automáticamente a <b>%s</b>.",
                old_stage.name,
                target.name,
            ),
            subtype_xmlid="mail.mt_note",
        )
        return True

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
            stage_reviews = rec._current_stage_reviews()
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
            stage_reviews = rec._current_stage_reviews()
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
        # Incluir reviews sin stage_id (p. ej. base_tier_validation_forward) en la etapa activa.
        return self.review_ids.filtered(
            lambda r: r.stage_id == self.stage_id
            or (
                not r.stage_id
                and r.status in ("waiting", "pending", "approved", "forwarded")
            )
        )

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
            target = rec._get_next_stage_target(require_can_edit=True)
            if target:
                rec._apply_next_stage(target)
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
            if not self.env.context.get("skip_document_check"):
                rec._check_required_documents_before_leave_stage()
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
            rec.with_context(
                skip_validation_check=True,
                skip_spend_request_check=True,
            ).write({"stage_id": target.id})
        return True
