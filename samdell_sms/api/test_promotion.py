import unittest.mock as mock

import frappe
from frappe.tests import UnitTestCase

import samdell_sms.api.promotion as promotion


def _db_get_value(grade_sorts, doctype, name, field):
	if doctype == "School Grade" and field == "sort_order":
		return grade_sorts.get(name)
	return None


class TestPromotion(UnitTestCase):
	def test_early_grades_average_uses_early_band_only(self):
		captured = {}
		sheets = {
			"MGS-001": frappe._dict(
				{
					"entries": [
						frappe._dict({"student": "STU-001", "overall_average": 88}),
						frappe._dict({"student": "STU-002", "overall_average": 70}),
					]
				}
			),
			"MGS-002": frappe._dict(
				{"entries": [frappe._dict({"student": "STU-001", "overall_average": 92})]}
			),
		}

		def fake_get_all(doctype, filters=None, fields=None, pluck=None, order_by=None, limit=None):
			if doctype == "School Grade":
				return ["Grade 1", "Grade 2", "Grade 3"]
			if doctype == "Student Batch Name":
				return ["B-001", "B-002"]
			if doctype == "Program Enrollment":
				captured["enrollment_filters"] = filters
				return ["AY-2024", "AY-2025"]
			if doctype == "Academic Term":
				captured["term_filters"] = filters
				return ["T-2024-1", "T-2025-1"]
			if doctype == "Master Grade Sheet":
				return [frappe._dict({"name": "MGS-001"}), frappe._dict({"name": "MGS-002"})]
			return []

		def fake_get_doc(doctype, name=None):
			if doctype == "Master Grade Sheet":
				return sheets[name]
			raise AssertionError(f"unexpected get_doc: {doctype} {name}")

		def fake_db_get_value(doctype, name, field):
			return _db_get_value({"Grade 1": 4, "Grade 3": 6}, doctype, name, field)

		policy = frappe._dict({"early_grades_start": "Grade 1", "early_grades_end": "Grade 3"})
		with (
			mock.patch("frappe.get_all", side_effect=fake_get_all),
			mock.patch("frappe.get_doc", side_effect=fake_get_doc),
			mock.patch("frappe.db.get_value", side_effect=fake_db_get_value),
		):
			average = promotion._get_early_grades_average("STU-001", policy)

		self.assertEqual(average, 90.0)
		self.assertEqual(captured["enrollment_filters"]["student"], "STU-001")
		self.assertEqual(captured["enrollment_filters"]["student_batch_name"], ["in", ["B-001", "B-002"]])
		self.assertEqual(captured["enrollment_filters"]["docstatus"], 1)
		self.assertEqual(captured["term_filters"]["academic_year"], ["in", ["AY-2024", "AY-2025"]])

	def test_early_grades_average_returns_zero_without_range(self):
		policy = frappe._dict({"early_grades_start": "", "early_grades_end": ""})
		with mock.patch("frappe.get_all", side_effect=AssertionError("get_all must not run")):
			self.assertEqual(promotion._get_early_grades_average("STU-001", policy), 0.0)

	def test_early_grades_average_returns_zero_without_enrollments(self):
		def fake_get_all(doctype, filters=None, fields=None, pluck=None, order_by=None, limit=None):
			if doctype == "School Grade":
				return ["Grade 1", "Grade 2"]
			if doctype == "Student Batch Name":
				return ["B-001"]
			if doctype == "Program Enrollment":
				return []
			return []

		def fake_db_get_value(doctype, name, field):
			return _db_get_value({"Grade 1": 4, "Grade 2": 5}, doctype, name, field)

		policy = frappe._dict({"early_grades_start": "Grade 1", "early_grades_end": "Grade 2"})
		with (
			mock.patch("frappe.get_all", side_effect=fake_get_all),
			mock.patch("frappe.db.get_value", side_effect=fake_db_get_value),
		):
			self.assertEqual(promotion._get_early_grades_average("STU-001", policy), 0.0)

	def test_current_year_average(self):
		sheets = {
			"MGS-010": frappe._dict(
				{"entries": [frappe._dict({"student": "STU-001", "overall_average": 84})]}
			),
			"MGS-011": frappe._dict(
				{
					"entries": [
						frappe._dict({"student": "STU-001", "overall_average": 90}),
						frappe._dict({"student": "STU-002", "overall_average": 95}),
					]
				}
			),
		}

		def fake_get_all(doctype, filters=None, fields=None, pluck=None, order_by=None, limit=None):
			if doctype == "Academic Term":
				return ["T-2025-1", "T-2025-2"]
			if doctype == "Master Grade Sheet":
				return [frappe._dict({"name": "MGS-010"}), frappe._dict({"name": "MGS-011"})]
			return []

		def fake_get_doc(doctype, name=None):
			if doctype == "Master Grade Sheet":
				return sheets[name]
			raise AssertionError(f"unexpected get_doc: {doctype} {name}")

		with (
			mock.patch("frappe.get_all", side_effect=fake_get_all),
			mock.patch("frappe.get_doc", side_effect=fake_get_doc),
		):
			average = promotion._get_current_year_average("STU-001", "AY-2025")

		self.assertEqual(average, 87.0)

	def test_average_over_terms_returns_zero_without_matching_entries(self):
		def fake_get_all(doctype, filters=None, fields=None, pluck=None, order_by=None, limit=None):
			return []

		with mock.patch("frappe.get_all", side_effect=fake_get_all):
			self.assertEqual(promotion._average_over_terms("STU-001", []), 0.0)
			self.assertEqual(promotion._average_over_terms("STU-001", ["T-2025-1"]), 0.0)

	def test_grades_in_range_uses_sort_order(self):
		def fake_get_all(doctype, filters=None, fields=None, pluck=None, order_by=None, limit=None):
			if doctype == "School Grade":
				return ["Grade 4", "Grade 5", "Grade 6", "Grade 7"]
			return []

		def fake_db_get_value(doctype, name, field):
			return _db_get_value(
				{"Grade 4": 7, "Grade 7": 10, "Grade 1": 4, "Grade 3": 6},
				doctype,
				name,
				field,
			)

		with (
			mock.patch("frappe.get_all", side_effect=fake_get_all),
			mock.patch("frappe.db.get_value", side_effect=fake_db_get_value),
		):
			self.assertEqual(
				promotion._get_grades_in_range("Grade 4", "Grade 7"),
				["Grade 4", "Grade 5", "Grade 6", "Grade 7"],
			)
			self.assertEqual(promotion._get_grades_in_range("", ""), [])

	def test_next_grade_stays_within_level_and_graduates_at_boundary(self):
		policy = frappe._dict(
			{
				"grade_sequence": [
					frappe._dict({"school_grade": "Grade 1", "sequence_no": 1}),
					frappe._dict({"school_grade": "Grade 2", "sequence_no": 2}),
					frappe._dict({"school_grade": "Grade 3", "sequence_no": 3}),
					frappe._dict({"school_grade": "Grade 4", "sequence_no": 4}),
					frappe._dict({"school_grade": "Grade 5", "sequence_no": 5}),
					frappe._dict({"school_grade": "Grade 6", "sequence_no": 6}),
					frappe._dict({"school_grade": "Grade 7", "sequence_no": 7}),
				]
			}
		)

		def fake_get_single(doctype):
			if doctype == "Promotion Policy":
				return policy
			raise AssertionError(f"unexpected get_single: {doctype}")

		levels = {
			"Grade 1": "Elementary",
			"Grade 2": "Elementary",
			"Grade 3": "Elementary",
			"Grade 4": "Elementary",
			"Grade 5": "Elementary",
			"Grade 6": "Elementary",
			"Grade 7": "Junior High School",
		}

		def fake_db_get_value(doctype, name, field):
			if doctype == "School Grade" and field == "level":
				return levels.get(name)
			return None

		with (
			mock.patch("frappe.get_single", side_effect=fake_get_single),
			mock.patch("frappe.db.get_value", side_effect=fake_db_get_value),
		):
			# Single promotion within level
			self.assertEqual(promotion._get_next_grade("Grade 4", "Promoted"), "Grade 5")
			# Double promotion within level
			self.assertEqual(promotion._get_next_grade("Grade 4", "Double Promoted"), "Grade 6")
			# Boundary: last grade of Elementary graduates (no next grade)
			self.assertIsNone(promotion._get_next_grade("Grade 6", "Promoted"))
			self.assertIsNone(promotion._get_next_grade("Grade 6", "Double Promoted"))
			# Double promotion capped at the last grade of the level
			self.assertEqual(promotion._get_next_grade("Grade 5", "Double Promoted"), "Grade 6")
			# Unknown grade
			self.assertIsNone(promotion._get_next_grade("Grade 12", "Promoted"))

	def test_students_in_grades_filters_by_batch_grade(self):
		captured = {}

		def fake_get_all(doctype, filters=None, fields=None, pluck=None, order_by=None, limit=None):
			if doctype == "Student Batch Name":
				return [
					frappe._dict({"name": "B-004", "school_grade": "Grade 4"}),
					frappe._dict({"name": "B-005", "school_grade": "Grade 5"}),
					frappe._dict({"name": "B-007", "school_grade": "Grade 7"}),
				]
			if doctype == "Program Enrollment":
				captured["enrollment_filters"] = filters
				return [
					frappe._dict({"student": "STU-001", "student_batch_name": "B-004"}),
					frappe._dict({"student": "STU-002", "student_batch_name": "B-005"}),
					frappe._dict({"student": "STU-003", "student_batch_name": "B-007"}),
				]
			return []

		with mock.patch("frappe.get_all", side_effect=fake_get_all):
			students = promotion._students_in_grades("AY-2026", ["Grade 4", "Grade 5", "Grade 6", "Grade 7"])

		self.assertEqual(len(students), 3)
		self.assertEqual(captured["enrollment_filters"]["academic_year"], "AY-2026")
		self.assertEqual(captured["enrollment_filters"]["docstatus"], 1)
		by_student = {s.student: s.school_grade for s in students}
		self.assertEqual(by_student["STU-001"], "Grade 4")
		self.assertEqual(by_student["STU-003"], "Grade 7")
