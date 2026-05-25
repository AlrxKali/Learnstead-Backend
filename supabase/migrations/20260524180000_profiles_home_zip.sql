-- Add home_zip_code to profiles so we can locality-match parents to
-- in-person / hybrid businesses.

ALTER TABLE public.profiles
    ADD COLUMN home_zip_code text
        CHECK (
            home_zip_code IS NULL
            OR home_zip_code ~ '^[0-9]{5}(-[0-9]{4})?$'
        );
