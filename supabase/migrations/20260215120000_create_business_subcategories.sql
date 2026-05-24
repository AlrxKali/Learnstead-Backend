-- Add INSERT policy on business_categories for service_role
ALTER TABLE business_categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role can insert categories"
    ON business_categories
    FOR INSERT
    TO service_role
    WITH CHECK (true);

-- Create subcategories table (no category_id — many-to-many via junction)
CREATE TABLE business_subcategories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    created_at timestamptz DEFAULT now()
);

ALTER TABLE business_subcategories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read subcategories"
    ON business_subcategories
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "service_role can insert subcategories"
    ON business_subcategories
    FOR INSERT
    TO service_role
    WITH CHECK (true);

-- Junction table for many-to-many categories <-> subcategories
CREATE TABLE business_category_subcategory (
    category_id uuid NOT NULL REFERENCES business_categories(id) ON DELETE CASCADE,
    subcategory_id uuid NOT NULL REFERENCES business_subcategories(id) ON DELETE CASCADE,
    PRIMARY KEY (category_id, subcategory_id)
);

ALTER TABLE business_category_subcategory ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read category_subcategory links"
    ON business_category_subcategory
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "service_role can insert category_subcategory links"
    ON business_category_subcategory
    FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "service_role can delete category_subcategory links"
    ON business_category_subcategory
    FOR DELETE
    TO service_role
    USING (true);
