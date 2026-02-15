-- Create profiles table
CREATE TABLE public.profiles (
    id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('parent', 'provider')),
    full_name text,
    created_at timestamptz DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Users can read their own profile
CREATE POLICY "Users can read own profile"
    ON public.profiles
    FOR SELECT
    TO authenticated
    USING (id = auth.uid());

-- Users can update their own profile
CREATE POLICY "Users can update own profile"
    ON public.profiles
    FOR UPDATE
    TO authenticated
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- Service role can insert profiles (used during signup)
-- The anon key INSERT is needed because the user is being created
-- and the insert happens in the same signup request before they have a session.
-- We use the service_role client server-side to do this safely.
CREATE POLICY "Service role can insert profiles"
    ON public.profiles
    FOR INSERT
    TO service_role
    WITH CHECK (true);

-- Allow authenticated users to read any profile (for public-facing provider names, etc.)
CREATE POLICY "Authenticated users can read all profiles"
    ON public.profiles
    FOR SELECT
    TO authenticated
    USING (true);
