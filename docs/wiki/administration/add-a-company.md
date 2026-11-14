---
title: Add a Company
order: 4
---

# Add a Company

You can add a group company to CentHR at any time. No development is needed.

1. Create the company in CentHR, with its own employee ID prefix and number series.
2. In [CentHR Settings](settings), add a row in **Authorization** with the company, the site address and the API credentials.
3. Check the users in **Error Alerts**.
4. Use the [Data Migration Tool](data-migration) to copy the history of the company, in the migration order.
5. Check the Data Logs and fix the failures.

After this, CentHR sends every change of the company to its site. Shift types and salary components also go to the new site.

The new company appears in the dashboard, the lists, the filters and the API Logger, the same as the other companies.
