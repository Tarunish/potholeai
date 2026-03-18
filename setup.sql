-- create_profiles_table
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text unique,
  email text,
  role text default 'Public',
  created_at timestamp default now()
);

-- enable_rls_profiles
alter table profiles enable row level security;

-- policy_insert_own_profile
create policy "insert own profile"
on profiles
for insert
with check (auth.uid() = id);

-- policy_select_own_profile
create policy "view own profile"
on profiles
for select
using (auth.uid() = id);

-- function_handle_new_user
create or replace function handle_new_user()
returns trigger as $$
begin
  insert into profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$ language plpgsql;

-- trigger_on_auth_user_created
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure handle_new_user();