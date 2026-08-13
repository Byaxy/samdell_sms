import frappe
from frappe.utils import flt


@frappe.whitelist(methods=["POST"])
def evaluate_promotions(academic_year: str):
	policy = frappe.get_single("Promotion Policy")
	if not policy.double_promotion_band_start:
		frappe.throw("Promotion Policy must define Double-Promotion Band Start")

	band_start = policy.double_promotion_band_start
	band_end = policy.double_promotion_band_end
	min_early = flt(policy.minimum_average_early_grades or 90)
	min_current = flt(policy.minimum_average_current_band or 90)

	programs_in_band = _get_programs_in_range(band_start, band_end)
	if not programs_in_band:
		frappe.throw(f"No programs found between {band_start} and {band_end}")

	students = frappe.get_all(
		"Program Enrollment",
		filters={
			"program": ["in", programs_in_band],
			"academic_year": academic_year,
			"docstatus": 1,
		},
		fields=["student", "program", "name"],
	)

	created = 0
	for s in students:
		avg_early = _get_early_grades_average(s.student, policy)
		avg_current = _get_current_year_average(s.student, academic_year)
		eligible = avg_early >= min_early and avg_current >= min_current

		existing = frappe.get_all(
			"Promotion Evaluation",
			filters={"student": s.student, "academic_year": academic_year},
			limit=1,
		)
		if existing:
			pe = frappe.get_doc("Promotion Evaluation", existing[0].name)
		else:
			pe = frappe.get_doc({"doctype": "Promotion Evaluation"})

		pe.update(
			{
				"student": s.student,
				"academic_year": academic_year,
				"current_program": s.program,
				"average_early_grades": flt(avg_early, 1),
				"average_current_band": flt(avg_current, 1),
				"eligible_double_promotion": 1 if eligible else 0,
				"recommendation": "Double Promote" if eligible else "Promote",
			}
		)
		pe.save(ignore_permissions=True)
		created += 1

	return created


@frappe.whitelist(methods=["POST"])
def generate_promotion_statements(academic_year: str):
	"""
	Create one Promotion Statement per enrolled student (ECE through Grade 9).

	Outcome is taken from the Promotion Evaluation recommendation when one
	exists; otherwise derived from the final average (>= 75 -> Promoted,
	else Retained). next_program is computed from the Promotion Policy
	grade_sequence.
	"""
	enrollments = frappe.get_all(
		"Program Enrollment",
		filters={"academic_year": academic_year, "docstatus": 1},
		fields=["student", "program", "name"],
	)

	created = 0
	for e in enrollments:
		final_average = _get_current_year_average(e.student, academic_year)

		evaluation = frappe.get_all(
			"Promotion Evaluation",
			filters={"student": e.student, "academic_year": academic_year},
			limit=1,
		)

		if evaluation:
			pe = frappe.get_doc("Promotion Evaluation", evaluation[0].name)
			outcome = _map_recommendation_to_outcome(pe.recommendation)
		else:
			outcome = "Promoted" if final_average >= 75 else "Retained"

		next_program = _get_next_program(e.program, outcome)

		statement = frappe.get_doc(
			{
				"doctype": "Promotion Statement",
				"student": e.student,
				"academic_year": academic_year,
				"current_program": e.program,
				"final_average": flt(final_average, 1),
				"outcome": outcome,
				"next_program": next_program,
			}
		)
		statement.insert(ignore_permissions=True)
		created += 1

	return created


def _map_recommendation_to_outcome(recommendation):
	mapping = {
		"Double Promote": "Double Promoted",
		"Promote": "Promoted",
		"Repeat": "Retained",
		"Review": "Conditioned",
	}
	return mapping.get(recommendation, "Promoted")


def _get_next_program(current_program, outcome=None):
	policy = frappe.get_single("Promotion Policy")
	sequence = policy.grade_sequence
	names = [row.program for row in sequence if row.program]
	if not names or current_program not in names:
		return None
	idx = names.index(current_program)
	step = 2 if outcome == "Double Promoted" else 1
	if idx + step < len(names):
		return names[idx + step]
	return None


def _get_programs_in_range(start, end):
	programs = frappe.get_all(
		"Program",
		filters={"name": ["between", [start, end]]},
		pluck="name",
		order_by="name",
	)
	return programs


def _get_early_grades_average(student, policy):
	"""Average of a student's results during the early-grade band.

	Only Master Grade Sheets from academic years in which the student was
	enrolled in a program between early_grades_start and early_grades_end
	are considered.
	"""
	start = policy.early_grades_start
	end = policy.early_grades_end
	if not start or not end:
		return 0.0

	early_programs = _get_programs_in_range(start, end)
	if not early_programs:
		return 0.0

	early_years = frappe.get_all(
		"Program Enrollment",
		filters={
			"student": student,
			"program": ["in", early_programs],
			"docstatus": 1,
		},
		pluck="academic_year",
	)
	if not early_years:
		return 0.0

	terms = frappe.get_all(
		"Academic Term",
		filters={"academic_year": ["in", early_years]},
		pluck="name",
	)

	return _average_over_terms(student, terms)


def _get_current_year_average(student, academic_year):
	terms = frappe.get_all(
		"Academic Term",
		filters={"academic_year": academic_year},
		pluck="name",
	)
	return _average_over_terms(student, terms)


def _average_over_terms(student, term_names):
	"""Average a student's overall_average across submitted grade sheets of the given terms."""
	if not term_names:
		return 0.0

	avgs = []
	for term in term_names:
		mgs_list = frappe.get_all(
			"Master Grade Sheet",
			filters={"academic_term": term, "docstatus": 1},
			fields=["name"],
		)
		for mgs_name in mgs_list:
			doc = frappe.get_doc("Master Grade Sheet", mgs_name.name)
			for entry in doc.entries:
				if entry.student == student and entry.overall_average:
					avgs.append(flt(entry.overall_average))

	return (sum(avgs) / len(avgs)) if avgs else 0.0
