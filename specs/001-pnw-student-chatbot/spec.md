# Feature Specification: PNW Student Knowledge Chatbot

**Feature Branch**: `001-pnw-student-chatbot`

**Created**: 2026-09-14

**Status**: Draft

**Input**: User description: "Create the initial software specification for a Purdue University Northwest (PNW) student knowledge chatbot using the stakeholder interview notes, compiled student interview notes, and initial corpus review notes" (Dean of Students Office stakeholder interview, compiled student interview notes, and initial corpus review notes, summarized below)

## Clarifications

### Session 2026-09-16

- Q: How should the system determine or verify that a user is a currently registered PNW student before answering? → A: Open access with a visible audience disclaimer ("intended for currently registered PNW students") and no login enforcement; no SSO/authentication is required.
- Q: What should be the primary interaction surface where students access the chatbot? → A: A standalone web page/application with its own dedicated URL (not embedded in pnw.edu or MyPNW for this version).
- Q: What is this chatbot's intended relationship to PNW's existing chatbot, "Leo"? → A: Run alongside Leo as a separate, independent tool, with no replacement of or integration with Leo for this version.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a Direct, Grounded Answer to a University Question (Priority: P1)

A currently registered PNW undergraduate or graduate student asks a question in plain language about a university policy, deadline, procedure, or requirement (for example, "How do I pay a parking ticket?" or "What is the add/drop deadline for this semester?"). The chatbot searches approved PNW information and responds with a direct answer, a simple explanation, and the official source that supports it — instead of only returning a list of links.

**Why this priority**: This is the core value proposition identified by both the stakeholder (reduce repetitive questions to the Dean of Students Office) and every student interview (students want one place to get a clear, direct answer instead of searching multiple pages). Without this, there is no product.

**Independent Test**: Can be fully tested by submitting a set of representative questions drawn from the stakeholder's common-question list (add/drop, registration, deadlines, policies) against the approved source corpus and confirming each answer is direct, understandable, and traceable to a specific approved source.

**Acceptance Scenarios**:

1. **Given** an approved PNW source contains a clear, unambiguous answer to a student's question, **When** the student asks that question in natural language, **Then** the chatbot returns a direct answer, a simple explanation, and a reference to the supporting official source.
2. **Given** a question whose answer requires combining information from a top-level page and a linked child page or document, **When** the student asks the question, **Then** the chatbot's answer reflects the combined information rather than only the top-level page's content.
3. **Given** a student asks a question covered by the stakeholder's list of common topics (e.g., registration, academic standing, grade appeals, financial aid deadlines), **When** approved source information exists for that topic, **Then** the chatbot provides a substantive answer rather than only a link.

---

### User Story 2 - Fail Safely When an Answer Cannot Be Reliably Given (Priority: P1)

A student asks a question that the chatbot cannot reliably answer — because the approved information is missing, insufficient, ambiguous, contradictory, outdated, or too personalized (e.g., diagnosing a specific registration error tied to that student's account). The chatbot clearly states that it cannot provide a reliable answer and directs the student to the appropriate PNW office, department, or advisor, instead of guessing or inventing an answer.

**Why this priority**: The stakeholder identified accuracy as the single biggest concern, and explicitly required the system to fail safely rather than present unsupported information as policy. This is a trust and safety requirement equal in priority to User Story 1 — a chatbot that answers confidently but incorrectly is worse than one that admits its limits.

**Independent Test**: Can be fully tested by submitting questions known to fall outside the approved corpus (or requiring personalized/private data) and confirming the chatbot declines to fabricate an answer and instead provides an appropriate referral.

**Acceptance Scenarios**:

1. **Given** no approved source contains sufficient information to answer a question, **When** the student asks that question, **Then** the chatbot states that it cannot provide a reliable answer and does not present a guess as fact.
2. **Given** a question requires access to a specific student's private records (e.g., "why did my registration fail") that general approved sources cannot resolve, **When** the student asks that question, **Then** the chatbot explains that it cannot access personal/private information and directs the student to the appropriate office or advisor.
3. **Given** two approved sources appear to conflict on the same topic, **When** the chatbot forms a response, **Then** the chatbot does not silently pick one source's answer, and instead communicates the uncertainty to the student.

---

### User Story 3 - Resolve Campus-Dependent Questions Correctly (Priority: P2)

A student asks a question whose correct answer depends on which PNW campus (Hammond or Westville) applies. The chatbot either determines the relevant campus from the question's context or asks the student which campus they mean, rather than assuming one campus and giving a potentially wrong answer.

**Why this priority**: Multiple student interviews (parking, catalog/program information) identified campus ambiguity as a specific, recurring source of confusion and wasted effort. Getting this wrong actively harms trust, so it is prioritized just below the core answer/fail-safe behaviors.

**Independent Test**: Can be fully tested by submitting questions that have campus-specific answers, with and without campus mentioned in the question, and confirming the chatbot either uses the correct campus context or asks a clarifying question rather than guessing.

**Acceptance Scenarios**:

1. **Given** a question's answer differs between Hammond and Westville, and the student's question specifies a campus, **When** the chatbot answers, **Then** the response uses the information for the specified campus only.
2. **Given** a question's answer differs by campus and the student's question does not indicate which campus, **When** the chatbot processes the question, **Then** the chatbot asks the student to clarify the campus before giving a campus-specific answer.

---

### User Story 4 - Understand Course Prerequisites and Program Requirements (Priority: P2)

A student asks about program requirements, course prerequisites, or graduate plan-of-study steps (e.g., "What are the prerequisites for [course]?" or "How do I submit my plan of study?"). The chatbot combines the relevant, related pieces of catalog and procedural information into one understandable answer while preserving which prerequisite belongs to which course and which requirement belongs to which program.

**Why this priority**: Student interviews specifically flagged program/prerequisite information as hard to find and easy to misunderstand, with real consequences (misunderstanding graduation requirements). This is high-value but depends on the core answer and safe-failure behaviors already being in place.

**Independent Test**: Can be fully tested by asking about a specific course's prerequisites or a specific program's requirements and confirming the returned prerequisite/requirement chain matches the correct course/program in the approved catalog source.

**Acceptance Scenarios**:

1. **Given** a course has one or more prerequisites listed in the approved catalog, **When** a student asks about that course's prerequisites, **Then** the chatbot's answer correctly associates each prerequisite with that specific course.
2. **Given** a graduate student asks what is required to submit a plan of study, **When** approved source information covers that process, **Then** the chatbot's answer includes the relevant steps (e.g., required approvals, timing) as supported by approved sources, and does not invent steps not present in those sources.

---

### User Story 5 - Get Accurate, Term-Correct Deadline Information (Priority: P3)

A student asks about an academic or financial deadline (e.g., add/drop date, refund deadline, financial aid deadline). The chatbot returns the date(s) correctly associated with the right term (fall/spring/summer), action, and condition, without mixing information from a different term.

**Why this priority**: Deadlines are high-impact (missing one has real consequences) and were specifically called out in the corpus review as coming from complex HTML tables that are easy to misread. This depends on the structured-data handling built for earlier stories, so it is sequenced after them.

**Independent Test**: Can be fully tested by asking for deadlines across multiple terms and conditions and confirming each returned date is correctly attributed to its term, action, and condition, with no cross-term mixing.

**Acceptance Scenarios**:

1. **Given** an approved source contains a table of deadlines by term and action, **When** a student asks for a specific term's specific deadline (e.g., "fall add/drop deadline"), **Then** the chatbot returns the date associated with that exact term and action.
2. **Given** a student asks a deadline question without specifying the term, **When** more than one applicable term's information exists (e.g., a past and an upcoming term), **Then** the chatbot clarifies which term is meant or clearly states which term the answer refers to, rather than presenting one term's date as universally correct.

---

### Edge Cases

- What happens when a student asks a question with no relevant approved PNW source at all (topic not covered in the corpus)? The chatbot must say it cannot provide a reliable answer and suggest an appropriate contact, rather than answering from general/unverified knowledge.
- What happens when a student's question spans multiple sub-topics (e.g., a deadline question and a prerequisite question combined)? The chatbot should address the parts it can answer reliably and clearly flag any part it cannot.
- What happens when the approved source information itself appears outdated (e.g., references a past academic year) alongside newer information? The chatbot should surface the uncertainty rather than presenting the outdated information as current.
- What happens when a student's question implies they are not a currently registered PNW student (e.g., a prospective student asking about admission)? Handling of non-target users is not fully specified in this version and should default to the fail-safe behavior (state the limitation, refer to an appropriate office) rather than guessing at policies for an out-of-scope population.
- What happens when relevant information exists only behind an expandable section, a nested/child page, or an attached document not directly on the page the student would land on first? The chatbot must still be able to draw on that information rather than treating only the top-level page as the source of truth.
- What happens when a question requires a genuinely personalized answer (specific to that student's registration, financial aid, or account status) that no general approved source could ever answer? The chatbot must not fabricate a personalized result and must direct the student to the correct office or advisor.
- What happens when a student asks something entirely unrelated to PNW university matters? The chatbot should decline to answer outside its intended scope rather than acting as a general-purpose assistant.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow a currently registered PNW undergraduate or graduate student to submit a question in natural language and receive a response.
- **FR-002**: System MUST search approved PNW information sources relevant to the submitted question before producing an answer.
- **FR-003**: System MUST provide a direct, concise answer, with a simple explanation, when the approved information sources contain sufficient reliable information to support that answer, rather than returning only a list of links.
- **FR-004**: System MUST ground every answer about university policies, rules, deadlines, procedures, academic requirements, courses, and programs in approved PNW source content, and MUST NOT present information as official PNW policy unless it is supported by an approved source.
- **FR-005**: System MUST NOT fabricate, guess, or infer university policy details, deadlines, or procedures that are not present in approved PNW sources.
- **FR-006**: System MUST include a reference to the official PNW source(s) supporting a grounded answer when such a source exists.
- **FR-007**: When approved information is insufficient, ambiguous, contradictory, or outdated for a given question, System MUST clearly state that it cannot provide a reliable answer rather than presenting a guess as fact.
- **FR-008**: When the system cannot reliably answer a question, or when a question requires access to private or student-specific records, System MUST direct the student to the appropriate PNW office, department, or advisor.
- **FR-009**: System MUST detect when a question's correct answer depends on missing context (campus, program, academic term, or student level) and MUST request clarification from the student rather than assuming a value.
- **FR-010**: System MUST distinguish between the PNW Hammond and Westville campuses when an answer differs by campus, and either determine the correct campus from the question's context or ask the student which campus applies.
- **FR-011**: System MUST be able to incorporate information found across multiple linked PNW pages and attached documents relevant to a question, not only the first/top-level page a search would surface.
- **FR-012**: System MUST support source content in multiple formats, including at minimum HTML webpages and PDF documents.
- **FR-013**: When source information is structured (e.g., an HTML table of deadlines), System MUST preserve the association between related values (a date remains associated with its correct term, action, and condition) and MUST NOT mix values across unrelated rows, columns, or terms.
- **FR-014**: System MUST preserve meaningful document structure (headings, sections, numbered procedures, bullet lists) so relationships between requirements, steps, and conditions are not lost when forming an answer.
- **FR-015**: System MUST treat information located behind expandable sections, nested/child pages, or linked/attached documents as part of the searchable university knowledge base when it is relevant to a question.
- **FR-016**: System MUST preserve the relationship between a course and its prerequisites when answering prerequisite-related questions, and MUST NOT attribute a prerequisite to the wrong course.
- **FR-017**: When two or more approved sources conflict on a topic relevant to a question, System MUST NOT silently choose one source's answer; it MUST communicate the resulting uncertainty to the student (per FR-007).
- **FR-018**: System SHOULD distinguish current from outdated information when that distinction can be established from approved sources, and SHOULD flag or prefer current information accordingly.
- **FR-019**: System MUST express answers in plain, student-understandable language rather than only reproducing raw policy, catalog, or table text verbatim.
- **FR-020**: System MUST NOT access, retrieve, or reveal private, student-specific records (e.g., an individual student's registration status, grades, financial aid status, or account details); answers MUST be limited to general, approved university information.
- **FR-021**: System MUST support questions covering, at minimum, the following topic areas: registration, add/drop processes, academic standing, grade appeals, financial aid deadlines, academic deadlines, course and program requirements, prerequisites, graduation procedures, plan of study questions, parking rules and procedures, student policies, campus services, and appropriate university contacts.
- **FR-022**: System MUST limit its intended user population, for this version, to currently registered PNW undergraduate and graduate students; supporting faculty, staff, or prospective student use cases is out of scope for this version.
- **FR-023**: When relevant to a question, System MUST surface important deadlines or conditions, any necessary campus/semester/program context, the supporting official source, and (when the system cannot fully resolve the question) the correct department or office to contact.
- **FR-024**: System MUST be openly accessible without requiring authenticated login or SSO verification, and MUST present a visible disclaimer stating that it is intended for currently registered PNW undergraduate and graduate students; the system MUST NOT enforce identity verification as a precondition to answering.
- **FR-025**: System MUST be delivered as a separate, independent tool that runs alongside PNW's existing chatbot, "Leo," for this version; System MUST NOT replace Leo, and integration with Leo is out of scope for this version.
- **FR-026**: System MUST be delivered as a standalone web page/application with its own dedicated URL for this version; embedding within pnw.edu or MyPNW is out of scope for this version.

### Key Entities

- **Question**: A student's natural-language input; may explicitly or implicitly reference context such as campus, program, academic term, or student level needed to resolve it correctly.
- **Source**: An approved unit of PNW information (a webpage, PDF, table, policy section, or attached document, retrieved at the granularity of a chunk) that can support an answer; carries its text and structural context (headings, table rows, procedure steps), plus optional campus, academic term, course, program, and student-level attributes — set only when the source itself establishes them, never guessed.
- **Response**: What the chatbot returns for a Question — a grounded answer (a direct answer, a plain-language explanation, and the supporting Source(s)), a clarification request (when campus, program, term, or student level is missing and needed to answer correctly), or a referral to the appropriate PNW office (when the chatbot cannot reliably answer or the question requires private data).

Campus, academic term, course/program, and student level are not separate stored entities — they are optional attributes of a Source or values carried on Question context, present only when an approved source establishes them.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a defined test set of questions drawn from the stakeholder's common-question categories (add/drop, registration, academic standing, grade appeals, financial aid deadlines, policies, deadlines, procedures, contacts), 100% of the answers the chatbot actually provides (as opposed to declining to answer) are grounded in, and traceable to, an approved PNW source.
- **SC-002**: Across the same test set, 0% of chatbot answers present fabricated or unsupported information as official PNW policy.
- **SC-003**: When a test question cannot be reliably answered from approved sources, the chatbot states its limitation and provides an appropriate office/department/advisor referral in 100% of those cases, rather than guessing.
- **SC-004**: For a defined set of campus-dependent test questions, the chatbot never answers using the wrong campus's information: in 100% of cases it either correctly identifies the relevant campus or asks a clarifying question first.
- **SC-005**: For a defined set of deadline test questions tied to structured schedule data, the reported date, term, and condition are correctly matched in 100% of test cases, with no cross-term mixing.
- **SC-006**: In usability testing, at least 80% of student testers report that getting an answer from the chatbot was easier than their prior process of manually searching PNW webpages for the same information.
- **SC-007**: For a defined set of test questions requiring private or personalized student data, the chatbot does not produce a fabricated personalized answer in 100% of cases; it instead explains the limitation and provides a referral.

## Assumptions

- The university will designate a defined set of approved PNW sources (webpages, PDFs, catalog pages, policy documents) as the authoritative knowledge base for grounding; content outside this approved set is out of scope for grounding answers.
- English-language interaction is assumed for this initial version; multilingual support is not addressed.
- Specific concurrent-usage or performance scaling targets were not provided in the interview notes and are deferred to the planning phase.
- This version does not access private, student-specific systems or records (e.g., an individual student's registration or financial aid account status); it is limited to general, approved, policy-level and procedural information.
- Keeping approved content current is a requirement (see FR-018), but the operational cadence for refreshing the source corpus was not specified and is left to the planning/implementation phase.
- This chatbot runs alongside PNW's existing chatbot, "Leo," as a separate, independent tool for this version; no replacement of or integration with Leo is in scope (see FR-025).
- The scope of this version is limited to currently registered undergraduate and graduate students, per stakeholder direction; no accommodations for faculty, staff, or prospective students are assumed.
