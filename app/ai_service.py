import json
import os
import urllib.request
import urllib.error
from datetime import datetime

CADCEED_SYSTEM_PROMPT = """
You are the Cadceed-Maal Solar Energy ERP AI Assistant.
Work like a professional ERP trainer, solar technical assistant, customer support advisor, and operations analyst.
Give practical, structured answers. Use concise business language. When relevant, provide:
1) Summary
2) Recommended action
3) Priority or risk
4) Step-by-step procedure
5) Customer/management message draft
Never change ERP records automatically. Only suggest actions for user review.
""".strip()


def get_api_key(setting=None):
    """Return API key from environment first, then database settings.
    Production recommendation: keep OPENAI_API_KEY in server environment variables.
    """
    key = os.environ.get("OPENAI_API_KEY") or (setting.api_key if setting and setting.api_key else "")
    return (key or "").strip()


def build_user_content(prompt, context_data=None):
    user_content = prompt or ""
    if context_data:
        user_content = f"ERP CONTEXT:\n{context_data}\n\nUSER REQUEST:\n{prompt or ''}"
    return user_content.strip()


def build_messages(system_prompt, prompt, context_data=None):
    user_content = build_user_content(prompt, context_data)
    return [
        {"role": "system", "content": system_prompt or CADCEED_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _safe_count(model):
    try:
        return model.query.count()
    except Exception:
        return 0

def get_erp_snapshot():
    """Small database-aware snapshot for local AI mode.
    This works without API and helps answer simple questions like:
    how many customers/projects/tickets/tasks are in the system?
    """
    try:
        from app.models import (
            Customer, Employee, Project, ProjectTask, SupportTicket,
            SalesInquiry, SalesQuotation, MaterialItem, SystemNotification
        )
        open_ticket_statuses = ['Open', 'Assigned', 'In Progress', 'Waiting Parts', 'Pending Customer']
        overdue_tasks = 0
        try:
            from datetime import date
            overdue_tasks = ProjectTask.query.filter(ProjectTask.due_date < date.today()).filter(ProjectTask.status != 'Completed').count()
        except Exception:
            overdue_tasks = 0
        open_tickets = 0
        urgent_tickets = 0
        try:
            open_tickets = SupportTicket.query.filter(SupportTicket.status.in_(open_ticket_statuses)).count()
            urgent_tickets = SupportTicket.query.filter(SupportTicket.priority == 'Urgent').filter(SupportTicket.status.in_(open_ticket_statuses)).count()
        except Exception:
            pass
        return {
            'customers': _safe_count(Customer),
            'employees': _safe_count(Employee),
            'projects': _safe_count(Project),
            'tasks': _safe_count(ProjectTask),
            'overdue_tasks': overdue_tasks,
            'service_tickets': _safe_count(SupportTicket),
            'open_tickets': open_tickets,
            'urgent_tickets': urgent_tickets,
            'crm_inquiries': _safe_count(SalesInquiry),
            'quotations': _safe_count(SalesQuotation),
            'material_items': _safe_count(MaterialItem),
            'notifications': _safe_count(SystemNotification),
        }
    except Exception:
        return {}


def _contains_any(text, words):
    return any(w in text for w in words)


def _extract_fault_code(text):
    import re
    m = re.search(r'\b([A-Z]?\d{2,4}|E\d{1,4}|F\d{1,4})\b', text.upper())
    return m.group(1) if m else ''


def local_ai_response(prompt, context_data=None):
    """Offline/local ERP helper.
    Phase 15J: smarter local answers + database-aware summaries.
    It does not call the internet and it does not modify records.
    """
    original = prompt or ""
    p = original.lower()
    c = context_data or ""
    both = (p + "\n" + c.lower()).strip()
    snap = get_erp_snapshot()

    header = "AI Local Assistant Response (API key not connected yet)\n"
    note = "Note: This is local/offline guidance. For full live AI, add OPENAI_API_KEY/API key in AI Settings.\n"

    # 1) Identity / simple Somali questions
    if _contains_any(both, ["maxaad tahay", "who are you", "what are you", "waa maxay ai", "what is ai"]):
        return f"""{header}
{note}

Waxaan ahay AI Assistant gudaha Cadceed-Maal ERP.
I am a built-in ERP assistant for Cadceed-Maal Solar Energy.

Waxaan kaa caawin karaa:
1. Service Ticket: cabasho customer, priority, technician checklist, customer reply.
2. CRM/Sales: follow-up message, lead status, next sales action.
3. Projects: project summary, risks, weekly report.
4. Reports: management summary and operational notes.
5. Translation: Somali ↔ English professional wording.
6. ERP guidance: sida loo isticmaalo modules-ka system-ka.

Tusaale su'aal fiican:
"Analyze this service ticket: customer says inverter fault E03 and battery drains fast at night. Give category, priority, possible causes, checklist and customer reply."
""".strip()

    # 2) Direct database count questions
    if _contains_any(both, ["how many", "immisa", "in my system", "systemka", "tirada", "count"]):
        labels = {
            'customers': 'Customers / Macaamiil',
            'employees': 'Employees / Shaqaale',
            'projects': 'Projects / Mashruucyo',
            'tasks': 'Tasks / Hawlo',
            'overdue_tasks': 'Overdue Tasks / Hawlo waqtigii dhaafay',
            'service_tickets': 'Service Tickets / Cabashooyin adeeg',
            'open_tickets': 'Open Tickets / Tickets furan',
            'urgent_tickets': 'Urgent Tickets / Degdeg',
            'crm_inquiries': 'CRM Inquiries / Weydiimo sales',
            'quotations': 'Quotations / Qiimeynno',
            'material_items': 'Material Items / Alaab',
            'notifications': 'Notifications / Ogeysiisyo',
        }
        lines = [f"- {labels[k]}: {v}" for k, v in snap.items() if k in labels]
        return f"""{header}
{note}

ERP Quick Count / Tirada System-ka
{chr(10).join(lines) if lines else '- Database snapshot is not available on this page.'}

Fiiro gaar ah:
Tiradani waxay ka imanaysaa database-ka hadda ku xiran local app-kaaga. Haddii aad database cusub ama folder kale isticmaalayso, tiradu way is beddeli kartaa.
""".strip()


    # Phase 15Q / AI Phase 1: structured offline responses for ERP AI modules
    if _contains_any(both, ["phase1_project_report", "project report ai", "daily site progress report", "generate ai daily report", "handover summary", "commissioning report"]):
        return f"""{header}
{note}

DRAFT - AI Project Report Writer

1. Project Information
{c[:1200] if c else original[:1200]}

2. Work Completed Summary
- The submitted form data has been converted into a formal project report draft.
- Review the original form fields and confirm that work completed, materials used, issues, and next plan are accurate.

3. Materials Used
- Use the materials section from the ERP form. If it is blank, mark it as Not provided.

4. Pending Work
- Complete all pending activities listed in the form.
- Assign a responsible person and target date before approval.

5. Issues / Risks
- Any issue mentioned in the form must be followed through until closure.
- If materials are missing, Warehouse should confirm availability and dispatch plan.

6. Required Actions
- Engineer/Project Manager to review this draft.
- Correct missing or unclear information.
- Approve only after checking technical accuracy.

7. Next Plan
- Continue the next activity listed in the ERP form.
- Update the project record after completion.

8. Professional Summary
This report is generated as a DRAFT for management review. It must not be treated as final until reviewed and approved in the ERP.
""".strip()

    if _contains_any(both, ["phase1_quotation", "quotation draft generator", "solar design draft", "generate ai quotation", "customer proposal text"]):
        return f"""{header}
{note}

DRAFT - AI Quotation Draft Generator

1. Customer Need Summary
{c[:1200] if c else original[:1200]}

2. Recommended Solar System
- Recommended system type should match the customer requirement and the ERP quotation/project type.
- Confirm whether the system is hybrid, off-grid, pumping, backup, commercial, residential, or mosque/school/farm use.

3. PV Sizing Draft
- Use actual daily load, site location, panel wattage, and expected sun hours.
- If load or sun hours are missing, sizing cannot be finalized.

4. Inverter Sizing Draft
- Size the inverter based on peak load, starting loads such as ACs/pumps, and future expansion.

5. Battery Sizing Draft
- Size battery based on night load, backup hours, usable ratio, and required autonomy.
- If night load is missing, request it before final approval.

6. BOQ Draft
- Solar panels
- Hybrid/off-grid inverter
- Lithium battery bank
- PV mounting structure
- DC/AC protection
- Cables and accessories
- Installation, testing, commissioning and handover

7. Technical Assumptions
- Draft only; engineering review required.
- Stock and prices must be confirmed from ERP before sending to customer.

8. Customer Proposal Text
Dear Customer, Cadceed-Maal Solar Energy has prepared a draft solar solution based on your requirement. The system will be finalized after technical review, stock confirmation, and management approval.

9. WhatsApp Follow-up Message
Dear Customer, thank you for your request. We are reviewing your load details and preparing a suitable solar quotation. We will confirm the final design, price, warranty and delivery timeline after engineering review.

Status: DRAFT - Requires Engineering, Warehouse, Finance and Manager approval.
""".strip()

    if _contains_any(both, ["phase1_stock", "stock assistant", "ask stock ai", "branch availability", "missing items", "reorder warning"]):
        show_cost = _contains_any(both, ["admin", "management", "finance"])
        cost_note = "Cost information may be shown only to authorized roles." if show_cost else "Cost and selling price are hidden for this role."
        return f"""{header}
{note}

DRAFT - AI Stock Assistant

1. Direct Answer
The stock answer must be based only on the ERP stock/material data shown below.

2. Stock Data Reviewed
{c[:1600] if c else original[:1600]}

3. Available Items
- List matching active items found in the ERP data.
- Confirm units and categories before reservation.

4. Missing Items
- If a requested item is not found, mark it as: Not found in provided stock data.

5. Branch Availability
- Branch-level quantity is not available unless branch stock records exist. Use material item master as reference only.

6. Reorder Warning
- If quantity/reorder fields are not provided, ask Warehouse to confirm physical stock.

7. Purchase Recommendation
- Create a purchase request for missing or low-stock items after warehouse confirmation.

8. Permission Note
{cost_note}

Status: DRAFT - Warehouse confirmation required before reservation or purchase.
""".strip()

    # 3) Service Ticket / Complaint smart response
    if _contains_any(both, ["ticket", "complaint", "fault", "cilad", "service", "inverter", "battery", "pump", "bms", "e03", "cabasho", "customer says"]):
        fault_code = _extract_fault_code(both)
        priority = "Urgent" if _contains_any(both, ["urgent", "degdeg", "stopped", "not working", "angry", "business", "fire", "smell", "sparking", "damay", "istaagay"]) else "High"
        category = "General Service Issue"
        if _contains_any(both, ["inverter", "fault", "e03", "error"]): category = "Inverter Fault"
        if _contains_any(both, ["battery", "bms", "soc", "backup", "night", "habeen"]): category = "Battery / BMS Issue"
        if _contains_any(both, ["pump", "bamka", "water"]): category = "Solar Pump Issue"
        if _contains_any(both, ["monitor", "wifi", "logger", "app"]): category = "Monitoring Issue"
        return f"""{header}
{note}

1. Ticket Summary / Soo koobid
Customer complaint should be registered as a Service Ticket and followed until customer confirmation.
Cabashada macmiilka waa in lagu furaa Service Ticket, laguna xiraa kaliya marka customer-ku xaqiijiyo in ciladdu dhammaatay.

2. Recommended Category / Nooca Ciladda
{category}{' - Fault code: ' + fault_code if fault_code else ''}

3. Recommended Priority / Muhiimadda
{priority}
Reason: system performance/customer operation may be affected.

4. Possible Causes / Sababaha Suurtagalka ah
- Inverter fault log/error code needs checking.
- Battery SOC may be low or cutoff setting may be wrong.
- BMS communication cable or address/DIP setting may be incorrect.
- Night load may be higher than design estimate.
- Loose AC/DC cable, breaker trip, or weak connection may exist.

5. Technician Checklist / Checklist-ka Technician-ka
- Take customer name, location, phone, and project reference.
- Ask customer to send clear photo of inverter fault screen.
- Check inverter fault history and current operating mode.
- Check PV voltage/current, battery SOC, BMS communication, AC load, breakers, and earthing.
- Compare night load against designed battery capacity.
- Correct settings, test the system, and record final result.
- Add service visit report, photos, work done, and customer confirmation.

6. Customer Reply Draft / Jawaab Customer
Dear Customer, thank you for contacting Cadceed-Maal Solar Energy. We have registered your complaint and our technical team will review it urgently. Please send a photo of the inverter fault code and your location. A technician will contact you for diagnosis or site visit.

7. Next ERP Action / Talaabada System-ka
Create or update Service Ticket → assign Technician → set Due Date → add Visit Report → close after customer confirmation.

Context Reviewed:
{c[:1500] if c else original[:1500]}
""".strip()

    # 4) CRM / Sales
    if _contains_any(both, ["crm", "lead", "follow", "quotation", "quote", "sales", "customer", "macmiil", "whatsapp", "restaurant", "hybrid"]):
        lead_status = "Warm"
        if _contains_any(both, ["urgent", "today", "quotation", "site survey", "ready", "restaurant", "business"]): lead_status = "Hot"
        return f"""{header}
{note}

1. CRM Summary
This is a sales opportunity and should be entered in Sales CRM as an inquiry/follow-up record.

2. Lead Status Suggestion
{lead_status}

3. Next Sales Actions
- Confirm customer name, phone, location, and project type.
- Ask for daily load and day/night usage.
- Schedule site survey if load details are not clear.
- Prepare quotation with scope, warranty, payment terms, and delivery timeline.
- Set next follow-up date in CRM.

4. WhatsApp Follow-up Draft
Dear Customer, thank you for your interest in Cadceed-Maal Solar Energy. We can prepare a suitable solar solution for your requirement. Please confirm your location, main electrical loads, and preferred installation timeline so our team can prepare the correct quotation.

5. ERP Action
Sales CRM → New Inquiry → assign sales person → set next follow-up → create quotation when details are complete.

Context Reviewed:
{c[:1500] if c else original[:1500]}
""".strip()

    # 5) Reports / summary
    if _contains_any(both, ["report", "summary", "management", "weekly", "executive", "warbixin", "soo koob"]):
        lines = []
        if snap:
            lines = [
                f"Active ERP Records: Projects {snap.get('projects',0)}, Tasks {snap.get('tasks',0)}, Customers {snap.get('customers',0)}, Employees {snap.get('employees',0)}.",
                f"Support: Service Tickets {snap.get('service_tickets',0)}, Open {snap.get('open_tickets',0)}, Urgent {snap.get('urgent_tickets',0)}.",
                f"Sales: CRM Inquiries {snap.get('crm_inquiries',0)}, Quotations {snap.get('quotations',0)}.",
            ]
        return f"""{header}
{note}

Management Summary Draft
{chr(10).join(lines) if lines else 'Use ERP context to include figures.'}

Key Observations
- Review open service tickets and urgent customer issues first.
- Follow up pending CRM inquiries and quotations.
- Check overdue tasks and assign responsible employees.
- Confirm project status, testing, commissioning, and handover progress.

Recommended Management Actions
1. Daily: review open tickets, overdue tasks, and urgent customer cases.
2. Weekly: review project progress, CRM follow-ups, service quality, and staff performance.
3. Monthly: review completed projects, customer satisfaction, and operational risks.

Context Reviewed:
{c[:1500] if c else original[:1500]}
""".strip()

    # 6) Translation simple
    if _contains_any(both, ["translate", "tarjum", "english", "somali"]):
        return f"""{header}
{note}

Translation Guidance
Paste the exact text in Optional ERP Context and ask either:
- Translate to professional English
- Translate to clear Somali

Suggested customer-service English style:
"Dear Customer, thank you for informing Cadceed-Maal Solar Energy. We have received your complaint and our technical team will contact you shortly to review and resolve the issue."

Suggested Somali style:
"Macmiil qaali ah, waad ku mahadsan tahay inaad la soo xiriirtay Cadceed-Maal Solar Energy. Cabashadaada waan diiwaangelinnay, kooxda farsamaduna way kula soo xiriiri doontaa si loo hubiyo loona xalliyo ciladda."

Text reviewed:
{c[:1500] if c else original[:1500]}
""".strip()

    # Default answer
    return f"""{header}
{note}

1. Understanding / Faham
Su'aashaadu waxay u egtahay hawl ERP ah. Fadlan sheeg module-ka aad ka hadlayso: Service Ticket, CRM, Project, Task, Quotation, Report, Materials, ama User Permissions.

2. Best Way to Ask
Use this format:
- Module: Service Ticket / CRM / Project / Report
- Customer/Project:
- Problem/Request:
- What output you need: summary, checklist, reply, report, or next action.

3. Useful Examples
- Analyze this service ticket and give category, priority, root cause, checklist, and customer reply.
- Write CRM follow-up WhatsApp message for a 10kW hybrid customer.
- Generate weekly management report for open tickets, projects, tasks, and CRM follow-ups.
- How many customers, projects, tasks, and service tickets are in my system?

4. Current ERP Snapshot
Customers: {snap.get('customers',0) if snap else 0} | Projects: {snap.get('projects',0) if snap else 0} | Tasks: {snap.get('tasks',0) if snap else 0} | Service Tickets: {snap.get('service_tickets',0) if snap else 0} | CRM Inquiries: {snap.get('crm_inquiries',0) if snap else 0}

Context Reviewed:
{c[:1200] if c else original[:1200] if original else 'No request provided.'}
""".strip()

def _normalize_api_url(setting):
    """Build the OpenAI API URL.
    - If user enters https://api.openai.com/v1, use /responses.
    - If user enters a full endpoint ending /responses or /chat/completions, keep it.
    - Default is the OpenAI Responses API.
    """
    raw = (getattr(setting, 'api_base_url', '') or '').strip()
    if not raw:
        return "https://api.openai.com/v1/responses"
    raw = raw.rstrip('/')
    if raw.endswith('/responses') or raw.endswith('/chat/completions'):
        return raw
    if raw.endswith('/v1'):
        return raw + '/responses'
    return raw


def _extract_responses_text(result):
    """Extract text from OpenAI Responses API JSON.
    Supports output_text and the structured output array.
    """
    if isinstance(result, dict):
        if result.get('output_text'):
            return result.get('output_text')
        parts = []
        for item in result.get('output', []) or []:
            for content in item.get('content', []) or []:
                text = content.get('text') or content.get('transcript')
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts).strip()
    return ""


def _call_openai_responses(setting, api_key, prompt, context_data=None):
    url = _normalize_api_url(setting)
    model = (getattr(setting, 'model_name', None) or 'gpt-4o-mini').strip()
    payload = {
        "model": model,
        "instructions": getattr(setting, 'system_prompt', None) or CADCEED_SYSTEM_PROMPT,
        "input": build_user_content(prompt, context_data),
        "temperature": float(getattr(setting, 'temperature', 0.2) or 0.2),
        "max_output_tokens": int(getattr(setting, 'max_tokens', 900) or 900),
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        result = json.loads(raw)
        content = _extract_responses_text(result)
        return content, None


def _call_openai_chat_completions(setting, api_key, prompt, context_data=None):
    url = _normalize_api_url(setting)
    model = (getattr(setting, 'model_name', None) or 'gpt-4o-mini').strip()
    payload = {
        "model": model,
        "messages": build_messages(getattr(setting, 'system_prompt', None), prompt, context_data),
        "temperature": float(getattr(setting, 'temperature', 0.2) or 0.2),
        "max_tokens": int(getattr(setting, 'max_tokens', 900) or 900),
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        result = json.loads(raw)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content, None


def call_ai(setting, prompt, context_data=None):
    """Call live OpenAI API when configured.
    If disabled, missing key, or API error occurs, return the local ERP helper plus an error message
    so the page never becomes blank and the issue is visible in AI Logs.
    """
    api_key = get_api_key(setting)

    if not setting or not getattr(setting, 'enabled', False):
        return local_ai_response(prompt, context_data), "AI disabled - local/offline response returned"
    if not api_key:
        return local_ai_response(prompt, context_data), "No OPENAI_API_KEY/API key configured - local/offline response returned"

    url = _normalize_api_url(setting)
    try:
        if url.endswith('/chat/completions'):
            content, error = _call_openai_chat_completions(setting, api_key, prompt, context_data)
        else:
            content, error = _call_openai_responses(setting, api_key, prompt, context_data)
        if content:
            return content, error
        return local_ai_response(prompt, context_data), "OpenAI API returned an empty response - local/offline response returned"
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = str(e)
        return local_ai_response(prompt, context_data), f"OpenAI API HTTPError: {e.code} {body[:800]}"
    except Exception as e:
        return local_ai_response(prompt, context_data), f"OpenAI API Error: {str(e)[:800]}"


def test_ai_connection(setting):
    """Small live API test used by the AI Settings page."""
    response, error = call_ai(setting, "Reply only with: AI API CONNECTED", context_data="Connection test from Cadceed-Maal ERP.")
    return response, error

def make_ai_ref():
    return "AI-" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:17]
