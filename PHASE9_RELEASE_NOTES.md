# Phase 9 Release Notes

## New Features

1. Project Task Management
   - Create tasks linked to projects
   - Assign tasks to users
   - Priority, status, due date, progress percentage, and remarks
   - Overdue task highlighting
   - My Tasks page now shows assigned project tasks

2. Issue & Risk Tracker
   - Record issues per project
   - Issue types: Technical, Material, Transport, Finance, Safety, Customer, Delay, Quality
   - Severity levels: Low, Medium, High, Critical
   - Responsible user, target resolution date, resolution notes
   - Overdue issue highlighting

3. Enhanced Dashboard
   - Open Tasks
   - Overdue Tasks
   - Open Issues
   - Critical Issues
   - Upcoming active tasks table

4. Project Detail Improvements
   - Project tasks summary
   - Issues and risks summary
   - Quick create buttons from project page

5. Render Stability
   - Added runtime.txt for Python 3.10.5
   - Continue using PYTHON_VERSION=3.10.5 on Render Environment for safety

## After Uploading Phase 9 to GitHub / Render

Run this command once in Render Shell to create the new tables:

```bash
python init_db.py
```

Then redeploy the Web Service.
