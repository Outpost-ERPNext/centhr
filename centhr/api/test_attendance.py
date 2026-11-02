from datetime import date, timedelta

from frappe.tests import IntegrationTestCase

from centhr.api.attendance import split_into_months


class TestSplitIntoMonths(IntegrationTestCase):
	def test_year_from_the_20th_gives_twelve_parts(self):
		parts = split_into_months("2026-01-20", "2027-01-19")

		self.assertEqual(len(parts), 12)
		self.assertEqual((parts[0].start_date, parts[0].end_date), (date(2026, 1, 20), date(2026, 2, 19)))
		self.assertEqual((parts[-1].start_date, parts[-1].end_date), (date(2026, 12, 20), date(2027, 1, 19)))

	def test_parts_have_no_gaps_or_overlaps(self):
		parts = split_into_months("2026-01-20", "2027-01-19")

		for part, following in zip(parts, parts[1:], strict=False):
			self.assertEqual(part.end_date + timedelta(days=1), following.start_date)

	def test_start_day_31_does_not_drift(self):
		parts = split_into_months("2026-01-31", "2026-05-30")

		self.assertEqual(
			[p.start_date for p in parts],
			[date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)],
		)
		self.assertEqual(parts[0].end_date, date(2026, 2, 27))
		self.assertEqual(parts[-1].end_date, date(2026, 5, 30))

	def test_last_short_part_stops_at_the_end(self):
		parts = split_into_months("2026-01-20", "2026-04-05")

		self.assertEqual((parts[-1].start_date, parts[-1].end_date), (date(2026, 3, 20), date(2026, 4, 5)))
