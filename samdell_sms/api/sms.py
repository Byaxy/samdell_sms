import frappe
from frappe.core.doctype.sms_settings.sms_settings import send_sms as frappe_send_sms


def send_sms(
	guardian,
	message,
	category,
	reference_doctype=None,
	reference_name=None,
):
	"""
	Send SMS via Frappe's native SMS Settings.

	Called internally by other features. Enqueued asynchronously,
	falls back to synchronous execution if no worker is available.
	"""
	if not frappe.db.get_single_value("SMS Settings", "sms_gateway_url"):
		frappe.log_error("SMS not sent — SMS Settings has no gateway URL", "SMS")
		return

	recipient_number = _resolve_guardian_phone(guardian)
	if not recipient_number:
		frappe.log_error(f"No phone number for Guardian {guardian}", "SMS")
		return

	log = frappe.get_doc({
		"doctype": "SMS Alert Log",
		"recipient_guardian": guardian,
		"recipient_number": recipient_number,
		"channel": "SMS",
		"category": category,
		"message": message,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"status": "Queued",
	})
	log.insert(ignore_permissions=True)

	frappe.enqueue(
		"samdell_sms.api.sms._send_sms_now",
		queue="short",
		timeout=60,
		now=True,
		recipient_number=recipient_number,
		message=message,
		log_name=log.name,
	)


def _send_sms_now(recipient_number, message, log_name):
	try:
		frappe_send_sms(recipients=[recipient_number], msg=message)
		frappe.db.set_value("SMS Alert Log", log_name, "status", "Sent")
		frappe.db.set_value("SMS Alert Log", log_name, "sent_at", frappe.utils.now_datetime())
	except Exception as e:
		frappe.db.set_value("SMS Alert Log", log_name, "status", "Failed")
		frappe.db.set_value("SMS Alert Log", log_name, "provider_response", str(e))
		frappe.log_error(f"SMS send failed: {e}", "SMS")


def _resolve_guardian_phone(guardian):
	if isinstance(guardian, str):
		guardian_doc = frappe.get_cached_doc("Guardian", guardian)
	else:
		guardian_doc = guardian
	mobile = guardian_doc.get("mobile_number") or guardian_doc.get("cell_number") or ""
	return mobile.strip()
