# Race Condition / Concurrency Audit Skill

## Overview
Race conditions occur when check-then-act sequences (TOCTOU) are not atomic, allowing double-spend, double-refund, duplicate processing.

## Audit Methodology
1. Find money/state-changing operations: payment, refund, recharge, coupon, points, inventory decrement, order status
2. Identify the pattern: read state → validate → write state (check-then-act)
3. Check atomicity: is the whole sequence in a transaction with lock? Is the update conditional (`WHERE status='pending'`)?
4. Check for async gaps: session_write_close, usleep, network calls BETWEEN check and act
5. Assess: can concurrent requests both pass the check?

## Common Vulnerable Patterns
- Read-then-write without lock: balance check then decrement
- `if (record.processed == false) { process(); mark_processed(); }` without atomic update
- Callback handlers with network delay between duplicate-check and mark
- Non-atomic coupon redemption / lottery draw
- `UPDATE ... WHERE id=?` without conditional (`AND status='unused'`)

## Key Reminders
- Use conditional atomic updates: `UPDATE ... SET used=1 WHERE id=? AND used=0` — check affected_rows
- Use `SELECT ... FOR UPDATE` (row lock) inside a transaction
- Remove artificial delays (usleep) between check and act
- Idempotency keys: unique constraint on transaction/order IDs

## Checklist
- [ ] Money/state changes are atomic (transaction + lock)?
- [ ] Updates are conditional on state (WHERE status=...)?
- [ ] No sleep/network gap between check and act?
- [ ] Unique constraint on idempotency key (order_no, recharge_no)?
