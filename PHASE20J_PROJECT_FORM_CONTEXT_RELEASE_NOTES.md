# Phase 20J - Project Form Context Fix

## Ujeeddo

Phase-kan wuxuu saxayaa forms-ka laga furo project la doortay. Project-ka iyo customer-kiisa hadda way sii raacayaan command-ka la furay, sida Quotation, Service Ticket, Warranty, iyo records-ka kale ee project-ka.

## Waxa la hagaajiyay

- Project Detail wuxuu leeyahay **Project Commands** oo si toos ah u gudbiya `project_id`.
- Quotation cusub wuxuu horay u doortaa project-ka iyo customer-ka saxda ah.
- Capacity iyo Project Type waxaa laga soo buuxiyaa project-ka marka xogtu jirto.
- Service Ticket iyo Warranty waxay horay u doortaan project-ka/customer-ka, waxayna soo buuxiyaan xogta ku habboon.
- `+ Create` wuxuu ilaaliyaa project context-ka marka page-ku leeyahay project la doortay.
- Server-ku wuxuu customer-ka ka xaqiijiyaa project-ka; user-ku si khalad ah customer kale uguma xiriirin karo record-ka.
- Project Commands waxaa kale oo ku jira Task, Material Request, Payment Request, Daily Report, Document, iyo Issue/Risk.

## Database iyo migration

Phase 20J ma beddelayo database schema-ga, sidaas darteed **migration cusub looma baahna**.

Render Pre-Deploy Command-ka sii hay:

```bash
python preflight_check_20d.py && flask db upgrade
```

Ha ku darin `init_db.py` ama `flask db stamp` database hore u shaqaynaya.

## Tijaabo

- Automated suite: `43 passed, 1 skipped`
- Browser QA: Project Commands -> Quotation wuxuu si sax ah u soo qabtay project-ka, customer-ka, capacity-ga, iyo project type-ka.

