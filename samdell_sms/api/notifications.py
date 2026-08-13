import frappe
from frappe.utils import flt, fmt_money, format_date

# SMS Alert Log-category names. Keep in sync with the Category select options
# on the SMS Alert Log doctype.
CATEGORY_ANNOUNCEMENT = "Announcement"
CATEGORY_FEE_DUE = "Fee Due"
CATEGORY_FEE_PAID = "Fee Paid"
CATEGORY_GRADE_RELEASE = "Grade Release"

# template_name of the approved WhatsApp Templates documents used for each
# category. send_whatsapp resolves these to the actual document name.
FEE_DUE_TEMPLATE = "fee_due"
FEE_PAID_TEMPLATE = "fee_paid"
GRADE_RELEASE_TEMPLATE = "grade_release"

SCHOOL_NAME = "John B. Sondah Memorial Christian School, Inc."


def _dispatch(
	guardians,
	category,
	whatsapp_template,
	whatsapp_params,
	sms_message,
	reference_doctype,
	reference_name,
	send_sms=True,
	send_whatsapp=True,
):
	"""Send one SMS + WhatsApp notification to each unique guardian.

	Guardians are deduplicated here so a parent with multiple students is
	never sent the same notification more than once for a single event.
	Channels that are not configured are skipped by the send wrappers.
	"""
	from samdell_sms.api.sms import send_sms as _send_sms
	from samdell_sms.api.whatsapp import send_whatsapp as _send_whatsapp

	for guardian in sorted(set(guardians or [])):
		if send_sms:
			_send_sms(guardian, sms_message, category, reference_doctype, reference_name)
		if send_whatsapp:
			_send_whatsapp(
				guardian, whatsapp_template, whatsapp_params, category, reference_doctype, reference_name
			)


def student_guardians(student):
	"""Unique guardians of a student."""
	return set(frappe.get_all("Student Guardian", filters={"parent": student}, pluck="guardian"))


def _already_notified(category, reference_doctype, reference_name):
	return frappe.db.exists(
		"SMS Alert Log",
		{
			"category": category,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		},
	)


def _fmt_money(amount, currency=None):
	if currency:
		return fmt_money(amount, currency=currency)
	return fmt_money(amount)


def notify_fee_due(doc, method=None):
	"""Notify a student's guardians when a Fees document is submitted."""
	if _already_notified(CATEGORY_FEE_DUE, doc.doctype, doc.name):
		return

	guardians = student_guardians(doc.student)
	if not guardians:
		return

	amount = _fmt_money(doc.grand_total, doc.currency)
	due_date = format_date(doc.due_date) if doc.due_date else ""
	student_name = doc.student_name or doc.student

	_dispatch(
		guardians=guardians,
		category=CATEGORY_FEE_DUE,
		whatsapp_template=FEE_DUE_TEMPLATE,
		whatsapp_params={"amount": amount, "student_name": student_name, "due_date": due_date},
		sms_message=(
			f"Dear Parent, a fee of {amount} for {student_name} is due on {due_date}. - {SCHOOL_NAME}"
		),
		reference_doctype=doc.doctype,
		reference_name=doc.name,
	)


def grade_release_on_update(doc, method=None):
	"""Notify guardians with results when a Master Grade Sheet is Released."""
	if doc.workflow_state != "Released":
		return
	if _already_notified(CATEGORY_GRADE_RELEASE, doc.doctype, doc.name):
		return

	academic_term = doc.academic_term or ""
	class_size = len(doc.entries)
	notified_guardians = set()

	for entry in doc.entries:
		guardians = student_guardians(entry.student) - notified_guardians
		if not guardians:
			continue
		notified_guardians.update(guardians)

		student_name = frappe.db.get_value("Student", entry.student, "student_name") or entry.student
		average = flt(entry.overall_average, 1)

		_dispatch(
			guardians=guardians,
			category=CATEGORY_GRADE_RELEASE,
			whatsapp_template=GRADE_RELEASE_TEMPLATE,
			whatsapp_params={
				"student_name": student_name,
				"academic_term": academic_term,
				"average": average,
				"rating": entry.overall_rating,
				"rank": entry.class_rank,
				"class_size": class_size,
			},
			sms_message=(
				f"Dear Parent, {student_name}'s results for {academic_term} are available: "
				f"Average {average}%, Rating {entry.overall_rating}, Rank {entry.class_rank} "
				f"of {class_size}. - {SCHOOL_NAME}"
			),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)


def fee_paid_sweep():
	"""Notify guardians once a Fees document is fully paid.

	Runs as a scheduled job because payment does not re-save the Fees
	document, so no document event reliably captures the paid state.
	Each paid fee is notified independently (one receipt per invoice);
	per-fee logs make re-runs idempotent.
	"""
	paid_fees = frappe.get_all(
		"Fees",
		filters={
			"docstatus": 1,
			"grand_total": (">", 0),
			"outstanding_amount": ("<=", 0),
		},
		fields=["name", "student", "student_name", "grand_total", "currency"],
	)

	for fee in paid_fees:
		if _already_notified(CATEGORY_FEE_PAID, "Fees", fee.name):
			continue

		guardians = student_guardians(fee.student)
		if not guardians:
			continue

		amount = _fmt_money(fee.grand_total, fee.currency)
		student_name = fee.student_name or fee.student

		_dispatch(
			guardians=guardians,
			category=CATEGORY_FEE_PAID,
			whatsapp_template=FEE_PAID_TEMPLATE,
			whatsapp_params={"amount": amount, "student_name": student_name},
			sms_message=(
				f"Dear Parent, thank you. Payment of {amount} received for {student_name}. - {SCHOOL_NAME}"
			),
			reference_doctype="Fees",
			reference_name=fee.name,
		)
