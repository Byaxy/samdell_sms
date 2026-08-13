import unittest.mock as mock
from datetime import date

import frappe
from frappe.tests import UnitTestCase

import samdell_sms.api.notifications as notifications


def _insert_log(logs, channel, guardian, category, reference_doctype, reference_name):
	logs.append(
		{
			"channel": channel,
			"recipient_guardian": guardian,
			"category": category,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		}
	)


def _fake_sms_sender(calls, logs):
	def fake_send_sms(guardian, message, category, reference_doctype=None, reference_name=None):
		calls.append((guardian, message, category, reference_doctype, reference_name))
		_insert_log(logs, "SMS", guardian, category, reference_doctype, reference_name)

	return fake_send_sms


def _fake_whatsapp_sender(calls, logs):
	def fake_send_whatsapp(guardian, template, params, category, reference_doctype=None, reference_name=None):
		calls.append((template, guardian, params, category, reference_doctype, reference_name))
		_insert_log(logs, "WhatsApp", guardian, category, reference_doctype, reference_name)

	return fake_send_whatsapp


class TestNotifications(UnitTestCase):
	def setUp(self):
		self.whatsapp_calls = []
		self.sms_calls = []
		self.logs = []
		self.guardian_map = {}
		self.patchers = [
			mock.patch(
				"samdell_sms.api.sms.send_sms",
				side_effect=_fake_sms_sender(self.sms_calls, self.logs),
			),
			mock.patch(
				"samdell_sms.api.whatsapp.send_whatsapp",
				side_effect=_fake_whatsapp_sender(self.whatsapp_calls, self.logs),
			),
			mock.patch.object(notifications, "student_guardians", side_effect=self._guardians),
			mock.patch.object(notifications, "_already_notified", side_effect=self._already_notified),
			mock.patch.object(notifications, "fmt_money", return_value="500.00"),
		]
		for patcher in self.patchers:
			patcher.start()
		self.addCleanup(lambda: [p.stop() for p in self.patchers])

	def _guardians(self, student):
		return self.guardian_map.get(student, set())

	def _already_notified(self, category, reference_doctype, reference_name):
		return any(
			row["category"] == category
			and row["reference_doctype"] == reference_doctype
			and row["reference_name"] == reference_name
			for row in self.logs
		)

	def test_notify_fee_due_sends_once_per_guardian(self):
		self.guardian_map = {"STU-001": {"G-001", "G-002"}}
		doc = frappe._dict(
			{
				"doctype": "Fees",
				"name": "ACC-FEE-00001",
				"student": "STU-001",
				"student_name": "John Doe",
				"grand_total": 500,
				"currency": "USD",
				"due_date": date(2026, 8, 30),
			}
		)

		notifications.notify_fee_due(doc)

		self.assertEqual(len(self.whatsapp_calls), 2)
		for template, guardian, params, category, ref_dt, ref_name in self.whatsapp_calls:
			self.assertEqual(template, "fee_due")
			self.assertEqual(category, "Fee Due")
			self.assertEqual(ref_dt, "Fees")
			self.assertEqual(ref_name, "ACC-FEE-00001")
			self.assertEqual(params["student_name"], "John Doe")
			self.assertIn(guardian, {"G-001", "G-002"})

		# A duplicate save / second submission must not notify again.
		self.whatsapp_calls.clear()
		notifications.notify_fee_due(doc)
		self.assertEqual(self.whatsapp_calls, [])

	def test_grade_release_dedupes_shared_guardian(self):
		self.guardian_map = {"STU-001": {"G-001"}, "STU-002": {"G-001"}}
		doc = frappe._dict(
			{
				"doctype": "Master Grade Sheet",
				"name": "MGS-00001",
				"workflow_state": "Released",
				"academic_term": "2026 Term 3",
				"entries": [
					frappe._dict(
						{
							"student": "STU-001",
							"overall_average": 85.5,
							"overall_rating": "S",
							"class_rank": 2,
						}
					),
					frappe._dict(
						{
							"student": "STU-002",
							"overall_average": 92.0,
							"overall_rating": "O",
							"class_rank": 1,
						}
					),
				],
			}
		)

		notifications.grade_release_on_update(doc)

		# One parent with two children in the sheet receives a single message.
		self.assertEqual(len(self.whatsapp_calls), 1)
		template, guardian, params, category, _, _ = self.whatsapp_calls[0]
		self.assertEqual(guardian, "G-001")
		self.assertEqual(template, "grade_release")
		self.assertEqual(category, "Grade Release")
		self.assertEqual(params["academic_term"], "2026 Term 3")
		self.assertEqual(params["average"], 85.5)
		self.assertEqual(params["class_size"], 2)

		# Later saves of the same sheet must not notify again.
		self.whatsapp_calls.clear()
		notifications.grade_release_on_update(doc)
		self.assertEqual(self.whatsapp_calls, [])

	def test_grade_release_ignores_non_released_sheets(self):
		doc = frappe._dict(
			{
				"doctype": "Master Grade Sheet",
				"name": "MGS-00002",
				"workflow_state": "Reviewed",
				"entries": [],
			}
		)
		notifications.grade_release_on_update(doc)
		self.assertEqual(self.whatsapp_calls, [])

	def test_fee_paid_sweep_notifies_paid_fees_once(self):
		self.guardian_map = {"STU-001": {"G-001"}, "STU-002": {"G-001"}}
		paid_fees = [
			frappe._dict(
				{
					"name": "ACC-FEE-00010",
					"student": "STU-001",
					"student_name": "John Doe",
					"grand_total": 300,
					"currency": "USD",
				}
			),
			frappe._dict(
				{
					"name": "ACC-FEE-00011",
					"student": "STU-002",
					"student_name": "Jane Doe",
					"grand_total": 400,
					"currency": "USD",
				}
			),
		]
		with mock.patch("frappe.get_all", return_value=paid_fees):
			notifications.fee_paid_sweep()

		# One receipt per paid fee, even when the parent has both students.
		self.assertEqual(len(self.whatsapp_calls), 2)
		ref_names = {ref_name for *_, ref_name in self.whatsapp_calls}
		self.assertEqual(ref_names, {"ACC-FEE-00010", "ACC-FEE-00011"})

		for template, guardian, _params, category, ref_dt, _ref_name in self.whatsapp_calls:
			self.assertEqual(template, "fee_paid")
			self.assertEqual(guardian, "G-001")
			self.assertEqual(category, "Fee Paid")
			self.assertEqual(ref_dt, "Fees")

		# Re-running the sweep must not notify already-notified fees again.
		self.whatsapp_calls.clear()
		with mock.patch("frappe.get_all", return_value=paid_fees):
			notifications.fee_paid_sweep()
		self.assertEqual(self.whatsapp_calls, [])

	def test_announcement_dispatches_once(self):
		from samdell_sms.samdell_sms.doctype.school_announcement import (
			school_announcement as announcement,
		)

		doc = frappe._dict(
			{
				"doctype": "School Announcement",
				"name": "ANNC-00001",
				"title": "School Closure",
				"body": "School closed tomorrow.",
				"publish_date": frappe.utils.now_datetime(),
				"audience": [frappe._dict({"target": "All"})],
				"send_sms": 0,
				"send_whatsapp": 1,
			}
		)
		with mock.patch("frappe.get_all", return_value=["G-001", "G-002"]):
			announcement.dispatch_announcement(doc)

		self.assertEqual(len(self.whatsapp_calls), 2)
		self.assertEqual(len(self.sms_calls), 0, f"send_sms={doc.send_sms!r} calls={self.sms_calls}")

		# Saving the same announcement again must not re-send.
		self.whatsapp_calls.clear()
		with mock.patch("frappe.get_all", return_value=["G-001", "G-002"]):
			announcement.dispatch_announcement(doc)
		self.assertEqual(self.whatsapp_calls, [])
