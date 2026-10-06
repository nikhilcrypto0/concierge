-- Defense in depth for the one rule that matters: money only moves with an approval.
-- The application already enforces it. These constraints make Postgres enforce it too, so the
-- guarantee holds even for a direct SQL write that bypasses the application code.
--
-- An executed action must (1) belong to an APPROVED request, (2) target the booking that request
-- was about, and (3) never exceed the authorised amount: the reviewer's lower amount when one
-- was set, otherwise the policy amount.

ALTER TABLE actions
    ADD CONSTRAINT action_is_a_refund CHECK (action = 'refund'),
    ADD CONSTRAINT action_amount_is_positive CHECK (amount_cents > 0);

CREATE FUNCTION enforce_action_matches_approval() RETURNS trigger AS $$
DECLARE
    approval approval_requests%ROWTYPE;
BEGIN
    SELECT * INTO approval FROM approval_requests WHERE id = NEW.approval_id;
    IF NOT FOUND OR approval.status <> 'approved' THEN
        RAISE EXCEPTION 'an action requires an approved approval request'
            USING ERRCODE = 'check_violation';
    END IF;
    IF approval.booking_reference <> NEW.booking_reference THEN
        RAISE EXCEPTION 'an action must target the booking its approval was for'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.amount_cents > COALESCE(approval.approved_amount_cents, approval.amount_cents) THEN
        RAISE EXCEPTION 'an action cannot exceed the authorised amount'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER actions_match_their_approval
    BEFORE INSERT ON actions
    FOR EACH ROW EXECUTE FUNCTION enforce_action_matches_approval();
