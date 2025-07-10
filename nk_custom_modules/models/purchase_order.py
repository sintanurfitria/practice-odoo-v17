import logging

from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    purchase_type = fields.Selection(
        [("material", "Materi"), ("service", "Service")],
        index=True,
    )
    purchase_order_supporting_document_line_ids = fields.One2many(
        "purchase.order.supporting.document",
        "order_id",
        string="Purchase ORder SUpporting DOcument Line",
    )

    def _prepare_supporting_document_vals(
        self, supporting_document_vals, filtered_document_requirement
    ):
        if not filtered_document_requirement:
            return supporting_document_vals

        supporting_document_vals += [
            Command.create(
                {
                    "order_id": self.id,
                    "po_attachment_requirement_id": document_requirement.id,
                }
            )
            for document_requirement in filtered_document_requirement
        ]
        return supporting_document_vals

    @api.onchange("purchase_type")
    def _onchange_purchase_type(self):
        document_requirement_ids = self.env[
            "purchase.order.attachment.requirement"
        ].search([])
        for rec in self:
            supporting_document_vals = [Command.clear()]
            if not rec.purchase_type:
                filtered_document_requirement = document_requirement_ids.filtered(
                    lambda x: x.document_type == "3_both"
                )
                supporting_document_vals = rec._prepare_supporting_document_vals(
                    supporting_document_vals, filtered_document_requirement
                )
                rec.purchase_order_supporting_document_line_ids = (
                    supporting_document_vals
                )
            elif rec.purchase_type == "material":
                filtered_document_requirement = document_requirement_ids.filtered(
                    lambda x: x.document_type in ("3_both", "1_material_purpose")
                )
                supporting_document_vals = rec._prepare_supporting_document_vals(
                    supporting_document_vals, filtered_document_requirement
                )
                rec.purchase_order_supporting_document_line_ids = (
                    supporting_document_vals
                )
            else:
                filtered_document_requirement = document_requirement_ids.filtered(
                    lambda x: x.document_type in ("3_both", "2_service_purpose")
                )
                supporting_document_vals = rec._prepare_supporting_document_vals(
                    supporting_document_vals, filtered_document_requirement
                )
                rec.purchase_order_supporting_document_line_ids = (
                    supporting_document_vals
                )

    def action_check_grouped_result(self):
        grouped_product_by_product_type = False
        if self.order_line:
            grouped_product_by_product_type = self.order_line.grouped(
                lambda x: x.product_id.detailed_type
            )
        _logger.info(f"Result : {grouped_product_by_product_type}")
        return True


class PurchaseOrderSupportingDocument(models.Model):
    _name = "purchase.order.supporting.document"
    _description = "Purchase Order Supporting Document"
    _inherit = ["mail.thread.main.attachment", "mail.activity.mixin"]

    name = fields.Char(compute="_compute_name", store=True, index="trigram")
    order_id = fields.Many2one(
        "purchase.order", string="Order ID", index=True, copy=False, ondelete="cascade"
    )
    po_attachment_requirement_id = fields.Many2one(
        "purchase.order.attachment.requirement",
        string="PO Attachment Requirement",
        index=True,
        copy=False,
    )

    nb_attachment = fields.Integer(
        string="Number of Attachments", compute="_compute_nb_attachment"
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "po_support_document_ir_attachments_rel",
        "po_support_document_id",
        "attachment_id",
        string="Attachments",
    )

    def attach_document(self, **kwargs):
        """When an attachment is uploaded as a receipt,
        set it as the main attachment."""
        self.message_main_attachment_id = kwargs["attachment_ids"][-1]

    @api.depends("attachment_ids")
    def _compute_nb_attachment(self):
        for rec in self:
            rec.nb_attachment = len(rec.attachment_ids)

    @api.depends("order_id", "po_attachment_requirement_id")
    @api.depends_context("company")
    def _compute_name(self):
        for rec in self:
            if not rec.po_attachment_requirement_id:
                rec.name = "-"
                continue

            rec.name = f"{rec.order_id.name} - {rec.po_attachment_requirement_id.name}"
