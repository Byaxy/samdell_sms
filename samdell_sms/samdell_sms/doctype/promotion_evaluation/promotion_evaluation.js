// Copyright (c) 2026, Charles Byakutaga and contributors
// For license information, please see license.txt

frappe.ui.form.on("Promotion Evaluation", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.academic_year) {
			return;
		}

		frm.add_custom_button(__("Evaluate Promotions"), () => {
			frm.call({
				method: "samdell_sms.api.promotion.evaluate_promotions",
				args: { academic_year: frm.doc.academic_year },
				callback(r) {
					if (r.message === undefined) {
						return;
					}
					frappe.msgprint(
						__("Created or updated {0} promotion evaluation(s).", [r.message])
					);
					frappe.set_route("List", "Promotion Evaluation", {
						academic_year: frm.doc.academic_year,
					});
				},
			});
		});

		frm.add_custom_button(__("Generate Statements"), () => {
			frm.call({
				method: "samdell_sms.api.promotion.generate_promotion_statements",
				args: { academic_year: frm.doc.academic_year },
				callback(r) {
					if (r.message === undefined) {
						return;
					}
					frappe.msgprint(
						__("Generated {0} promotion statement(s).", [r.message])
					);
					frappe.set_route("List", "Promotion Statement", {
						academic_year: frm.doc.academic_year,
					});
				},
			});
		}).addClass("btn-primary");
	},
});