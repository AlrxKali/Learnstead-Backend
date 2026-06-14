-- Parent ↔ provider direct chat.
--
-- One conversation per (parent, business) pair. Either participant can
-- post messages. Realtime is enabled on both tables.

CREATE TABLE public.conversations (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id          uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    business_id        uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    last_message_at    timestamptz,
    last_message_body  text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (parent_id, business_id)
);

CREATE INDEX conversations_parent_id_idx  ON public.conversations(parent_id);
CREATE INDEX conversations_business_id_idx ON public.conversations(business_id);
CREATE INDEX conversations_last_message_at_idx
    ON public.conversations(last_message_at DESC NULLS LAST);


CREATE TABLE public.messages (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    sender_id       uuid NOT NULL REFERENCES auth.users(id),
    body            text NOT NULL
                    CHECK (length(body) > 0 AND length(body) <= 4000),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX messages_conversation_id_idx ON public.messages(conversation_id);
CREATE INDEX messages_created_at_idx       ON public.messages(created_at);


-- ----- RLS -----

ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages      ENABLE ROW LEVEL SECURITY;

-- Membership test for conversations: caller is the parent or owns the
-- business on the other end.
CREATE OR REPLACE FUNCTION public._is_conversation_participant(conv_id uuid)
RETURNS boolean AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.conversations c
        WHERE c.id = conv_id
          AND (
            c.parent_id = auth.uid()
            OR EXISTS (
                SELECT 1 FROM public.businesses b
                WHERE b.id = c.business_id
                  AND b.owner_id = auth.uid()
            )
          )
    );
$$ LANGUAGE sql STABLE SECURITY DEFINER;

CREATE POLICY "Participants read conversations"
    ON public.conversations FOR SELECT
    TO authenticated
    USING (
        parent_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = conversations.business_id
              AND b.owner_id = auth.uid()
        )
    );

-- Parents are the only ones who can start a conversation.
CREATE POLICY "Parents create conversations"
    ON public.conversations FOR INSERT
    TO authenticated
    WITH CHECK (parent_id = auth.uid());

-- Updates are needed for the touch_conversation_on_message trigger.
CREATE POLICY "Participants update conversations"
    ON public.conversations FOR UPDATE
    TO authenticated
    USING (
        parent_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = conversations.business_id
              AND b.owner_id = auth.uid()
        )
    )
    WITH CHECK (
        parent_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = conversations.business_id
              AND b.owner_id = auth.uid()
        )
    );

CREATE POLICY "Participants read messages"
    ON public.messages FOR SELECT
    TO authenticated
    USING (public._is_conversation_participant(messages.conversation_id));

CREATE POLICY "Participants send messages"
    ON public.messages FOR INSERT
    TO authenticated
    WITH CHECK (
        sender_id = auth.uid()
        AND public._is_conversation_participant(messages.conversation_id)
    );


-- ----- Trigger: bump conversation activity on new message -----

CREATE OR REPLACE FUNCTION public.touch_conversation_on_message()
RETURNS trigger AS $$
BEGIN
    UPDATE public.conversations
    SET last_message_at = NEW.created_at,
        last_message_body = NEW.body
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER touch_conversation_after_message
    AFTER INSERT ON public.messages
    FOR EACH ROW
    EXECUTE FUNCTION public.touch_conversation_on_message();


-- ----- Realtime -----

-- Make INSERT/UPDATE events on these tables available over Supabase
-- Realtime. RLS still gates which rows each subscriber sees.
ALTER PUBLICATION supabase_realtime ADD TABLE public.conversations;
ALTER PUBLICATION supabase_realtime ADD TABLE public.messages;
