import frappe
from frappe.model.document import Document
from frappe.utils import flt


class NationalExamRecord(Document):
	def validate(self):
		self._derive_grades()
		self._compute_overall_average()

	def _derive_grades(self):
		scale_name = None
		if "grading_scale" in frappe.get_meta("Education Settings").get_valid_columns():
			scale_name = frappe.db.get_single_value("Education Settings", "grading_scale")
		if not scale_name:
			scale_name = frappe.db.get_value("Grading Scale", {}, "name")
		if not scale_name:
			return
		intervals = frappe.get_all(
			"Grading Scale Interval",
			filters={"parent": scale_name},
			fields=["grade_code", "threshold"],
			order_by="threshold desc",
		)
		for row in self.subject_scores:
			if row.score is None or not intervals:
				continue
			row.grade = next(
				(i.grade_code for i in intervals if flt(row.score) >= flt(i.threshold)),
				"F",
			)

	def _compute_overall_average(self):
		scores = [flt(r.score) for r in self.subject_scores if r.score is not None]
		self.overall_average = flt(sum(scores) / len(scores), 1) if scores else None
