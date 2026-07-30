(function replaceLoaderLogo() {
	function getLogoSrc() {
		if (window.frappe && frappe.boot && frappe.boot.app_logo_url)
			return frappe.boot.app_logo_url;
		var loginLogo = document.querySelector(".page-card-head img");
		if (loginLogo && loginLogo.src) return loginLogo.src;
		return "/files/app-logo.png";
	}
	function swapLogo() {
		var freeze = document.getElementById("freeze")
			|| document.querySelector(".page-loading-indicator");
		if (!freeze) return;
		freeze.querySelectorAll("svg").forEach(function (s) { s.style.display = "none"; });
		var img = freeze.querySelector("img");
		if (!img) {
			img = document.createElement("img");
			img.alt = "Loading";
			freeze.insertBefore(img, freeze.firstChild);
		}
		img.src = getLogoSrc();
		img.style.cssText = "width:110px;height:110px;object-fit:contain;display:block;margin:0 auto 20px;";
	}
	swapLogo();
	if (document.readyState === "loading")
		document.addEventListener("DOMContentLoaded", swapLogo);
})();

class Theme {
	constructor() {
		this.CACHE_KEY = "app_theme_v1";
		this.CSS_VAR_MAP = {
			"--app-primary":             "primaryColor",
			"--app-primary-hover":       "primaryHover",
			"--app-danger":              "dangerColor",
			"--app-danger-hover":        "dangerHover",
			"--app-accent-color":        "accentColor",
			"--app-sidebar-bg":          "sidebarBg",
			"--app-sidebar-text":        "sidebarText",
			"--app-sidebar-active-bg":   "sidebarActiveItemBg",
			"--app-sidebar-active-text": "sidebarActiveText",
			"--app-navbar-bg":           "navbarBg",
			"--app-navbar-text":         "navbarText",
			"--app-navbar-icon":         "navbarIcon",
			"--app-page-head-bg":        "pageHeadBg",
			"--app-page-head-text":      "pageHeadText",
			"--app-table-header-bg":     "tableHeaderBg",
			"--app-table-header-text":   "tableHeaderText",
			"--app-table-even-bg":       "tableEvenBg",
			"--app-table-row-hover-bg":  "tableRowHoverBg",
			"--app-select-row-hover-bg": "selectRowHoverBg",
			"--app-btn-primary-bg":      "btnPrimaryBg",
			"--app-btn-primary-hover":   "btnPrimaryHover",
			"--app-btn-primary-text":    "btnPrimaryText",
			"--app-btn-danger-bg":       "btnDangerBg",
			"--app-btn-danger-hover":    "btnDangerHover",
		};
	}

	async init() {
		var cached = this.loadCache();
		if (cached) this.applyConfig(cached);
		await this.fetchAndApply();
		this.subscribeRealtime();
		this.setupMutationObserver();
	}

	async fetchAndApply() {
		try {
			var result = await frappe.call({
				method: "samdell_sms.api.get_theme",
			});
			if (result && result.message) {
				this.applyConfig(result.message);
				this.saveCache(result.message);
			}
		} catch (err) {
			console.warn("[Theme] Could not load theme config.", err);
		}
	}

	applyConfig(config) {
		var root = document.documentElement;
		for (var cssVar in this.CSS_VAR_MAP) {
			if (!this.CSS_VAR_MAP.hasOwnProperty(cssVar)) continue;
			var configKey = this.CSS_VAR_MAP[cssVar];
			var value = config[configKey];
			if (value) root.style.setProperty(cssVar, value);
		}
	}

	subscribeRealtime() {
		if (!window.frappe || !frappe.realtime) return;
		frappe.realtime.on("app_theme_updated", function () {
			this.clearCache();
			window.location.reload();
		}.bind(this));
	}

	setupMutationObserver() {
		if (!window.MutationObserver) return;
		var self = this;
		var observer = new MutationObserver(function (mutations) {
			mutations.forEach(function (mutation) {
				mutation.addedNodes.forEach(function (node) {
					if (node.nodeType !== Node.ELEMENT_NODE) return;
					if (node.id === "freeze" || (node.classList && node.classList.contains("page-loading-indicator"))) {
						var logoSrc = (window.frappe && frappe.boot && frappe.boot.app_logo_url) || "/files/app-logo.png";
						node.querySelectorAll("svg").forEach(function (s) { s.style.display = "none"; });
						var img = node.querySelector("img");
						if (!img) {
							img = document.createElement("img");
							img.alt = "Loading";
							node.insertBefore(img, node.firstChild);
						}
						img.src = logoSrc;
						img.style.cssText = "width:110px;height:110px;object-fit:contain;display:block;margin:0 auto 20px;";
					}
				});
			});
		});
		observer.observe(document.body, { childList: true, subtree: true });
	}

	loadCache() {
		if (frappe.boot && frappe.boot.developer_mode) return null;
		try {
			var raw = localStorage.getItem(this.CACHE_KEY);
			return raw ? JSON.parse(raw) : null;
		} catch (e) {
			return null;
		}
	}

	saveCache(config) {
		try { localStorage.setItem(this.CACHE_KEY, JSON.stringify(config)); } catch (e) {}
	}

	clearCache() {
		try { localStorage.removeItem(this.CACHE_KEY); } catch (e) {}
	}

	applyAndReload() {
		this.clearCache();
		window.location.reload();
	}
}

function initTheme() {
	window.Theme = new Theme();
	window.Theme.init();
}
if (!window.Theme) {
	if (document.readyState === "loading")
		document.addEventListener("DOMContentLoaded", initTheme);
	else initTheme();
}
