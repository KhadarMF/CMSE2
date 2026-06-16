# Phase 16E - WhatsApp Template Delivery Fix

This update changes the WhatsApp outbound test and quotation notification flow to use an approved Meta WhatsApp template message instead of free-form text.

## Updated
- Added `send_whatsapp_template()` in `app/whatsapp_service.py`.
- WhatsApp API Test now sends the approved template `cmse_test` by default.
- Quotation WhatsApp notification now sends the approved template `cmse_test` by default.
- Default template can be changed in Render Environment Variables:
  - `WHATSAPP_TEMPLATE_NAME=cmse_test`
  - `WHATSAPP_TEMPLATE_LANGUAGE=en`

## Why
Free-form text messages may not be delivered if the customer has not opened a WhatsApp conversation within the allowed 24-hour window. Approved templates are the correct method for starting or re-opening WhatsApp conversations.
