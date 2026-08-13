import frappe
from frappe.model.document import Document

from samdell_sms.api import notifications

# Base template_name of the approved WhatsApp Templates document used for
# announcements (e.g. a doc named "announcement-en" with template_name
# "announcement"). send_whatsapp resolves this to the actual document name.
ANNOUNCEMENT_TEMPLATE = "announcement"


class SchoolAnnouncement(Document):
	pass


def on_update(doc, method):
	dispatch_announcement(doc)


def dispatch_announcement(doc):
	if not doc.publish_date:
		return

	# Guard against re-sending when the announcement is saved again later.
	if notifications._already_notified(notifications.CATEGORY_ANNOUNCEMENT, doc.doctype, doc.name):
		return

	guardians = _resolve_audience(doc)
	if not guardians:
		return

	notifications._dispatch(
		guardians=guardians,
		category=notifications.CATEGORY_ANNOUNCEMENT,
		whatsapp_template=ANNOUNCEMENT_TEMPLATE,
		whatsapp_params={"title": doc.title},
		sms_message=_build_message(doc),
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		send_sms=bool(doc.send_sms),
		send_whatsapp=bool(doc.send_whatsapp),
	)


def _resolve_audience(doc):
	targets = {row.target for row in doc.audience}
	guardians = set()

	if "All" in targets:
		guardians.update(frappe.get_all("Guardian", pluck="name"))
		return guardians

	if "Specific Class" in targets and doc.audience_class:
		students = frappe.get_all(
			"Student Group Student",
			filters={"parent": doc.audience_class},
			pluck="student",
		)
		for student in students:
			guardians.update(notifications.student_guardians(student))
		targets.discard("Specific Class")

	for target in targets:
		enrollments = frappe.get_all(
			"Program Enrollment",
			filters={"docstatus": 1},
			fields=["student", "program"],
		)
		for e in enrollments:
			student = e.student
			matches = False
			if target == "Students":
				matches = True
			elif target == "Parents":
				matches = _has_guardian(student)
			elif target == "Staff":
				matches = _is_staff_student(student)
			if matches:
				guardians.update(notifications.student_guardians(student))

	return guardians


def _has_guardian(student):
	student_doc = frappe.get_cached_doc("Student", student)
	return bool(student_doc.guardians)


def _is_staff_student(student):
	return False


def _build_message(doc):
	body = frappe.utils.strip_html(doc.body or "")
	return f"{doc.title}: {body}"[:160]
