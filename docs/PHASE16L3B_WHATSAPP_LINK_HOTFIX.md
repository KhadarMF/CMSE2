# Phase 16L.3B WhatsApp Link Hotfix

This hotfix fixes WhatsApp quotation button URLs that open as 404 because Meta leaves the literal `{{1}}` placeholder in the final URL, for example:

`https://cmse2.onrender.com/sales/q/%7B%7B1%7D%7D<signed-token>`

The public quotation route now strips accidental `{{1}}` / encoded `{{1}}` prefixes before validating the signed token.

## Included status

- Delivered/Read/Failed webhook status update support: already included from 16L.2.
- Retry/Resend button: already included from 16L.3A.
- Conversation history: not yet included; planned for 16L.3C / 16L.4.
