# Phase 16G - Quotation WhatsApp Template Fix

This patch separates the WhatsApp test template from the quotation sending workflow.

## Changed
- `/whatsapp/test` continues to use the test template (`cmse_test`).
- Quotation **Send WhatsApp** now uses the approved Utility template `quotation_ready`.
- The quotation template sends three body variables:
  1. Customer Name
  2. Quotation Number
  3. Quotation URL
- The dynamic URL button receives the quotation URL, so the **Open Quotation** button can open the ERP quotation page.
- `send_whatsapp_template()` now supports optional Meta template `components` without breaking the existing test template.

## Render Environment Variables
Optional defaults for the test page:

```env
WHATSAPP_TEMPLATE_NAME=cmse_test
WHATSAPP_TEMPLATE_LANGUAGE=en
```

The quotation route explicitly uses:

```env
quotation_ready / en
```

## Test
After deploying:
1. Open `/whatsapp/test` and send a test message.
2. Open a quotation detail page and click **Send WhatsApp**.
3. The received WhatsApp message should show the quotation template, not the old test message.
