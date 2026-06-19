# Phase 16K - WhatsApp Full Public URL Fix

This release stabilizes WhatsApp quotation links.

## What changed
- Quotation WhatsApp button now sends the complete public URL as one dynamic URL variable.
- Public quotation link uses the short signed route: `/sales/q/<token>`.
- The public quotation page opens without ERP login.
- A public PDF route was added: `/sales/q/<token>/pdf`.
- Public quotation page now includes a **Download PDF** button.

## Meta template configuration
For the `quotation_ready` template button:

- Button type: `Visit website`
- URL type: `Dynamic`
- Website URL: `{{1}}`
- Sample URL: `https://cmse2.onrender.com/sales/q/example-token`

Do not use `/sales/quotation/1`; that is the internal ERP route and requires login.
