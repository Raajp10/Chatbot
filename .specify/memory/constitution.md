<!--
Sync Impact Report
- Version change: 1.0.1 → 2.0.0
- Rationale (2.0.0, MAJOR): The course now explicitly requires Docker for
  this project, reversing the prior explicit "no Docker" constraint in
  Principle V (a NON-NEGOTIABLE principle). This is a redefinition of a
  NON-NEGOTIABLE principle's actual requirement, not a wording clarification,
  so it is versioned as MAJOR per the Governance section's own rule. The
  system now MUST run via Docker Compose (a `backend` service and a
  `frontend` service) as the standard environment; ChromaDB remains a single
  embedded, file-based store (no separate Chroma server container), now
  persisted via a Docker volume instead of a bare local directory. No other
  principle changed; free-tier-only and single-embedded-vector-store remain
  non-negotiable.
- Modified principles: V. Local-First, Free-Tier Stack → Containerized,
  Free-Tier Stack (Docker Compose is now required instead of prohibited)
- Added sections: none
- Removed sections: none
- Deferred placeholders: none
-->

<!--
Sync Impact Report (1.0.1, historical)
- Version change: 1.0.0 → 1.0.1
- Rationale (1.0.1, PATCH): /speckit-analyze on feature 001-pnw-student-chatbot
  flagged (finding C1) that Principle II's blanket "...or outdated... MUST
  clearly state it cannot provide a reliable answer" reads as unconditional,
  while FR-018 ("SHOULD distinguish current from outdated... and SHOULD flag
  or prefer current information accordingly") and the feature's plan.md/
  data-model.md/tasks.md already implement a narrower rule: fail-safe applies
  only when NO current/newer approved information is available; when current
  information is also available, the system prefers it and may still answer,
  flagging the older source's caveat instead of declining. This amendment
  makes that carve-out explicit in the principle text itself so the
  constitution and the implemented design cannot drift apart. No principle
  was redefined or weakened — the exception was already load-bearing in the
  approved design; this only makes it traceable from the constitution.
- Modified principles: II. Fail Safe, Never Guess (wording clarification only)
- Added sections: none
- Removed sections: none
- Deferred placeholders: none
-->

<!--
Sync Impact Report (1.0.0, historical)
- Version change: (unratified template) → 1.0.0
- Rationale: Initial ratification. The prior file contained only unfilled
  `[PLACEHOLDER]` tokens from the constitution-template scaffold; no real
  governance existed yet. Principles below are derived from decisions already
  recorded and agreed for feature 001-pnw-student-chatbot in spec.md, plan.md,
  and research.md (grounding/fail-safe requirements, the clarified access-model
  decision, and the course's explicit simplicity/local-stack/free-tier
  constraints), not invented independently of that record.
- Modified principles: N/A (initial ratification, nothing to rename)
- Added sections: Core Principles (I–V), Content & Context Integrity,
  Development Workflow, Governance
- Removed sections: none (all template placeholders replaced)
- Deferred placeholders: none — RATIFICATION_DATE and LAST_AMENDED_DATE are
  both set to the date this constitution was first ratified.
-->

# PNW Student Knowledge Chatbot Constitution

## Core Principles

### I. Grounded Answers Only (NON-NEGOTIABLE)

Every answer about a university policy, deadline, procedure, academic requirement,
course, or program MUST be grounded in, and traceable to, an approved PNW source.
The system MUST NOT fabricate, guess, or infer policy details, deadlines, or
procedures that are not present in that corpus, and MUST cite the specific
supporting source whenever it gives a direct answer.

**Rationale**: This is the product's core trust guarantee. An answer that sounds
confident but is unsupported is worse than no answer, because it can be acted on
as if it were official policy.

### II. Fail Safe, Never Guess

When approved information is insufficient, ambiguous, or contradictory for a
given question, or when a question requires access to private/personalized
student data, the system MUST clearly state that it cannot provide a reliable
answer and MUST direct the student to the appropriate PNW office, department, or
advisor — instead of presenting a guess as fact or silently picking one side of a
conflicting source. When the only relevant approved information is explicitly
outdated and no current/newer approved information is also available, the same
fail-safe rule applies. When current/newer approved information IS also
available alongside an older source, the system MUST prefer the current
information and MAY still answer, flagging the older source's caveat in its
explanation rather than declining outright — this is the exception FR-018
describes ("SHOULD... flag or prefer current information"), and it does not
weaken the fail-safe guarantee for cases where no current information exists.

**Rationale**: Accuracy and safe failure are trust requirements equal in priority
to answering at all; a chatbot that answers confidently but incorrectly does more
harm than one that admits its limits.

### III. No Private Data, No Login Wall

The system MUST NOT access, retrieve, or reveal private or student-specific
records (registration status, grades, financial aid status, account details).
Because no such data is ever touched, the system MUST remain openly reachable
without requiring authentication or SSO for this version, showing only a visible
disclaimer that it is intended for currently registered PNW students.

**Rationale**: An authentication wall would add real engineering cost without
protecting anything, since the system is scoped to general, approved information
only. This reflects the deliberate access-model decision already recorded in
spec.md's Clarifications.

### IV. Simplicity Over Engineering Polish

Every design and implementation decision MUST favor the simplest approach that
satisfies the current, approved requirement. Do not add abstractions, services,
or infrastructure (extra databases, containers, queues, frameworks) beyond what
an approved requirement actually needs. Added complexity MUST be justified
against a concrete, current need — never a hypothetical future one.

**Rationale**: This is a v1 course/student project with limited time; unjustified
complexity slows delivery and obscures whether the core grounding and fail-safe
behavior actually works, which is the part that matters most.

### V. Containerized, Free-Tier Stack (NON-NEGOTIABLE)

The system MUST run via Docker Compose as its standard environment: a `backend`
service (FastAPI, dependencies managed with `uv` inside the image) and a
`frontend` service (React/Vite, dependencies managed with `npm` inside the
image), brought up together with `docker compose up --build`. The system MUST
use only free-tier APIs — Google Gemini for generation and embeddings — and
MUST NOT depend on a paid LLM or embedding service. ChromaDB MUST remain a
single embedded, file-based store (no separate Chroma server process/container),
with its data directory persisted via a Docker volume so ingested content
survives container restarts.

**Rationale**: These are explicit, non-negotiable course requirements for this
project. Docker Compose is now required (reversing the prior no-Docker
constraint) so the two-service local architecture is reproducible across
machines without a shared native Python/Node setup; free-tier-only and a single
embedded vector store remain required for the same cost and simplicity reasons
as before.

## Content & Context Integrity

Structured relationships present in source material MUST survive ingestion and
answer generation: a deadline MUST stay attached to its correct term and
condition, and a prerequisite MUST stay attached to its correct course — these
MUST NOT be flattened, mixed across unrelated rows/terms, or attributed to the
wrong course/program. When a question's correct answer depends on missing
context (campus, program, academic term, or student level), the system MUST ask
the student to clarify rather than assume a value; Hammond vs. Westville campus
differences MUST be resolved from context or by asking, never guessed.

## Development Workflow

Features proceed through the Spec Kit flow — `/speckit-specify` →
`/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement` —
before implementation begins. Ambiguities MUST be resolved via `/speckit-clarify`
(or an explicit, recorded user decision) before `/speckit-plan`, not silently
assumed by the implementer. Automated tests MUST accompany any change to
grounding, fail-safe, clarification, or retrieval behavior (contract tests for
`POST /api/query`, unit tests for the affected logic); because this v1 has no
end-to-end browser test suite, the manual scenarios in `quickstart.md` MUST be
re-validated before a feature touching those behaviors is considered done.

## Governance

This constitution supersedes ad hoc practice for this project. Amendments
require a documented rationale, an update to this file via `/speckit-constitution`,
and a version bump under semantic versioning: MAJOR for backward-incompatible
removal or redefinition of a principle, MINOR for a new principle or materially
expanded guidance, PATCH for wording/clarification only. A plan or task that
would violate a NON-NEGOTIABLE principle (I or V) MUST be rejected, or its
violation explicitly justified in that feature's `plan.md` Complexity Tracking
section, before implementation proceeds. Reviews (including `/code-review`)
should check compliance with Principles I–III in particular, since they encode
this project's user-facing trust and safety guarantees.

**Version**: 2.0.0 | **Ratified**: 2026-09-16 | **Last Amended**: 2026-09-21
