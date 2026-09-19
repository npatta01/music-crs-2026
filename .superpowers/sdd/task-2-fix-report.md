# Task 2 Assertion Fix Report

Fixed the two requested landing-page review findings:

- Reduced-motion now requires the CSS rule’s near-zero computed duration; `0s` is no longer accepted.
- Added an ordered DOM assertion for the six cards and every card’s exact link order.

`index.html` was unchanged. Verification and the commit details are recorded in the handoff response.
