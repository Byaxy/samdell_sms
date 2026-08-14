// Copyright (c) 2026, Charles Byakutaga and contributors
// For license information, please see license.txt

frappe.ui.form.on("Promotion Statement", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.outcome !== "Graduated") {
			return;
		}

		frm.add_custom_button(__("Re-Enroll Next Level"), () => {
			frm.call({
				method: "samdell_sms.api.enroll.reenroll_next_level",
				args: { promotion_statement_name: frm.doc.name },
				callback(r) {
					if (!r.message) {
						return;
					}
					let prefill = r.message;
					frappe.msgprint(
						__(
							"Preparing enrollment for {0} in {1} ({2} - {3}). Check and Save.",
							[prefill.student_name, prefill.academic_year, prefill.program, prefill.student_batch_name]
						)
					);
					frappe.model.with_doctype("Program Enrollment", () => {
						frappe.new_doc("Program Enrollment", prefill);
					});
				},
			});
		}).addClass("btn-primary");
	},
});