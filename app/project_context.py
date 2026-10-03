"""Shared project/customer context for project-originated create forms.

Project records pre-date the Customer foreign key convention and therefore
store ``customer_name`` as text.  Create forms should still behave as one
connected workspace: when they receive a project id, this module resolves the
matching Customer master record and exposes one consistent context.
"""

from app import db
from app.models import Customer, Project


def parse_optional_id(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def customer_by_name(customer_name):
    name = (customer_name or "").strip()
    if not name:
        return None
    customer = Customer.query.filter(Customer.customer_name == name).first()
    if customer:
        return customer
    return Customer.query.filter(db.func.lower(Customer.customer_name) == name.lower()).first()


def resolve_project_customer(project_id=None, customer_id=None, customer_name=None):
    """Return the selected Project and its authoritative Customer record.

    A valid project always wins over separately supplied customer parameters.
    That prevents a quotation, service ticket, or warranty from being saved
    under a customer that does not own the selected project.
    """
    project_pk = parse_optional_id(project_id)
    customer_pk = parse_optional_id(customer_id)
    project = db.session.get(Project, project_pk) if project_pk else None

    if project:
        return project, customer_by_name(project.customer_name)

    customer = db.session.get(Customer, customer_pk) if customer_pk else None
    if not customer:
        customer = customer_by_name(customer_name)
    return None, customer

