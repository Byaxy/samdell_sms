import frappe
from frappe.model.document import Document

CACHE_KEY = "app_desk_theme"

DEFAULTS = {
	"primary_color":                 "#6B3A2A",
	"primary_hover":                 "#542C1F",
	"danger_color":                  "#DC2626",
	"danger_hover":                  "#B91C1C",
	"accent_color":                  "#C5A028",
	"sidebar_background":            "#F5F0EB",
	"sidebar_text_color":            "#5C2E16",
	"active_item_background":        "#6B3A2A",
	"active_item_text":              "#C5A028",
	"navbar_background":             "#6B3A2A",
	"navbar_text_color":             "#FFFFFF",
	"navbar_icon_color":             "#FFFFFF",
	"page_head_bg":                  "#F5F0EB",
	"page_head_text":                "#5C2E16",
	"table_header_bg":               "#6B3A2A",
	"table_header_text":             "#FFFFFF",
	"even_row_bg":                   "#FDF8F0",
	"table_row_hover_bg":            "#F5E6C8",
	"selectdropdown_row_hover_bg":   "#F5E6C8",
	"primary_button_bg":             "#6B3A2A",
	"primary_button_hover":          "#542C1F",
	"primary_button_text":           "#FFFFFF",
	"danger_button_bg":              "#DC2626",
	"danger_button_hover":           "#B91C1C",
}


class Theme(Document):

	def on_update(self):
		frappe.cache().delete_value(CACHE_KEY)
		frappe.publish_realtime("app_theme_updated", message={"reload": True})

	@frappe.whitelist()
	def reset_to_defaults(self):
		for fieldname, value in DEFAULTS.items():
			self.set(fieldname, value)
		self.save()
		frappe.cache().delete_value(CACHE_KEY)
