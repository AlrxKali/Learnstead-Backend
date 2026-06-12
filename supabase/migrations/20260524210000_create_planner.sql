-- Parent-side planner: plans and the sessions inside them.

CREATE TABLE public.plans (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id   uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    business_id uuid REFERENCES public.businesses(id) ON DELETE SET NULL,
    title       text NOT NULL,
    notes       text,
    color       text NOT NULL DEFAULT '#6F9A84'
                CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
    created_at  timestamptz DEFAULT now(),
    updated_at  timestamptz DEFAULT now()
);

CREATE INDEX plans_parent_id_idx ON public.plans(parent_id);

CREATE TRIGGER set_plans_updated_at
    BEFORE UPDATE ON public.plans
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

ALTER TABLE public.plans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Parents read their own plans"
    ON public.plans FOR SELECT
    TO authenticated
    USING (parent_id = auth.uid());

CREATE POLICY "Parents insert their own plans"
    ON public.plans FOR INSERT
    TO authenticated
    WITH CHECK (parent_id = auth.uid());

CREATE POLICY "Parents update their own plans"
    ON public.plans FOR UPDATE
    TO authenticated
    USING (parent_id = auth.uid())
    WITH CHECK (parent_id = auth.uid());

CREATE POLICY "Parents delete their own plans"
    ON public.plans FOR DELETE
    TO authenticated
    USING (parent_id = auth.uid());


CREATE TABLE public.plan_sessions (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id    uuid NOT NULL REFERENCES public.plans(id) ON DELETE CASCADE,
    starts_at  timestamptz NOT NULL,
    ends_at    timestamptz NOT NULL,
    status     text NOT NULL DEFAULT 'planned'
               CHECK (status IN ('planned', 'cancelled')),
    notes      text,
    created_at timestamptz DEFAULT now(),
    CONSTRAINT plan_sessions_time_valid CHECK (ends_at > starts_at)
);

CREATE INDEX plan_sessions_plan_id_idx ON public.plan_sessions(plan_id);
CREATE INDEX plan_sessions_starts_at_idx ON public.plan_sessions(starts_at);

ALTER TABLE public.plan_sessions ENABLE ROW LEVEL SECURITY;

-- All policies check ownership through the parent plan.
CREATE POLICY "Parents read sessions of their plans"
    ON public.plan_sessions FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.plans p
            WHERE p.id = plan_sessions.plan_id
              AND p.parent_id = auth.uid()
        )
    );

CREATE POLICY "Parents insert sessions on their plans"
    ON public.plan_sessions FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.plans p
            WHERE p.id = plan_sessions.plan_id
              AND p.parent_id = auth.uid()
        )
    );

CREATE POLICY "Parents update sessions on their plans"
    ON public.plan_sessions FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.plans p
            WHERE p.id = plan_sessions.plan_id
              AND p.parent_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.plans p
            WHERE p.id = plan_sessions.plan_id
              AND p.parent_id = auth.uid()
        )
    );

CREATE POLICY "Parents delete sessions on their plans"
    ON public.plan_sessions FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.plans p
            WHERE p.id = plan_sessions.plan_id
              AND p.parent_id = auth.uid()
        )
    );
