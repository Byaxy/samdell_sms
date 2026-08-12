import io

import pyqrcode
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, flt, add_days


class StudentIDCard(Document):
	def before_insert(self):
		if not self.card_number:
			self.card_number = self._next_card_number()

	def validate(self):
		if not self.issued_date:
			self.issued_date = today()
		if not self.expiry_date:
			self.expiry_date = self._default_expiry()
		if not self.qr_code:
			self.qr_code = self._generate_qr()

	def _next_card_number(self):
		year = frappe.utils.now_datetime().strftime("%Y")
		count = frappe.db.count(
			"Student ID Card",
			filters={
				"card_number": ["like", f"JBS-{year}-%"],
				"name": ["!=", self.name or ""],
			},
		)
		return f"JBS-{year}-{count + 1:05d}"

	def _default_expiry(self):
		academic_years = frappe.get_all(
			"Academic Year",
			fields=["year_start_date", "year_end_date"],
			order_by="year_start_date desc",
			limit=1,
		)
		if academic_years and academic_years[0].year_end_date:
			return academic_years[0].year_end_date
		return str(add_days(today(), 365))

	def _generate_qr(self):
		if not self.card_number:
			return None
		qr = pyqrcode.create(self.card_number)
		buf = io.BytesIO()
		qr.png(buf, scale=4)
		content = buf.getvalue()
		file_doc = frappe.get_doc({
			"doctype": "File",
			"file_name": f"qr_{self.card_number}.png",
			"attached_to_doctype": self.doctype,
			"attached_to_name": self.name,
			"is_private": 0,
			"content": content,
		})
		file_doc.save(ignore_permissions=True)
		return file_doc.file_url
