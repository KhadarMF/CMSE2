# Phase 15F - AI Assistant & Smart ERP Intelligence

Added:
- AI Assistant menu and dashboard.
- AI Settings page for admin.
- AI Ask page for general ERP help, translations, report drafting and customer messages.
- AI Service Ticket Helper: analyzes complaint, suggests priority, root cause, technician checklist and customer reply.
- AI CRM Follow-up Helper: creates follow-up plan and WhatsApp-style customer message.
- AI Report Generator: drafts weekly operations, service support, CRM and executive reports.
- AI Interaction Log for audit, review and management control.
- Offline-safe mode: if no API key is configured, requests are still logged and guidance is returned.

Important:
- Live AI is disabled by default.
- Set OPENAI_API_KEY in Render Environment Variables or enter API key in Admin > AI Settings.
- AI suggestions do not update ERP data automatically. User must review and save official records manually.

Test:
1. Copy previous instance/solar_documents.db into this folder's instance folder.
2. Run python init_db.py
3. Run python run.py
4. Open AI Assistant > AI Dashboard.
5. For live AI, configure AI Settings.