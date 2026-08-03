# Phase 16B — AI CRM Agent + AI Project Manager

## Added

### AI CRM Agent
- New AI menu page: `AI Assistant → AI CRM Agent`
- New inquiry detail action button: `AI CRM Agent`
- Generates:
  - Lead Temperature: Hot / Warm / Cold
  - Opportunity Score
  - Customer Need Summary
  - Recommended Next Action
  - WhatsApp follow-up in Somali
  - WhatsApp follow-up in English
  - Email follow-up draft
  - Sales objection handling notes
  - Manager notes
- Saves AI output to `AIInteractionLog`.
- Saves useful AI fields to `SalesInquiry`:
  - `ai_opportunity_score`
  - `ai_lead_temperature`
  - `ai_followup_text`
  - `ai_recommended_action`
  - `ai_last_followup`

### AI Project Manager
- New AI menu page: `AI Assistant → AI Project Manager`
- New project detail action button: `AI Project Manager`
- Generates:
  - Project Health Score
  - Risk Level
  - Delay Prediction
  - Progress Summary
  - Key Risks
  - Recommended Actions
  - Required Management Decisions
  - Team / Resource Notes
  - Customer Communication Note
- Saves AI output to `AIInteractionLog`.
- Saves useful AI fields to `Project`:
  - `ai_health_score`
  - `ai_risk_level`
  - `ai_delay_prediction`
  - `ai_project_summary`
  - `ai_recommended_actions`
  - `ai_last_analysis`

## Database
- Auto-upgrade code added for existing PostgreSQL deployments.
- The system attempts to add missing Phase 16B columns automatically on app request.

## Permissions
- Added permissions:
  - `ai-crm-agent`
  - `ai-project-manager`

## Notes
- AI outputs remain draft guidance. Management, Sales, or Project Manager must review before customer communication or operational decisions.
