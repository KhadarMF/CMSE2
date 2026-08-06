# Phase 20I — Evidence-Based Project Milestone Engine

## What changed

The Project Command Center now uses real milestone records instead of a visual
summary only. Every new and existing project receives these six milestones:

1. Survey & Assessment — 10%
2. Design & Approval — 15%
3. Procurement — 20%
4. Installation — 35%
5. Testing & Commissioning — 15%
6. Handover — 5%

The project weights total 100%. Each milestone also has its own Physical,
Procurement, and Documents weights. A dimension with 0% is N/A and is excluded
from that milestone's calculation.

## Evidence and calculation

- Physical progress comes from required linked tasks and, where configured,
  the latest approved Daily Site Report (70% tasks + 30% daily evidence).
- Procurement progress comes from required linked Material Requests. Issued or
  Closed is 100%; Partially Issued is 80%; Approved is 50%.
- Document progress comes from approved forms and uploaded documents listed as
  requirements for the milestone.
- Optional records do not reduce the score when required/critical records have
  been defined.
- Overall Project Progress is the sum of each milestone score multiplied by its
  project weight. Financial progress remains separate from physical progress.

## Who completes a milestone

1. Team Leader or manager links the tasks, material requests, reports, forms,
   documents, and issues to the correct milestone.
2. Team Leader presses **Run gates & submit**.
3. The system rechecks every gate. Missing evidence changes the milestone to
   Blocked and shows the exact blocker list.
4. If all gates pass, the milestone becomes **Ready for Approval**.
5. A different Admin, Management, or Operation Manager user approves it.
6. Only then does it become **Completed**.

The submitter cannot approve their own milestone. Admin/Management/Operation
Manager can use **Emergency override**, but a meaningful reason is mandatory;
the action, user, time, old status, new status, and reason are retained in the
audit history. A completed milestone can also be reopened with an audit reason.

The Project itself becomes Completed only when every milestone is Completed or
Completed with Exception. Directly selecting Project Status = Completed is
blocked while any milestone is still open.

## Automatic completion gates

The system requires all applicable checks to pass:

- milestone dimension weights total 100%;
- all six project milestone weights total 100%;
- a physical work plan exists and every required/critical task is 100%;
- an approved Daily Site Report exists when the milestone requires one;
- procurement records exist and every required/critical request is Issued or
  Closed;
- document/form requirements exist and every required/critical requirement is
  approved;
- no open Critical issue blocks the milestone; and
- the calculated milestone score is 100%.

## Database migration

Revision: `b20i0000a001`

The migration creates the milestone, document requirement, and audit tables;
links tasks, material requests, documents, Daily Site Reports, and issues to a
milestone; and safely seeds the six milestones for existing projects. Existing
projects already marked Completed are retained as controlled legacy exceptions.

## Local upgrade

Back up the existing database, extract the release, copy your existing `.env`
and database into the new folder, then run:

```powershell
python run.py
```

The local launcher applies the migration automatically. Do not run `init_db.py`
when keeping an existing database.

## Render upgrade

1. Download a fresh Admin backup to your computer.
2. Commit and push all release files, including `migrations/`.
3. In Render, replace the old Pre-Deploy Command with:

```text
python preflight_check_20d.py && flask db upgrade
```

Do not include `flask db stamp cc82184d6822` in the permanent command. Stamping
can mark migrations complete without applying them.

4. Use Manual Deploy → Deploy latest commit.
5. Confirm the deploy log contains:

```text
Running upgrade b20h0000a003 -> b20i0000a001
```

6. Open one project, verify the six milestones, and test one milestone as Team
   Leader and another user as manager.

## Verification performed

- Fresh SQLite migration through `b20i0000a001`: passed.
- Legacy repair/migration regression: passed.
- Team Leader project scoping and submission: passed.
- Independent manager approval and self-approval protection: passed.
- Missing-evidence blocker and audited exception: passed.
- Project completion lock: passed.
- Full automated suite: 41 passed, 1 intentionally skipped.
- Browser visual QA of Project Command Center and Milestone Gate: passed.
