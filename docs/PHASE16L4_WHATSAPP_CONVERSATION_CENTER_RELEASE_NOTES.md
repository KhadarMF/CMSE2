# Phase 16L.4 - WhatsApp Conversation Center

## Main Additions

1. WhatsApp Conversation Center
   - New page: `/whatsapp/conversations`
   - Groups WhatsApp messages by customer phone number.
   - Shows last message, unread incoming count, failed count, and total messages per conversation.
   - Search by customer name, phone number, or message text.
   - Filter by message status.

2. Customer Conversation Thread
   - New page: `/whatsapp/conversations/<phone>`
   - Shows full inbound/outbound thread in chronological order.
   - Shows message direction, timestamp, delivery status, read status, and failed status.
   - Allows opening the detailed message log from each chat bubble.

3. Send From Conversation Center
   - Users can send a free-text WhatsApp message from inside the conversation thread.
   - The message is logged in `WhatsAppMessage` with Meta response and status.
   - Note: Meta free-text sending requires an open 24-hour customer service window. If closed, use approved template messages.

4. Retry / Resend Support
   - Existing single-message resend remains available on message detail.
   - New conversation-level `Retry Failed` button retries recent failed outbound messages for that customer.

5. Read Management
   - New `Mark Read` button changes inbound `Received` messages in that thread to `Read`.
   - Dashboard now shows WhatsApp unread, failed, and total message counters.

6. CRM Integration
   - Conversation detail attempts to link the customer profile by phone or name.
   - Shows linked quotations, projects, sales inquiries, and support tickets.
   - Links open the matching ERP detail pages.

7. Navigation
   - Added `WhatsApp Conversation Center` to the Admin/AI menu and System Center menu.
   - Existing WhatsApp Messages log remains available.

## Files Changed

- `app/routes/whatsapp_routes.py`
- `app/routes/dashboard_routes.py`
- `app/templates/base.html`
- `app/templates/dashboard/dashboard.html`
- `app/templates/whatsapp/messages.html`
- `app/templates/whatsapp/message_detail.html`
- `app/templates/whatsapp/conversations.html` (new)
- `app/templates/whatsapp/conversation_detail.html` (new)

## Deployment Notes

- No database migration is required; this phase reuses the existing `WhatsAppMessage` table.
- Run normally on Render after replacing the ZIP contents.
- Ensure existing WhatsApp environment variables remain configured:
  - `WHATSAPP_ACCESS_TOKEN`
  - `WHATSAPP_PHONE_NUMBER_ID`
  - `WHATSAPP_BUSINESS_ACCOUNT_ID`
  - `WHATSAPP_VERIFY_TOKEN`
  - `PUBLIC_BASE_URL`

