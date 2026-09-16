frappe.listview_settings["Master Grade Sheet"] = {
	add_fields: ["workflow_state"],
	get_indicator(doc) {
		const colors = {
			Draft: "grey",
			Submitted: "blue",
			Reviewed: "orange",
			Approved: "green",
			Released: "dark green",
		};
		const state = doc.workflow_state || "Draft";
		return [__(state), colors[state] || "grey", `workflow_state,=,${state}`];
	},
};
