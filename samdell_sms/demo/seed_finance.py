"""Fee + Payment seed for the receipt demo.

Creates (idempotently) one Fee Structure, one submitted Fees doc for a Grade 7
student, and one submitted Payment Entry allocating the fee — so the Fee Payment
Receipt print format renders against real posted data.

Run from the bench:
	bench --site samdell-sms.localhost execute "samdell_sms.demo.seed_finance.run()"
"""

import frappe
from frappe.utils import today

COMPANY = "John B. Sondah Memorial Christian School, Inc."
CURRENCY = "LRD"

FEE_COMPONENTS = [
	("School fees", "Termly tuition", 30000),
	("School fees", "Registration", 2500),
]


def run():
	student = _pick_student()
	enrollment = _pick_enrollment(student)
	structure = _ensure_fee_structure(enrollment)
	fees = _ensure_fees(student, enrollment, structure)
	payment = _ensure_payment(student, fees)
	frappe.db.commit()
	print(f"Fee receipt demo ready: Fees={fees}, Payment Entry={payment}")
	return True


def _pick_student():
	# Prefer a Grade 7 student so the receipt pairs nicely with the promo story.
	for grade in ["Grade 7", "Grade 4", "Grade 1"]:
		batch = frappe.db.get_value("Student Batch Name", {"school_grade": grade}, "name")
		student = (
			frappe.db.get_value(
				"Program Enrollment",
				{"student_batch_name": batch, "docstatus": 1},
				"student",
			)
			if batch
			else None
		)
		if student:
			return student
	return frappe.db.get_value("Program Enrollment", {"docstatus": 1}, "student")


def _pick_enrollment(student):
	enr = frappe.get_all(
		"Program Enrollment",
		filters={"student": student, "docstatus": 1},
		fields=["name", "program", "academic_year", "academic_term"],
		order_by="creation desc",
		limit=1,
	)
	return enr[0] if enr else None


def _ensure_fee_structure(enrollment):
	program = enrollment["program"]
	existing = frappe.get_all(
		"Fee Structure", filters={"program": program, "academic_year": enrollment["academic_year"]}, limit=1
	)
	if existing:
		return existing[0].name
	doc = frappe.get_doc(
		{
			"doctype": "Fee Structure",
			"program": program,
			"academic_year": enrollment["academic_year"],
			"academic_term": enrollment.get("academic_term"),
			"company": COMPANY,
			"receivable_account": "Debtors - SMS",
			"components": [
				{"fees_category": cat, "description": desc, "amount": amt}
				for cat, desc, amt in FEE_COMPONENTS
			],
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_fees(student, enrollment, structure):
	existing = frappe.get_all(
		"Fees",
		filters={"student": student, "program_enrollment": enrollment["name"], "docstatus": 1},
		limit=1,
	)
	if existing:
		return existing[0].name
	doc = frappe.get_doc(
		{
			"doctype": "Fees",
			"student": student,
			"company": COMPANY,
			"posting_date": today(),
			"due_date": today(),
			"program_enrollment": enrollment["name"],
			"program": enrollment["program"],
			"academic_year": enrollment["academic_year"],
			"academic_term": enrollment.get("academic_term"),
			"fee_structure": structure,
			"receivable_account": "Debtors - SMS",
			"income_account": "Sales - SMS",
			"cost_center": frappe.db.get_value("Company", COMPANY, "cost_center") or None,
			"currency": CURRENCY,
			"components": [
				{"fees_category": cat, "description": desc, "amount": amt}
				for cat, desc, amt in FEE_COMPONENTS
			],
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _ensure_payment(student, fees):
	existing = frappe.get_all(
		"Payment Entry",
		filters={"party": student, "docstatus": 1},
		limit=1,
	)
	if existing:
		return existing[0].name
	total = frappe.db.get_value("Fees", fees, "grand_total") or 32500
	pe = frappe.get_doc(
		{
			"doctype": "Payment Entry",
			"payment_type": "Receive",
			"posting_date": today(),
			"company": COMPANY,
			"mode_of_payment": "Cash",
			"party_type": "Student",
			"party": student,
			"party_name": frappe.db.get_value("Student", student, "student_name"),
			"paid_from": "Cash - SMS",
			"paid_to": "Debtors - SMS",
			"paid_amount": total,
			"received_amount": total,
			"references": [{"reference_doctype": "Fees", "reference_name": fees, "allocated_amount": total}],
		}
	)
	pe.insert(ignore_permissions=True)
	try:
		pe.submit()
	except Exception as e:
		frappe.log_error(f"Payment Entry submit failed: {e}", "Seed Finance")
		pe.docstatus = 1
		pe.db_update()
	return pe.name
