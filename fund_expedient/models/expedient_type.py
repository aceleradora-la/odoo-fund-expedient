# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.tools.sql import table_exists
from odoo.exceptions import UserError, ValidationError


class ExpedientTypeStageAssign(models.Model):
    _name = "fund.expedient.type.stage.assign"
    _description = "Asignación por Tipo y Etapa"
    _order = "type_id, sequence, id"
    _rec_name = "display_name"

    type_id = fields.Many2one(
        "fund.expedient.type",
        string="Tipo",
        required=True,
        ondelete="cascade",
    )
    stage_id = fields.Many2one(
        "fund.expedient.stage",
        string="Etapa",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(
        default=10,
        help="Orden de la etapa dentro del tipo de expediente.",
    )
    use_requestor = fields.Boolean(
        string="Solicitante",
        help="Si está activo, la etapa se asigna al Solicitante del expediente (requestor_id). "
        "En ese caso no se usan grupos, puestos ni usuarios.",
    )
    group_ids = fields.Many2many(
        "res.groups",
        "fund_expedient_type_stage_assign_group_rel",
        "assign_id",
        "group_id",
        string="Grupos de usuarios",
        help="Usuarios de estos grupos pueden ser asignados o son responsables en esta etapa.",
    )
    job_ids = fields.Many2many(
        "hr.job",
        "fund_expedient_type_stage_assign_job_rel",
        "assign_id",
        "job_id",
        string="Puestos del organigrama",
        help="Empleados con estos puestos pueden ser asignados o son responsables en esta etapa.",
    )
    user_ids = fields.Many2many(
        "res.users",
        "fund_expedient_type_stage_assign_user_rel",
        "assign_id",
        "user_id",
        string="Usuarios",
        help="Usuarios concretos asignados a esta etapa (además de grupos y puestos).",
    )
    hide_type_id = fields.Boolean(string="Ocultar Tipo")
    allow_edit_type_id = fields.Boolean(
        string="Permitir modificar tipo",
        help="Si está activo, el campo Tipo del expediente puede editarse en esta etapa. "
        "Si está inactivo y el tipo es visible, queda bloqueado.",
    )
    allow_edit_line_amount_final = fields.Boolean(
        string="Permitir editar importe definitivo (líneas)",
        help="Si está activo, se pueden cargar importes definitivos en las líneas del expediente "
        "y el total confirmado manual en esta etapa.",
    )
    hide_encuadre_id = fields.Boolean(string="Ocultar Encuadre")
    hide_estimated_need_date = fields.Boolean(string="Ocultar Fecha estimada")
    hide_recommended_supplier_id = fields.Boolean(string="Ocultar Proveedor recomendado")
    hide_analytic_account_id = fields.Boolean(string="Ocultar Cuenta analítica")
    hide_amount_estimated = fields.Boolean(string="Ocultar Total estimado")
    require_disposition = fields.Boolean(
        string="Requiere disposición",
        help="Si está activo, para esta etapa debe existir al menos una disposición vinculada al expediente.",
    )
    disposition_file_required = fields.Boolean(
        string="Archivo obligatorio en disposición",
        help="Si está activo, la disposición requerida debe tener un archivo subido.",
    )
    default_disposition_notes = fields.Html(
        string="Observaciones por defecto (Disposición)",
        sanitize="email_outgoing",
        help="Texto predeterminado (HTML) que se copiará en Observaciones al crear una Disposición de esta etapa. "
        "Admite campos dinámicos del expediente insertados con el selector del editor (/ Marcador de posición dinámico).",
    )
    require_resolution = fields.Boolean(
        string="Requiere resolución",
        help="Si está activo, para esta etapa debe existir al menos una resolución vinculada al expediente.",
    )
    resolution_file_required = fields.Boolean(
        string="Archivo obligatorio en resolución",
        help="Si está activo, la resolución requerida debe tener un archivo subido.",
    )
    require_technical_spec_document = fields.Boolean(
        string="Especificación técnica obligatoria",
        help=(
            "Si está activo, al salir de esta etapa el expediente debe tener al menos "
            "un documento marcado como Especificación técnica con archivo subido."
        ),
    )
    require_particular_conditions_document = fields.Boolean(
        string="Condiciones particulares obligatorias",
        help=(
            "Si está activo, al salir de esta etapa el expediente debe tener al menos "
            "un documento marcado como Condiciones particulares con archivo subido."
        ),
    )
    default_resolution_notes = fields.Html(
        string="Observaciones por defecto (Resolución)",
        sanitize="email_outgoing",
        help="Texto predeterminado (HTML) que se copiará en Observaciones al crear una Resolución de esta etapa. "
        "Admite campos dinámicos del expediente insertados con el selector del editor (/ Marcador de posición dinámico).",
    )
    is_final_stage = fields.Boolean(
        string="Etapa final del flujo",
        help="Si está activo, no se puede pasar a una etapa posterior salvo cancelar el expediente.",
    )
    require_notification = fields.Boolean(
        string="Requiere notificación a oferentes",
        help="Si está activo, debe enviarse correo a todos los oferentes que respondieron la cotización "
        "antes de poder salir de esta etapa (según registro de envíos).",
    )
    notification_template_id = fields.Many2one(
        "mail.template",
        string="Plantilla de correo (notificación)",
        domain="[('model_id.model', '=', 'fund.expedient')]",
        help="Plantilla usada para notificar; los destinatarios se determinan por las cotizaciones del expediente.",
    )
    notification_mail_server_id = fields.Many2one(
        "ir.mail_server",
        string="Servidor de correo saliente",
        help="Opcional. Si está vacío se usa el servidor por defecto de Odoo.",
    )
    company_id = fields.Many2one(
        related="type_id.company_id",
        store=True,
    )
    dynamic_placeholder_model = fields.Char(
        compute="_compute_dynamic_placeholder_model",
        help="Modelo de referencia para el selector de campos dinámicos (uso interno del widget).",
    )

    def _compute_dynamic_placeholder_model(self):
        for rec in self:
            rec.dynamic_placeholder_model = "fund.expedient"

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "type_stage_uniq",
            "unique(type_id, stage_id)",
            "Ya existe una asignación para este tipo y etapa.",
        )
    ]

    @api.depends("type_id", "stage_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.type_id and rec.stage_id:
                rec.display_name = f"{rec.type_id.name} / {rec.stage_id.name}"
            else:
                rec.display_name = ""

    @api.onchange("use_requestor")
    def _onchange_use_requestor(self):
        if self.use_requestor:
            self.group_ids = [(5, 0, 0)]
            self.job_ids = [(5, 0, 0)]
            self.user_ids = [(5, 0, 0)]

    @api.constrains("use_requestor", "group_ids", "job_ids", "user_ids")
    def _check_requestor_exclusive(self):
        for rec in self:
            if rec.use_requestor and (rec.group_ids or rec.job_ids or rec.user_ids):
                raise ValidationError(
                    "Si marca 'Solicitante', no puede configurar grupos, puestos o usuarios en esa etapa."
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("use_requestor"):
                vals["group_ids"] = [(5, 0, 0)]
                vals["job_ids"] = [(5, 0, 0)]
                vals["user_ids"] = [(5, 0, 0)]
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("use_requestor"):
            vals = dict(vals)
            vals["group_ids"] = [(5, 0, 0)]
            vals["job_ids"] = [(5, 0, 0)]
            vals["user_ids"] = [(5, 0, 0)]
        return super().write(vals)

    @api.constrains(
        "require_notification",
        "notification_template_id",
    )
    def _check_notification_template(self):
        for rec in self:
            if rec.require_notification and not rec.notification_template_id:
                raise ValidationError(
                    "Si marca 'Requiere notificación', debe indicar una plantilla de correo."
                )

    def init(self):
        """Eliminar constraints legacy que impidan reutilizar etapas entre tipos.

        En versiones anteriores pudo existir un UNIQUE(stage_id) en la tabla, lo que
        bloquea usar la misma etapa en tipos distintos. Este modelo ya define el
        constraint correcto: UNIQUE(type_id, stage_id).
        """
        # En upgrades, este init puede correrse antes de que la tabla exista.
        if not table_exists(self.env.cr, "fund_expedient_type_stage_assign"):
            return
        self.env.cr.execute(
            """
            DO $$
            DECLARE
                r record;
            BEGIN
                FOR r IN (
                    SELECT con.conname
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                    WHERE con.contype = 'u'
                      AND nsp.nspname = current_schema()
                      AND rel.relname = 'fund_expedient_type_stage_assign'
                      AND (
                        SELECT array_agg(att.attname::text ORDER BY att.attname)::text[]
                        FROM unnest(con.conkey) AS k(attnum)
                        JOIN pg_attribute att
                          ON att.attrelid = rel.oid
                         AND att.attnum = k.attnum
                      ) = ARRAY['stage_id']::text[]
                ) LOOP
                    EXECUTE format('ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I', 'fund_expedient_type_stage_assign', r.conname);
                END LOOP;
            END $$;
            """
        )


class ExpedientType(models.Model):
    _name = "fund.expedient.type"
    _description = "Tipo de Expediente"
    _order = "sequence, id"

    name = fields.Char(required=True, string="Tipo")
    sequence = fields.Integer(default=10)
    operation_type = fields.Selection(
        [("expense", "Gasto"), ("income", "Ingreso")],
        string="Tipo de operación",
        default="expense",
        required=True,
        help="Gasto: el expediente genera Solicitud de Gasto y consume presupuesto. "
        "Ingreso: genera Solicitud de Ingreso, se vincula a facturas de venta y suma al saldo presupuestario.",
    )
    contract_kind = fields.Selection(
        [
            ("none", "No aplica"),
            ("service_lease", "Locación de Servicios"),
            ("work_lease", "Locación de Obra"),
        ],
        string="Locación",
        default="none",
        required=True,
        help="Si es Locación de Servicios u Obra, las líneas del expediente habilitan Fecha Inicio/Fin "
        "y quedan disponibles los reportes de contratación y proyección mensual.",
    )
    approval_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda (tipo de expediente)",
        required=True,
        default=lambda self: self.env.company.currency_id,
        help="Moneda estándar de Odoo usada para expresar totales del expediente para este tipo. "
        "Las conversiones se realizan usando cotizaciones estándar (Monedas).",
    )
    default_description = fields.Html(
        string="Descripción/Memo por defecto",
        sanitize="email_outgoing",
        help="Texto predeterminado que se copiará al campo Descripción/Memo al crear un expediente de este tipo. "
        "No sobrescribe una descripción ingresada manualmente. "
        "Admite campos dinámicos del expediente insertados con el selector del editor "
        "(/ Marcador de posición dinámico); se completan al crear/cambiar el tipo.",
    )
    dynamic_placeholder_model = fields.Char(
        compute="_compute_dynamic_placeholder_model",
        help="Modelo de referencia para el selector de campos dinámicos (uso interno del widget).",
    )

    def _compute_dynamic_placeholder_model(self):
        for rec in self:
            rec.dynamic_placeholder_model = "fund.expedient"
    stage_assign_ids = fields.One2many(
        "fund.expedient.type.stage.assign",
        "type_id",
        string="Asignaciones por etapa",
    )
    sequence_id = fields.Many2one(
        "ir.sequence",
        string="Secuencia numérica del tipo",
        copy=False,
        help="Numeración independiente para expedientes de este tipo (además del número interno EXP-).",
    )
    encuadre_ids = fields.Many2many(
        "fund.expedient.encuadre",
        "fund_expedient_type_encuadre_rel",
        "type_id",
        "encuadre_id",
        string="Encuadres permitidos",
        help="Lista de encuadres que pueden seleccionarse para este tipo de expediente.",
    )
    unit_mode = fields.Selection(
        [
            ("ur", "Unidad Retributiva (UR)"),
            ("uf", "Unidad Funcional (UF)"),
        ],
        string="Unidad de aprobación",
        default="ur",
        required=True,
        help="Unidad utilizada para los umbrales de aprobación y análisis (UR o UF).",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    def action_create_type_sequence(self):
        """Crea una secuencia dedicada para este tipo (numeración por tipo)."""
        Sequence = self.env["ir.sequence"].sudo()
        for rec in self:
            if rec.sequence_id:
                raise UserError(
                    _("El tipo «%s» ya tiene una secuencia asignada (%s).")
                    % (rec.name, rec.sequence_id.display_name)
                )
            prefix = "".join(c for c in (rec.name or "TIPO")[:12].upper() if c.isalnum()) or "TIPO"
            seq = Sequence.create(
                {
                    "name": _("Numeración expedientes - %s") % rec.name,
                    "code": "fund.expedient.type.%s" % rec.id,
                    "prefix": "%s-" % prefix,
                    "padding": 4,
                    "implementation": "no_gap",
                    "company_id": rec.company_id.id or False,
                }
            )
            rec.sequence_id = seq.id
        return True
