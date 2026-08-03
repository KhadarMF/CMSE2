# PHASE 16A — AI Service Ticket Agent

## Cadceed-Maal Solar Energy ERP

This release adds a real AI Service Ticket Agent to the After-Sales & Warranty module.

## New Features

1. **Analyze with AI button** on Service Ticket detail page.
2. AI generates and saves:
   - AI Category
   - AI Priority
   - Likely Root Cause
   - Technician Action Plan
   - Spare Parts / Tools
   - Estimated Visit Time
   - Customer Reply Draft in Somali + English
   - Technician Checklist
   - Confidence Score
   - Last AI Analysis date/time
3. AI analysis is saved directly on the ticket record.
4. Every AI analysis is also saved in AI Logs as `AI Service Ticket Agent`.
5. Existing databases are auto-upgraded with new columns on startup.
6. New permission key added: `ai-service-ticket-agent`.

## New Database Fields Added to support_ticket

- ai_category
- ai_priority
- ai_root_cause
- ai_action_plan
- ai_spare_parts
- ai_visit_estimate
- ai_customer_reply
- ai_technician_checklist
- ai_confidence_score
- ai_last_analysis

## How to Test

1. Login as Admin.
2. Ensure `ai-service-ticket-agent` permission is enabled for the user/role.
3. Open After-Sales & Warranty → Service Tickets.
4. Open any ticket.
5. Click **Analyze with AI**.
6. Confirm the AI panel fills with category, priority, root cause, action plan and customer reply.
7. Check AI Assistant → AI Logs to confirm a log was created.

## Notes

- The AI output is a draft and must be reviewed by an engineer.
- The feature uses the existing OpenAI API settings already configured in Phase 15S/15T.
- If API fails, the system stores local/offline output and records the error in AI Logs.
