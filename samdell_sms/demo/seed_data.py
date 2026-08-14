import random

import frappe
from frappe.utils import add_days, flt, today

COMPANY = "SAMDELL MEMORIAL SCHOOL"
CURRENCY = "LRD"
ACADEMIC_YEAR = "2025-2026"
PREV_YEAR = "2024-2025"

# Programs are the four ministry levels; grades live on School Grades/Batches.
PROGRAMS = ["Early Childhood", "Elementary", "Junior High School", "Senior High School"]

GRADES = ["Nursery", "Pre-K", "Kindergarten"] + [f"Grade {i}" for i in range(1, 10)]
ALL_GRADES = ["Nursery", "Pre-K", "Kindergarten"] + [f"Grade {i}" for i in range(1, 13)]

LEVEL_BY_GRADE = {
	"Nursery": "Early Childhood",
	"Pre-K": "Early Childhood",
	"Kindergarten": "Early Childhood",
	**{f"Grade {i}": "Elementary" for i in range(1, 7)},
	**{f"Grade {i}": "Junior High School" for i in range(7, 10)},
	**{f"Grade {i}": "Senior High School" for i in range(10, 13)},
}

# Realistic Liberian first/last names
FIRST_NAMES = [
	"Amara",
	"Bendu",
	"Chea",
	"Doris",
	"Emmanuel",
	"Fatmata",
	"Gladys",
	"Hawa",
	"Ibrahim",
	"Joseph",
	"Kadiatu",
	"Louise",
	"Moses",
	"Nellie",
	"Osman",
	"Princess",
	"Queenie",
	"Ruth",
	"Sia",
	"Tamba",
	"Umu",
	"Veyah",
	"Willie",
	"Yatta",
]
LAST_NAMES = [
	"Kollie",
	"Tarpeh",
	"Kamara",
	"Flomo",
	"Weah",
	"Gaye",
	"Johnson",
	"Smith",
	"Tubman",
	"Paye",
	"Kpoto",
	"Dolo",
	"Sherman",
	"Toe",
	"Wesseh",
	"Bokai",
	"Fahnbulleh",
	"Gweh",
	"Holder",
	"Jallah",
]

SUBJECTS = {
	"Nursery": ["Early Learning", "Numeracy", "Literacy"],
	"Pre-K": ["Early Learning", "Numeracy", "Literacy", "Art & Music"],
	"Kindergarten": ["Early Learning", "Numeracy", "Literacy", "Art & Music"],
	"Grade 1": ["English", "Mathematics", "Science", "Social Studies"],
	"Grade 2": ["English", "Mathematics", "Science", "Social Studies"],
	"Grade 3": ["English", "Mathematics", "Science", "Social Studies"],
	"Grade 4": ["English", "Mathematics", "Science", "Social Studies"],
	"Grade 5": ["English", "Mathematics", "Science", "Social Studies"],
	"Grade 6": ["English", "Mathematics", "Science", "Social Studies"],
	"Grade 7": ["English", "Mathematics", "Integrated Science", "Social Studies"],
	"Grade 8": ["English", "Mathematics", "Integrated Science", "Social Studies"],
	"Grade 9": ["English", "Mathematics", "Integrated Science", "Social Studies"],
}

# Students in Grades 4-7 who should clear the 90% double-promotion bar
DOUBLE_PROMO_TARGETS = {"Grade 4", "Grade 5", "Grade 6", "Grade 7"}


def _get_company():
	"""Resolve the actual Company record (seed data used the branding name which
	is not a real Company doc). Falls back to the branding constant."""
	company = frappe.db.get_value("Company", filters={}, fieldname="name")
	return company or COMPANY


def run():
	_clear_seed_data()

	academic_year = _ensure_academic_year(ACADEMIC_YEAR)

	term_1 = _ensure_academic_term(academic_year, "Term 1")
	term_2 = _ensure_academic_term(academic_year, "Term 2")

	programs = _ensure_programs()
	_ensure_school_grades()
	_ensure_courses()
	_grading_scale()
	batches = _ensure_student_batches(academic_year)
	student_groups = _ensure_student_groups(programs, batches, academic_year)

	students_data = _make_students(programs)
	students = _ensure_students(students_data)
	_enroll_students(students, students_data, academic_year, batches)
	_populate_groups(students, students_data, student_groups)

	_ensure_assessment_groups()
	_ensure_assessment_plans(student_groups, programs, academic_year, term_1, term_2)
	_seed_assessment_results(students, students_data, student_groups, academic_year, term_1, term_2)

	_seed_master_grade_sheets(student_groups, academic_year, term_1, term_2)
	_seed_historical_mgs(students, students_data, academic_year)
	_ensure_promotion_policy()
	_generate_evaluations_and_statements(academic_year)
	_ensure_workflow_states()
	_seed_national_exam_records(students, academic_year)
	_seed_announcements()
	_seed_assets()
	_seed_print_formats()
	_seed_payment_entry(students)
	_seed_branding()
	_seed_ece_progress_reports(students)
	_seed_finance_demo(students)

	frappe.db.commit()
	print("Seed data complete.")
	return True


def _clear_seed_data():
	# Idempotency: drop records created by this script, in reverse dependency order.
	# Direct DB deletes avoid cancel/delete validation on submitted docs.
	for dt in [
		"Master Grade Sheet Entry",
		"Master Grade Sheet",
		"Promotion Statement",
		"Promotion Evaluation",
		"Assessment Result",
		"Assessment Plan Criteria",
		"Assessment Plan",
		"Student ID Card",
		"National Exam Subject Score",
		"National Exam Record",
		"School Announcement Audience",
		"School Announcement",
		"Website Enquiry",
		"Early Childhood Progress Report",
	]:
		frappe.db.delete(dt)

	for dt in [
		"Program Enrollment Course",
		"Program Enrollment",
		"Student Group Student",
		"Student Group",
		"Student Batch Name",
		"Student Guardian",
		"Student",
		"Guardian",
		"Course",
		"Assessment Criteria",
		"Program",
	]:
		frappe.db.delete(dt)

	frappe.db.delete("Asset Finance Book")
	frappe.db.delete("Asset")
	frappe.db.delete("Asset Category")
	frappe.db.delete("Payment Entry")
	frappe.db.commit()


def _ensure_academic_year(name):
	if frappe.db.exists("Academic Year", name):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Academic Year",
			"academic_year_name": name,
			"year_start_date": f"{name[:4]}-08-01",
			"year_end_date": f"{name[5:]}-07-31",
		}
	).insert(ignore_permissions=True)
	return doc.name


def _ensure_academic_term(academic_year, term_name):
	name = f"{academic_year} ({term_name})"
	if frappe.db.exists("Academic Term", name):
		return name
	start = f"{academic_year[:4]}-08-01"
	end = f"{academic_year[5:]}-07-31"
	doc = frappe.get_doc(
		{
			"doctype": "Academic Term",
			"academic_year": academic_year,
			"term_name": term_name,
			"title": name,
			"term_start_date": start,
			"term_end_date": end,
		}
	).insert(ignore_permissions=True)
	return doc.name


def _ensure_programs():
	programs = {}
	for level in PROGRAMS:
		if not frappe.db.exists("Program", level):
			frappe.get_doc(
				{
					"doctype": "Program",
					"program_name": level,
					"program_abbreviation": level[:3].upper(),
				}
			).insert(ignore_permissions=True)
		programs[level] = level
	return programs


def _ensure_school_grades():
	for grade in ALL_GRADES:
		if not frappe.db.exists("School Grade", grade):
			frappe.get_doc(
				{
					"doctype": "School Grade",
					"grade_name": grade,
					"level": LEVEL_BY_GRADE[grade],
					"sort_order": ALL_GRADES.index(grade) + 1,
				}
			).insert(ignore_permissions=True)
	return {grade: grade for grade in ALL_GRADES}


def _ensure_student_batches(academic_year):
	batches = {}
	for grade in GRADES:
		name = f"{grade} - {academic_year}"
		if not frappe.db.exists("Student Batch Name", name):
			frappe.get_doc(
				{
					"doctype": "Student Batch Name",
					"batch_name": name,
					"school_grade": grade,
				}
			).insert(ignore_permissions=True)
		batches[grade] = name
	return batches


def _ensure_courses():
	for subjects in SUBJECTS.values():
		for subj in subjects:
			if not frappe.db.exists("Course", subj):
				frappe.get_doc(
					{
						"doctype": "Course",
						"course_name": subj,
						"description": f"{subj} course",
					}
				).insert(ignore_permissions=True)
			if not frappe.db.exists("Assessment Criteria", subj):
				frappe.get_doc(
					{
						"doctype": "Assessment Criteria",
						"assessment_criteria": subj,
					}
				).insert(ignore_permissions=True)


def _grading_scale():
	name = "SAMDELL SMS O/S/T/F"
	if not frappe.db.exists("Grading Scale", name):
		frappe.get_doc({"doctype": "Grading Scale", "grading_scale_name": name}).insert(
			ignore_permissions=True
		)


def _ensure_student_groups(programs, batches, academic_year):
	groups = {}
	for grade in GRADES:
		level = LEVEL_BY_GRADE[grade]
		name = f"{grade} - {academic_year}"
		if not frappe.db.exists("Student Group", name):
			frappe.get_doc(
				{
					"doctype": "Student Group",
					"student_group_name": name,
					"group_based_on": "Batch",
					"program": programs[level],
					"batch": batches[grade],
					"academic_year": academic_year,
					"max_strength": 40,
				}
			).insert(ignore_permissions=True)
		groups[grade] = name
	return groups


def _make_students(programs):
	"""~18 students spread across grades; Grades 4-7 get the 90+ history."""
	random.seed(42)
	students = []
	count_by_grade = {
		"Nursery": 1,
		"Pre-K": 1,
		"Kindergarten": 2,
		"Grade 1": 2,
		"Grade 2": 2,
		"Grade 3": 2,
		"Grade 4": 2,
		"Grade 5": 2,
		"Grade 6": 2,
		"Grade 7": 2,
		"Grade 8": 1,
		"Grade 9": 1,
	}
	used = set()
	for grade, n in count_by_grade.items():
		for _ in range(n):
			while True:
				first = random.choice(FIRST_NAMES)
				last = random.choice(LAST_NAMES)
				full = f"{first} {last}"
				if full not in used:
					used.add(full)
					break
			is_double_candidate = (
				grade in DOUBLE_PROMO_TARGETS
				and len([s for s in students if s["grade"] == grade and s.get("double_promo")]) < 1
			)
			target = (
				random.randint(91, 96) if is_double_candidate else random.choice([78, 81, 84, 87, 90, 93])
			)
			students.append(
				{
					"full_name": full,
					"first_name": first,
					"last_name": last,
					"grade": grade,
					"program": programs[LEVEL_BY_GRADE[grade]],
					"double_promo": is_double_candidate,
					"target_average": target,
				}
			)
	return students


def _ensure_students(students_data):
	students = {}
	for s in students_data:
		full_name = s["full_name"]
		existing = frappe.get_all("Student", filters={"student_name": full_name}, fields=["name"], limit=1)
		if existing:
			students[full_name] = existing[0].name
			continue
		guardian = _ensure_guardian(full_name)
		doc = frappe.get_doc(
			{
				"doctype": "Student",
				"student_name": full_name,
				"first_name": s["first_name"],
				"last_name": s["last_name"],
				"gender": "Male"
				if s["first_name"] in ["Emmanuel", "Ibrahim", "Joseph", "Moses", "Osman", "Tamba", "Willie"]
				else "Female",
				"date_of_birth": f"{random.randint(2006, 2019)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
				"student_email_id": f"{s['first_name'].lower()}.{s['last_name'].lower()}@samdell.school",
				"nationality": "Liberian",
				"enabled": 1,
				"guardians": [{"guardian": guardian}],
			}
		).insert(ignore_permissions=True)
		students[full_name] = doc.name
	return students


def _ensure_guardian(student_name):
	guardian_name = f"Guardian of {student_name}"
	if frappe.db.exists("Guardian", guardian_name):
		return guardian_name
	phone = f"0770 {random.randint(100, 999)} {random.randint(100, 999)}"
	doc = frappe.get_doc(
		{
			"doctype": "Guardian",
			"guardian_name": guardian_name,
			"mobile_number": phone,
			"email_address": f"guardian.{random.randint(1000, 9999)}@samdell.school",
		}
	).insert(ignore_permissions=True)
	return doc.name


def _enroll_students(students, students_data, academic_year, batches):
	for s in students_data:
		student = students[s["full_name"]]
		if frappe.db.exists("Program Enrollment", {"student": student, "academic_year": academic_year}):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": student,
				"program": s["program"],
				"student_batch_name": batches[s["grade"]],
				"academic_year": academic_year,
				"enrollment_date": today(),
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()


def _populate_groups(students, students_data, student_groups):
	by_grade = {}
	for s in students_data:
		by_grade.setdefault(s["grade"], []).append(students[s["full_name"]])
	for grade, group_name in student_groups.items():
		group = frappe.get_doc("Student Group", group_name)
		if group.students:
			continue
		roll = 1
		for student in by_grade.get(grade, []):
			group.append(
				"students",
				{
					"student": student,
					"student_name": frappe.db.get_value("Student", student, "student_name"),
					"group_roll_number": roll,
					"active": 1,
				},
			)
			roll += 1
		if group.students:
			group.save(ignore_permissions=True)


def _ensure_assessment_groups():
	for name in ["Period 1", "Period 2", "Period 3", "Period 4", "Period 5", "Period 6", "End of Term Exam"]:
		if not frappe.db.exists("Assessment Group", name):
			frappe.get_doc(
				{
					"doctype": "Assessment Group",
					"assessment_group_name": name,
					"parent_assessment_group": "All Assessment Groups",
					"is_group": 0,
				}
			).insert(ignore_permissions=True)


def _ensure_assessment_plans(student_groups, programs, academic_year, term_1, term_2):
	plans = {}
	global_slot = 0
	for grade, group in student_groups.items():
		level = LEVEL_BY_GRADE[grade]
		subjects = SUBJECTS[grade]
		for term in [term_1, term_2]:
			slot = 0
			for i in range(1, 7):
				for subj in subjects:
					global_slot += 1
					slot += 1
					start_hour = 9 + (slot % 8)
					name = f"{group} {term} {subj} Period {i}"
					if frappe.db.exists("Assessment Plan", {"assessment_name": name}):
						continue
					plan = frappe.get_doc(
						{
							"doctype": "Assessment Plan",
							"assessment_name": name,
							"student_group": group,
							"program": programs[level],
							"course": subj,
							"assessment_group": f"Period {i}",
							"academic_year": academic_year,
							"maximum_assessment_score": 100,
							"grading_scale": "SAMDELL SMS O/S/T/F",
							"schedule_date": add_days(today(), global_slot),
							"from_time": f"{start_hour:02d}:00:00",
							"to_time": f"{start_hour + 1:02d}:00:00",
							"assessment_criteria": [{"assessment_criteria": subj, "maximum_score": 100}],
						}
					).insert(ignore_permissions=True)
					frappe.db.set_value("Assessment Plan", plan.name, "academic_term", term)
			for subj in subjects:
				global_slot += 1
				slot += 1
				start_hour = 9 + (slot % 8)
				name = f"{group} {term} {subj} Exam"
				if frappe.db.exists("Assessment Plan", {"assessment_name": name}):
					continue
				plan = frappe.get_doc(
					{
						"doctype": "Assessment Plan",
						"assessment_name": name,
						"student_group": group,
						"program": programs[level],
						"course": subj,
						"assessment_group": "End of Term Exam",
						"academic_year": academic_year,
						"maximum_assessment_score": 100,
						"grading_scale": "SAMDELL SMS O/S/T/F",
						"schedule_date": add_days(today(), global_slot),
						"from_time": f"{start_hour:02d}:00:00",
						"to_time": f"{start_hour + 1:02d}:00:00",
						"assessment_criteria": [{"assessment_criteria": subj, "maximum_score": 100}],
					}
				).insert(ignore_permissions=True)
				frappe.db.set_value("Assessment Plan", plan.name, "academic_term", term)
	return plans


def _seed_assessment_results(students, students_data, student_groups, academic_year, term_1, term_2):
	for s in students_data:
		group = student_groups[s["grade"]]
		subjects = SUBJECTS[s["grade"]]
		base = s["target_average"]
		has_low = s["full_name"] in _LOW_SCORE_STUDENTS
		student = students[s["full_name"]]
		student_name = s["full_name"]
		for term in [term_1, term_2]:
			for subj in subjects:
				for i in range(1, 7):
					score = base + random.randint(-3, 4)
					if has_low:
						score = min(score, 73)
					plan = _plan_name(group, term, subj, period=i)
					if not frappe.db.exists(
						"Assessment Result", {"assessment_plan": plan, "student": student}
					):
						frappe.get_doc(
							{
								"doctype": "Assessment Result",
								"assessment_plan": plan,
								"student": student,
								"student_name": student_name,
								"academic_term": term,
								"academic_year": academic_year,
								"total_score": score,
								"maximum_score": 100,
								"details": [
									{"assessment_criteria": subj, "score": score, "maximum_score": 100}
								],
							}
						).insert(ignore_permissions=True)
				score = base + random.randint(-2, 3)
				if has_low:
					score = min(score, 74)
				plan = _plan_name(group, term, subj, exam=True)
				if not frappe.db.exists("Assessment Result", {"assessment_plan": plan, "student": student}):
					frappe.get_doc(
						{
							"doctype": "Assessment Result",
							"assessment_plan": plan,
							"student": student,
							"student_name": student_name,
							"academic_term": term,
							"academic_year": academic_year,
							"total_score": score,
							"maximum_score": 100,
							"details": [{"assessment_criteria": subj, "score": score, "maximum_score": 100}],
						}
					).insert(ignore_permissions=True)


def _plan_name(group, term, subj, period=None, exam=False):
	if exam:
		assessment_name = f"{group} {term} {subj} Exam"
	else:
		assessment_name = f"{group} {term} {subj} Period {period}"
	plan = frappe.db.get_value("Assessment Plan", {"assessment_name": assessment_name}, "name")
	if not plan:
		raise frappe.DoesNotExistError(assessment_name)
	return plan


_LOW_SCORE_STUDENTS = {
	"Bendu Tarpeh",
	"Chea Kamara",
}


def _seed_master_grade_sheets(student_groups, academic_year, term_1, term_2):
	from samdell_sms.api.grade_sheet import pull_results

	for _grade, group in student_groups.items():
		for term in [term_1, term_2]:
			if frappe.db.exists("Master Grade Sheet", {"student_group": group, "academic_term": term}):
				continue
			mgs = frappe.get_doc(
				{
					"doctype": "Master Grade Sheet",
					"student_group": group,
					"academic_term": term,
				}
			)
			mgs.insert(ignore_permissions=True)
			try:
				pull_results(mgs.name)
			except Exception:
				pass
			mgs.load_from_db()
			if mgs.entries:
				try:
					mgs.submit()
				except Exception:
					mgs.docstatus = 1
					mgs.db_update()


def _seed_historical_mgs(students, students_data, academic_year):
	"""Fabricate Grade 1-3 Master Grade Sheets for prior years so the
	early-grades average is meaningful for the double-promotion band."""
	candidates = [s for s in students_data if s.get("double_promo")]
	if not candidates:
		return

	years = [
		(2023, "2023-2024", "Grade 1"),
		(2024, "2024-2025", "Grade 2"),
		(2025, "2025-2026", "Grade 3"),
	]
	for _year_num, year_name, grade in years:
		if year_name == academic_year:
			continue
		_ensure_academic_year(year_name)
		batch = f"{grade} - {year_name}"
		if not frappe.db.exists("Student Batch Name", batch):
			frappe.get_doc(
				{
					"doctype": "Student Batch Name",
					"batch_name": batch,
					"school_grade": grade,
				}
			).insert(ignore_permissions=True)
		group = f"{grade} - {year_name}"
		if not frappe.db.exists("Student Group", group):
			frappe.get_doc(
				{
					"doctype": "Student Group",
					"student_group_name": group,
					"group_based_on": "Batch",
					"program": LEVEL_BY_GRADE[grade],
					"batch": batch,
					"academic_year": year_name,
				}
			).insert(ignore_permissions=True)
		for s in candidates:
			student = students[s["full_name"]]
			if frappe.db.exists("Program Enrollment", {"student": student, "academic_year": year_name}):
				continue
			enr = frappe.get_doc(
				{
					"doctype": "Program Enrollment",
					"student": student,
					"program": LEVEL_BY_GRADE[grade],
					"student_batch_name": batch,
					"academic_year": year_name,
					"enrollment_date": today(),
				}
			)
			enr.insert(ignore_permissions=True)
			enr.submit()
		term = _ensure_academic_term(year_name, "Term 1")
		if frappe.db.exists("Master Grade Sheet", {"academic_term": term}):
			continue
		mgs = frappe.get_doc(
			{
				"doctype": "Master Grade Sheet",
				"student_group": group,
				"academic_term": term,
			}
		)
		mgs.insert(ignore_permissions=True)
		for s in candidates:
			avg = 92 + ((s["target_average"] - 90) % 4)
			mgs.append(
				"entries",
				{
					"student": students[s["full_name"]],
					"overall_average": avg,
					"overall_rating": "O" if avg >= 95 else "S",
					"class_rank": 1,
				},
			)
		if mgs.entries:
			try:
				mgs.submit()
			except Exception:
				mgs.docstatus = 1
				mgs.db_update()


def _ensure_promotion_policy():
	policy = frappe.get_single("Promotion Policy")
	changed = False
	if not policy.double_promotion_band_start:
		policy.double_promotion_band_start = "Grade 4"
		policy.double_promotion_band_end = "Grade 7"
		policy.early_grades_start = "Grade 1"
		policy.early_grades_end = "Grade 3"
		policy.minimum_average_early_grades = 90
		policy.minimum_average_current_band = 90
		changed = True
	if not policy.grade_sequence or {r.school_grade for r in policy.grade_sequence} != set(ALL_GRADES):
		policy.grade_sequence = []
		for i, grade in enumerate(ALL_GRADES, start=1):
			policy.append("grade_sequence", {"school_grade": grade, "sequence_no": i})
		changed = True
	if changed:
		policy.save(ignore_permissions=True)


def _ensure_workflow_states():
	"""Frappe's `WorkflowState` docs (standalone) are required by `frappe.desk.form.meta.load_workflows`.
	The workflow fixture captures only the `Workflow` record, so create the referenced states explicitly."""
	for state in ["Draft", "Submitted", "Reviewed", "Approved", "Released"]:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{
					"doctype": "Workflow State",
					"workflow_state_name": state,
				}
			).insert(ignore_permissions=True)


def _generate_evaluations_and_statements(academic_year):
	from samdell_sms.api.promotion import evaluate_promotions, generate_promotion_statements

	if not frappe.get_all("Promotion Evaluation", filters={"academic_year": academic_year}):
		try:
			evaluate_promotions(academic_year)
		except Exception as e:
			frappe.log_error(f"evaluate_promotions seed: {e}", "Seed")
	if not frappe.get_all("Promotion Statement", filters={"academic_year": academic_year}):
		try:
			generate_promotion_statements(academic_year)
		except Exception as e:
			frappe.log_error(f"generate_promotion_statements seed: {e}", "Seed")


def _seed_national_exam_records(students, academic_year):
	exam_students = [students[k] for k in list(students)[:4]]
	results = ["Pass", "Pass", "Pass", "Fail"]
	for i, student in enumerate(exam_students):
		doc = frappe.get_doc(
			{
				"doctype": "National Exam Record",
				"student": student,
				"exam_type": "WASSCE",
				"academic_year": academic_year,
				"candidate_number": f"WAEC-{academic_year[:4]}-{1000 + i}",
				"overall_result": results[i],
				"subject_scores": [
					{"subject": "English", "score": random.randint(65, 95)},
					{"subject": "Mathematics", "score": random.randint(65, 95)},
					{"subject": "Integrated Science", "score": random.randint(65, 95)},
					{"subject": "Social Studies", "score": random.randint(65, 95)},
				],
			}
		).insert(ignore_permissions=True)
		doc.submit()


def _seed_announcements():
	items = [
		{
			"title": "Welcome to the New School Year",
			"body": "Classes resume on Monday at 8:00 AM. Uniforms and books are available at the school office.",
			"audience": ["All"],
			"send_sms": 1,
		},
		{
			"title": "Parent-Teacher Conference",
			"body": "We invite all parents to the termly parent-teacher conference next Friday from 2:00 PM.",
			"audience": ["Parents"],
			"send_sms": 0,
		},
		{
			"title": "Inter-House Sports Day",
			"body": "Annual sports day is scheduled for the last Saturday of the term. All students must participate.",
			"audience": ["Students"],
			"send_sms": 0,
		},
	]
	for item in items:
		title = item["title"]
		if frappe.db.exists("School Announcement", {"title": title}):
			continue
		frappe.get_doc(
			{
				"doctype": "School Announcement",
				"title": title,
				"body": item["body"],
				"audience": [{"target": t} for t in item["audience"]],
				"send_sms": item["send_sms"],
				"publish_date": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)


def _ensure_asset_account_types():
	account_types = {
		"Fixed Assets - SMS": "Fixed Asset",
		"Accumulated Depreciation - SMS": "Accumulated Depreciation",
		"Depreciation - SMS": "Depreciation",
	}
	for account, account_type in account_types.items():
		if frappe.db.exists("Account", account) and not frappe.db.get_value(
			"Account", account, "account_type"
		):
			frappe.db.set_value("Account", account, "account_type", account_type)


def _seed_branding():
	# Brand palette is always synced so re-runs (and prior bad seeds) converge to
	# the official Mahogany Brown + Gold theme used across desk, web, and print.
	BRAND_PRIMARY = "#6B3A2A"
	BRAND_GOLD = "#C5A028"
	branding = frappe.get_single("School Branding Settings")
	changed = False
	if not branding.school_name:
		branding.school_name = "SAMDELL MEMORIAL SCHOOL"
		branding.school_motto = "Knowledge • Discipline • Service"
		branding.tagline = "Nurturing tomorrow's leaders with faith and excellence."
		changed = True
	if not branding.school_levels:
		branding.school_levels = "Early Childhood\nElementary\nJunior Secondary\nSenior Secondary"
		changed = True
	for field, value in {
		"primary_color": BRAND_PRIMARY,
		"secondary_color": BRAND_GOLD,
		"accent_color": BRAND_GOLD,
	}.items():
		if branding.get(field) != value:
			branding.set(field, value)
			changed = True
	if changed:
		branding.save(ignore_permissions=True)

	website = frappe.get_single("Website Settings")
	website_changed = False
	if website.home_page not in ("index", "home", "/"):
		website.home_page = "index"
		website_changed = True
	if website.app_name != "SAMDELL MEMORIAL SCHOOL":
		website.app_name = "SAMDELL MEMORIAL SCHOOL"
		website_changed = True
	if website_changed:
		website.save(ignore_permissions=True)


def _seed_assets():
	_ensure_asset_account_types()
	company = _get_company()
	if not frappe.db.exists("Location", "Main Building"):
		frappe.get_doc({"doctype": "Location", "location_name": "Main Building"}).insert(
			ignore_permissions=True
		)
	categories = {
		"Furniture & Fixtures": ["Desks and chairs", "Cabinets"],
		"Computers & IT Equipment": ["Desktop computers", "Projector"],
		"Laboratory Equipment": ["Microscopes", "Lab tables"],
		"Sports Equipment": ["Football goals", "Basketball hoops"],
		"Buildings & Property": ["Main classroom block"],
		"Vehicles": ["School bus"],
	}
	for category, items in categories.items():
		if not frappe.db.exists("Asset Category", category):
			frappe.get_doc(
				{
					"doctype": "Asset Category",
					"asset_category_name": category,
					"accounts": [
						{
							"company_name": company,
							"fixed_asset_account": "Fixed Assets - SMS",
							"accumulated_depreciation_account": "Accumulated Depreciation - SMS",
							"depreciation_expense_account": "Depreciation - SMS",
						}
					],
				}
			).insert(ignore_permissions=True)
		for item in items:
			if not frappe.db.exists("Asset", {"asset_name": item}):
				if not frappe.db.exists("Item", item):
					frappe.get_doc(
						{
							"doctype": "Item",
							"item_code": item,
							"item_name": item,
							"item_group": "All Item Groups",
							"is_fixed_asset": 1,
							"is_stock_item": 0,
							"is_sales_item": 0,
							"asset_category": category,
						}
					).insert(ignore_permissions=True)
				amount = random.randint(15000, 250000)
				doc = frappe.get_doc(
					{
						"doctype": "Asset",
						"asset_name": item,
						"asset_category": category,
						"company": company,
						"item_code": item,
						"gross_purchase_amount": amount,
						"net_purchase_amount": amount,
						"purchase_date": today(),
						"available_for_use_date": today(),
						"location": "Main Building",
					}
				)
				doc.insert(ignore_permissions=True)


def _seed_print_formats():
	"""Custom Jinja print formats: Report Card, Certificate of Promotion, Fee Payment Receipt."""
	from samdell_sms.demo.print_formats import _ensure_print_formats

	_ensure_print_formats()


def _seed_payment_entry(students):
	"""One submitted Payment Entry so the Fee Payment Receipt can be demoed live."""
	if not students:
		return
	student = next(iter(students.values()))
	if frappe.db.exists("Payment Entry", {"party": student}):
		return
	try:
		pe = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"posting_date": today(),
				"company": _get_company(),
				"mode_of_payment": "Cash",
				"party_type": "Student",
				"party": student,
				"paid_from": "Cash - SMS",
				"paid_to": "Debtors - SMS",
				"paid_amount": 250.0,
				"received_amount": 250.0,
			}
		)
		pe.insert(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(f"Payment Entry seed: {e}", "Seed")


def _bid():
	return frappe.generate_hash("", 10)


def _seed_ece_progress_reports(students):
	"""One ECE Progress Report per ECE student so the print format demos live."""
	ece_students = frappe.get_all(
		"Program Enrollment",
		filters={"program": "Early Childhood", "docstatus": 1},
		fields=["student"],
	)
	term = frappe.get_all("Academic Term", limit=1, order_by="creation desc")
	term = term[0]["name"] if term else None
	teacher = frappe.db.get_value("Employee", {"first_name": "Class Teacher"}, "name") or None
	for enr in ece_students:
		if frappe.db.exists(
			"Early Childhood Progress Report",
			{"student": enr["student"], "academic_term": term},
		):
			continue
		comments = (
			"Ajoy and confident learner. Shows strong early literacy skills and "
			"takes part happily in group activities."
		)
		frappe.get_doc(
			{
				"doctype": "Early Childhood Progress Report",
				"student": enr["student"],
				"academic_term": term,
				"teacher": teacher,
				"readiness": "Ready for Next Level",
				"comments": comments,
				"teacher_signed": 1,
				"principal_approved": 1,
			}
		).insert(ignore_permissions=True)


def _seed_finance_demo(students):
	"""Submitted Fees + Payment Entry so the Fee Payment Receipt print format demos live."""
	from samdell_sms.demo.seed_finance import run as seed_finance

	try:
		seed_finance()
	except Exception as e:
		frappe.log_error(f"seed_finance: {e}", "Seed")
