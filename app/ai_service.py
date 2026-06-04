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
    return os.environ.get("OPENAI_API_KEY") or (setting.api_key if setting and setting.api_key else "")


def build_messages(system_prompt, prompt, context_data=None):
    user_content = prompt
    if context_data:
        user_content = f"ERP CONTEXT:\n{context_data}\n\nUSER REQUEST:\n{prompt}"
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

def call_ai(setting, prompt, context_data=None):
    """OpenAI-compatible chat completion call using urllib only.
    If no key or disabled, returns a useful offline/local ERP response instead of a blank page.
    """
    api_key = get_api_key(setting)
    # If not enabled or no key, still return a useful local answer.
    if not setting or not getattr(setting, 'enabled', False):
        return local_ai_response(prompt, context_data), "AI disabled - local/offline response returned"
    if not api_key:
        return local_ai_response(prompt, context_data), "No OPENAI_API_KEY/API key configured - local/offline response returned"

    payload = {
        "model": setting.model_name or "gpt-4o-mini",
        "messages": build_messages(setting.system_prompt, prompt, context_data),
        "temperature": float(setting.temperature or 0.2),
        "max_tokens": int(setting.max_tokens or 900),
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        setting.api_base_url or "https://api.openai.com/v1/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            result = json.loads(raw)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content or local_ai_response(prompt, context_data), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = str(e)
        return local_ai_response(prompt, context_data), f"HTTPError: {e.code} {body[:500]}"
    except Exception as e:
        return local_ai_response(prompt, context_data), str(e)


def make_ai_ref():
    return "AI-" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:17]
