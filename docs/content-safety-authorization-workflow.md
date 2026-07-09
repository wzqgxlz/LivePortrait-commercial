# Content Safety And Authorization Workflow

This workflow defines the MVP controls for source-image authorization, content
review, prohibited use handling, and support traceability for the commercial-safe
Humans mode API.

It is not legal advice. Before public launch, have legal counsel review the
policy language, consent records, portrait-right requirements, privacy terms,
and prohibited-use list.

Animals mode is out of scope.

## Current MVP Controls

The current API and frontend already enforce these baseline controls:

- Users must submit `consent_confirmed=true` before a job is created.
- The job record stores `consent_confirmed`.
- The job record stores `usage_policy_version`.
- The job record can store lightweight authorization metadata:
  `authorization_basis`, `authorization_reference`, `authorization_reviewer`,
  and `authorization_status`.
- Input files are hashed as `source_sha256` and `driving_sha256`.
- Successful output is hashed as `output_sha256`.
- Audit events record `created`, `running`, `succeeded`, and `failed`.
- `GET /api/jobs/{job_id}/export` downloads the job support package.
- `GET /api/authorization-records/export?authorization_reference=<reference>`
  downloads a grouped support package for recent jobs tied to one authorization
  reference.
- The frontend shows authorization language and optional authorization record
  fields before submission.

These controls are enough for internal MVP trials and B-side pilots when paired
with a fuller manual authorization record outside the API.

## Authorization Record

For every external tester, customer, or B-side pilot, keep an authorization
record before processing real people. The MVP stores lightweight authorization
metadata on each API job, but the fuller record can still live outside the API
at first, such as in a customer ticket, CRM, contract folder, or secure shared
drive.

Minimum authorization record fields:

| Field | Requirement |
| --- | --- |
| Customer or tester ID | Required |
| Authorized operator | Required |
| Source person identity or role | Required when legally permitted |
| Authorization basis | Consent, employment agreement, talent contract, customer-owned asset, or other reviewed basis |
| Allowed use | Demo, internal test, campaign draft, production asset, or support reproduction |
| Expiration or review date | Required for external pilots |
| Source asset reference | Filename, asset ID, or storage pointer |
| API job ID | Required after submission |
| Source hash | `source_sha256` from job/export |
| Output hash | `output_sha256` when generated |
| Reviewer | Required for B-side customer use |
| Notes | Optional |

Do not rely only on a checkbox for commercial customer use. The checkbox is the
in-product confirmation; the API authorization metadata helps connect a job to
the external authorization record, and the external record remains the support
and compliance evidence.

## Content Review

Use this review flow before allowing outputs to leave the internal test group.

### Pre-Submission Review

- Confirm the source image is an authorized person or authorized asset.
- Confirm the driving image/video is allowed for the project.
- Confirm the requested use is within the authorization scope.
- Reject low-confidence authorization cases before upload.
- Reject requests involving public figures, politicians, minors, explicit
  material, fraud, impersonation, or harassment unless legal and policy review
  has explicitly approved the use case.

### Post-Generation Review

- Confirm the output matches the approved use.
- Confirm the output is not misleadingly presented as real footage.
- Confirm the output does not add prohibited context, gestures, or identity
  claims.
- Download `GET /api/jobs/{job_id}/export` for any output that will be sent to a
  customer or used in support.

## Prohibited Uses

The MVP must not be used for:

- Unauthorized person likeness generation.
- Impersonation or identity deception.
- Fraud, scams, fake endorsements, or fake evidence.
- Sexual or explicit content.
- Political persuasion, political deepfakes, or election-related manipulation.
- Harassment, intimidation, blackmail, or reputational harm.
- Processing minors without a separately reviewed legal and safety workflow.
- Attempts to bypass consent, audit, or content review controls.

If a request touches any prohibited category, do not process it through the MVP.
Escalate to legal/policy review.

## Manual Review

Manual review is required when:

- The person is a public figure or high-risk individual.
- The source image is user-provided and authorization is not independently
  documented.
- The output will be used outside internal testing.
- A customer asks to process many people or a batch of assets.
- The requested use involves advertising, public release, or paid distribution.
- A generated result is reported as suspicious or harmful.

Manual review should produce either:

- Approved with scope and expiration.
- Rejected with reason.
- Needs more evidence.

Record that decision in the external authorization record and link it to the API
job ID.

## Support And Audit Workflow

For a reported job:

1. Find failed or suspicious jobs:

```http
GET /api/jobs?status=failed
```

2. Inspect the job:

```http
GET /api/jobs/{job_id}
```

3. Download the traceability package:

```http
GET /api/jobs/{job_id}/export
```

4. Compare export fields against the authorization record:

- `consent_confirmed`
- `usage_policy_version`
- `authorization_basis`
- `authorization_reference`
- `authorization_reviewer`
- `authorization_status`
- `source_sha256`
- `driving_sha256`
- `output_sha256`
- `created_at`
- `updated_at`
- `audit_events`

5. Preserve the export with the support case. Do not share source or output
files outside the authorized support channel.

For a customer ticket, CRM ID, contract ID, or other authorization reference
that covers multiple jobs, use:

```http
GET /api/jobs?authorization_reference=<reference>
GET /api/authorization-records/export?authorization_reference=<reference>
```

The grouped export is useful for internal review and customer support, but it
should still be linked back to the full external authorization record.

## Retention

Recommended MVP retention:

- Keep authorization records for the full customer agreement or pilot period.
- Keep job audit exports for support cases according to the customer agreement.
- Keep `cleanup-runs.jsonl` with API operational records.
- Delete raw uploads and generated outputs when they are no longer needed for
  active work, support, or legal retention.
- Run `scripts/cleanup_api_jobs.py --older-than-days 7 --dry-run` before
  deleting files.

Adjust retention periods with legal counsel before public launch.

## Future Product Work

The MVP still needs a stronger productized workflow before open public access:

- First-class authorization-record API/table with customer/user ownership.
- Per-user or per-customer accounts.
- Role-based access for operators and reviewers.
- Upload support for authorization documents.
- Content moderation service integration.
- Reviewer decision log.
- Watermarking or provenance marking policy.
- Admin dashboard for failed jobs, exports, and cleanup records.

Until those exist, use this MVP only for controlled internal tests or B-side
pilots with manual authorization records.
