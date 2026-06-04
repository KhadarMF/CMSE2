
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Project, MaterialItem, MaterialRequest, MaterialRequestLine, MaterialIssue, MaterialIssueLine, MaterialReturn, MaterialReturnLine, MATERIAL_DOC_STATUSES
materials_bp = Blueprint("materials", __name__, url_prefix="/materials")

def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date() if value else None

def parse_float(value):
    try: return float(value or 0)
    except Exception: return 0

def make_ref(prefix):
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

@materials_bp.before_app_request
def ensure_material_tables():
    try: db.create_all()
    except Exception: pass

@materials_bp.route("/")
@login_required
def dashboard():
    requests = MaterialRequest.query.order_by(MaterialRequest.created_at.desc()).limit(10).all()
    summary = {"requests": MaterialRequest.query.count(), "issues": MaterialIssue.query.count(), "returns": MaterialReturn.query.count(), "issue_cost": sum(i.total_issue_cost for i in MaterialIssue.query.all()), "return_cost": sum(r.total_return_cost for r in MaterialReturn.query.all())}
    return render_template("materials/dashboard.html", requests=requests, summary=summary)

@materials_bp.route("/items")
@login_required
def items():
    q=(request.args.get("q") or "").strip(); query=MaterialItem.query
    if q:
        like=f"%{q}%"; query=query.filter((MaterialItem.item_name.ilike(like)) | (MaterialItem.item_code.ilike(like)) | (MaterialItem.category.ilike(like)))
    return render_template("materials/items.html", items=query.order_by(MaterialItem.item_name.asc()).all(), q=q)

@materials_bp.route("/items/create", methods=["GET","POST"])
@login_required
def create_item():
    if request.method=="POST":
        item=MaterialItem(item_code=request.form.get("item_code") or None,item_name=request.form.get("item_name"),description=request.form.get("description"),unit=request.form.get("unit"),category=request.form.get("category"),unit_cost=parse_float(request.form.get("unit_cost")),is_active=request.form.get("is_active")=="on")
        db.session.add(item); db.session.commit(); flash("Material item created.","success"); return redirect(url_for("materials.items"))
    return render_template("materials/item_form.html", item=None)

@materials_bp.route("/requests")
@login_required
def requests_list():
    project_id=request.args.get("project_id"); query=MaterialRequest.query
    if project_id: query=query.filter_by(project_id=project_id)
    return render_template("materials/requests.html", requests=query.order_by(MaterialRequest.created_at.desc()).all(), projects=Project.query.order_by(Project.project_name.asc()).all(), filters=request.args)

@materials_bp.route("/requests/create", methods=["GET","POST"])
@login_required
def create_request():
    projects=Project.query.order_by(Project.project_name.asc()).all(); items=MaterialItem.query.filter_by(is_active=True).order_by(MaterialItem.item_name.asc()).all()
    if request.method=="POST":
        req=MaterialRequest(ref_no=make_ref("MRF"), project_id=request.form.get("project_id"), request_date=parse_date(request.form.get("request_date")) or date.today(), purpose=request.form.get("purpose"), status=request.form.get("status") or "Submitted", requested_by_id=current_user.id, remarks=request.form.get("remarks"))
        db.session.add(req); db.session.flush(); created=0
        item_ids=request.form.getlist("item_id")
        for idx,item_id in enumerate(item_ids, start=1):
            selected=MaterialItem.query.get(item_id) if item_id else None
            item_name=request.form.get(f"item_name_row_{idx}") or (selected.item_name if selected else "")
            qty=parse_float(request.form.get(f"quantity_row_{idx}"))
            if not item_name or qty<=0: continue
            db.session.add(MaterialRequestLine(request_id=req.id,item_id=selected.id if selected else None,item_name=item_name,description=request.form.get(f"description_row_{idx}") or (selected.description if selected else ""),quantity_requested=qty,unit=request.form.get(f"unit_row_{idx}") or (selected.unit if selected else ""),estimated_unit_cost=parse_float(request.form.get(f"unit_cost_row_{idx}") or (selected.unit_cost if selected else 0)),remarks=request.form.get(f"remarks_row_{idx}")))
            created+=1
        if created==0: db.session.rollback(); flash("No material lines entered.","danger"); return redirect(url_for("materials.create_request"))
        db.session.commit(); flash(f"Material request {req.ref_no} created.","success"); return redirect(url_for("materials.request_detail", request_id=req.id))
    return render_template("materials/request_form.html", projects=projects, items=items, statuses=MATERIAL_DOC_STATUSES)

@materials_bp.route("/requests/<int:request_id>")
@login_required
def request_detail(request_id):
    return render_template("materials/request_detail.html", req=MaterialRequest.query.get_or_404(request_id))

@materials_bp.route("/requests/<int:request_id>/issue", methods=["GET","POST"])
@login_required
def issue_from_request(request_id):
    req=MaterialRequest.query.get_or_404(request_id)
    if request.method=="POST":
        issue=MaterialIssue(ref_no=make_ref("MIN"), request_id=req.id, project_id=req.project_id, issue_date=parse_date(request.form.get("issue_date")) or date.today(), issued_by_id=current_user.id, received_by=request.form.get("received_by"), status="Issued", remarks=request.form.get("remarks"))
        db.session.add(issue); db.session.flush(); created=0
        for line in req.lines:
            qty=parse_float(request.form.get(f"qty_{line.id}"))
            if qty<=0: continue
            db.session.add(MaterialIssueLine(issue_id=issue.id,item_id=line.item_id,item_name=line.item_name,description=line.description,quantity_issued=qty,unit=line.unit,unit_cost=parse_float(request.form.get(f"cost_{line.id}") or line.estimated_unit_cost),remarks=request.form.get(f"remarks_{line.id}")))
            created+=1
        if created==0: db.session.rollback(); flash("No issue lines entered.","danger"); return redirect(url_for("materials.issue_from_request", request_id=req.id))
        req.status="Issued"; db.session.commit(); flash(f"Material issue {issue.ref_no} created.","success"); return redirect(url_for("materials.issue_detail", issue_id=issue.id))
    return render_template("materials/issue_form.html", req=req)


@materials_bp.route("/issues")
@login_required
def issues_list():
    project_id = request.args.get("project_id")
    query = MaterialIssue.query
    if project_id:
        query = query.filter_by(project_id=project_id)
    issues = query.order_by(MaterialIssue.created_at.desc()).all()
    return render_template("materials/issues.html", issues=issues, projects=Project.query.order_by(Project.project_name.asc()).all(), filters=request.args)

@materials_bp.route("/issues/<int:issue_id>")
@login_required
def issue_detail(issue_id):
    return render_template("materials/issue_detail.html", issue=MaterialIssue.query.get_or_404(issue_id))

@materials_bp.route("/returns/create", methods=["GET","POST"])
@login_required
def create_return():
    projects=Project.query.order_by(Project.project_name.asc()).all(); items=MaterialItem.query.filter_by(is_active=True).order_by(MaterialItem.item_name.asc()).all()
    if request.method=="POST":
        ret=MaterialReturn(ref_no=make_ref("MRT"), project_id=request.form.get("project_id"), return_date=parse_date(request.form.get("return_date")) or date.today(), returned_by=request.form.get("returned_by"), received_by_id=current_user.id, reason=request.form.get("reason"), status="Returned", remarks=request.form.get("remarks"))
        db.session.add(ret); db.session.flush(); created=0
        item_ids=request.form.getlist("item_id")
        for idx,item_id in enumerate(item_ids, start=1):
            selected=MaterialItem.query.get(item_id) if item_id else None
            item_name=request.form.get(f"item_name_row_{idx}") or (selected.item_name if selected else "")
            qty=parse_float(request.form.get(f"quantity_row_{idx}"))
            if not item_name or qty<=0: continue
            db.session.add(MaterialReturnLine(return_id=ret.id,item_id=selected.id if selected else None,item_name=item_name,description=request.form.get(f"description_row_{idx}") or (selected.description if selected else ""),quantity_returned=qty,unit=request.form.get(f"unit_row_{idx}") or (selected.unit if selected else ""),unit_cost=parse_float(request.form.get(f"unit_cost_row_{idx}") or (selected.unit_cost if selected else 0)),remarks=request.form.get(f"remarks_row_{idx}")))
            created+=1
        if created==0: db.session.rollback(); flash("No return lines entered.","danger"); return redirect(url_for("materials.create_return"))
        db.session.commit(); flash(f"Material return {ret.ref_no} created.","success"); return redirect(url_for("materials.return_detail", return_id=ret.id))
    return render_template("materials/return_form.html", projects=projects, items=items)


@materials_bp.route("/returns")
@login_required
def returns_list():
    project_id = request.args.get("project_id")
    query = MaterialReturn.query
    if project_id:
        query = query.filter_by(project_id=project_id)
    returns = query.order_by(MaterialReturn.created_at.desc()).all()
    return render_template("materials/returns.html", returns=returns, projects=Project.query.order_by(Project.project_name.asc()).all(), filters=request.args)

@materials_bp.route("/returns/<int:return_id>")
@login_required
def return_detail(return_id):
    return render_template("materials/return_detail.html", ret=MaterialReturn.query.get_or_404(return_id))



@materials_bp.route("/reports")
@login_required
def material_reports():
    projects = Project.query.order_by(Project.project_name.asc()).all()
    rows = []
    for project in projects:
        requests = MaterialRequest.query.filter_by(project_id=project.id).all()
        issues = MaterialIssue.query.filter_by(project_id=project.id).all()
        returns = MaterialReturn.query.filter_by(project_id=project.id).all()
        rows.append({
            "project": project,
            "request_count": len(requests),
            "issue_count": len(issues),
            "return_count": len(returns),
            "issue_cost": sum(i.total_issue_cost for i in issues),
            "return_cost": sum(r.total_return_cost for r in returns),
            "net_cost": sum(i.total_issue_cost for i in issues) - sum(r.total_return_cost for r in returns),
        })
    return render_template("materials/reports.html", rows=rows)

@materials_bp.route("/project/<int:project_id>/report")
@login_required
def project_material_report(project_id):
    project=Project.query.get_or_404(project_id)
    requests=MaterialRequest.query.filter_by(project_id=project.id).order_by(MaterialRequest.created_at.desc()).all()
    issues=MaterialIssue.query.filter_by(project_id=project.id).order_by(MaterialIssue.created_at.desc()).all()
    returns=MaterialReturn.query.filter_by(project_id=project.id).order_by(MaterialReturn.created_at.desc()).all()
    summary={"request_cost":sum(r.total_estimated_cost for r in requests),"issue_cost":sum(i.total_issue_cost for i in issues),"return_cost":sum(r.total_return_cost for r in returns),"net_material_cost":sum(i.total_issue_cost for i in issues)-sum(r.total_return_cost for r in returns)}
    return render_template("materials/project_report.html", project=project, requests=requests, issues=issues, returns=returns, summary=summary, report_ref=f"PMR-{project.id:04d}-{datetime.utcnow().strftime('%Y%m%d')}")
