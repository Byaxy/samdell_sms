// Copyright (c) 2026, Charles Byakutaga and contributors
// For license information, please see license.txt

frappe.ui.form.on("Master Grade Sheet", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Pull Results"), () => {
				frm.call({
					method: "samdell_sms.api.grade_sheet.pull_results",
					args: { master_grade_sheet_name: frm.doc.name },
					callback(r) {
						if (r.message === undefined) {
							return;
						}
						frappe.msgprint(
							__("Pulled results for {0} students.", [r.message])
						);
						frm.reload_doc();
					},
				});
			}).addClass("btn-primary");
		}
	},
});
