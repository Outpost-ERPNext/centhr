---
title: Statutory Compliance
order: 6
---

# Statutory Compliance

A statutory obligation is an amount that the company must pay to an authority, for example tax or pension deducted from salaries. The Compliance tab of the [Payroll Dashboard](payroll-dashboard) shows what each obligation accrued in the cycle, what was paid and when it is due.

## Set up an obligation

Select **Configure obligations** on the Compliance tab. A dialog lists the obligations of the company. Select **Add obligation** to create one, or the pencil icon to change one. You can also disable or delete an obligation. If you do not have permission to change obligations, the list is read-only.

Create one record for each obligation:

| Field | Value |
|---|---|
| **Obligation** | The name, for example PAYE or Pension |
| **Company** | The company that owes it |
| **Liability Account** | The account where payroll books the amount. It must be a plain liability account, not a payable party account |
| **Payment Account** | The bank or cash account that pays it |
| **Frequency** | Monthly, Quarterly, Bi-Annually or Yearly |
| **Due Day** | The day of the month when payment is due |
| **Due Months** | For a frequency other than Monthly: the months when payment is due |

## Deadlines

A monthly obligation falls due in the month after the cycle. Other obligations fall due in their next due month.

| Deadline status | Meaning |
|---|---|
| **Settled** | Nothing is outstanding |
| **On Track** | The deadline is more than 7 days away |
| **Due Soon** | The deadline is in 7 days or less |
| **Overdue** | The deadline has passed and an amount is outstanding |

## See where the amount comes from

Select **Breakdown** on the row. The dialog shows each employee and the salary components that payroll books to the liability account of the obligation, from the submitted salary slips of the cycle.

- **From salary slips** is the total of these components.
- **Booked without a slip** is what the ledger holds on the account and no salary slip explains, for example a manual journal entry.
- **Payable in the cycle** is the sum of the two.

Select **Export (Excel)** to download the breakdown. CentHR finds the components by their account, not by their name. Set the account of each salary component for the company.

## See the vouchers and the payment requests

Select the number of vouchers, or the payment details, on the row. The dialog lists each accrual voucher and each payment voucher of the cycle with its type, date and amount. Select a voucher to open it in Desk. The dialog also lists the payment requests of the obligation with their status.

## Pay an obligation

1. On the Compliance tab, select **Request payment** on the row.
2. Check the amount and the account in **Pay from**.
3. Select **Request payment**.

CentHR creates a Payment Request Form with the status **Pending Approval**. A user with the role Accounts Manager or System Manager approves or rejects it in the dialog of the row. A rejection needs a reason.

After the approval, CentHR creates a draft bank entry. Accounts reviews and submits it. The payment request then gets the status **Paid**. An obligation has one open payment request at a time.
