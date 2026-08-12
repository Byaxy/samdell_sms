import frappe

ROLE_HOME_PAGE = [
	("Principal", "desk/operations-center"),
	("HR Manager", "desk/hr"),
	("Accounts User", "desk/accounts"),
	("Registrar", "desk/registrar"),
	("Instructor", "desk/instructor"),
	("Front Desk", "desk/front-desk"),
	("Discipline Officer", "desk/discipline"),
	("Librarian", "desk/library"),
	("Transport Coordinator", "desk/transport"),
]


def get_website_user_home_page(user):
	if frappe.db.exists("Student", {"user": user}) or frappe.db.exists("Guardian", {"user": user}):
		return "/portal"

	roles = frappe.get_roles()
	if "System Manager" in roles:
		return "desk"

	for role, home in ROLE_HOME_PAGE:
		if role in roles:
			return home
