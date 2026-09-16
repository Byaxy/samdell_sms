"""Print Format fixtures for the demo sprint.

Builds the four stakeholder-facing print formats as native Print Format docs:
- Report Card (Master Grade Sheet) - subject grid joined from Assessment Results
- Promotion Statement (Certificate of Promotion) - §3.4 literal layout
- Fee Payment Receipt (Payment Entry)
- ECE Progress Report (Early Childhood Progress Report)

All are custom Jinja formats rendered server-side by frappe/www/printview.py,
which exposes `doc` and the full `frappe` module to the template.
"""

import frappe
from frappe.utils import flt

from samdell_sms.api.branding import get_school_colors

PERIODS = ["Period 1", "Period 2", "Period 3", "Period 4", "Period 5", "Period 6"]


def _ensure_print_formats():
	_ensure_print_format(
		"Report Card",
		"Master Grade Sheet",
		REPORT_CARD_TEMPLATE,
	)
	_ensure_print_format(
		"Promotion Statement",
		"Promotion Statement",
		PROMOTION_STATEMENT_TEMPLATE,
	)
	_ensure_print_format(
		"Fee Payment Receipt",
		"Payment Entry",
		FEE_PAYMENT_RECEIPT_TEMPLATE,
	)
	_ensure_print_format(
		"ECE Progress Report",
		"Early Childhood Progress Report",
		ECE_PROGRESS_REPORT_TEMPLATE,
	)


def _ensure_print_format(name, doc_type, html):
	existing = frappe.db.get_value("Print Format", {"name": name, "doc_type": doc_type}, "name")
	if existing:
		pf = frappe.get_doc("Print Format", existing)
		if pf.html != html:
			pf.html = html
			pf.save(ignore_permissions=True)
		return name
	frappe.get_doc(
		{
			"doctype": "Print Format",
			"name": name,
			"doc_type": doc_type,
			"module": "SAMDELL SMS",
			"custom_format": 1,
			"print_format_type": "Jinja",
			"html": html,
			"margin_top": 12,
			"margin_bottom": 12,
			"margin_left": 12,
			"margin_right": 12,
		}
	).insert(ignore_permissions=True)
	return name


def get_report_card_rows(mgs, student):
	"""Subject-level scores for one student, joined live from Assessment Results.

	Returns a list of {subject, periods: [6], exam, average}. Periods and exam are
	the raw percentages; average = (periods avg x 0.75) + (exam x 0.25).
	"""
	plans = frappe.get_all(
		"Assessment Plan",
		filters={"student_group": mgs.student_group, "academic_term": mgs.academic_term},
		fields=["name", "course", "assessment_group"],
		order_by="idx",
	)
	group_names = {}
	for p in plans:
		if p.assessment_group:
			group_names[p.name] = (
				frappe.db.get_value("Assessment Group", p.assessment_group, "assessment_group_name") or ""
			)

	results = frappe.get_all(
		"Assessment Result",
		filters={"student": student, "assessment_plan": ["in", [p.name for p in plans]]},
		fields=["assessment_plan", "total_score", "maximum_score"],
	)
	by_plan = {r.assessment_plan: r for r in results}

	course_map = {}
	for p in plans:
		gn = (group_names.get(p.name) or "").lower()
		if "exam" in gn:
			key = ("exam", p.course)
		else:
			key = ("period", p.course)
		course_map.setdefault(p.course, []).append((key, p.name))

	rows = []
	for course, items in course_map.items():
		period_scores = [None] * 6
		exam_score = None
		for (kind, _c), plan in items:
			r = by_plan.get(plan)
			score = None
			if r and r.maximum_score:
				score = flt(r.total_score) / flt(r.maximum_score) * 100
			if kind == "exam":
				exam_score = score
			else:
				# map by period name
				for i, period in enumerate(PERIODS):
					if plan == _find_period_plan(course, period, plans, group_names):
						period_scores[i] = score

		avail = [s for s in period_scores if s is not None]
		if exam_score is not None and avail:
			average = (sum(avail) / len(avail) * 0.75) + (exam_score * 0.25)
		elif avail:
			average = sum(avail) / len(avail)
		else:
			average = None

		rows.append(
			{
				"subject": course,
				"periods": period_scores,
				"exam": exam_score,
				"average": flt(average, 1) if average is not None else None,
			}
		)

	return rows


def _find_period_plan(course, period, plans, group_names):
	for p in plans:
		if p.course != course:
			continue
		if (group_names.get(p.name) or "") == period:
			return p.name
	return None


def get_guardian_name(student):
	guardians = frappe.get_all(
		"Student Guardian",
		filters={"parent": student},
		fields=["guardian"],
		limit=1,
	)
	if not guardians:
		return ""
	return frappe.db.get_value("Guardian", guardians[0].guardian, "guardian_name") or ""


def branding_dict():
	b = frappe.get_single("School Branding Settings")
	colors = get_school_colors()
	return {
		"school_name": b.school_name or "SAMDELL MEMORIAL SCHOOL",
		"school_motto": b.school_motto or "",
		"logo": b.logo or "",
		"primary_color": colors["primary_color"],
		"accent_color": colors["accent_color"],
		"principal_name": b.principal_name or "",
	}


REPORT_CARD_TEMPLATE = """{% set branding = branding_dict() %}
{% set guardian = get_guardian_name %}
{% set rows_fn = get_report_card_rows %}
<style>
	@page { size: A4 portrait; margin: 12mm; }
	body { font-family: Georgia, serif; color: #222; }
	.school-head { text-align: center; margin-bottom: 4mm; }
	.school-head h2 { margin: 0; color: {{ branding.primary_color }}; }
	.school-head .motto { font-style: italic; color: {{ branding.accent_color }}; font-size: 11pt; }
	.student-page { page-break-after: always; }
	.student-page:last-child { page-break-after: auto; }
	h3.title { text-align: center; letter-spacing: 2px; border-bottom: 2px solid {{ branding.primary_color }}; padding-bottom: 2mm; color: {{ branding.primary_color }}; }
	table.grid { width: 100%; border-collapse: collapse; font-size: 10pt; margin-top: 4mm; }
	table.grid th, table.grid td { border: 1px solid #888; padding: 2px 4px; text-align: center; }
	table.grid th { background: #eef; color: {{ branding.primary_color }}; }
	.meta { width: 100%; margin: 3mm 0; }
	.meta td { font-size: 11pt; padding: 1px 4px; }
	.legend { margin-top: 5mm; font-size: 10pt; border: 1px solid #888; padding: 3mm; }
	.sig-line { border-bottom: 1px solid #000; }
	.sig { width: 100%; margin-top: 8mm; }
	.sig td { font-size: 10pt; text-align: center; }
	.needs-attention { color: {{ branding.accent_color }}; font-weight: bold; }
	.good { color: #0a58ca; }
</style>
{% for entry in doc.entries %}
<div class="student-page">
	<div class="school-head">
		{% if branding.logo %}<img src="{{ branding.logo }}" style="height: 24mm; margin-bottom: 1mm;">{% endif %}
		<h2>{{ branding.school_name }}</h2>
		<div class="motto">{{ branding.school_motto }}</div>
		<div>{{ doc.academic_term }}</div>
	</div>
	<h3 class="title">REPORT CARD</h3>
	<table class="meta">
		<tr><td width="50%"><b>Student:</b> {{ frappe.db.get_value('Student', entry.student, 'student_name') }}</td>
			<td><b>Grade/Class:</b> {{ doc.student_group }}</td></tr>
		<tr><td><b>Rank:</b> {{ entry.class_rank or '-' }}</td>
			<td><b>Semester Average:</b> {{ entry.overall_average or '-' }}%</td></tr>
	</table>
	{% set rows = rows_fn(doc, entry.student) %}
	<table class="grid">
		<tr>
			<th style="width:22%; text-align:left;">Subject</th>
			<th>P1</th><th>P2</th><th>P3</th><th>P4</th><th>P5</th><th>P6</th>
			<th>Exam</th><th>Average</th>
		</tr>
		{% for r in rows %}
		<tr>
			<td style="text-align:left;">{{ r.subject }}</td>
			{% for s in r.periods %}
			<td class="{{ 'good' if (s is not none and s >= 75) else ('needs-attention' if s is not none) }}">{{ s if s is not none else '-' }}</td>
			{% endfor %}
			<td class="{{ 'good' if (r.exam is not none and r.exam >= 75) else ('needs-attention' if r.exam is not none) }}">{{ r.exam if r.exam is not none else '-' }}</td>
			<td class="{{ 'good' if (r.average is not none and r.average >= 75) else ('needs-attention' if r.average is not none) }}">{{ r.average if r.average is not none else '-' }}</td>
		</tr>
		{% endfor %}
		<tr>
			<td style="text-align:left;"><b>Semester Average</b></td>
			<td colspan="7"></td>
			<td><b>{{ entry.overall_average or '-' }}%</b></td>
		</tr>
		<tr>
			<td style="text-align:left;">Rating</td>
			<td colspan="8" style="text-align:left;">{{ entry.overall_rating or '' }}</td>
		</tr>
	</table>
	<table class="grid" style="margin-top:3mm;">
		<tr><th style="text-align:left;">Conduct</th><th style="text-align:left;">Adjustment Ability</th><th style="text-align:left;">Days Absent</th><th style="text-align:left;">Tardy</th></tr>
		<tr>
			<td>{{ entry.conduct or '' }}</td>
			<td>{{ entry.adjustment_ability or '' }}</td>
			<td>{{ entry.days_absent or 0 }}</td>
			<td>{{ entry.tardy or 0 }}</td>
		</tr>
	</table>
	<div class="legend">
		<b>Grading Scale:</b> O = Outstanding (95&ndash;100) &nbsp; S = Satisfactory (85&ndash;94) &nbsp; T = Trying (75&ndash;84) &nbsp; F = Failure (below 75).<br>
		Passing mark is <b>75%</b>. A mark below 75 in any subject indicates that subject needs special attention.
		Conduct is graded separately on its own A&ndash;D scale.
	</div>
	<table class="sig">
		<tr>
			<td><div class="sig-line">&nbsp;</div>Guardian's Signature</td>
			<td><div class="sig-line">&nbsp;</div>Class Teacher</td>
			<td><div class="sig-line">&nbsp;</div>Principal</td>
		</tr>
	</table>
</div>
{% endfor %}
"""


PROMOTION_STATEMENT_TEMPLATE = """{% set branding = branding_dict() %}
<style>
	@page { size: A4 portrait; margin: 16mm; }
	body { font-family: Georgia, serif; color: #111; }
	.school-head { text-align: center; margin-bottom: 8mm; }
	.school-head h2 { margin: 0; color: {{ branding.primary_color }}; }
	.school-head .motto { font-style: italic; color: {{ branding.accent_color }}; font-size: 11pt; }
	h3.title { text-align: center; letter-spacing: 3px; border-bottom: 3px double {{ branding.primary_color }}; padding-bottom: 3mm; color: {{ branding.primary_color }}; font-size: 15pt; }
	.student-name { text-align: center; font-size: 15pt; margin: 8mm 0 4mm; }
	.body-text { font-size: 12pt; line-height: 2.0; margin: 6mm 0; }
	.outcomes { font-size: 12pt; margin: 5mm 8mm; line-height: 1.9; }
	.stamp { display: inline-block; border: 3px solid {{ branding.accent_color }}; color: {{ branding.accent_color }}; font-weight: bold; letter-spacing: 2px; padding: 2mm 6mm; transform: rotate(-6deg); margin: 4mm 0; }
	.sig { width: 100%; margin-top: 14mm; }
	.sig td { font-size: 11pt; text-align: center; }
	.sig-line { border-bottom: 1px solid #000; }
	.footer { margin-top: 10mm; font-size: 10pt; text-align: center; }
</style>
<div class="school-head">
	{% if branding.logo %}<img src="{{ branding.logo }}" style="height: 22mm;">{% endif %}
	<h2>{{ branding.school_name }}</h2>
	<div class="motto">{{ branding.school_motto }}</div>
</div>
<h3 class="title">CERTIFICATE OF PROMOTION</h3>
<div class="student-name"><b>{{ frappe.db.get_value('Student', doc.student, 'student_name') }}</b></div>
<div class="body-text">
	Has <b>{{ 'satisfactorily' if doc.outcome in ('Promoted', 'Double Promoted', 'Graduated') else 'not satisfactorily' }}</b> completed the academic work of
	<b>{{ doc.current_program }}</b> for the academic year <b>{{ doc.academic_year }}</b>, and is:
</div>
<div class="outcomes">
	1. Promoted to {{ doc.next_program or '_____' }}
		{{ '(CHECKED &mdash; DOUBLE PROMOTION)' if doc.outcome == 'Double Promoted' else '' }}<br>
	2. Conditioned in {{ doc.conditioned_subject or '_____' }} and must attend vacation school. ______<br>
	3. Retained in Grade {{ doc.current_program }} ______<br>
	4. Asked not to re-enroll next year ______<br>
</div>
{% if doc.outcome in ('Promoted', 'Double Promoted') or doc.outcome == 'Graduated' %}
<div style="text-align:center;"><span class="stamp">{{ 'GRADUATED' if doc.outcome == 'Graduated' else 'PROMOTED' }}</span></div>
{% endif %}
<div style="margin-top:6mm; font-size:12pt;">This {{ frappe.utils.formatdate(frappe.utils.today(), 'dd') }} day of {{ frappe.utils.formatdate(frappe.utils.today(), 'MMMM') }} A.D. {{ frappe.utils.formatdate(frappe.utils.today(), 'YYYY') }}.</div>
<table class="sig">
	<tr>
		<td width="50%"><div class="sig-line">&nbsp;</div>{{ branding.principal_name or 'Principal' }}<br><small>Principal</small></td>
		<td><div class="sig-line">&nbsp;</div>School Seal</td>
	</tr>
</table>
<div class="footer">{{ branding.school_name }} &middot; {{ branding.school_motto }}</div>
"""


FEE_PAYMENT_RECEIPT_TEMPLATE = """{% set branding = branding_dict() %}
<style>
	@page { size: A4 portrait; margin: 14mm; }
	body { font-family: Georgia, serif; color: #111; }
	.school-head { text-align: center; margin-bottom: 6mm; }
	.school-head h2 { margin: 0; color: {{ branding.primary_color }}; }
	.school-head .motto { font-style: italic; color: {{ branding.accent_color }}; font-size: 11pt; }
	h3.title { text-align: center; letter-spacing: 3px; border-bottom: 2px solid {{ branding.primary_color }}; padding-bottom: 2mm; color: {{ branding.primary_color }}; }
	table.grid { width: 100%; border-collapse: collapse; font-size: 11pt; margin-top: 5mm; }
	table.grid td { padding: 3px 5px; }
	table.grid tr.row-border td { border-bottom: 1px solid #aaa; }
	.amount { text-align: right; }
	.totals td { font-size: 12pt; }
	.footer { margin-top: 12mm; text-align: center; font-size: 10pt; }
	.sig { width: 100%; margin-top: 10mm; }
	.sig td { text-align: center; font-size: 10pt; }
	.sig-line { border-bottom: 1px solid #000; }
</style>
<div class="school-head">
	{% if branding.logo %}<img src="{{ branding.logo }}" style="height: 20mm;">{% endif %}
	<h2>{{ branding.school_name }}</h2>
	<div class="motto">{{ branding.school_motto }}</div>
</div>
<h3 class="title">FEE PAYMENT RECEIPT</h3>
<table class="grid">
	<tr class="row-border"><td width="30%"><b>Receipt No.</b></td><td>{{ doc.name }}</td></tr>
	<tr class="row-border"><td><b>Date</b></td><td>{{ frappe.utils.formatdate(doc.posting_date) }}</td></tr>
	<tr class="row-border"><td><b>Student</b></td><td>{{ doc.party_name or doc.party }}</td></tr>
	<tr class="row-border"><td><b>Payment Mode</b></td><td>{{ doc.mode_of_payment or '' }}</td></tr>
	<tr class="row-border"><td><b>Reference</b></td><td>{{ doc.reference_no or '' }}</td></tr>
	<tr class="row-border"><td><b>Amount Paid</b></td><td class="amount"><b>{{ frappe.utils.fmt_money(doc.paid_amount, currency=doc.paid_from_account_currency or 'USD') }}</b></td></tr>
	<tr class="row-border"><td><b>Outstanding</b></td><td class="amount">{{ frappe.utils.fmt_money(doc.get('outstanding_amount') or 0, currency=doc.paid_from_account_currency or 'USD') }}</td></tr>
</table>
{% if doc.references %}
<table class="grid" style="margin-top:5mm;">
	<tr><td><b>Allocated against:</b></td></tr>
	{% for ref in doc.references %}
	<tr class="row-border"><td>{{ ref.reference_doctype }} &mdash; {{ ref.reference_name }}</td></tr>
	{% endfor %}
</table>
{% endif %}
<table class="sig">
	<tr>
		<td width="50%"><div class="sig-line">&nbsp;</div>Received By</td>
		<td><div class="sig-line">&nbsp;</div>Cashier</td>
	</tr>
</table>
<div class="footer">Thank you for your payment. {{ branding.school_name }}</div>
"""


ECE_PROGRESS_REPORT_TEMPLATE = """{% set branding = branding_dict() %}
<style>
	@page { size: A4 portrait; margin: 14mm; }
	body { font-family: Georgia, serif; color: #111; }
	.school-head { text-align: center; margin-bottom: 6mm; }
	.school-head h2 { margin: 0; color: {{ branding.primary_color }}; }
	.school-head .motto { font-style: italic; color: {{ branding.accent_color }}; font-size: 11pt; }
	h3.title { text-align: center; letter-spacing: 3px; border-bottom: 2px solid {{ branding.primary_color }}; padding-bottom: 2mm; color: {{ branding.primary_color }}; }
	table.grid { width: 100%; border-collapse: collapse; font-size: 11pt; margin-top: 5mm; }
	table.grid td { padding: 3px 5px; }
	table.grid tr.row-border td { border-bottom: 1px solid #aaa; }
	.student-name { font-size: 13pt; margin: 5mm 0; }
	.ready-badge { display: inline-block; background: {{ branding.primary_color }}; color: #fff; font-weight: bold; padding: 1mm 4mm; border-radius: 3px; }
	.improve-badge { display: inline-block; background: {{ branding.accent_color }}; color: #fff; font-weight: bold; padding: 1mm 4mm; border-radius: 3px; }
	.sig { width: 100%; margin-top: 14mm; }
	.sig td { text-align: center; font-size: 10pt; }
	.sig-line { border-bottom: 1px solid #000; }
	.footer { margin-top: 10mm; font-size: 10pt; text-align: center; }
</style>
<div class="school-head">
	{% if branding.logo %}<img src="{{ branding.logo }}" style="height: 20mm;">{% endif %}
	<h2>{{ branding.school_name }}</h2>
	<div class="motto">{{ branding.school_motto }}</div>
</div>
<h3 class="title">EARLY CHILDHOOD PROGRESS REPORT</h3>
<div class="student-name"><b>{{ frappe.db.get_value('Student', doc.student, 'student_name') }}</b></div>
<table class="grid">
	<tr class="row-border"><td width="30%"><b>Academic Term</b></td><td>{{ doc.academic_term }}</td></tr>
	<tr class="row-border"><td><b>Class Teacher</b></td><td>{{ doc.teacher or 'Class Teacher' }}</td></tr>
	<tr class="row-border"><td><b>Progress Summary</b></td>
		<td>{% if doc.readiness == 'Needs to Improve' %}
			<span class="improve-badge">NEEDS TO IMPROVE</span>
			{% if doc.improve_area %}&nbsp;&mdash; {{ doc.improve_area }}{% endif %}
		{% else %}
			<span class="ready-badge">READY FOR NEXT LEVEL</span>
		{% endif %}</td></tr>
</table>
{% if doc.comments %}
<table class="grid" style="margin-top:5mm;">
	<tr><td><b>Teacher's Comments</b></td></tr>
	<tr class="row-border"><td>{{ doc.comments }}</td></tr>
</table>
{% endif %}
<table class="sig">
	<tr>
		<td width="50%"><div class="sig-line">&nbsp;</div>Class Teacher{% if doc.teacher_signed %} &#10003;{% endif %}</td>
		<td><div class="sig-line">&nbsp;</div>Principal{% if doc.principal_approved %} &#10003;{% endif %}</td>
	</tr>
</table>
<div class="footer">{{ branding.school_name }} &middot; {{ branding.school_motto }}</div>
"""
