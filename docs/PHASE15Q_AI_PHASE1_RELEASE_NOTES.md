# Phase 15Q — ERP AI Integration Phase 1

## Cadceed-Maal Solar Energy

This release adds the first practical AI modules inside the ERP.

## New AI Modules

1. **AI Project Report Writer**
   - URL: `/ai/project-report`
   - Can generate professional draft reports from:
     - Site Survey & Load Assessment
     - Load Assessment
     - Daily Site Report
     - Delivery Note
     - Testing
     - Commissioning
     - Handover
   - Direct form button added: **AI Report**

2. **AI Quotation Draft Generator**
   - URL: `/ai/quotation-draft`
   - Can generate:
     - customer need summary
     - draft solar sizing notes
     - BOQ draft notes
     - proposal wording
     - WhatsApp follow-up message
   - Direct quotation button added: **AI Draft**

3. **AI Stock Assistant**
   - URL: `/ai/stock-assistant`
   - Can answer stock/material questions from ERP material item data.
   - Direct button added from Material Items: **Ask Stock AI**

## Permission Keys Added

Admin can grant these new permissions from User Form Permissions:

- `ai-project-report`
- `ai-quotation`
- `ai-stock`

These are also included under the AI Assistant parent menu.

## Security & Control

- AI outputs are saved in existing AI logs.
- AI outputs are DRAFT by default.
- Final approval must still be done by responsible staff.
- Stock cost visibility is limited to Admin, Management and Finance Officer roles.
- AI does not modify ERP records automatically.

## Files Changed

- `app/routes/ai_routes.py`
- `app/ai_service.py`
- `app/models.py`
- `app/permissions.py`
- `app/templates/base.html`
- `app/templates/ai/dashboard.html`
- `app/templates/forms/detail.html`
- `app/templates/sales/quotation_detail.html`
- `app/templates/materials/items.html`

## New Templates

- `app/templates/ai/phase1_project_report.html`
- `app/templates/ai/phase1_project_report_single.html`
- `app/templates/ai/phase1_quotation.html`
- `app/templates/ai/phase1_quotation_single.html`
- `app/templates/ai/phase1_stock.html`

## Testing Performed

- Python compile check completed successfully for modified source files.
- Full Flask app runtime test was not executed in this container because Flask is not installed in the tool environment.

