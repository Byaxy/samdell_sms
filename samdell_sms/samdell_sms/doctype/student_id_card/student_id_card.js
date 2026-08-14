// Copyright (c) 2026, Charles Byakutaga and contributors
// For license information, please see license.txt

frappe.ui.form.on("Student ID Card", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status !== "Active") {
			return;
		}

		frm.add_custom_button(__("Reissue Card"), () => {
			frappe.confirm(
				__("Mark this card as Lost and issue a new card to the student?"),
				() => {
					frm.call({
						method: "samdell_sms.api.id_card.reissue_card",
						args: { id_card_name: frm.doc.name },
						callback(r) {
							if (!r.message) {
								return;
							}
							frappe.msgprint(
								__(
									"Card {0} marked as Lost. New card {1} issued as {2}.",
									[r.message.old_card, r.message.new_card, r.message.card_number]
								)
							);
							frm.reload_doc();
						},
					});
				},
			);
		});
	},
});