import frappe


def get_school_abbr() -> str:
	"""Return the school's display abbreviation for the text logo mark.

	Prefers the ERPNext Company abbreviation when the default company is named
	exactly like the school (e.g. Company "SAMDELL MEMORIAL SCHOOL" -> "SMS").
	Otherwise the abbreviation is generated from the school name the same way
	Frappe does, first letters of each word ("Samdell Memorial School" -> "SM").
	"""
	school_name = (frappe.get_single("School Branding Settings").school_name or "").strip()
	company = frappe.defaults.get_defaults().get("company")
	if company and frappe.db.exists("Company", company):
		doc = frappe.get_cached_doc("Company", company)
		if doc.abbr and doc.name == school_name:
			return doc.abbr
	return frappe.utils.get_abbr(school_name or "SM", max_len=2)
