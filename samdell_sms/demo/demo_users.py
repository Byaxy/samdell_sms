"""Demo role-based logins for the stakeholder walkthrough.

Creates (idempotently) the role users referenced by the demo guide, sets a known
password on every demo user (students included), and links the `user` field on
Student / Guardian records so Frappe's website-user redirect to /portal fires.

Run from the bench:
	bench --site samdell-sms.localhost execute samdell_sms.demo.demo_users.run
"""

import frappe

DEMO_PASSWORD = "Samdell@2026"

ROLE_USERS = {
	"principal@samdell.school": {
		"full_name": "Head Teacher — SAMDELL SMS",
		"roles": ["Principal"],
	},
	"registrar@samdell.school": {
		"full_name": "Registrar — SAMDELL SMS",
		"roles": ["Registrar", "Front Desk"],
	},
	"teacher@samdell.school": {
		"full_name": "Class Teacher — SAMDELL SMS",
		"roles": ["Instructor"],
	},
	"accounts@samdell.school": {
		"full_name": "Accounts Officer — SAMDELL SMS",
		"roles": ["Accounts User"],
	},
	"frontdesk@samdell.school": {
		"full_name": "Front Desk Officer — SAMDELL SMS",
		"roles": ["Front Desk"],
	},
}

DEFAULT_HOME_ROLE = "Principal"


def run():
	_clear_linked_users()
	for email, cfg in ROLE_USERS.items():
		_ensure_user(email, cfg["full_name"], cfg["roles"], DEMO_PASSWORD)

	_ensure_guardian_user(DEMO_PASSWORD)
	_link_student_users()
	_link_guardian_users()
	_ensure_teacher_employee()

	frappe.db.commit()
	print("Demo users ready.")
	return True


def _clear_linked_users():
	frappe.db.set_value("Student", {"user": ["is", "set"]}, "user", None)
	frappe.db.set_value("Guardian", {"user": ["is", "set"]}, "user", None)


def _ensure_user(email, full_name, roles, password):
	user = frappe.get_doc("User", email) if frappe.db.exists("User", email) else frappe.new_doc("User")
	user.update(
		{
			"email": email,
			"first_name": full_name,
			"send_welcome_email": 0,
			"enabled": 1,
		}
	)
	user.flags.ignore_permissions = True
	user.save(ignore_permissions=True)
	user.new_password = password
	user.save(ignore_permissions=True)
	user.add_roles(*roles)
	if "LMS Student" in user.get("roles"):
		user.remove_roles("LMS Student")
	return user.name


def _ensure_guardian_user(password):
	guardian = frappe.get_all("Guardian", fields=["name", "guardian_name", "email_address"], limit=1)
	if not guardian:
		return
	g = guardian[0]
	email = g.get("email_address") or "guardian.demo@samdell.school"
	user = frappe.get_doc("User", email) if frappe.db.exists("User", email) else frappe.new_doc("User")
	user.update(
		{
			"email": email,
			"first_name": g.get("guardian_name") or "Guardian — SAMDELL SMS",
			"send_welcome_email": 0,
			"enabled": 1,
		}
	)
	user.flags.ignore_permissions = True
	user.save(ignore_permissions=True)
	user.new_password = password
	user.save(ignore_permissions=True)
	user.add_roles("Guardian")
	frappe.db.set_value("Guardian", g["name"], "user", user.name)


def _link_student_users():
	students = frappe.get_all("Student", fields=["name", "student_email_id"])
	updated = 0
	for s in students:
		if not s.get("student_email_id"):
			continue
		user = s["student_email_id"]
		if not frappe.db.exists("User", user):
			_ensure_user(
				user,
				s["student_email_id"].split("@")[0].replace(".", " ").title(),
				["Student"],
				DEMO_PASSWORD,
			)
		else:
			_ensure_user(user, user.split("@")[0].replace(".", " ").title(), ["Student"], DEMO_PASSWORD)
		frappe.db.set_value("Student", s["name"], "user", user)
		updated += 1
	print(f"Linked {updated} students to portal users.")


def _link_guardian_users():
	guardians = frappe.get_all("Guardian", fields=["name", "email_address", "user"])
	updated = 0
	for g in guardians:
		if g.get("user"):
			continue
		email = g.get("email_address")
		if not email:
			continue
		user = frappe.get_doc("User", email) if frappe.db.exists("User", email) else frappe.new_doc("User")
		user.update(
			{
				"email": email,
				"first_name": frappe.db.get_value("Guardian", g["name"], "guardian_name") or email,
				"send_welcome_email": 0,
				"enabled": 1,
			}
		)
		user.flags.ignore_permissions = True
		user.save(ignore_permissions=True)
		user.new_password = DEMO_PASSWORD
		user.save(ignore_permissions=True)
		user.add_roles("Guardian")
		frappe.db.set_value("Guardian", g["name"], "user", user.name)
		updated += 1
	print(f"Linked {updated} guardians to portal users.")


def _ensure_teacher_employee():
	if frappe.db.exists("Employee", {"first_name": "Class Teacher"}):
		return
	company = frappe.db.get_value("Company", filters={}, fieldname="name")
	if not frappe.db.exists("Designation", "Teacher"):
		frappe.get_doc({"doctype": "Designation", "designation_name": "Teacher"}).insert(
			ignore_permissions=True
		)
	employee = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": "Class Teacher",
			"last_name": "SAMDELL SMS",
			"company": company,
			"status": "Active",
			"gender": "Female",
			"date_of_birth": "1990-01-15",
			"date_of_joining": "2025-09-01",
			"designation": "Teacher",
		}
	)
	employee.insert(ignore_permissions=True)
