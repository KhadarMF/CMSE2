# Phase 17A.1 - Navigation & UI Redesign

## Built from
Phase 16L.4 WhatsApp Conversation Center.

## What changed
- Replaced the crowded top menu with a hybrid ERP shell:
  - fixed left sidebar
  - clean top bar
  - logo as Dashboard/Home link
  - hamburger menu for tablet/mobile
- Reorganized navigation into workflow groups:
  - Dashboard
  - Master Data
  - Sales
  - Projects
  - Operations
  - Reports
  - AI Center
  - System
- Moved Customers into Master Data near the top.
- Added WhatsApp Inbox under Sales for daily CRM use.
- Kept WhatsApp API / Message Log under System for admin/debugging use.
- Added Quick Create menu.
- Added search box placeholder with Ctrl+K focus shortcut.
- Added breadcrumb row.
- Added responsive sidebar/backdrop for smaller screens.

## Compatibility
- Existing routes, permissions, forms, reports, and database models are not intentionally changed.
- This phase focuses on UI shell/navigation only.

## Recommended test after deploy
1. Login as Admin and confirm sidebar appears.
2. Open Customers from Master Data.
3. Open Quotations from Sales.
4. Open WhatsApp Inbox from Sales.
5. Open WhatsApp Message Log from System.
6. Test on phone/tablet width using the hamburger menu.
