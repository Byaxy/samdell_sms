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

	grades_in_band = _get_grades_in_range(band_start, band_end)
	if not grades_in_band:
		frappe.throw(f"No School Grades found between {band_start} and {band_end}")

	students = _students_in_grades(academic_year, grades_in_band)

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
				"current_program": s.school_grade,
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
	Create one Promotion Statement per enrolled student.

	Outcome is taken from the Promotion Evaluation recommendation when one
	exists; otherwise derived from the final average (>= 75 -> Promoted,
	else Retained). next_program resolves within the student's current level
	only; a student in the last grade of a level (or at the end of school)
	receives outcome "Graduated" with no next grade.
	"""
	enrollments = frappe.get_all(
		"Program Enrollment",
		filters={"academic_year": academic_year, "docstatus": 1},
		fields=["student", "student_batch_name"],
	)

	created = 0
	for e in enrollments:
		current_grade = _grade_of_batch(e.student_batch_name)
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

		next_grade = _get_next_grade(current_grade, outcome)
		if outcome in ("Promoted", "Double Promoted") and next_grade:
			single = _get_next_grade(current_grade, "Promoted")
			if outcome == "Double Promoted" and next_grade == single:
				outcome = "Promoted"
		elif outcome in ("Promoted", "Double Promoted") and current_grade and not next_grade:
			outcome = "Graduated"

		statement = frappe.get_doc(
			{
				"doctype": "Promotion Statement",
				"student": e.student,
				"academic_year": academic_year,
				"current_program": current_grade,
				"final_average": flt(final_average, 1),
				"outcome": outcome,
				"next_program": next_grade,
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


def _get_next_grade(current_grade, outcome=None):
	"""Next School Grade for a student, stepping only within their current level.

	Double promotion skips one grade; if the second step would leave the
	level, it is capped at the level's last grade. Returns None when the
	student is already in the last grade of their level.
	"""
	if not current_grade:
		return None

	policy = frappe.get_single("Promotion Policy")
	ordered = [
		row.school_grade
		for row in sorted(policy.grade_sequence, key=lambda r: r.sequence_no)
		if row.school_grade
	]
	if current_grade not in ordered:
		return None

	level = frappe.db.get_value("School Grade", current_grade, "level")
	level_grades = [g for g in ordered if frappe.db.get_value("School Grade", g, "level") == level]
	if current_grade not in level_grades:
		return None

	idx = level_grades.index(current_grade)
	step = 2 if outcome == "Double Promoted" else 1
	if idx + step < len(level_grades):
		return level_grades[idx + step]
	if step == 2 and idx + 1 < len(level_grades):
		return level_grades[idx + 1]
	return None


def _get_grades_in_range(start, end):
	if not start or not end:
		return []
	start_order = frappe.db.get_value("School Grade", start, "sort_order")
	end_order = frappe.db.get_value("School Grade", end, "sort_order")
	if start_order is None or end_order is None:
		return []
	return frappe.get_all(
		"School Grade",
		filters={"sort_order": ["between", [start_order, end_order]]},
		pluck="name",
		order_by="sort_order",
	)


def _students_in_grades(academic_year, grades):
	batches = frappe.get_all(
		"Student Batch Name",
		filters={"school_grade": ["in", grades]},
		fields=["name", "school_grade"],
	)
	if not batches:
		return []

	grade_by_batch = {b.name: b.school_grade for b in batches}
	enrollments = frappe.get_all(
		"Program Enrollment",
		filters={
			"student_batch_name": ["in", list(grade_by_batch)],
			"academic_year": academic_year,
			"docstatus": 1,
		},
		fields=["student", "student_batch_name"],
	)
	return [
		frappe._dict({"student": e.student, "school_grade": grade_by_batch.get(e.student_batch_name)})
		for e in enrollments
	]


def _grade_of_batch(student_batch_name):
	if not student_batch_name:
		return None
	return frappe.db.get_value("Student Batch Name", student_batch_name, "school_grade")


def _get_early_grades_average(student, policy):
	"""Average of a student's results during the early-grade band.

	Only Master Grade Sheets from academic years in which the student was
	enrolled in a batch whose School Grade is between early_grades_start and
	early_grades_end are considered.
	"""
	start = policy.early_grades_start
	end = policy.early_grades_end
	if not start or not end:
		return 0.0

	early_grades = _get_grades_in_range(start, end)
	if not early_grades:
		return 0.0

	early_batches = frappe.get_all(
		"Student Batch Name",
		filters={"school_grade": ["in", early_grades]},
		pluck="name",
	)
	if not early_batches:
		return 0.0

	early_years = frappe.get_all(
		"Program Enrollment",
		filters={
			"student": student,
			"student_batch_name": ["in", early_batches],
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
