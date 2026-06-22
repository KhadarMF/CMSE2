# Phase 16L.3A - WhatsApp Production Link, Resend, and Quotation Customer Combo Fix

## Added
- Quotation form Customer field is now a real dropdown/combobox loaded from the Customers table.
- Quotation WhatsApp number textbox auto-fills from the selected quotation customer's phone number.
- Quotation WhatsApp messages now use PUBLIC_BASE_URL for public links, preventing local links like http://127.0.0.1:5000.
- Quotation WhatsApp uses `quotation_ready_v2` by default.
- Quotation template variables now match the approved v2 template:
  - Body {{1}} = Customer Name
  - Body {{2}} = Quotation Number
  - Button {{1}} = signed quotation token
- Added Resend button on WhatsApp Message Detail page.
- Resend creates a new WhatsAppMessage log record and preserves provider response/error.

## Meta Template Expected
Template name:
- `quotation_ready_v2`

Button setup:
- URL Type: Dynamic
- Website URL: `https://cmse2.onrender.com/sales/q/{{1}}`
- Sample URL: `https://cmse2.onrender.com/sales/q/example-token`

## Environment Variables
Render should include:
- `PUBLIC_BASE_URL=https://cmse2.onrender.com`
- `WHATSAPP_QUOTATION_TEMPLATE_NAME=quotation_ready_v2`
- `WHATSAPP_QUOTATION_TEMPLATE_LANGUAGE=en`

Keep `WHATSAPP_TEMPLATE_NAME=cmse_test` for the manual WhatsApp API Test page.
