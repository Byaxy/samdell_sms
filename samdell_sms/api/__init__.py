import frappe

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


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_theme():
	cached = frappe.cache().get_value(CACHE_KEY)
	if cached:
		return cached

	saved = frappe.db.get_singles_dict("Theme") or {}
	config = _build_config(saved)
	frappe.cache().set_value(CACHE_KEY, config, expires_in_sec=86400)
	return config


def _sanitize_color(value):
	if not value:
		return value
	value = value.strip()
	if value and not value.startswith("#"):
		return f"#{value}"
	return value


def _build_config(saved):
	def v(fieldname):
		raw = saved.get(fieldname) or DEFAULTS.get(fieldname, "")
		return _sanitize_color(raw)

	return {
		"primaryColor":        v("primary_color"),
		"primaryHover":        v("primary_hover"),
		"dangerColor":         v("danger_color"),
		"dangerHover":         v("danger_hover"),
		"accentColor":         v("accent_color"),
		"sidebarBg":           v("sidebar_background"),
		"sidebarText":         v("sidebar_text_color"),
		"sidebarActiveItemBg": v("active_item_background"),
		"sidebarActiveText":   v("active_item_text"),
		"navbarBg":            v("navbar_background"),
		"navbarText":          v("navbar_text_color"),
		"navbarIcon":          v("navbar_icon_color"),
		"pageHeadBg":          v("page_head_bg"),
		"pageHeadText":        v("page_head_text"),
		"tableHeaderBg":       v("table_header_bg"),
		"tableHeaderText":     v("table_header_text"),
		"tableEvenBg":         v("even_row_bg"),
		"tableRowHoverBg":     v("table_row_hover_bg"),
		"selectRowHoverBg":    v("selectdropdown_row_hover_bg"),
		"btnPrimaryBg":        v("primary_button_bg"),
		"btnPrimaryHover":     v("primary_button_hover"),
		"btnPrimaryText":      v("primary_button_text"),
		"btnDangerBg":         v("danger_button_bg"),
		"btnDangerHover":      v("danger_button_hover"),
	}
