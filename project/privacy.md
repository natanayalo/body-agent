# Privacy & Safety

This document summarizes what is redacted, how private data is handled, and the safety posture of responses.

## Redaction (scrub)

- The `scrub` node removes phone numbers, emails, and common identifiers from the user query.
- Downstream nodes should prefer `user_query_redacted` where available.
- Logs should never include raw user text; structured debug metadata is allowed.

## Private memory encryption (field-level)

- Sensitive fields in `private_user_memory` (e.g., `value`) are encrypted with a per-user key.
- Keys are stored under `${APP_DATA_DIR}/keys/<user_id>.key` and created on first use (see `app/tools/crypto.py`).
- Index queries are guarded by `user_id` term filters to enforce tenancy.

## Disclaimers & risk gating

- The final assistant message always includes a medical disclaimer.
- If `risk_ml` triggers `urgent_care` or `see_doctor`, the message includes an urgent-care line.
- The `critic` node checks for citations and avoids diagnostic language.

## Data retention

- Private memory supports TTL on transient items (planned); the server does not store prompts.
- Elasticsearch indices are local by default; remote deployments should treat ES as sensitive storage.
