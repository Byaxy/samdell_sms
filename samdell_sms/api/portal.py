import frappe


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_branding():
	branding = frappe.get_single("School Branding Settings")
	return {
		"school_name": branding.school_name or "",
		"school_motto": branding.school_motto or "",
		"tagline": branding.tagline or "",
		"logo": branding.logo or "",
		"primary_color": branding.primary_color or "#6B3A2A",
		"secondary_color": branding.secondary_color or "#C5A028",
		"accent_color": branding.accent_color or "#C5A028",
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
