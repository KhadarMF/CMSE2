# Phase 16D - WhatsApp Cloud API Integration

This release connects Cadceed-Maal ERP to Meta WhatsApp Cloud API.

## Added
- New WhatsApp service helper: `app/whatsapp_service.py`
- New WhatsApp routes: `app/routes/whatsapp_routes.py`
- Webhook endpoint: `/whatsapp/webhook`
- Manual test page: `/whatsapp/test`
- Quotation detail button: **Send WhatsApp**
- WhatsApp send logs saved in `NotificationLog`
- Environment variable examples for Render

## Meta WhatsApp details used
- Public Render URL: `https://cmse2.onrender.com`
- Webhook URL: `https://cmse2.onrender.com/whatsapp/webhook`
- Phone Number ID: `1091324590741999`
- WhatsApp Business Account ID: `4334785340171192`
- Verify Token: `cmse_whatsapp_verify_2026`

## Required Render Environment Variables
Set these in Render Dashboard → Environment:

```env
WHATSAPP_ACCESS_TOKEN=PASTE_YOUR_META_ACCESS_TOKEN_HERE
WHATSAPP_PHONE_NUMBER_ID=1091324590741999
WHATSAPP_BUSINESS_ACCOUNT_ID=4334785340171192
WHATSAPP_VERIFY_TOKEN=cmse_whatsapp_verify_2026
WHATSAPP_GRAPH_API_VERSION=v25.0
PUBLIC_BASE_URL=https://cmse2.onrender.com
```

Do not paste the access token into source code or GitHub.

## Meta Webhook Configuration
In Meta Developer Console → WhatsApp → Configuration, set:

- Callback URL: `https://cmse2.onrender.com/whatsapp/webhook`
- Verify Token: `cmse_whatsapp_verify_2026`

Subscribe to WhatsApp webhook fields such as `messages`.

## How to test
1. Deploy this ZIP to Render.
2. Add the Render environment variables above.
3. Visit `/whatsapp/test` as Admin.
4. Enter a recipient phone number in international format, for example `+25263XXXXXXX`.
5. Send a test message.
6. Open a quotation detail page and use **Send WhatsApp**.

## Notes
- Without a payment method, Meta may allow only limited or customer-initiated/free-tier messaging.
- For production customer notifications, add a valid payment method in Meta Business Settings.
- Access tokens generated in API Setup are temporary. For production, create a System User token with WhatsApp permissions.
