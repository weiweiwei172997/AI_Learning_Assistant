<!--
Owner: project-maintainer
Last Reviewed: 2026-10-27
Status: Accepted
-->

# ADR 010: BNBU Institutional Auth

## Context

The local teaching deployment is intended for BNBU users. Retaining legacy
institution-specific domains in validation, interface copy, and product
documentation creates misleading sign-in guidance.

## Decision

Weak local authentication accepts addresses ending in `@bnbu.edu.cn` or
`@mail.bnbu.edu.cn`. Existing role and token response shapes remain unchanged;
accepted BNBU accounts use the `teacher` role, which retains full phase-1
generation capability.

All active product copy, tests, reference slide branding, and governance material
use BNBU terminology.

On 2026-10-27, the user confirmed the student domain as `@mail.bnbu.edu.cn`.
The earlier `@mail.bnbu.cn` entry was a transcription error and is not an
accepted domain.

## Consequences

- Accounts from other domains cannot register or log in.
- Previously created sessions remain usable until expiry because bearer-token
  validation is unchanged.
- Previously created accounts from other domains cannot create a new session.
- A future domain expansion must update the auth contract, implementation, and
  focused tests together.
