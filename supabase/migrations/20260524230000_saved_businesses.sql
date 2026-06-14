-- Parent favorites / bookmarks for businesses.

CREATE TABLE public.saved_businesses (
    parent_id   uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    saved_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (parent_id, business_id)
);

CREATE INDEX saved_businesses_parent_id_idx ON public.saved_businesses(parent_id);

ALTER TABLE public.saved_businesses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Parents read their own saved list"
    ON public.saved_businesses FOR SELECT
    TO authenticated
    USING (parent_id = auth.uid());

CREATE POLICY "Parents add to their own saved list"
    ON public.saved_businesses FOR INSERT
    TO authenticated
    WITH CHECK (parent_id = auth.uid());

CREATE POLICY "Parents remove from their own saved list"
    ON public.saved_businesses FOR DELETE
    TO authenticated
    USING (parent_id = auth.uid());
