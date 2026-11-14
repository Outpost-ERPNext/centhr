---
title: Roles and Access
order: 4
---

# Roles and Access

Your roles decide which screens you see and which actions you can do. Your company permissions decide which companies' records you see.

## Where access comes from

CentHR does not have its own permission list. It uses the standard permissions of the HR site:

- **Role permissions** decide which record types a role can read, create, change, submit, cancel or delete. The administrator sets them in **Role Permission Manager**.
- **User permissions** limit a user to one or more companies. A user limited to one company sees only the records of that company.

CentHR checks your permissions again on every action. A button that shows on the screen does not bypass these checks.

:::note
To give a user access to a CentHR screen, give their role the matching permission in Role Permission Manager. CentHR shows the screen in the menu when the role can read that record type.
:::

## Typical responsibilities

| Person | Work in CentHR |
|---|---|
| Central administrator | Connects company sites, chooses who gets failure alerts, runs the Data Migration Tool, resyncs failed transfers |
| HR manager | Oversees HR for the group, gives the final approval of leave, maintains leave types, shifts, salary structures and payroll |
| Company HR user | Maintains employees, attendance, leave and shifts for one company |
| Payroll user | Maintains salary structures and assignments, and runs payroll |
| Head of department (leave approver) | Gives the first approval of leave applications |
| Line manager | Approves attendance requests and IOUs of the employees who report to them |
| Finance 1 and Finance 2 | Approve and pay IOUs and claims. See [IOU Management](../iou) |
| Employee | Uses the self-service forms, and sees their own records |

## Shared records

A line manager or an IOU approver often has only the Employee role. CentHR shares each request with its approver, so the approver can open and act on that one record without wider access.

A manager in a different company gets access to an employee automatically when the employee reports to them. See [Cross-Company Reporting](../employee-master/cross-company-reporting).
