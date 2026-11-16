# Copyright (c) 2026, Outpost Work LLP and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from centhr.pms.scoring import Band, find_band_row

# Kept out of the DocType folder on purpose: Frappe creates and commits test records for every DocType a
# DocType test module links to, and these tests only call validate() on unsaved documents.


def make_settings(**values):
	return frappe.get_doc({"doctype": "PMS Settings", "company": "_Test PMS Company", **values})


class TestPMSSettings(IntegrationTestCase):
	def test_weights_must_add_up_to_100(self):
		make_settings(overall_kpi_weight=70, overall__360_weight=30).validate()
		make_settings().validate()

		with self.assertRaises(frappe.ValidationError):
			make_settings(overall_kpi_weight=70, overall__360_weight=20).validate()
		with self.assertRaises(frappe.ValidationError):
			make_settings(overall_kpi_weight=120, overall__360_weight=-20).validate()

	def test_score_ranges_are_checked_in_every_table(self):
		for table in ("kpi_score", "overall_score", "increments"):
			with self.assertRaises(frappe.ValidationError):
				make_settings(**{table: [{"score": "eighty", "remark": "Good"}]}).validate()

	def test_increment_needs_a_number(self):
		make_settings(increments=[{"score": "80-100", "status": "Increment", "increment_": "10%"}]).validate()
		make_settings(increments=[{"score": "0-40", "status": "PIP"}]).validate()

		with self.assertRaises(frappe.ValidationError):
			make_settings(increments=[{"score": "80-100", "status": "Increment"}]).validate()


class TestScoreBand(IntegrationTestCase):
	def test_range_includes_both_ends(self):
		band = Band.parse("80 \u2013 100%")

		self.assertTrue(band.contains(80))
		self.assertTrue(band.contains(100))
		self.assertFalse(band.contains(79.99))

	def test_above_leaves_the_number_itself_out(self):
		band = Band.parse("> 100")

		self.assertFalse(band.contains(100))
		self.assertTrue(band.contains(100.5))

	def test_single_score(self):
		self.assertTrue(Band.parse("100").contains(100))
		self.assertFalse(Band.parse("100").contains(99))

	def test_invalid_ranges_are_rejected(self):
		for text in ("", None, "high", "100-80", "80-", "-80"):
			with self.assertRaises(frappe.ValidationError, msg=text):
				Band.parse(text)

	def test_find_band_row(self):
		rows = [frappe._dict(score="0-50", remark="Poor"), frappe._dict(score="51-100", remark="Good")]

		self.assertEqual(find_band_row(50, rows).remark, "Poor")
		self.assertEqual(find_band_row(51, rows).remark, "Good")
		# 50.5 is in neither range
		self.assertIsNone(find_band_row(50.5, rows))
