import frappe

from samdell_sms.api.branding import get_school_abbr


def get_context(context):
	branding = frappe.get_single("School Branding Settings")
	context.branding = branding
	context.abbr = get_school_abbr()

	context.announcements = frappe.get_all(
		"School Announcement",
		fields=["title", "body", "publish_date"],
		order_by="publish_date desc",
		limit=3,
	)
	context.school_levels = [level.strip() for level in (branding.school_levels or "").split("\n") if level.strip()]

	context.no_cache = 1
	return context
