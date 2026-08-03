# Phase 17A.1B Navigation BuildError Hotfix

Fixed dashboard startup failure caused by an invalid endpoint in the new Quick Create menu.

## Fix
- Replaced `master.new_customer` with existing endpoint `master.create_customer` in `app/templates/base.html`.

## Verified by static route scan
- The base navigation template no longer references missing endpoints found in the current route files.

## User impact
- Dashboard should open normally.
- Quick Create > Customer now links to the existing customer creation page.
