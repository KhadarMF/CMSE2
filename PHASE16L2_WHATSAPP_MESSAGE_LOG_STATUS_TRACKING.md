# Phase 16L.2 – WhatsApp Message Log & Status Tracking

This release adds a WhatsApp tracking layer for CMSE ERP.

## Added

- New database model: `WhatsAppMessage`
- New page: `/whatsapp/messages`
- New detail page: `/whatsapp/messages/<id>`
- WhatsApp outbound logging for:
  - WhatsApp API Test
  - Sales Quotation WhatsApp sending
- Webhook status tracking for:
  - Sent
  - Delivered
  - Read
  - Failed
- Inbound WhatsApp message logging
- Menu entries:
  - AI Assistant → WhatsApp Messages (Admin)
  - System Center → WhatsApp Messages

## What the log stores

- Customer/recipient
- Phone number
- Template name
- Related document type and reference
- Meta message ID (`wamid...`)
- Status
- Error message if failed
- Provider response
- Webhook payload
- Sent, Delivered, Read, Failed timestamps

## Notes

- The new table is created automatically via `db.create_all()` when the app runs.
- The webhook must remain subscribed to `messages` in Meta Developers.
- Delivery/read status depends on Meta sending webhook status callbacks.
