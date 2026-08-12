import frappe
from frappe.model.document import Document

# Base template_name of the approved WhatsApp Templates document used for
# announcements (e.g. a doc named "announcement-en" with template_name
# "announcement"). send_whatsapp resolves this to the actual document name.
ANNOUNCEMENT_TEMPLATE = "announcement"


class SchoolAnnouncement(Document):
	pass


def on_update(doc, method):
	dispatch_announcement(doc)


def dispatch_announcement(doc):
	if not doc.publish_date or doc.flags.sms_sent:
		return

	from samdell_sms.api.sms import send_sms
	from samdell_sms.api.whatsapp import send_whatsapp

	guardians = _resolve_audience(doc)
	if not guardians:
		doc.flags.sms_sent = True
		return

	message = _build_message(doc)
	for guardian in guardians:
		if doc.send_sms:
			send_sms(guardian, message, "Announcement", "School Announcement", doc.name)
		if doc.send_whatsapp:
			send_whatsapp(guardian, ANNOUNCEMENT_TEMPLATE, {"title": doc.title}, "Announcement", "School Announcement", doc.name)

	doc.flags.sms_sent = True


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
			guardians.update(_student_guardians(student))
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
				guardians.update(_student_guardians(student))

	return guardians


def _student_guardians(student):
	return frappe.get_all(
		"Student Guardian",
		filters={"parent": student},
		pluck="guardian",
	)


def _has_guardian(student):
	student_doc = frappe.get_cached_doc("Student", student)
	return bool(student_doc.guardians)


def _is_staff_student(student):
	return False


def _build_message(doc):
	body = frappe.utils.strip_html(doc.body or "")
	return f"{doc.title}: {body}"[:160]
