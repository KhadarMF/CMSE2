# Phase 20E — Project Command Center

Phase 20E replaces the project detail screen with a decision-ready Command
Center. It uses existing operational records, so no database migration is
required and there is no duplicate progress source to maintain.

## Included

- Weighted overall progress with a visible formula
- Lifecycle milestones and current project gate
- Task-level Gantt timeline with owners, progress, and overdue warnings
- Physical progress from task completion and the latest daily site report
- Procurement progress from material requests, approvals, issues, and returns
- Financial snapshot for authorized roles: approved revenue, committed costs,
  cash paid, outstanding cost, forecast profit, and margin
- Separate SLSH totals so currencies are never added to USD totals
- Required-form checklist plus document approval readiness
- Prioritized issues and risks with ownership and target dates
- AI Project Manager summary when available, with a live rule-based fallback
- Print-friendly layout and responsive mobile/desktop presentation
- Project preselection when adding forms, documents, materials, or payments

## Progress formula

Overall progress is intentionally transparent:

- 25% lifecycle milestone progress
- 35% physical progress
- 20% procurement progress
- 20% document readiness

Financial performance is displayed alongside delivery progress but is not used
to inflate physical completion.

## Financial access and calculation

Financial content remains protected by existing Payment Request, Payroll, and
Accounting permissions. Approved/converted project quotations provide revenue.
Committed cost combines net issued material value, payroll due, and non-material
payment requests. Material-linked payment requests are excluded when issued
inventory already represents the cost, preventing double counting.

## Verification

- Full automated suite: 27 passed, 1 intentionally skipped
- Command Center route and calculation regression test included
- Desktop and 390px mobile visual QA completed
- No browser console errors detected
