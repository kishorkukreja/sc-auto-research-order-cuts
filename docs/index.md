# Documentation Index — Order Cut Optimisation via Autoagent

> Package generated on 2026-04-06 from conversation: "Autonomous Supply Chain Order Cut Optimisation PoC"
> Contains 8 files covering: framework selection, problem framing, use case design, system architecture, data model, build process, risks, and client presentation structure.

---

## Files in This Package

| File | What it contains | Audience |
|---|---|---|
| `index.md` | This file — package overview, dependency map, how to use | Everyone |
| `glossary.md` | All acronyms and domain terms (order cuts, fill rate, harness, Harbor, etc.) | Anyone reading the other files |
| `architecture.md` | Component diagram + data flow for the autoagent loop applied to supply chain | Engineers, solution architects |
| `tech-details.md` | Stack, install commands, verifier code skeleton, dataset schema, key technical decisions | Engineering / implementation team |
| `process.md` | Predict→Simulate→Optimize task loop, meta-agent optimisation loop, Day 1/Day 2 build plan | Delivery lead, engineer |
| `decisions.md` | 7 key decisions with rationale — framework, problem framing, demand signal, metric, data | All stakeholders |
| `data-model.md` | Entity definitions, field-level schema for all CSV files, key constraints | Engineer writing verifier and synthetic data |
| `requirements.md` | 15 functional requirements, 7 non-functional requirements, out-of-scope list | PM, engineer, client |
| `risks.md` | 10 risks with likelihood/impact/mitigation, 3 open issues, blocker register | Delivery lead, Kish |
| `slides-outline.md` | 10-slide client deck outline with speaker notes and visual guidance | Kish (presenting to client) |

---

## Dependency Map

```
glossary.md
  - standalone; consumed by all other files

architecture.md
  - references terms from glossary.md
  - component details elaborated in tech-details.md
  - design choices explained in decisions.md

tech-details.md
  - implements architecture from architecture.md
  - code snippets reference data schema from data-model.md
  - informed by decisions in decisions.md

process.md
  - describes execution of architecture.md components
  - Day 1/Day 2 plan delivers requirements.md items
  - risks from risks.md are mitigated in process steps

data-model.md
  - defines the entities that tech-details.md code operates on
  - constraints inform requirements.md FR-11 (capacity constraint)

decisions.md
  - rationale underpins all other files; read this first if context is unclear

requirements.md
  - derived from decisions.md and architecture.md
  - out-of-scope section bounds process.md

risks.md
  - risks reference architecture.md components and process.md steps
  - mitigations map to process.md Day 1 setup steps

slides-outline.md
  - synthesises all files into client-facing narrative
  - Slide 6 requires data from actual results.tsv (not yet available)
```

---

## What Each File Publishes / Consumes

| File | Publishes | Consumes |
|---|---|---|
| `glossary.md` | Term definitions | Nothing |
| `architecture.md` | Component names, data flow, integration points | `glossary.md` |
| `tech-details.md` | Stack, code, schemas, install commands | `architecture.md`, `glossary.md`, `data-model.md` |
| `process.md` | Workflow steps, decision points, Day 1/2 plan | `architecture.md`, `requirements.md` |
| `data-model.md` | Entity definitions, field schemas, constraints | `glossary.md` |
| `decisions.md` | Decision rationale, constraints, alternatives | `glossary.md` |
| `requirements.md` | Functional + non-functional requirements, out-of-scope | `decisions.md`, `architecture.md` |
| `risks.md` | Risk register, open issues, blockers | `architecture.md`, `process.md` |
| `slides-outline.md` | Client narrative, speaker notes, visual guidance | All other files |

---

## How to Use This Package

**Starting a new chat with this context?**
Paste `index.md` + `decisions.md` + `architecture.md`. That gives a fresh Claude instance enough to continue without re-explaining.

**Handing to an engineer?**
Point them to: `tech-details.md` → `data-model.md` → `process.md` (Day 1 steps). In that order.

**Preparing the client demo?**
Use `slides-outline.md` directly. Fill Slide 6 with actual results.tsv data after the overnight run.

**Picking up in a new chat after the overnight run?**
Paste `index.md` + `tech-details.md` + results.tsv content. Ask Claude to help interpret the iteration log and identify the key harness changes.

**UC2 (NPL Build Quantity) is not scaffolded.** The use case is fully designed in the original conversation (see Archive file). To build it, start a new chat with this index + the archive + "scaffold UC2."
