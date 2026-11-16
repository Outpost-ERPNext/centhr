"""PMS scores: the score bands of PMS Settings and the monthly KPI score."""

from dataclasses import dataclass
from math import inf

import frappe
from frappe import _
from frappe.utils import flt

# HR pastes ranges with an en or em dash
DASHES = str.maketrans({"\u2013": "-", "\u2014": "-"})


@dataclass(frozen=True)
class Band:
	"""A score range typed by HR: "80-100", a single score "100", or ">100" for anything above."""

	low: float
	high: float
	# ">100" leaves 100 itself to the band below
	above_low: bool = False

	@classmethod
	def parse(cls, text: str | None) -> "Band":
		value = (text or "").replace("%", "").replace(" ", "").translate(DASHES)
		try:
			if value.startswith(">"):
				return cls(float(value[1:]), inf, above_low=True)
			low, dash, high = value.partition("-")
			band = cls(float(low), float(high if dash else low))
		except ValueError:
			band = None
		if not band or band.low > band.high:
			frappe.throw(
				_("{0} is not a score range. Use a range such as 80-100, a single score, or >100.").format(
					frappe.bold(text or _("Empty"))
				),
				title=_("Invalid Score Range"),
			)
		return band

	def contains(self, score: float) -> bool:
		if self.above_low:
			return score > self.low
		return self.low <= score <= self.high


def find_band_row(score: float, rows: list):
	"""The first row whose `score` range holds the score, None when it falls between the ranges."""
	for row in rows:
		if Band.parse(row.score).contains(score):
			return row
	return None


def score_kpi_row(row) -> tuple[float, float]:
	"""Percent of the target achieved, and the score it earns.

	Higher is better unless the polarity is Negative, where beating the target means staying under it
	and achieving 0 is the best outcome. A row never earns more than its own weight.
	"""
	if row.not_measured:
		return 0.0, 0.0

	target, achieved, weight = flt(row.target), flt(row.achieved), flt(row.weight)
	if not target:
		percent = 0.0
	elif (row.polarity or "").lower() == "negative":
		percent = target / achieved * 100 if achieved else 100.0
	else:
		percent = achieved / target * 100
	return percent, min(percent / 100 * weight, weight)


def score_kpi_result(rows: list) -> float:
	"""Fill each row's percent and score, and return the month's score out of 100.

	The score is 0 while no measured row has an achieved value, so an untouched result is not scored.
	"""
	total = 0.0
	for row in rows:
		percent, score = score_kpi_row(row)
		row.percent, row.weighted_score = flt(percent, 2), flt(score, 2)
		total += score

	untouched = all(not row.not_measured and not flt(row.achieved) for row in rows)
	return 0.0 if untouched else min(flt(total, 2), 100.0)


def kpi_remark(score: float, bands: list) -> str:
	"""The remark of a monthly KPI score, from the company's KPI Score bands."""
	if not score:
		return _("Not Captured")

	row = find_band_row(score, bands)
	if row:
		return row.remark
	# The score falls between two bands, such as 50.5 between 0-50 and 51-100
	if score <= 30:
		return _("Poor Performance")
	if score <= 70:
		return _("Good Performance")
	return _("Excellent Performance")
