# Business Logic Audit Skill

## Overview
Business logic flaws are design-level bugs: price manipulation, negative quantities, discount abuse, step-skipping, privilege flow bypass.

## Audit Methodology
1. Map business flows: order → payment → ship → refund; register → verify → activate; withdraw → approve
2. For each state transition, verify server-side validation of every parameter
3. Look for client-trusted values: price, amount, discount, points, quantity, time, probability
4. Check step ordering: can steps be skipped/reordered (pay after ship, verify after activate)?
5. Check for missing idempotency / rate limits on value operations

## Common Vulnerable Patterns
- `price`/`amount`/`refund_amount` taken from client without server recompute
- `order_time`/`timestamp` from client → discount window bypass
- Negative quantity / negative amount / zero-price orders
- Coupon/discount stack abuse, missing per-user cap
- Lottery/probability params from client
- Points deduction without upper-bound check
- State machine not enforced server-side (merchant self-approve)

## Key Reminders
- Money, time, quantity, probability must ALWAYS be computed server-side
- Never trust client for anything that affects value
- Enforce state machines server-side (valid transitions only)
- Check idempotency: duplicate submit of the same operation

## Checklist
- [ ] Prices/amounts recomputed server-side, never trusted from client?
- [ ] Time windows checked against server time?
- [ ] Quantities validated (positive, bounded, ≤ stock)?
- [ ] State transitions enforced with valid transition map?
- [ ] Discounts/coupons have per-user caps and can't stack infinitely?
