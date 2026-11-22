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
| **Missing Salary Structure** | The employee is active and has no salary structure |
| **Inactive Salary Structure** | The salary structure of the employee is inactive or not submitted. Payroll skips the employee |
| **New Joiners** | The employee joined in this cycle without a salary structure |
| **Pending Leave Applications** | A leave application in this cycle waits for approval |
| **Attendance & Absences** | The employee has unmarked or absent days in the cycle, or days in a request that waits for approval |
| **Negative Salary Safeguard** | The salary slip has a net pay of zero or less. If the slip recovers an advance, the row shows the amount |
| **Accounting Dimensions** | The employee has no department, no channel or no payroll cost center. The row names what is missing |
| **Bank Details** | The employee is paid by bank and has no account number |
| **On Hold** | The salary of the employee is on hold in this cycle |

A site without channels does not check the channel. The payroll cost center comes from the employee or, if the employee has none, from the department.

Select **Re-run audit** after you fix the problems.

### Days that wait for approval

A day without attendance is not unmarked when an open leave application or a draft attendance request covers it. The audit and the **Attendance** tab count such a day as "awaiting approval". The approver must approve or reject the request.

### Send reminders

- On the **Attendance & Absences** or **Pending Leave Applications** card, select **Notify all**.
- Or select employees with the checkboxes, then select **Notify**.

CentHR sends one email to each employee who has unmarked days. It sends one email to each approver with all the open leave applications and attendance requests of their team. The approver is the leave approver of the document, then the line manager, then the leave approver of the department. The row shows when the last reminder went out.

### Assign salary structures

Select employees on the **Missing Salary Structure**, **Inactive Salary Structure** or **New Joiners** card, then select **Assign salary structure**. The bulk assignment opens. After you select the structure and the date, the employees from the audit are selected in its list. See [Salary Structure Assignments](salary-structure-assignments).

### Delete negative draft slips

On the **Negative Salary Safeguard** card, select **Delete *n* negative drafts**. CentHR deletes the draft salary slips of the cycle with a net pay below zero. It keeps submitted slips and slips of exactly zero. Correct the cause, then generate the slips again.

An advance deduction that is larger than the salary is a usual cause. CentHR does not change the deduction. You decide how to recover the advance.

### Mark attendance automatically

**Mark auto attendance** shows when a salary structure of the company has automatic attendance. See [Payroll settings](#payroll-settings). The action marks Present on each unmarked working day of the cycle, up to today, for the employees on such a structure. It does not change holidays, leave, days in an open request, or days that have attendance. The same action runs each day by itself.

### Hold a salary

To withhold the salary of an employee, select **Set hold** on the row. Select how long the hold lasts: this pay cycle only, several pay cycles, or until you release it. Enter the reason. Each salary slip of the hold gets the status **Withheld**, and the normal bank entry does not pay it.

- The **On Hold** card lists the employees on hold, with the reason, the end of the hold and who set it.
- To remove a hold, select **Release** on the row. To remove many holds, select the rows, then select **Release holds**.
- To pay a withheld salary after the run, use **Release withheld salaries** on the run card. See [Run Payroll](run-payroll#pay-withheld-salaries).

## Advances & Deductions

This tab lists paid advances that the employee has not settled by a claim or a return.

To recover an advance from salary:

1. Select **Recover** on the row of the advance.
2. Select the deduction component and enter the amount.
3. Select **Recover in payroll**.

CentHR submits an additional salary deduction. The salary slip of the cycle reduces the net pay by that amount, and HRMS records it as a return on the advance.

Select an advance to see its quick view. It shows:

- If the advance is overdue, due in this cycle or upcoming.
- Why payroll recovers it, or does not recover it, in this cycle.
- The expense claims and salary deductions that settled it, with the salary slip of each deduction.

On the **Payroll Processing** tab, the **IOU deduction** column shows what each salary slip deducts to recover advances.

## Reports

The Reports tab groups the reports in Payroll, Attendance, Leaves, HR & Staff, Advances and Other. It shows only the reports that you have permission to open. A report opens in Desk.

A new custom report shows by itself when it reports on an HR or payroll document, or belongs to an HR, payroll or CentHR module.

## Payroll settings

Select **Payroll settings** at the top of the dashboard. You must select a company first. Only an HR Manager can change the settings.

| Setting | Applies to | Meaning |
|---|---|---|
| **Pay cycle starts on day** | The company | Day 1 to 28. The dialog shows the dates of the next cycle. CentHR runs monthly cycles only |
| **Recover overdue advances in payroll** | The company | When you generate payroll, overdue advances are deducted from the salary of that cycle |
| **Working days are counted from** | All companies | Leave or Attendance |
| **A day without attendance counts as** | All companies | Present or Absent. Used when working days are counted from attendance |
| **Count holidays as working days** | All companies | Holidays are part of the days that a salary is spread over |
| **Book payroll per employee** | All companies | The accrual journal names each employee on the payroll payable line |

The last four settings are the Payroll Settings of HRMS. A change applies to every company of the site.

### Confidential batches and auto-attendance

In **Payroll settings**, select **Confidential batches and auto-attendance**. Add one rule for each salary structure that needs one.

| Field | Meaning |
|---|---|
| **Confidential** | The employees on the structure are paid in their own payroll batch. Only users with the role see these employees, their salary slips and their amounts |
| **Role that may see them** | The role for a confidential structure. A System Manager always sees them |
| **Payroll batch** | The name of the batch, for example Confidential or Expat |
| **Mark attendance automatically** | Unmarked working days of these employees become Present |

A user without the role does not see the employees of a confidential structure on any tab, in the totals, in lists or in reports. Employees still see their own salary slips.

