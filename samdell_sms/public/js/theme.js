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
		this.applyDesktopPalette();
		this.recolorDeskIcons();
		this.recolorAppSwitcher();
		this.subscribeRealtime();
		this.setupMutationObserver();
	}

	async fetchAndApply() {
		try {
			var result = await frappe.call({
				method: "samdell_sms.api.get_theme",
				type: "GET",
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
		this.applyDesktopPalette();
		this.recolorDeskIcons();
		this.recolorAppSwitcher();
	}

	applyDesktopPalette() {
		if (!window.frappe || !frappe.utils) return;
		var primary = this.primaryColor();
		frappe.utils.desktop_pallete = { blue: primary, gray: primary };
	}

	primaryColor() {
		var value = getComputedStyle(document.documentElement)
			.getPropertyValue("--app-primary")
			.trim();
		return value || "#6B3A2A";
	}

	accentColor() {
		var value = getComputedStyle(document.documentElement)
			.getPropertyValue("--app-accent-color")
			.trim();
		return value || "#C5A028";
	}

	recolorDeskIcons() {
		if (!window.fetch) return;
		var self = this;
		var primary = this.primaryColor();
		var accent = this.accentColor();
		var targets = document.querySelectorAll(
			'.desktop-icon .icon-container img.app-icon, .sidebar-header img.logo, img[src*="icons/desktop_icons/"]'
		);
		targets.forEach(function (img) {
			if (img.closest && img.closest(".dropdown-menu-item")) return;
			var src = img.getAttribute("src") || img.src || "";
			if (src.indexOf("data:") === 0) return;
			if (src.indexOf(".svg") === -1 && src.indexOf("icons/desktop_icons") === -1) return;
			self.recolorImg(img, src, primary, accent);
		});
	}

	recolorImg(img, src, primary, accent) {
		var self = this;
		var apply = function (svgText) {
			if (!svgText) return;
			var rewritten = self.rewriteFills(svgText, primary, accent);
			img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(rewritten);
		};
		if (this.svgCache && this.svgCache[src]) {
			apply(this.svgCache[src]);
			return;
		}
		fetch(src)
			.then(function (response) {
				return response.text();
			})
			.then(function (text) {
				if (!self.svgCache) self.svgCache = {};
				self.svgCache[src] = text;
				apply(text);
			})
			.catch(function () {});
	}

	recolorAppSwitcher() {
		if (!window.fetch) return;
		var self = this;
		var primary = this.primaryColor();
		var targets = document.querySelectorAll(
			'.sidebar-header img[src*="icons/desktop_icons/"], .frappe-menu img[src*="icons/desktop_icons/"], .dropdown-menu-item img[src*="icons/desktop_icons/"]'
		);
		targets.forEach(function (img) {
			var src = img.getAttribute("src") || img.src || "";
			if (src.indexOf("data:") === 0) return;
			if (src.indexOf(".svg") === -1) return;
			self.recolorImgWhite(img, src, primary);
		});
	}

	recolorImgWhite(img, src, primary) {
		var self = this;
		var apply = function (svgText) {
			if (!svgText) return;
			var rewritten = self.rewriteFillsWhite(svgText, primary);
			img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(rewritten);
		};
		if (this.svgCache && this.svgCache[src]) {
			apply(this.svgCache[src]);
			return;
		}
		fetch(src)
			.then(function (response) {
				return response.text();
			})
			.then(function (text) {
				if (!self.svgCache) self.svgCache = {};
				self.svgCache[src] = text;
				apply(text);
			})
			.catch(function () {});
	}

	rewriteFillsWhite(svg, primary) {
		var primaryMap = ["#0289F7", "#004880", "#0E7159", "#06B58B", "#7B808A"];
		var out = svg;
		primaryMap.forEach(function (hex) {
			out = out.split(hex).join(primary);
			out = out.split(hex.toLowerCase()).join(primary);
		});
		return out;
	}

	rewriteFills(svg, primary, accent) {
		var primaryMap = ["#0289F7", "#004880", "#0E7159", "#06B58B", "#7B808A"];
		var out = svg;
		primaryMap.forEach(function (hex) {
			out = out.split(hex).join(primary);
			out = out.split(hex.toLowerCase()).join(primary);
		});
		out = out.split('fill="white"').join('fill="' + accent + '"');
		out = out.split('stroke="white"').join('stroke="' + accent + '"');
		["#0981E3", "#FFFFFF", "#E7E5F9"].forEach(function (hex) {
			out = out.split(hex).join(accent);
		});
		return out;
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
				if (
					(node.classList &&
						(node.classList.contains("desktop-icon") ||
							node.classList.contains("desktop-container") ||
							node.classList.contains("sidebar-header") ||
							node.classList.contains("sidebar-header-menu") ||
							node.classList.contains("frappe-menu") ||
							node.classList.contains("dropdown-menu-item"))) ||
					(node.querySelector &&
						(node.querySelector(".desktop-icon") ||
							node.querySelector(".sidebar-header") ||
							node.querySelector(".sidebar-header-menu") ||
							node.querySelector(".frappe-menu img[src*='icons/desktop_icons/']")))
				) {
					self.recolorDeskIcons();
					self.recolorAppSwitcher();
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
