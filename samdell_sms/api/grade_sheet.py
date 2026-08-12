import frappe
from frappe.utils import flt


@frappe.whitelist(methods=["POST"])
def pull_results(master_grade_sheet_name: str):
	mgs = frappe.get_doc("Master Grade Sheet", master_grade_sheet_name)
	student_group = mgs.student_group
	academic_term = mgs.academic_term

	students = frappe.get_all(
		"Student Group Student",
		filters={"parent": student_group},
		fields=["student", "student_name"],
		order_by="idx",
	)

	assessment_plans = frappe.get_all(
		"Assessment Plan",
		filters={
			"student_group": student_group,
			"academic_term": academic_term,
		},
		fields=["name", "assessment_group"],
	)

	period_plans = []
	exam_plans = []
	for plan in assessment_plans:
		group_name = frappe.db.get_value("Assessment Group", plan.assessment_group, "assessment_group_name") if plan.assessment_group else ""
		group_name = (group_name or "").lower()
		if "exam" in group_name:
			exam_plans.append(plan.name)
		else:
			period_plans.append(plan.name)

	grading_scale_name = _get_grading_scale_name()

	entries = []
	for s in students:
		period_scores = _get_student_averages(s.student, period_plans)
		exam_scores = _get_student_averages(s.student, exam_plans)

		if not period_scores and not exam_scores:
			continue

		avg_periods = sum(period_scores) / len(period_scores) if period_scores else 0
		avg_exams = sum(exam_scores) / len(exam_scores) if exam_scores else 0
		overall = (avg_periods * 0.75) + (avg_exams * 0.25) if avg_exams else avg_periods

		rating = _derive_rating(overall, grading_scale_name)

		entries.append({
			"student": s.student,
			"overall_average": flt(overall, 1),
			"overall_rating": rating,
		})

	entries.sort(key=lambda e: e["overall_average"], reverse=True)
	for i, entry in enumerate(entries):
		entry["class_rank"] = i + 1

	mgs.set("entries", [])
	for e in entries:
		mgs.append("entries", e)

	mgs.save(ignore_permissions=True)

	return len(entries)


def _get_student_averages(student, plan_names):
	if not plan_names:
		return []
	results = frappe.get_all(
		"Assessment Result",
		filters={
			"student": student,
			"assessment_plan": ["in", plan_names],
		},
		fields=["assessment_plan", "total_score", "maximum_score"],
	)
	avgs = []
	for r in results:
		if r.maximum_score:
			avgs.append(flt(r.total_score) / flt(r.maximum_score) * 100)
	return avgs


def _get_grading_scale_name():
	name = None
	if "grading_scale" in frappe.get_meta("Education Settings").get_valid_columns():
		name = frappe.db.get_single_value("Education Settings", "grading_scale")
	if name:
		return name
	return frappe.db.get_value("Grading Scale", {}, "name")


def _derive_rating(score, grading_scale_name):
	if not grading_scale_name:
		if score >= 95:
			return "O"
		elif score >= 85:
			return "S"
		elif score >= 75:
			return "T"
		else:
			return "F"

	intervals = frappe.get_all(
		"Grading Scale Interval",
		filters={"parent": grading_scale_name},
		fields=["grade_code", "threshold"],
		order_by="threshold desc",
	)
	for interval in intervals:
		if score >= flt(interval.threshold):
			return interval.grade_code
	return "F"
