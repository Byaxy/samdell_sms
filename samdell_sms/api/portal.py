import frappe

from samdell_sms.api.branding import get_school_colors


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_branding():
	branding = frappe.get_single("School Branding Settings")
	colors = get_school_colors()
	return {
		"school_name": branding.school_name or "",
		"school_motto": branding.school_motto or "",
		"tagline": branding.tagline or "",
		"logo": branding.logo or "",
		"primary_color": colors["primary_color"],
		"secondary_color": colors["accent_color"],
		"accent_color": colors["accent_color"],
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_enquiry(full_name, phone, email, message):
	enquiry = frappe.get_doc({
		"doctype": "Website Enquiry",
		"full_name": full_name,
		"phone": phone,
		"email": email,
		"message": message,
		"submitted_at": frappe.utils.now_datetime(),
	})
	enquiry.insert(ignore_permissions=True)
	return {"name": enquiry.name}
