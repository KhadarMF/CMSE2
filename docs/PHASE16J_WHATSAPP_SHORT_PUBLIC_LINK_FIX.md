# Phase 16J - WhatsApp Short Public Quotation Link Fix

## What changed

This release fixes Meta WhatsApp Dynamic URL button issues by using a short public quotation link:

```text
https://cmse2.onrender.com/sales/q/<signed-token>
```

The signed token contains the quotation ID and reference number internally, so Meta needs only one URL variable.

## Meta template setting required

For the `quotation_ready` template button, configure:

```text
URL Type: Dynamic
Website URL: https://cmse2.onrender.com/sales/q/{{1}}
Sample URL: example-token
```

Do not put the full URL in the sample field. The sample field is only for the token variable.

## WhatsApp message behavior

When Send WhatsApp is clicked from a quotation:

- Body variable {{1}} = customer name
- Body variable {{2}} = quotation reference number
- Body variable {{3}} = full public quotation URL
- Button variable {{1}} = signed token only

## Public quotation route

Added:

```text
/sales/q/<token>
```

This route opens the quotation without ERP login after validating the signed token.

## Backward compatibility

The older public route remains available:

```text
/sales/public/quotations/<quotation_id>/<token>
```
