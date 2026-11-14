---
title: Approve and Pay
order: 4
---

# Approve and Pay

Approvers act on IOUs and claims on the IOU Dashboard. In the menu, select **IOU > IOU Dashboard**.

## Approval stages

| Document | Stage 1 | Stage 2 | Stage 3 |
|---|---|---|---|
| IOU application | HOD (the line manager) approves | Finance 1 approves | Finance 2 pays |
| IOU claim | HOD (the line manager) approves | Finance 1 approves | — |

The HOD is the **Reports To** manager of the employee. The administrator sets Finance 1 and Finance 2 in [CentHR Settings](../administration/settings#iou).

If the employee has no line manager, an HR manager acts at the HOD stage.

To find your work, select the **Waiting for Me** card on the [IOU Dashboard](dashboard).

## Approve, reject or modify

At the HOD and Finance 1 stages, the approver has three actions:

- **Approve** moves the document to the next stage.
- **Reject** stops the document. You must enter a reason. The employee gets an email with the reason.
- **Modify** changes the IOU amount, or the claim type and amount of claim rows. The employee gets an email with the change.

## Pay an IOU (Finance 2)

Finance 2 does not reject or modify. Finance 2 approves the IOU by paying it.

1. Select **Pay** on the IOU.
2. In **Paid From**, select the bank account.
3. Enter the **Bank Reference No**. If you leave it empty, CentHR uses the document number.
4. Under **Payment Advice**, select **Attach** and upload the payment advice.
5. Confirm.

CentHR creates a payment entry and the settlement period of the IOU starts.

:::caution
The user who approved the IOU as Finance 1 cannot pay it. Another Finance user or the proxy must pay.
:::

## Pay a claim (Finance 1)

When an approved claim has an amount to pay the employee, Finance 1 or their proxy sees **Pay** on the claim. The steps are the same as for an IOU.

## Proxies

Each approver can have a proxy in CentHR Settings. The proxy can act at the same stage as the approver.

If the approver does not act within the escalation time (24 hours by default), CentHR sends an email to the proxy. It does this one time for each stage.
