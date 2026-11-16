"""The quarterly 360 review: a questionnaire per employee, closed into one review per reviewer."""

import frappe
from frappe import _

from centhr.centhr.doctype.pms_360_degree.pms_360_degree import get_department_review
from centhr.pms.period import QUARTERS

QUESTIONNAIRE = "PMS Questionnaire"
ALLOCATION = "PMS Form Allocation"
MAPPING = "PMS Employee Relationship"
SAVEPOINT = "pms_close_questionnaire"


class QuestionnaireBuilder:
	"""Create PMS Form: gives the chosen questions to every eligible employee of the departments that
	take part in the quarter's 360 review. An employee is eligible once they have a submitted KPI
	Result in the quarter. An open questionnaire gets the questions it does not have yet."""

	def __init__(
		self,
		company: str,
		fiscal_year: str,
		quarter: str,
		questions: list[dict],
		departments: list[str] | None = None,
		designation: str | None = None,
	):
		self.company = company
		self.fiscal_year = fiscal_year
		self.quarter = quarter
		self.questions = self.clean(questions)
		self.designation = designation
		self.departments = self.get_departments(departments)
		self.outcome = frappe._dict(created=[], updated=[], skipped=[])

	def clean(self, questions: list[dict]) -> list[dict]:
		rows = [{**q, "question": (q.get("question") or "").strip()} for q in questions]
		rows = [row for row in rows if row["question"]]
		if not rows:
			frappe.throw(_("Add at least one question."))
		texts = [row["question"] for row in rows]
		if len(texts) != len(set(texts)):
			frappe.throw(_("The same question is added twice."))
		return rows

	def get_departments(self, chosen: list[str] | None) -> list[str]:
		setup = frappe.db.get_value(
			"PMS 360 Degree",
			{"company": self.company, "fiscal_year": self.fiscal_year, "quarter": self.quarter},
			"name",
		)
		if not setup:
			frappe.throw(
				_("Set up the 360 review of {0} for {1} {2} first.").format(
					self.company, self.quarter, self.fiscal_year
				),
				title=_("No 360 Review"),
			)
		in_review = frappe.get_all(
			"PMS 360 Degree Departments", filters={"parent": setup}, pluck="department"
		)
		return [d for d in in_review if not chosen or d in chosen]

	def run(self, preview: bool = False) -> dict:
		"""With `preview`, only report what would happen."""
		employees = self.get_employees()
		scored = get_employees_with_kpi_result([e.name for e in employees], self.fiscal_year, self.quarter)
		existing = self.get_existing([e.name for e in employees])

		for employee in employees:
			questionnaire = existing.get(employee.name)
			if employee.name not in scored:
				self.skip(employee, _("No submitted KPI Result in {0}").format(self.quarter))
			elif questionnaire and questionnaire.status != "Open":
				self.skip(employee, _("Questionnaire is closed already"))
			elif questionnaire:
				self.outcome.updated.append(employee.name)
				if not preview:
					self.add_questions(questionnaire.name)
			else:
				self.outcome.created.append(employee.name)
				if not preview:
					self.create(employee)
		return self.outcome

	def get_employees(self) -> list:
		filters = {"company": self.company, "status": "Active", "department": ["in", self.departments]}
		if self.designation:
			filters["designation"] = self.designation
		return frappe.get_all(
			"Employee",
			filters=filters,
			fields=["name", "employee_name", "department"],
			order_by="employee_name asc",
		)

	def get_existing(self, employees: list[str]) -> dict:
		rows = frappe.get_all(
			QUESTIONNAIRE,
			filters={"employee": ["in", employees], "fiscal_year": self.fiscal_year, "quarter": self.quarter},
			fields=["name", "employee", "status"],
		)
		return {row.employee: row for row in rows}

	def skip(self, employee, reason: str) -> None:
		self.outcome.skipped.append(
			{"employee": employee.name, "employee_name": employee.employee_name, "reason": reason}
		)

	def create(self, employee) -> None:
		frappe.get_doc(
			{
				"doctype": QUESTIONNAIRE,
				"employee": employee.name,
				"department": employee.department,
				"fiscal_year": self.fiscal_year,
				"quarter": self.quarter,
				"pms_questionnaire_list": [self.make_row(question) for question in self.questions],
			}
		).insert()

	def add_questions(self, name: str) -> None:
		questionnaire = frappe.get_doc(QUESTIONNAIRE, name)
		have = {row.question for row in questionnaire.pms_questionnaire_list}
		for question in self.questions:
			if question["question"] not in have:
				questionnaire.append("pms_questionnaire_list", self.make_row(question))
		questionnaire.save()

	def make_row(self, question: dict) -> dict:
		return {
			"question": question["question"],
			"question_trait": question.get("question_trait"),
			"question_head": question.get("question_head") or "Non KPI",
			"added_by": frappe.session.user,
		}


def close_questionnaire(name: str) -> list[str]:
	"""Close a questionnaire and ask its reviewers: the line manager and the peers of the employee's
	peer mapping, as far as the department's 360 review includes them. Returns the allocations."""
	questionnaire = frappe.get_doc(QUESTIONNAIRE, name)
	questionnaire.check_permission("write")
	if questionnaire.status != "Open":
		frappe.throw(_("This questionnaire is closed already."))
	if not questionnaire.pms_questionnaire_list:
		frappe.throw(
			_("Add questions to the questionnaire of {0} first.").format(questionnaire.employee_name)
		)
	check_has_kpi_result(questionnaire)

	reviewers = get_reviewers(questionnaire)
	if not reviewers:
		frappe.throw(
			_("{0} has no line manager or peers to review them. Check their peer mapping.").format(
				questionnaire.employee_name
			)
		)
	allocations = [allocate(questionnaire, reviewer, relationship) for reviewer, relationship in reviewers]
	questionnaire.status = "Completed"
	questionnaire.save()
	return allocations


def close_questionnaires(names: list[str]) -> dict:
	"""Close several questionnaires. One that cannot be closed is reported and does not stop the rest."""
	outcome = frappe._dict(closed=[], failed=[])
	for name in names:
		frappe.db.savepoint(SAVEPOINT)
		try:
			close_questionnaire(name)
			outcome.closed.append(name)
		except frappe.ValidationError as e:
			frappe.db.rollback(save_point=SAVEPOINT)
			frappe.clear_messages()
			outcome.failed.append({"questionnaire": name, "error": frappe.utils.strip_html(str(e))})
	return outcome


def reopen_questionnaire(name: str) -> None:
	"""Take a closed questionnaire back, to change its questions. Only while nobody has reviewed yet."""
	questionnaire = frappe.get_doc(QUESTIONNAIRE, name)
	questionnaire.check_permission("write")
	allocations = frappe.get_all(
		ALLOCATION, filters={"form_reference": name, "docstatus": 1}, fields=["name", "status"]
	)
	if any(allocation.status == "Completed" for allocation in allocations):
		frappe.throw(_("Reviews have been submitted for this questionnaire, so it cannot be reopened."))
	for allocation in allocations:
		cancel_allocation(allocation.name)
	questionnaire.status = "Open"
	questionnaire.save()


def get_reviewers(questionnaire) -> list[tuple[str, str]]:
	"""(reviewer, relationship) for each active reviewer the department's 360 review includes."""
	review = get_department_review(
		questionnaire.company, questionnaire.department, questionnaire.fiscal_year, questionnaire.quarter
	)
	if not review:
		frappe.throw(
			_("{0} is not part of the 360 review of {1} {2}.").format(
				questionnaire.department, questionnaire.quarter, questionnaire.fiscal_year
			)
		)
	if not frappe.db.exists(MAPPING, questionnaire.employee):
		frappe.throw(
			_("{0} has no peer mapping. Run peer mapping first.").format(questionnaire.employee_name)
		)

	mapping = frappe.get_doc(MAPPING, questionnaire.employee)
	reviewers = []
	if review.superior and mapping.line_manager:
		reviewers.append((mapping.line_manager, "Line Manager"))
	if review.peers:
		reviewers += [(row.employee, "Peers") for row in mapping.peers]

	active = set(
		frappe.get_all(
			"Employee",
			filters={"name": ["in", [r for r, _type in reviewers]], "status": "Active"},
			pluck="name",
		)
	)
	return [(reviewer, relationship) for reviewer, relationship in reviewers if reviewer in active]


def allocate(questionnaire, reviewer: str, relationship: str) -> str:
	allocation = frappe.get_doc(
		{
			"doctype": ALLOCATION,
			"reviewer": reviewer,
			"reviewee": questionnaire.employee,
			"relationship_type": relationship,
			"fiscal_year": questionnaire.fiscal_year,
			"quarter": questionnaire.quarter,
			"form_reference": questionnaire.name,
		}
	)
	allocation.flags.ignore_permissions = True
	allocation.insert()
	allocation.submit()
	return allocation.name


def cancel_allocation(name: str) -> None:
	allocation = frappe.get_doc(ALLOCATION, name)
	allocation.flags.ignore_permissions = True
	allocation.cancel()


def sync_peer_allocations(mapping) -> None:
	"""A peer mapping changed while reviews are still open: peers who were removed are no longer asked
	(unless they reviewed already), and new peers are."""
	peers = {row.employee for row in mapping.peers}
	pending = frappe.get_all(
		ALLOCATION,
		filters={"reviewee": mapping.employee, "docstatus": 1, "status": "Pending"},
		fields=["name", "reviewer", "relationship_type", "form_reference"],
	)
	for questionnaire_name in {allocation.form_reference for allocation in pending}:
		questionnaire = frappe.get_doc(QUESTIONNAIRE, questionnaire_name)
		review = get_department_review(
			questionnaire.company, questionnaire.department, questionnaire.fiscal_year, questionnaire.quarter
		)
		if not review or not review.peers:
			continue
		asked = set(
			frappe.get_all(
				ALLOCATION,
				filters={"form_reference": questionnaire_name, "docstatus": 1, "relationship_type": "Peers"},
				pluck="reviewer",
			)
		)
		for allocation in pending:
			gone = allocation.relationship_type == "Peers" and allocation.reviewer not in peers
			if allocation.form_reference == questionnaire_name and gone:
				cancel_allocation(allocation.name)
		for peer in peers - asked:
			allocate(questionnaire, peer, "Peers")


# Shared checks


def check_has_kpi_result(questionnaire) -> None:
	scored = get_employees_with_kpi_result(
		[questionnaire.employee], questionnaire.fiscal_year, questionnaire.quarter
	)
	if not scored:
		frappe.throw(
			_("{0} has no submitted KPI Result in {1} {2}.").format(
				questionnaire.employee_name, questionnaire.quarter, questionnaire.fiscal_year
			)
		)


def get_employees_with_kpi_result(employees: list[str], fiscal_year: str, quarter: str) -> set[str]:
	if not employees:
		return set()
	return set(
		frappe.get_all(
			"KPI Result",
			filters={
				"employee": ["in", employees],
				"fiscal_year": fiscal_year,
				"month": ["in", QUARTERS[quarter]],
				"docstatus": 1,
			},
			pluck="employee",
		)
	)
