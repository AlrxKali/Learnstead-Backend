-- Create business_categories lookup table
CREATE TABLE public.business_categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text UNIQUE NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- Create businesses table
CREATE TABLE public.businesses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name text NOT NULL,
    description text,
    phone text,
    email text,
    website text,
    address_line1 text,
    address_line2 text,
    city text,
    state text,
    zip_code text,
    category_id uuid REFERENCES public.business_categories(id),
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Trigger function to auto-update updated_at
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_businesses_updated_at
    BEFORE UPDATE ON public.businesses
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- Enable RLS
ALTER TABLE public.business_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.businesses ENABLE ROW LEVEL SECURITY;

-- RLS policies for business_categories (read-only for authenticated users)
CREATE POLICY "Authenticated users can read categories"
    ON public.business_categories
    FOR SELECT
    TO authenticated
    USING (true);

-- RLS policies for businesses
CREATE POLICY "Authenticated users can read all businesses"
    ON public.businesses
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Users can insert their own business"
    ON public.businesses
    FOR INSERT
    TO authenticated
    WITH CHECK (owner_id = auth.uid());

CREATE POLICY "Users can update their own business"
    ON public.businesses
    FOR UPDATE
    TO authenticated
    USING (owner_id = auth.uid())
    WITH CHECK (owner_id = auth.uid());

CREATE POLICY "Users can delete their own business"
    ON public.businesses
    FOR DELETE
    TO authenticated
    USING (owner_id = auth.uid());

-- Seed default categories
INSERT INTO public.business_categories (name) VALUES
    ('Tutoring'),
    ('Co-op'),
    ('Enrichment Program'),
    ('Online Course'),
    ('Microschool'),
    ('Other');
