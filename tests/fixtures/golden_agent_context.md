## Opportunity — constraints

- Required on create: Name, StageName
- CloseDate must be on or after 2025-08-15 and, when StageName is Closed Won, on or before 2026-08-15. Prefer 2026-06-16. Never invent dates outside this window.
- When `Amount` > 100000, set `Executive_Sponsor__c` to a non-empty string (do not invent other fields).
- When `Discount__c` > 0.3, either set `Approval_Status__c` to Approved or lower `Discount__c` to ≤ 0.3.
- Allowed `StageName`: Prospecting, Qualification, Proposal, Negotiation, Closed Won, Closed Lost

<!-- approx_tokens: 134 -->
