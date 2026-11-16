import { api } from "@/data/api"
import { MONTHS } from "@/data/pms"

const METHOD = "centhr.pms.api"

export const QUARTERS: Record<string, string[]> = {
	Q1: ["Jan", "Feb", "Mar"],
	Q2: ["Apr", "May", "Jun"],
	Q3: ["Jul", "Aug", "Sep"],
	Q4: ["Oct", "Nov", "Dec"],
}

export function currentQuarter(): string {
	const month = MONTHS[new Date().getMonth()]
	return Object.keys(QUARTERS).find((quarter) => QUARTERS[quarter].includes(month))!
}

/** The quarter every 360 review page works on; company and department narrow it. */
export interface QuarterScope {
	fiscalYear: string
	quarter: string
	company: string
	department: string
}

function scopeArgs(scope: QuarterScope) {
	return {
		fiscal_year: scope.fiscalYear,
		quarter: scope.quarter,
		company: scope.company || undefined,
		department: scope.department || undefined,
	}
}

// Create PMS Form

export interface FormQuestion {
	question: string
	question_trait?: string | null
}
export interface BuildOutcome {
	created: string[]
	updated: string[]
	skipped: { employee: string; employee_name: string; reason: string }[]
}

export function createQuestionnaires(scope: QuarterScope, questions: FormQuestion[], designation: string | null, preview: boolean) {
	return api<BuildOutcome>(`${METHOD}.create_questionnaires`, {
		company: scope.company,
		fiscal_year: scope.fiscalYear,
		quarter: scope.quarter,
		questions,
		departments: scope.department ? [scope.department] : undefined,
		designation: designation || undefined,
		preview: preview ? 1 : 0,
	})
}

// Form Dashboard

export interface QuestionnaireRow {
	name: string
	employee: string
	employee_name: string
	company: string
	department: string | null
	status: "Open" | "Completed"
	questions: number
	reviews_total: number
	reviews_done: number
}

export function getQuestionnaires(scope: QuarterScope) {
	return api<QuestionnaireRow[]>(`${METHOD}.get_questionnaires`, scopeArgs(scope))
}

export function closeQuestionnaires(names: string[]) {
	return api<{ closed: string[]; failed: { questionnaire: string; error: string }[] }>(`${METHOD}.close_questionnaires`, { names })
}

export function reopenQuestionnaire(name: string) {
	return api<void>(`${METHOD}.reopen_questionnaire`, { name })
}

// Reviews

export interface ReviewRow {
	name: string
	reviewee: string
	reviewee_name: string
	reviewer?: string
	reviewer_name?: string
	department: string | null
	relationship_type: string
	fiscal_year?: string
	quarter?: string
	status: "Pending" | "Completed"
	review_date: string | null
}

export function getReviewStatus(scope: QuarterScope) {
	return api<ReviewRow[]>(`${METHOD}.get_review_status`, scopeArgs(scope))
}

export function getMyReviews() {
	return api<ReviewRow[]>(`${METHOD}.get_my_reviews`)
}

export interface ReviewForm {
	allocation: string
	reviewee: string
	reviewee_name: string
	reviewee_designation: string | null
	department: string | null
	relationship_type: string
	fiscal_year: string
	quarter: string
	status: "Pending" | "Completed"
	review_date: string | null
	company_logo: string | null
	questions: { question: string; question_trait: string | null }[]
	ratings: number[]
	question_remarks: (string | null)[]
	remarks: string | null
}

export function getReviewForm(allocation: string) {
	return api<ReviewForm>(`${METHOD}.get_review_form`, { allocation })
}

export function submitReview(allocation: string, answers: { rating: number; remarks?: string }[], remarks: string) {
	return api<string>(`${METHOD}.submit_review`, { allocation, answers, remarks: remarks || undefined })
}

// Results

export interface OverallRow {
	employee: string
	employee_name: string
	company: string
	department: string | null
	designation: string | null
	kpi_score: number | null
	review_score: number | null
	reviews_done: number
	reviews_total: number
	overall_score: number | null
	overall_remark: string | null
}

export function getOverallScores(scope: QuarterScope, month: string) {
	return api<OverallRow[]>(`${METHOD}.get_overall_scores`, {
		...scopeArgs(scope),
		// A month replaces the quarter: its KPI score, with the 360 score of its quarter
		quarter: month ? undefined : scope.quarter,
		month: month || undefined,
	})
}

export function generateScoreSheets(scope: QuarterScope) {
	return api<{ created: string[]; existing: number; not_ready: number }>(`${METHOD}.generate_score_sheets`, {
		company: scope.company,
		fiscal_year: scope.fiscalYear,
		quarter: scope.quarter,
	})
}

export function decideScoreSheets(names: string[], decision: "approve" | "reject") {
	return api<number>(`${METHOD}.decide_score_sheets`, { names, decision })
}
