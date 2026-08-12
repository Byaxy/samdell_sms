import frappe
from frappe.utils import today


def auto_create_id_card(doc, method):
	"""Auto-create a Student ID Card when a Program Enrollment is submitted (if none active)."""
	if frappe.db.exists(
		"Student ID Card",
		{"student": doc.student, "status": "Active"},
	):
		return

	card = frappe.get_doc({
		"doctype": "Student ID Card",
		"student": doc.student,
		"issued_date": today(),
	})
	card.insert(ignore_permissions=True)
	frappe.db.set_value("Student ID Card", card.name, "status", "Active")


@frappe.whitelist()
def reissue_card(id_card_name):
	"""
	Mark the existing Student ID Card as Lost and create a new one
	for the same student with the next card number.
	"""
	old_card = frappe.get_doc("Student ID Card", id_card_name)
	if old_card.status == "Lost":
		frappe.throw(f"Student ID Card {old_card.name} is already marked as Lost")

	frappe.db.set_value("Student ID Card", old_card.name, "status", "Lost")
	frappe.db.set_value("Student ID Card", old_card.name, "expiry_date", today())

	new_card = frappe.get_doc({
		"doctype": "Student ID Card",
		"student": old_card.student,
		"issued_date": today(),
	})
	new_card.insert(ignore_permissions=True)

	frappe.db.set_value("Student ID Card", new_card.name, "status", "Active")

	return {
		"old_card": old_card.name,
		"new_card": new_card.name,
		"card_number": new_card.card_number,
	}
