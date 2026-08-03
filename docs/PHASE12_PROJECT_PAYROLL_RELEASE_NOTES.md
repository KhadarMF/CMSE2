# Phase 12 - Project Payroll / Employee Salary Accounting

Added:
- Project Payroll module
- Payroll Periods by month/year
- Manager payroll entry per employee/project/month
- Previous balance support
- Automatic previous balance option from unpaid old entries
- Finance payment recording
- Employee payroll statement: projects worked, total due, total paid, remaining balance
- Project payroll report: employees, due/paid/balance per project
- Full Project Report includes Payroll Summary

Roles:
- Admin / Management / Operation Manager can create and approve payroll entries.
- Admin / Management / Finance Officer can record payments.

Local testing:
1. env\Scripts\activate
2. pip install -r requirements.txt
3. python init_db.py
4. python run.py
5. Open Project Payroll from the top menu
