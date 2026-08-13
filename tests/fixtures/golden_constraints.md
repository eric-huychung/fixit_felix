# Constraints — org `00DORG`

Scanned at: 2026-08-10T12:00:00+00:00

## Opportunity

### Schema fields

- `Amount` (Amount): optional
- `Name` (Name): required — max length: 120
- `StageName` (Stage): required — picklist: Prospecting, Qualification, Proposal, Negotiation, Closed Won, Closed Lost

### Validation rules

#### Field `Amount`

- **Amount_Requires_Sponsor** (active)
  - Meaning: Amount over 100000 requires Executive_Sponsor__c to be set.
  - Error message: Please contact your administrator.
  - Fields: Amount, Executive_Sponsor__c

  <details><summary>Formula</summary>

  ```
  AND(Amount > 100000, ISBLANK(Executive_Sponsor__c))
  ```

  </details>

#### Field `Discount__c`

- **Discount_Needs_Approval** (active, package `pkg`)
  - Meaning: Discount__c cannot exceed 30 unless Approval_Status__c is Approved.
  - Error message: Discount cannot exceed 30% without approval.
  - Fields: Discount__c, Approval_Status__c

  <details><summary>Formula</summary>

  ```
  AND(Discount__c > 0.3, TEXT(Approval_Status__c) <> "Approved")
  ```

  </details>

#### Object-level rules

- **Legacy_Inactive_Rule** (inactive)
  - Meaning: This inactive rule must not appear in agent context.
  - Error message: Legacy

  <details><summary>Formula</summary>

  ```
  false
  ```

  </details>

### Apex addError (best effort)

- `OpportunityDiscountGuard` [high]: Discount exceeds hard policy limit of 50%.

```apex
opp.addError('Discount exceeds hard policy limit of 50%.');
```

## Scan errors

The following stages failed. This report may be incomplete.

- **apex** / `ManagedPkgTrigger`: Body not readable
