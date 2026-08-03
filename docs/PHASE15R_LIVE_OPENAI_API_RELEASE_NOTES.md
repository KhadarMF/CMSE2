# Phase 15R — Live OpenAI API Integration

## What changed

This release connects the ERP AI Assistant to the live OpenAI API when an API key is configured.

## Updated files

- `app/ai_service.py`
  - Added live OpenAI Responses API call.
  - Kept Chat Completions compatibility if API Base URL ends with `/chat/completions`.
  - Added safer API URL normalization.
  - Added clear API error handling.
  - Kept local ERP fallback so pages do not become blank if the API fails.
  - Added connection test helper.

- `app/routes/ai_routes.py`
  - AI settings now default to `https://api.openai.com/v1/responses`.
  - Added “Save & Test API Connection” workflow.
  - Upgrades old default `/chat/completions` endpoint to `/responses`.

- `app/templates/ai/settings.html`
  - Added clearer API setup instructions.
  - Added API test button.
  - Added test result and error display.

- `app/models.py`
  - AISetting default provider updated to OpenAI Responses API.
  - AISetting default API Base URL updated to `/v1/responses`.

- `.env.example`
  - Added `OPENAI_API_KEY` example.

## How to configure

Recommended production setup:

1. Create an OpenAI API key from the OpenAI dashboard.
2. Add it to your server environment variables as:

```bash
OPENAI_API_KEY=sk-your_key_here
```

3. Restart the ERP app.
4. Login as Admin.
5. Open `AI Assistant > AI Settings`.
6. Confirm:
   - Enable Live AI: checked
   - Provider: OpenAI Responses API
   - Model Name: gpt-4o-mini
   - API Base URL: https://api.openai.com/v1/responses
7. Click `Save & Test API Connection`.
8. Expected result: `AI API CONNECTED`.

## Security note

Do not share the API key with staff. Admin should configure the key on the server or in AI Settings. The ERP uses the environment variable first, then the saved database key.
