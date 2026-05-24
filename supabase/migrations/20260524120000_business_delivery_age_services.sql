-- Add delivery_mode, age range, and business↔subcategory link.

-- 1) delivery_mode on businesses
ALTER TABLE public.businesses
    ADD COLUMN delivery_mode text NOT NULL DEFAULT 'in_person'
        CHECK (delivery_mode IN ('online', 'in_person', 'hybrid'));

-- 2) min/max age on businesses (nullable, sanity-bounded)
ALTER TABLE public.businesses
    ADD COLUMN min_age int CHECK (min_age IS NULL OR (min_age >= 0 AND min_age <= 99)),
    ADD COLUMN max_age int CHECK (max_age IS NULL OR (max_age >= 0 AND max_age <= 99)),
    ADD CONSTRAINT businesses_age_range_valid
        CHECK (min_age IS NULL OR max_age IS NULL OR min_age <= max_age);

-- 3) business ↔ subcategory junction table
CREATE TABLE public.business_subcategory (
    business_id    uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    subcategory_id uuid NOT NULL REFERENCES public.business_subcategories(id) ON DELETE CASCADE,
    created_at     timestamptz DEFAULT now(),
    PRIMARY KEY (business_id, subcategory_id)
);

ALTER TABLE public.business_subcategory ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read business_subcategory"
    ON public.business_subcategory
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Owners can insert their business subcategories"
    ON public.business_subcategory
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = business_subcategory.business_id
              AND b.owner_id = auth.uid()
        )
    );

CREATE POLICY "Owners can delete their business subcategories"
    ON public.business_subcategory
    FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = business_subcategory.business_id
              AND b.owner_id = auth.uid()
        )
    );

-- 4) Seed the subcategory catalog and category links.
--    Uses ON CONFLICT to be safe if the migration is re-applied.

INSERT INTO public.business_subcategories (name) VALUES
    ('Math Tutoring'),
    ('Reading Tutoring'),
    ('Writing Tutoring'),
    ('Science Tutoring'),
    ('Test Prep'),
    ('Foreign Language'),
    ('Creative Arts'),
    ('Music'),
    ('Theater'),
    ('STEM'),
    ('Nature-Based Learning'),
    ('Physical Education'),
    ('Social-Emotional Learning'),
    ('Project-Based Learning'),
    ('Multi-Age Learning'),
    ('Parent-Led'),
    ('Small Group Sessions'),
    ('One-on-One'),
    ('Self-Paced'),
    ('Live Online'),
    ('After-School Programs'),
    ('Weekend Workshops'),
    ('Summer Camps')
ON CONFLICT (name) DO NOTHING;

-- Link subcategories to top-level categories.
WITH cat AS (
    SELECT id, name FROM public.business_categories
), sub AS (
    SELECT id, name FROM public.business_subcategories
)
INSERT INTO public.business_category_subcategory (category_id, subcategory_id)
SELECT c.id, s.id
FROM cat c
JOIN sub s ON (
    (c.name = 'Tutoring' AND s.name IN (
        'Math Tutoring','Reading Tutoring','Writing Tutoring','Science Tutoring',
        'Test Prep','Foreign Language','One-on-One','Small Group Sessions'
    )) OR
    (c.name = 'Co-op' AND s.name IN (
        'Multi-Age Learning','Parent-Led','Project-Based Learning','Small Group Sessions'
    )) OR
    (c.name = 'Enrichment Program' AND s.name IN (
        'Creative Arts','Music','Theater','STEM','Nature-Based Learning',
        'Physical Education','Social-Emotional Learning','After-School Programs',
        'Weekend Workshops','Summer Camps'
    )) OR
    (c.name = 'Online Course' AND s.name IN (
        'Self-Paced','Live Online','One-on-One','Small Group Sessions','Foreign Language'
    )) OR
    (c.name = 'Microschool' AND s.name IN (
        'Multi-Age Learning','Project-Based Learning','Small Group Sessions',
        'Social-Emotional Learning','Nature-Based Learning'
    ))
)
ON CONFLICT DO NOTHING;
