import unittest.mock as mock

import frappe
from frappe.tests import UnitTestCase

import samdell_sms.api.promotion as promotion


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
			if doctype == "Program":
				return ["Grade 1", "Grade 2", "Grade 3"]
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

		policy = frappe._dict({"early_grades_start": "Grade 1", "early_grades_end": "Grade 3"})
		with (
			mock.patch("frappe.get_all", side_effect=fake_get_all),
			mock.patch("frappe.get_doc", side_effect=fake_get_doc),
		):
			average = promotion._get_early_grades_average("STU-001", policy)

		self.assertEqual(average, 90.0)
		self.assertEqual(captured["enrollment_filters"]["program"], ["in", ["Grade 1", "Grade 2", "Grade 3"]])
		self.assertEqual(captured["enrollment_filters"]["docstatus"], 1)
		self.assertEqual(captured["term_filters"]["academic_year"], ["in", ["AY-2024", "AY-2025"]])

	def test_early_grades_average_returns_zero_without_range(self):
		policy = frappe._dict({"early_grades_start": "", "early_grades_end": ""})
		with mock.patch("frappe.get_all", side_effect=AssertionError("get_all must not run")):
			self.assertEqual(promotion._get_early_grades_average("STU-001", policy), 0.0)

	def test_early_grades_average_returns_zero_without_enrollments(self):
		def fake_get_all(doctype, filters=None, fields=None, pluck=None, order_by=None, limit=None):
			if doctype == "Program":
				return ["Grade 1", "Grade 2"]
			if doctype == "Program Enrollment":
				return []
			return []

		policy = frappe._dict({"early_grades_start": "Grade 1", "early_grades_end": "Grade 2"})
		with mock.patch("frappe.get_all", side_effect=fake_get_all):
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
