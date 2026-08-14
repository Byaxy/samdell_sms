import unittest.mock as mock

import frappe
from frappe.tests import UnitTestCase

import samdell_sms.api.enroll as enroll


class TestEnroll(UnitTestCase):
	def test_next_level_order(self):
		self.assertEqual(enroll._next_level("Early Childhood"), "Elementary")
		self.assertEqual(enroll._next_level("Elementary"), "Junior High School")
		self.assertEqual(enroll._next_level("Junior High School"), "Senior High School")
		self.assertIsNone(enroll._next_level("Senior High School"))
		self.assertIsNone(enroll._next_level("Unknown"))

	def test_first_grade_of_level(self):
		grades = {"Nursery": 1, "Grade 1": 4, "Grade 7": 10, "Grade 10": 13}

		def fake_db_get_value(doctype, filters, field, order_by=None):
			self.assertEqual(doctype, "School Grade")
			self.assertEqual(filters, {"level": "Elementary"})
			self.assertEqual(field, "name")
			self.assertEqual(order_by, "sort_order asc")
			rows = [(g, s) for g, s in grades.items() if g == "Grade 1"]
			return rows[0][0] if rows else None

		with mock.patch("frappe.db.get_value", side_effect=fake_db_get_value):
			self.assertEqual(enroll._first_grade_of_level("Elementary"), "Grade 1")

	def test_next_academic_year_by_start_date(self):
		current = frappe._dict({"year_end_date": "2026-07-15"})

		def fake_get_doc(doctype, name=None):
			self.assertEqual(doctype, "Academic Year")
			self.assertEqual(name, "2025-2026")
			return current

		def fake_db_exists(doctype, name=None):
			if doctype == "Academic Year":
				return True
			return False

		def fake_get_all(doctype, filters=None, fields=None, order_by=None, limit=None):
			self.assertIn("year_start_date", filters)
			self.assertEqual(filters["year_start_date"], [">", "2026-07-15"])
			return [{"name": "2026-2027", "year_start_date": "2026-09-01"}]

		with (
			mock.patch("frappe.get_doc", side_effect=fake_get_doc),
			mock.patch("frappe.db.exists", side_effect=fake_db_exists),
			mock.patch("frappe.get_all", side_effect=fake_get_all),
		):
			self.assertEqual(enroll._next_academic_year("2025-2026"), "2026-2027")

	def test_get_or_create_batch_reuses_existing(self):
		def fake_db_exists(doctype, name):
			self.assertEqual(doctype, "Student Batch Name")
			self.assertEqual(name, "Grade 7 - 2026-2027")
			return True

		with mock.patch("frappe.db.exists", side_effect=fake_db_exists):
			name = enroll._get_or_create_batch("Grade 7", "2026-2027")
			self.assertEqual(name, "Grade 7 - 2026-2027")

	def test_reenroll_next_level_returns_prefill_payload(self):
		statement = frappe._dict(
			{
				"outcome": "Graduated",
				"student": "STU-009",
				"current_program": "Grade 9",
				"academic_year": "2025-2026",
			}
		)

		levels = {"Grade 9": "Junior High School"}

		inserted = []

		batch_doc = mock.MagicMock()
		batch_doc.name = "Grade 10 - 2026-2027"

		def fake_insert_with_permissions(ignore_permissions=True):
			inserted.append(batch_doc)
			return batch_doc

		batch_doc.insert.side_effect = fake_insert_with_permissions

		def fake_get_doc(doctype, name=None):
			if isinstance(doctype, dict):
				self.assertEqual(doctype["doctype"], "Student Batch Name")
				self.assertEqual(doctype["batch_name"], "Grade 10 - 2026-2027")
				self.assertEqual(doctype["school_grade"], "Grade 10")
				return batch_doc
			if doctype == "Promotion Statement":
				return statement
			if doctype == "Academic Year" and name == "2025-2026":
				return frappe._dict({"year_end_date": "2026-07-15"})
			raise AssertionError(f"unexpected get_doc: {doctype} {name}")

		def fake_db_get_value(doctype, filters, field, order_by=None):
			if doctype == "School Grade" and field == "level":
				return levels.get(filters)
			if doctype == "School Grade" and filters == {"level": "Senior High School"}:
				return "Grade 10"
			if doctype == "Student" and field == "student_name":
				return "Bendu Tarpeh"
			raise AssertionError(f"unexpected db.get_value: {doctype} {filters} {field}")

		def fake_db_exists(doctype, name=None):
			return False

		def fake_get_all(doctype, filters=None, fields=None, order_by=None, limit=None):
			if doctype == "Academic Year":
				return [{"name": "2026-2027", "year_start_date": "2026-09-01"}]
			return []

		with (
			mock.patch("frappe.get_doc", side_effect=fake_get_doc),
			mock.patch("frappe.db.get_value", side_effect=fake_db_get_value),
			mock.patch("frappe.db.exists", side_effect=fake_db_exists),
			mock.patch("frappe.get_all", side_effect=fake_get_all),
		):
			payload = enroll.reenroll_next_level("PS-0001")

		self.assertEqual(payload["doctype"], "Program Enrollment")
		self.assertEqual(payload["student"], "STU-009")
		self.assertEqual(payload["academic_year"], "2026-2027")
		self.assertEqual(payload["program"], "Senior High School")
		self.assertEqual(payload["student_batch_name"], "Grade 10 - 2026-2027")
		self.assertEqual(payload["student_name"], "Bendu Tarpeh")
		self.assertEqual(len(inserted), 1)
		self.assertEqual(inserted[0].name, "Grade 10 - 2026-2027")

	def test_reenroll_next_level_rejects_non_graduated(self):
		statement = frappe._dict(
			{
				"outcome": "Promoted",
				"student": "STU-009",
				"current_program": "Grade 8",
				"academic_year": "2025-2026",
			}
		)

		def fake_get_doc(doctype, name=None):
			if isinstance(doctype, dict):
				return None
			if doctype == "Promotion Statement":
				return statement
			raise AssertionError(f"unexpected get_doc: {doctype} {name}")

		with mock.patch("frappe.get_doc", side_effect=fake_get_doc):
			with self.assertRaises(frappe.ValidationError):
				enroll.reenroll_next_level("PS-0002")

	def test_reenroll_next_level_rejects_final_level(self):
		statement = frappe._dict(
			{
				"outcome": "Graduated",
				"student": "STU-012",
				"current_program": "Grade 12",
				"academic_year": "2025-2026",
			}
		)

		def fake_get_doc(doctype, name=None):
			if doctype == "Promotion Statement":
				return statement
			raise AssertionError(f"unexpected get_doc: {doctype} {name}")

		def fake_db_get_value(doctype, filters, field, order_by=None):
			if doctype == "School Grade" and field == "level":
				return "Senior High School"
			raise AssertionError(f"unexpected db.get_value: {doctype} {filters} {field}")

		with (
			mock.patch("frappe.get_doc", side_effect=fake_get_doc),
			mock.patch("frappe.db.get_value", side_effect=fake_db_get_value),
		):
			with self.assertRaises(frappe.ValidationError):
				enroll.reenroll_next_level("PS-0003")
