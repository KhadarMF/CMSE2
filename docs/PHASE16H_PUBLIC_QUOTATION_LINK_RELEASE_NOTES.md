# Phase 16H - Public Quotation WhatsApp Link

This update adds a secure public quotation page that can be opened from WhatsApp without ERP login.

## Changes
- Added signed public quotation URL generation.
- Added `/sales/public/quotations/<quotation_id>/<token>` public route.
- Added standalone public quotation template.
- Updated quotation WhatsApp template link to use the public customer URL instead of the protected ERP detail page.

## Result
Customers can open quotation links from WhatsApp without entering ERP username/password.
