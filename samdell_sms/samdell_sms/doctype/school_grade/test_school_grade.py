import frappe
from frappe.tests import UnitTestCase


class TestSchoolGrade(UnitTestCase):
	def test_grade_creation(self):
		doc = frappe._dict(
			{"doctype": "School Grade", "grade_name": "Grade 5", "level": "Elementary", "sort_order": 8}
		)
		self.assertEqual(doc.grade_name, "Grade 5")
		self.assertEqual(doc.level, "Elementary")

	def test_level_options(self):
		self.assertIn("Elementary", "Early Childhood\nElementary\nJunior High School\nSenior High School")
