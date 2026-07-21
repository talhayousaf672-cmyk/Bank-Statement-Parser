# Web Data Security Checklist

Talha owns this checklist with Umer for the web app handoff.

## Required Before Web Launch

- Supabase row-level security must isolate statements by user or tenant.
- Uploaded PDFs must use private storage buckets only.
- Generated Excel files must use private storage buckets only.
- All file access must use short-lived signed URLs.
- Uploaded PDFs and generated exports must have lifecycle auto-delete rules.
- API requests must require authenticated Supabase JWTs.
- Parser jobs must store only needed metadata in the database.
- Logs must never include full account numbers, raw statement text, or file contents.
- AI fallback must be opt-in and must not run without user consent.
- AI fallback output must pass reconciliation before export.
- Admin/service-role keys must never be exposed to the frontend.
- Review queue rows must inherit the same tenant isolation as statements.
- Rate limits must protect upload, parse, AI fallback, and download endpoints.
- Backups must follow the same retention policy as the main database.
- Supabase migrations must be reviewed before production deployment:
  - `supabase/migrations/001_review_queue.sql`
  - `supabase/migrations/002_statement_files_storage.sql`

## Open Decisions

- Exact retention window for uploaded PDFs.
- Exact retention window for generated Excel files.
- Whether account numbers should be masked in the UI by default.
- Whether users can manually delete statements and exports before auto-expiry.
