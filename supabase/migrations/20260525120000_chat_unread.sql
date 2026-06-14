-- Per-side last_read_at on conversations + RPC that returns the
-- caller's unread count, grouped by conversation.

ALTER TABLE public.conversations
    ADD COLUMN parent_last_read_at   timestamptz,
    ADD COLUMN provider_last_read_at timestamptz;


-- Per-conversation unread counts for the calling user. Returns one row
-- per conversation with at least one unread message; conversations with
-- no unread are simply omitted.
CREATE OR REPLACE FUNCTION public.get_unread_counts()
RETURNS TABLE (conversation_id uuid, unread_count int)
LANGUAGE sql
STABLE
SECURITY INVOKER
AS $$
    SELECT m.conversation_id, COUNT(*)::int AS unread_count
    FROM public.messages m
    JOIN public.conversations c ON c.id = m.conversation_id
    WHERE m.sender_id <> auth.uid()
      AND (
        -- Caller is the parent on this conversation
        (c.parent_id = auth.uid()
         AND (c.parent_last_read_at IS NULL
              OR m.created_at > c.parent_last_read_at))
        OR
        -- Caller owns the business this conversation is for
        (EXISTS (
            SELECT 1
            FROM public.businesses b
            WHERE b.id = c.business_id
              AND b.owner_id = auth.uid()
         )
         AND (c.provider_last_read_at IS NULL
              OR m.created_at > c.provider_last_read_at))
      )
    GROUP BY m.conversation_id;
$$;

GRANT EXECUTE ON FUNCTION public.get_unread_counts() TO authenticated;
