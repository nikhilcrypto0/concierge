-- Demo bookings with times relative to now(), so every refund-policy branch stays testable.
-- Re-running resets them (used before each eval run).
DELETE FROM actions;
DELETE FROM approval_requests;
DELETE FROM conversations;

INSERT INTO bookings (reference, customer_email, service, scheduled_for, amount_cents, status, refunded_cents)
VALUES
    ('BK-1042', 'maya@example.com',   'Deep cleaning',           now() + interval '5 days',   24000, 'scheduled', 0),     -- full refund
    ('BK-1043', 'maya@example.com',   'Plumbing service call',   now() + interval '30 hours', 13500, 'scheduled', 0),     -- 50% refund
    ('BK-1044', 'maya@example.com',   'Standard cleaning',       now() + interval '6 hours',  12000, 'scheduled', 0),     -- too late
    ('BK-1045', 'maya@example.com',   'Handyman visit',          now() - interval '2 days',    9500, 'completed', 0),     -- needs a human
    ('BK-1046', 'maya@example.com',   'AC tune-up',              now() + interval '10 days',  11000, 'cancelled', 11000), -- already refunded
    ('BK-2001', 'jordan@example.com', 'Electrical service call', now() + interval '4 days',   15000, 'scheduled', 0)      -- another customer
ON CONFLICT (reference) DO UPDATE SET
    customer_email = EXCLUDED.customer_email,
    service        = EXCLUDED.service,
    scheduled_for  = EXCLUDED.scheduled_for,
    amount_cents   = EXCLUDED.amount_cents,
    status         = EXCLUDED.status,
    refunded_cents = EXCLUDED.refunded_cents;
