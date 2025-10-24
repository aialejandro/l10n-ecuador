# -*- coding: utf-8 -*-
"""Utility helpers to retrieve authorized documents from the SRI web service."""

import logging
from datetime import datetime

from zeep.helpers import serialize_object

from odoo import _, models

_logger = logging.getLogger(__name__)


class L10nEcEdiImportSRIClient(models.AbstractModel):
    _name = "l10n.ec.edi.import.sri.client"
    _description = "SRI Authorization Client"

    def fetch_document(self, company, access_key):
        """Return the authorized XML associated with an access key.

        Parameters
        ----------
        company: res.company
            Company whose environment determines which SRI endpoint is used.
        access_key: str
            49 digit access key identifying the document.

        Returns
        -------
        dict
            Dictionary containing `xml`, `authorization`, `authorization_date`,
            and optional `message` keys.
        """

        if not access_key:
            return {"xml": None, "message": "Missing access key"}

        environment = company.l10n_ec_type_environment or "test"
        environment = "production" #REMOVE THIS LINE ON PRODUCTION
        edi_format = self.env["account.edi.format"].sudo()
        client = edi_format._l10n_ec_get_edi_ws_client(environment, "authorization")
        if client is None:
            return {
                "xml": None,
                "message": _(
                    "Unable to contact SRI authorization endpoint for environment %s",
                    environment,
                ),
            }
        try:
            response = client.service.autorizacionComprobante(
                claveAccesoComprobante=access_key
            )
        except Exception as err:  # noqa: BLE001 - network failure needs logging
            _logger.warning("SRI authorization request failed: %s", err)
            return {"xml": None, "message": str(err)}

        payload = serialize_object(response, dict) if response else {}
        autorizaciones = (payload.get("autorizaciones") or {}).get("autorizacion")
        if not autorizaciones:
            return {
                "xml": None,
                "message": _(
                    "Authorization response for %s did not contain any document.",
                    access_key,
                ),
            }
        if not isinstance(autorizaciones, list):
            autorizaciones = [autorizaciones]

        for autorizacion in autorizaciones:
            estado = autorizacion.get("estado")
            if estado != "AUTORIZADO":
                continue
            xml_payload = autorizacion.get("comprobante") or ""
            numero_autorizacion = autorizacion.get("numeroAutorizacion")
            fecha_autorizacion = autorizacion.get("fechaAutorizacion")
            if isinstance(fecha_autorizacion, datetime):
                authorization_date = fecha_autorizacion
            else:
                authorization_date = self._parse_date(fecha_autorizacion)
            return {
                "xml": xml_payload,
                "authorization": numero_autorizacion,
                "authorization_date": authorization_date,
            }

        messages = []
        for autorizacion in autorizaciones:
            detalle = autorizacion.get("mensajes") or {}
            mensaje = detalle.get("mensaje")
            if not mensaje:
                continue
            if isinstance(mensaje, list):
                messages.extend(msg.get("mensaje") for msg in mensaje if msg.get("mensaje"))
            else:
                messages.append(mensaje.get("mensaje"))
        joined = "; ".join(filter(None, messages))
        return {
            "xml": None,
            "message": joined or _("SRI returned the document in a non-authorized state"),
        }

    def _parse_date(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except (TypeError, ValueError):
                continue
        return None
