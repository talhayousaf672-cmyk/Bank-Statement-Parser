-- Private Supabase Storage buckets and owner-isolation policies.
--
-- Expected object path convention:
--   statement-pdfs/{user_id}/{statement_id}.pdf
--   statement-exports/{user_id}/{statement_id}.xlsx

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
    ('statement-pdfs', 'statement-pdfs', false, 52428800, array['application/pdf']),
    (
        'statement-exports',
        'statement-exports',
        false,
        52428800,
        array[
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/octet-stream'
        ]
    )
on conflict (id) do update
set
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Users can read their statement PDFs" on storage.objects;
create policy "Users can read their statement PDFs"
on storage.objects
for select
to authenticated
using (
    bucket_id = 'statement-pdfs'
    and (storage.foldername(name))[1] = auth.uid()::text
);

drop policy if exists "Users can upload their statement PDFs" on storage.objects;
create policy "Users can upload their statement PDFs"
on storage.objects
for insert
to authenticated
with check (
    bucket_id = 'statement-pdfs'
    and (storage.foldername(name))[1] = auth.uid()::text
);

drop policy if exists "Users can delete their statement PDFs" on storage.objects;
create policy "Users can delete their statement PDFs"
on storage.objects
for delete
to authenticated
using (
    bucket_id = 'statement-pdfs'
    and (storage.foldername(name))[1] = auth.uid()::text
);

drop policy if exists "Users can read their statement exports" on storage.objects;
create policy "Users can read their statement exports"
on storage.objects
for select
to authenticated
using (
    bucket_id = 'statement-exports'
    and (storage.foldername(name))[1] = auth.uid()::text
);

drop policy if exists "Users can upload their statement exports" on storage.objects;
create policy "Users can upload their statement exports"
on storage.objects
for insert
to authenticated
with check (
    bucket_id = 'statement-exports'
    and (storage.foldername(name))[1] = auth.uid()::text
);

drop policy if exists "Users can delete their statement exports" on storage.objects;
create policy "Users can delete their statement exports"
on storage.objects
for delete
to authenticated
using (
    bucket_id = 'statement-exports'
    and (storage.foldername(name))[1] = auth.uid()::text
);
