frappe.ui.form.on("Theme", {
	refresh(frm) {
		frm.add_custom_button(__("Apply Theme"), () => {
			frm.save().then(() => {
				if (window.Theme) {
					window.Theme.applyAndReload();
				} else {
					localStorage.removeItem("app_theme_v1");
					window.location.reload();
				}
			});
		}, __("Actions"));

		frm.add_custom_button(__("Reset to Defaults"), () => {
			frappe.confirm(
				__("Reset all colors to defaults? This cannot be undone."),
				() => {
					frm.call("reset_to_defaults")
						.then(() => {
							frappe.show_alert({
								message: __("Theme reset to defaults."),
								indicator: "green",
							});
							localStorage.removeItem("app_theme_v1");
							setTimeout(() => window.location.reload(), 500);
						})
						.catch(() => frappe.msgprint(__("Reset failed. Please try again.")));
				},
			);
		}, __("Actions"));

		if (!frm.doc.__islocal) {
			frm.set_intro(
				__("Edit colors in the tabs below, then click <b>Actions → Apply Theme</b> to save and apply."),
				"blue",
			);
		}
	},
});
