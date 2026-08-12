import frappe

from samdell_sms.api.branding import get_school_abbr


def get_context(context):
	from frappe.www.login import get_context as original_get_context

	original_get_context(context)

	branding = frappe.get_single("School Branding Settings")
	context.branding = branding
	context.abbr = get_school_abbr()
	return context
