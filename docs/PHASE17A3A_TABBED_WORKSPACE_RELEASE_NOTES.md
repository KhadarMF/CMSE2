# Phase 17A.3A – Tabbed Workspace & Window Manager

## Summary
This phase adds a lightweight internal ERP workspace on top of the existing navigation foundation. It does not change database models, authentication, permissions, or business logic.

## Added
- Internal workspace tab bar below the top navigation.
- Close (×) button on every open form/page tab.
- Windows dropdown in the top bar showing all currently open forms/pages.
- Close Current, Close Others, and Close All actions.
- Active tab highlight.
- Open-once behavior through URL-based tab tracking.
- Local browser storage for open tabs.

## Notes
- This is Phase 17A.3A only. It intentionally excludes unsaved-change protection, restore prompts, keyboard shortcuts, and split-screen features. Those are planned for later phases.
- The implementation is front-end only and preserves all existing server routes and permissions.
