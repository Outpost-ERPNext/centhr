---
title: Payroll Dashboard
order: 3
---

# Payroll Dashboard

The Payroll Dashboard shows one company and one pay cycle. All its tabs use the company and the cycle that you select at the top.

In the menu, select **Payroll > Payroll Processing > Payroll Dashboard**.

At the top, select the company, the year and the pay period. The **Cycle** label shows the first and the last day of the cycle. To generate payroll, you must select one company.

The pay cycle follows the payroll settings of the company. For example, a cycle can run from the 20th of one month to the 19th of the next.

## Tabs

| Tab | What it shows |
|---|---|
| **Pre-Check Audit** | Problems to fix before you run payroll, per employee |
| **Employees** | The employees in the cycle, with their structure and pay |
| **Attendance** | The attendance of each employee, as payroll will count it |
| **Payroll Processing** | The totals of the cycle against the last cycle, the payroll runs and the salary slips. You generate and run payroll here. See [Run Payroll](run-payroll) |
| **Analytics** | Payroll by department, component and employee, over months, and against the accounts |
| **Advances & Deductions** | Employee advances not yet recovered, and the deductions of this cycle |
| **Reports** | The HR and payroll reports that you can open, by category |
| **Compliance** | Statutory obligations, payments and deadlines. See [Statutory Compliance](compliance) |

Select **Refresh** to load the data again.

## Pre-Check Audit

Run the audit before every payroll run. Each card counts the employees who fail one check. Select a card to see those employees.

| Check | Flags an employee when |
|---|---|
| **Salary Structure Assignment** | The employee is active and has no salary structure, or the structure is inactive |
| **New Joiners** | The employee joined in this cycle without a salary structure |
| **Pending Leave Applications** | A leave application in this cycle waits for approval |
| **Attendance & Absences** | The employee has unmarked or absent days in the cycle |
| **Negative Salary Safeguard** | The salary slip has a net pay of zero or less |
| **Accounting Dimensions** | The employee has no payroll cost center, and the department has none |
| **Bank Details** | The employee is paid by bank and has no account number |

Select **Re-run audit** after you fix the problems.

### Hold a salary

To withhold the salary of an employee for this cycle, select **Set hold** on the row. The salary slip of the employee then gets the status **Withheld**, and the normal bank entry does not pay it.

- To remove the hold before you generate payroll, select **Release** on the row.
- To pay a withheld salary after the run, use **Release withheld salaries** on the run card. See [Run Payroll](run-payroll#pay-withheld-salaries).

## Advances & Deductions

This tab lists paid advances that the employee has not settled by a claim or a return.

To recover an advance from salary:

1. Select **Recover** on the row of the advance.
2. Select the deduction component and enter the amount.
3. Select **Recover in payroll**.

CentHR submits an additional salary deduction. The salary slip of the cycle reduces the net pay by that amount, and HRMS records it as a return on the advance.

## Reports

The Reports tab groups the reports in Payroll, Attendance, Leaves, HR & Staff and Advances. It shows only the reports that you have permission to open. A report opens in Desk.
