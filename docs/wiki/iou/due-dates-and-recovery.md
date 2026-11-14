---
title: Due Dates and Salary Recovery
order: 5
---

# Due Dates and Salary Recovery

Each paid IOU has a due date. The employee must settle the IOU with a claim before that date. After the due date, CentHR deducts the outstanding amount from the salary of the employee.

## The due date

| Purpose type | Due date |
|---|---|
| Travel | Payment date + tenure + 7 days |
| Other | Payment date + 5 days |

The administrator can change the 7 days and the 5 days in [CentHR Settings](../administration/settings#iou).

## Reminders

Every day, CentHR checks the open IOUs. Three days before the due date, CentHR sends the employee an email to submit the claim.

## Salary recovery

Seven days before the next payroll date, CentHR does these steps for each IOU that is past its due date:

1. It creates a salary deduction (Additional Salary) for the outstanding amount, for the next payroll.
2. It sends the employee an email. The HOD, HR and Finance get a copy.

CentHR skips an IOU when a claim against it waits for approval, or when a deduction already exists.

The payroll date is the **Payroll Day of Month** in CentHR Settings. If it is 0, the payroll date is the last day of the month.

HR can also recover an advance by hand from the **Advances & Deductions** tab of the [Payroll Dashboard](../payroll/payroll-dashboard).
