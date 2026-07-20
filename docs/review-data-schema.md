# Review Data Schema

Talha owns the validation data shape. Umer can use this for desktop and web review screens.

## Review Queue Fields

| Field | Type | Notes |
|---|---|---|
| id | text/uuid | Primary key |
| statement_id | text/uuid | Links to uploaded or local statement |
| user_id | text/uuid/null | Required for web multi-user isolation |
| bank_id | text | Parser/bank identifier |
| account_number | text/null | Mask in UI unless full value is needed |
| row_number | integer/null | Null for statement-level issues |
| flag_code | text | Example: missing_balance, balance_mismatch |
| flag_message | text | Human-readable issue |
| flag_severity | text | info, warning, error |
| transaction_snapshot | json/text | Transaction as parsed at time of review |
| status | text | open, resolved, rejected |
| assigned_to | text/null | Optional reviewer |
| notes | json/text | Reviewer notes |
| created_at | timestamp | Set on insert |
| updated_at | timestamp | Set on update |

## SQLite Draft

```sql
CREATE TABLE review_queue (
    id TEXT PRIMARY KEY,
    statement_id TEXT NOT NULL,
    bank_id TEXT NOT NULL,
    account_number TEXT,
    row_number INTEGER,
    flag_code TEXT NOT NULL,
    flag_message TEXT NOT NULL,
    flag_severity TEXT NOT NULL,
    transaction_snapshot TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    assigned_to TEXT,
    notes TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

## Supabase/Postgres Draft

Concrete migration files live in:

- `supabase/migrations/001_review_queue.sql`
- `supabase/migrations/002_statement_files_storage.sql`

```sql
CREATE TABLE review_queue (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    statement_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES auth.users(id),
    bank_id text NOT NULL,
    account_number text,
    row_number integer,
    flag_code text NOT NULL,
    flag_message text NOT NULL,
    flag_severity text NOT NULL CHECK (flag_severity IN ('info', 'warning', 'error')),
    transaction_snapshot jsonb,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'rejected')),
    assigned_to text,
    notes jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE review_queue ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read their review items"
ON review_queue
FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can update their review items"
ON review_queue
FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);
```

## Rules

- Store validation flags as structured data, not plain text only.
- Keep a transaction snapshot so later parser changes do not alter old reviews.
- Do not store raw PDF text in review queue rows.
- Mask account numbers in UI by default.
- Store private PDFs under `statement-pdfs/{user_id}/{statement_id}.pdf`.
- Store private exports under `statement-exports/{user_id}/{statement_id}.xlsx`.
