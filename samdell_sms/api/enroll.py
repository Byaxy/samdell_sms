import frappe
from frappe.utils import today

LEVEL_ORDER = [
	"Early Childhood",
	"Elementary",
	"Junior High School",
	"Senior High School",
]


@frappe.whitelist(methods=["POST"])
def reenroll_next_level(promotion_statement_name: str):
	"""Build the next-level Program Enrollment for a Graduated student.

	Only meaningful for a Promotion Statement whose outcome is
	``Graduated`` (end of level: Kindergarten, Grade 6, Grade 9, Grade 12).
	Resolves the student's graduating grade, the next ministry level and its
	first School Grade, the next Academic Year, and the matching Student
	Batch Name, then returns a prefill payload for a new Program Enrollment.

	Nothing is saved server-side: the registrar reviews and submits the
	prefilled form themselves.
	"""
	statement = frappe.get_doc("Promotion Statement", promotion_statement_name)
	if statement.outcome != "Graduated":
		frappe.throw(
			frappe._("Re-enrollment into the next level is only available for a Graduated statement.")
		)

	current_grade = statement.current_program
	if not current_grade:
		frappe.throw(frappe._("Promotion Statement has no Current Grade set."))

	current_level = frappe.db.get_value("School Grade", current_grade, "level")
	next_level = _next_level(current_level)
	if not next_level:
		frappe.throw(
			frappe._(
				"{} is the final ministry level. This student has completed school "
				"and cannot re-enroll into a next level."
			).format(current_level)
		)

	first_grade = _first_grade_of_level(next_level)
	if not first_grade:
		frappe.throw(frappe._("No School Grade found for level '{}'.").format(next_level))

	next_year = _next_academic_year(statement.academic_year)
	if not next_year:
		frappe.throw(
			frappe._(
				"No academic year follows {}. Please create it first "
				"(e.g. Academic Year 2027-2028), then retry."
			).format(statement.academic_year)
		)

	batch_name = _get_or_create_batch(first_grade, next_year)

	student_name = frappe.db.get_value("Student", statement.student, "student_name") or statement.student

	return {
		"doctype": "Program Enrollment",
		"student": statement.student,
		"academic_year": next_year,
		"program": next_level,
		"student_batch_name": batch_name,
		"enrollment_date": today(),
		"student_name": student_name,
	}


def _next_level(level):
	if level not in LEVEL_ORDER:
		return None
	idx = LEVEL_ORDER.index(level)
	if idx + 1 >= len(LEVEL_ORDER):
		return None
	return LEVEL_ORDER[idx + 1]


def _first_grade_of_level(level):
	return frappe.db.get_value(
		"School Grade",
		{"level": level},
		"name",
		order_by="sort_order asc",
	)


def _next_academic_year(current_year_name):
	current = (
		frappe.get_doc("Academic Year", current_year_name)
		if frappe.db.exists("Academic Year", current_year_name)
		else None
	)
	end_date = current.year_end_date if current else None

	filters = {}
	if end_date:
		filters = {"year_start_date": [">", end_date]}
	next_year = frappe.get_all(
		"Academic Year",
		filters=filters,
		fields=["name", "year_start_date"],
		order_by="year_start_date asc",
		limit=1,
	)
	if next_year:
		return next_year[0]["name"]

	if current_year_name and "-" in current_year_name:
		try:
			start = int(current_year_name.split("-")[0].strip())
		except ValueError:
			return None
		fallback = f"{start + 1}-{start + 2}"
		if frappe.db.exists("Academic Year", fallback):
			return fallback

	return None


def _get_or_create_batch(grade, academic_year):
	name = f"{grade} - {academic_year}"
	if not frappe.db.exists("Student Batch Name", name):
		frappe.get_doc(
			{
				"doctype": "Student Batch Name",
				"batch_name": name,
				"school_grade": grade,
			}
		).insert(ignore_permissions=True)
	return name
