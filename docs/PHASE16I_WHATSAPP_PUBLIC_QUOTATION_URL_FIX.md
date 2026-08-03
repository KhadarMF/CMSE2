# Phase 16I - WhatsApp Public Quotation URL Fix

This patch fixes the WhatsApp quotation button URL.

## What changed

- The quotation message body still receives the full public URL.
- The WhatsApp dynamic URL button now receives only the URL path, not the full URL.
- This avoids broken links such as Facebook or duplicated URL prefixes.

## Required Meta template setting

For the `quotation_ready` template, the Call-to-Action website URL must be:

```text
https://cmse2.onrender.com/{{1}}
```

The URL sample should be a path only, for example:

```text
sales/public/quotations/1/example-token
```

Do not put a full URL in the button variable sample.
