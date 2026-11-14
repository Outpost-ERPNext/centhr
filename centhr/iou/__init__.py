"""IOU Management (SOP/AP/003): IOUs are Employee Advances, IOU and expense claims are Expense Claims.

Approval: HOD (the employee's Reports To) → Finance 1 → Finance 2 (pays the IOU). Claims stop at Finance 1.
The approvers and their proxies are set in CentHr Settings, IOU tab.
"""

ADVANCE = "Employee Advance"
CLAIM = "Expense Claim"
IOU_DOCTYPES = (ADVANCE, CLAIM)
