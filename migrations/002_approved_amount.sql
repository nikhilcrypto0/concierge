-- Three-way approval: a reviewer may approve a LOWER amount than the policy computed.
-- amount_cents stays the policy amount (the ceiling and the identity of the request);
-- approved_amount_cents is what was actually authorised, NULL meaning "the full policy amount".
ALTER TABLE approval_requests
    ADD COLUMN approved_amount_cents INTEGER,
    ADD CONSTRAINT approved_amount_within_policy
        CHECK (approved_amount_cents IS NULL
               OR (approved_amount_cents > 0 AND approved_amount_cents <= amount_cents)),
    ADD CONSTRAINT approved_amount_only_when_approved
        CHECK (approved_amount_cents IS NULL OR status = 'approved');
