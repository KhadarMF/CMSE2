# Phase 16L.3A Stable Fix

Fixes added after local testing:

1. Robust `.env` loading from the project root so `WHATSAPP_ACCESS_TOKEN` is read reliably in local Visual Studio/VS Code runs.
2. Quotation WhatsApp number auto-fill improved: inquiry phone first, then Customer table phone using exact/trimmed/case-insensitive customer name lookup.
3. Quotation form now shows selected customer phone/WhatsApp preview from the Customers table.
4. Quotation WhatsApp detail page shows a clear warning when no customer phone exists.

Do not commit `.env`. Keep permanent Meta token only in local `.env` and Render Environment Variables.
