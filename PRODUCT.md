# Product

## Register

product

## Users

**Candidates** — job seekers checking resume fitness before applying. They open this mid job-hunt, often stressed, wanting a clear signal: is this resume ready? They care about specifics, not encouragement.

**Recruiters** — in-house or agency hiring managers screening applicants for active roles. They are in workflow mode: posting jobs, reviewing ranked candidates, tracking progress. Time is the constraint.

## Product Purpose

An AI-powered talent platform with two sides: candidates check their resume against any job posting URL for a detailed ATS score breakdown, and recruiters post roles and get AI-ranked candidate shortlists. The system uses a tiered LLM routing chain (ApeKey.ai → Claude → Groq) for scoring.

Success: a candidate uploads a resume, pastes a job URL, and knows in 20 seconds exactly which keywords to add and what to fix. A recruiter posts a role and within minutes sees a ranked list with justifications.

## Brand Personality

Precise · Trustworthy · Efficient

Voice: direct, specific, data-grounded. Never vague. No "supercharge your career." Instead: "You matched 12 of 18 required keywords. Add Docker and TypeScript to your Skills section."

Tone: confident and honest. If a resume scores 38/100, the interface says so clearly and explains why — not softened with false positivity.

## Anti-references

- **Generic HR SaaS (Greenhouse/Workday/BambooHR)** — dated enterprise UX, gray sidebars, boring tables, no personality, no hierarchy. Feels like 2015 IT procurement.
- **AI startup cream/beige** — the warm-tinted white + indigo-on-cream aesthetic that every 2024-2025 AI tool copies. Immediately reads as AI-generated.
- **Dashboard clichés** — hero-metric template with big gradient KPI numbers, identical icon-grid stat cards, hollow donut charts for everything.
- **LinkedIn** — social-feed energy, clutter, connection spam, infinite scroll. This is a focused tool, not a social network.

## Design Principles

1. **Data earns the trust** — show numbers, breakdowns, and justifications. Don't soften scores. A precise negative is more useful than a vague positive.
2. **The interface disappears into the task** — Linear-style: the tool gets out of the way. Sidebars, tables, forms should feel familiar and fast, not decorated.
3. **One thing per screen** — each page has one primary action. Don't show the recruiter's analytics AND candidate upload on the same dashboard.
4. **Empty states teach, not shrug** — new users see clear next actions, not "nothing here yet." The empty state is an onboarding touchpoint.
5. **Consistency over surprise** — same button shapes, same form vocabulary, same icon weight across both candidate and recruiter surfaces. Delight is in the data, not the decoration.

## Accessibility & Inclusion

- WCAG 2.1 AA minimum.
- All form inputs labelled; all interactive elements keyboard-navigable.
- Avoid color-only encoding for scores — pair color with text labels.
- Respect `prefers-reduced-motion` for all transitions.
- No PDFs as primary content.
