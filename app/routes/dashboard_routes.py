import csv
import io

from flask import Blueprint, make_response, render_template, request
from flask_login import current_user, login_required

from app.dashboard_command_center import build_dashboard_command_center


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    command_center = build_dashboard_command_center(current_user, request.args)
    return render_template(
        "dashboard/dashboard.html",
        command_center=command_center,
    )


@dashboard_bp.route("/dashboard/export.csv")
@login_required
def export_csv():
    """Export the filtered portfolio in an Excel-friendly UTF-8 CSV."""
    command_center = build_dashboard_command_center(current_user, request.args)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Dashboard Command Center V5"])
    writer.writerow(["As of", command_center["as_of"].isoformat()])
    writer.writerow(["Scope", command_center["scope_label"]])
    writer.writerow([])

    header = [
        "Project",
        "Customer",
        "Status",
        "Overall %",
        "Physical %",
        "Materials Ready %",
        "Documents %",
        "Risk",
        "Delayed",
        "Open Issues",
        "Overdue Tasks",
        "Last Approved Daily Report",
    ]
    if command_center["flags"]["finance"]:
        header[5:5] = [
            "Financial %",
            "Revenue USD",
            "Committed Cost USD",
            "Paid Cost USD",
            "Outstanding USD",
            "Profit USD",
        ]
    writer.writerow(header)

    for row in command_center["portfolio"]:
        values = [
            row["project"].project_name,
            row["project"].customer_name,
            row["project"].status,
            row["overall"],
            row["physical"],
            row["materials"],
            row["documents"],
            row["risk"],
            "Yes" if row["is_delayed"] else "No",
            row["open_issues"],
            row["overdue_tasks"],
            row["last_report_date"].isoformat() if row["last_report_date"] else "",
        ]
        if command_center["flags"]["finance"]:
            values[5:5] = [
                row["financial_progress"],
                f"{row['revenue']:.2f}",
                f"{row['committed_cost']:.2f}",
                f"{row['paid_cost']:.2f}",
                f"{row['outstanding']:.2f}",
                f"{row['profit']:.2f}",
            ]
        writer.writerow(values)

    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        f"attachment; filename=dashboard_command_center_{command_center['as_of'].isoformat()}.csv"
    )
    return response
