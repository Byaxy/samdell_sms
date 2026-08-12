import json

import frappe


def send_whatsapp(
	guardian,
	template,
	params,
	category,
	reference_doctype=None,
	reference_name=None,
):
	"""
	Send WhatsApp via frappe_whatsapp app.

	Falls back silently if frappe_whatsapp is not installed or not configured.
	"""
	if not frappe.db.exists("DocType", "WhatsApp Message"):
		frappe.log_error("frappe_whatsapp not installed, WhatsApp not sent", "WhatsApp")
		return

	recipient_number = _resolve_guardian_phone(guardian)
	if not recipient_number:
		frappe.log_error(f"No phone number for Guardian {guardian}", "WhatsApp")
		return

	log = frappe.get_doc({
		"doctype": "SMS Alert Log",
		"recipient_guardian": guardian,
		"recipient_number": recipient_number,
		"channel": "WhatsApp",
		"category": category,
		"message": _build_whatsapp_message(template, params),
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"status": "Queued",
	})
	log.insert(ignore_permissions=True)

	frappe.enqueue(
		"samdell_sms.api.whatsapp._send_whatsapp_now",
		queue="short",
		timeout=60,
		now=True,
		recipient_number=recipient_number,
		template=template,
		params=params,
		log_name=log.name,
	)


def _send_whatsapp_now(recipient_number, template, params, log_name):
	"""Send a template message via the frappe_whatsapp WhatsApp Message doctype."""
	try:
		template_doc = _resolve_whatsapp_template(template)
		if not template_doc:
			frappe.throw(f"No WhatsApp template found for '{template}'")

		frappe.get_doc({
			"doctype": "WhatsApp Message",
			"to": recipient_number,
			"type": "Outgoing",
			"template": template_doc,
			"body_param": _normalize_params(params),
		}).insert(ignore_permissions=True)
		frappe.db.set_value("SMS Alert Log", log_name, "status", "Sent")
		frappe.db.set_value("SMS Alert Log", log_name, "sent_at", frappe.utils.now_datetime())
	except Exception as e:
		frappe.db.set_value("SMS Alert Log", log_name, "status", "Failed")
		frappe.db.set_value("SMS Alert Log", log_name, "provider_response", str(e))
		frappe.log_error(f"WhatsApp send failed: {e}", "WhatsApp")


def _resolve_whatsapp_template(template):
	"""Resolve the WhatsApp Templates doc for a template identifier.

	Accepts either the WhatsApp Templates document name (e.g. "announcement-en")
	or the base template_name (e.g. "announcement"). Returns None when no
	matching WhatsApp Templates document exists.
	"""
	if not template:
		return None

	if frappe.db.exists("WhatsApp Templates", template):
		return template

	return frappe.db.get_value("WhatsApp Templates", {"template_name": template}, "name")


def _normalize_params(params):
	"""Return a JSON dict of ordered template parameters.

	WhatsApp Message.send_template() reads body_param as a JSON object and
	uses its values in insertion order as the template body parameters.
	"""
	if params is None:
		params = {}
	if isinstance(params, str):
		params = json.loads(params)
	if isinstance(params, list):
		params = {str(index + 1): value for index, value in enumerate(params)}
	return json.dumps(params)


def _resolve_guardian_phone(guardian):
	from .sms import _resolve_guardian_phone as resolve
	return resolve(guardian)


def _build_whatsapp_message(template, params):
	return f"Template: {template} | Params: {params}"
