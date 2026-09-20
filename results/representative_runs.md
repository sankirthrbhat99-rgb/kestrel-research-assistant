# Kestrel Representative Runs

**Generated:** 2026-09-20T13:45:59  
**LLM mode:** OFFLINE (no API key configured)  
**LangSmith tracing:** DISABLED (set LANGCHAIN_TRACING_V2=true + LANGCHAIN_API_KEY)  
**Session ID:** `aa64556e-63de-4db9-9b4f-37d7b048ad97`  

> Note: Without an API key all answers use the deterministic offline fallback
> (keyword routing + chunk excerpt). Answers are prefixed `[OFFLINE]`.
> With a real key the LLM produces fluent, cited answers.

---

## Case 1: Single-hop

**Question:** How many Beacons can I create on the Growth plan?  
**Standalone rewrite:** How many Beacons can I create on the Growth plan?  
**Route:** `retrieval`  
**Verification verdict:** `supported`  
**Evidence chunks retrieved:** 6  
**Elapsed:** 22.42s  
**Trace URL:** None (LangSmith not configured)  

### Answer

```
[OFFLINE] Based on the knowledge base (no LLM configured):

• [spec-beacons:4] The number of Beacons a project may hold depends on its plan: Starter projects may create 5 Beacons, Growth projects 60, and Scale projects 500. All three condition modes and all four destination types are available on every plan; the plan limit is purely on count. A Beacon that uses a breakdown cou

• [onboarding-guide:4] Beacons are evaluated every 5 minutes and can notify Slack, email, a webhook, or PagerDuty. Leave anomaly mode for later: it needs 14 days of history before it can build a seasonal baseline, so it will not fire usefully on a brand-new project. Starter projects can have 5 Beacons, Growth 60, and Scal

• [rn-3-5:2] For example, you can now alert when daily sign-ups fall more than 20 percent compared with the previous day. Beacons continue to be evaluated every 5 minutes, and the per-project Beacon limits are unchanged: 5 on Starter, 60 on Growth and 500 on Scale. Destinations remain Slack, webhook and email. #

• [rn-3-5:1] The limit applies to request count, not event count, so batching multiple events into a single /v2/ingest call (up to 500 events or 2 MB) remains the most effective way to stay under the limit. Requests above the limit still receive HTTP 429 with a Retry-After header, and all official SDKs honour th
```

### Citations

- `spec-beacons:4` — Beacons: Alerting Specification
- `onboarding-guide:4` — Customer Onboarding Guide
- `rn-3-5:2` — Kestrel 3.5 Release Notes
- `rn-3-5:1` — Kestrel 3.5 Release Notes
- `pricing-plans:1` — Plans, Pricing and Limits
- `onboarding-guide:3` — Customer Onboarding Guide

### Top evidence chunks

- `spec-beacons:4` (score=0.7902): The number of Beacons a project may hold depends on its plan: Starter projects may create 5 Beacons, Growth projects 60, and Scale projects 500. All three condition modes and all four destination type…
- `onboarding-guide:4` (score=0.7421): Beacons are evaluated every 5 minutes and can notify Slack, email, a webhook, or PagerDuty. Leave anomaly mode for later: it needs 14 days of history before it can build a seasonal baseline, so it wil…
- `rn-3-5:2` (score=0.6908): For example, you can now alert when daily sign-ups fall more than 20 percent compared with the previous day. Beacons continue to be evaluated every 5 minutes, and the per-project Beacon limits are unc…

---

## Case 2: Multi-hop (follow-up with pronoun resolution)

**Question:** And on Scale?  
**Standalone rewrite:** And on Scale?  
**Route:** `retrieval`  
**Verification verdict:** `supported`  
**Evidence chunks retrieved:** 6  
**Elapsed:** 0.04s  
**Trace URL:** None (LangSmith not configured)  

### Answer

```
[OFFLINE] Based on the knowledge base (no LLM configured):

• [product-faq:5] Yes. Version 4.0.3 introduced an idempotency key on every synced row. Affected customers were contacted and given a cleanup script; the details are in the post-mortem for that incident. ## Product roadmap Is there a mobile app for viewing dashboards? Not planned for 2026. The web application is resp

• [pricing-plans:2] Scale pricing is custom and quoted by the sales team; there is no published list price. Scale is intended for 250,000,000 or more events per month, and overage terms are negotiated as part of the agreement. Scale includes unlimited seats. Queryable event retention is 25 months. The ingest API rate l

• [pricing-plans:4] Teams evaluating Kestrel usually start on a 14-day trial, which provides Growth features with a hard cap of 500,000 events. Starter suits small products with a handful of analysts who need funnels and cohorts and can live with 30 days of history. Growth is the typical choice for a product team that

• [spec-sdks-kql:3] It is available in the interface, through the Query API, and as the source for metric syncs in Warehouse Sync. A query names a source, applies filters, sets a time range, and aggregates. The canonical example: EVENTS WHERE name = 'checkout' SINCE 7d COUNT BY country The `SINCE` shorthand, added in r
```

### Citations

- `product-faq:5` — Product FAQ
- `pricing-plans:2` — Plans, Pricing and Limits
- `pricing-plans:4` — Plans, Pricing and Limits
- `spec-sdks-kql:3` — SDKs and Kestrel Query Language Reference
- `rn-4-0:1` — Kestrel 4.0 Release Notes
- `spec-beacons:2` — Beacons: Alerting Specification

### Top evidence chunks

- `product-faq:5` (score=0.6046): Yes. Version 4.0.3 introduced an idempotency key on every synced row. Affected customers were contacted and given a cleanup script; the details are in the post-mortem for that incident. ## Product roa…
- `pricing-plans:2` (score=0.6010): Scale pricing is custom and quoted by the sales team; there is no published list price. Scale is intended for 250,000,000 or more events per month, and overage terms are negotiated as part of the agre…
- `pricing-plans:4` (score=0.5918): Teams evaluating Kestrel usually start on a 14-day trial, which provides Growth features with a hard cap of 500,000 events. Starter suits small products with a handful of analysts who need funnels and…

### History used

- user: How many Beacons can I create on the Growth plan?…

---

## Case 3: Unsupported question

**Question:** What is the current stock price of NVIDIA?  
**Standalone rewrite:** What is the current stock price of NVIDIA?  
**Route:** `retrieval`  
**Verification verdict:** `supported`  
**Evidence chunks retrieved:** 6  
**Elapsed:** 0.04s  
**Trace URL:** None (LangSmith not configured)  

### Answer

```
[OFFLINE] Based on the knowledge base (no LLM configured):

• [pricing-plans:1] Growth costs $412 per month and includes 25,000,000 events per month. Overage is charged at $0.62 per 10,000 events. Growth includes 15 seats, and additional seats can be purchased. Queryable event retention is 13 months. The ingest API rate limit is 1,800 requests per second per project, and the qu

• [pricing-plans:0] Plans, Pricing and Limits This page is the canonical reference for Kestrel plans. It reflects pricing effective 2026-02-03. Kestrel is offered in three plans: Starter, Growth and Scale. All prices are in US dollars and are billed monthly unless an annual agreement is in place. See the Billing, Overa

• [pricing-plans:2] Scale pricing is custom and quoted by the sales team; there is no published list price. Scale is intended for 250,000,000 or more events per month, and overage terms are negotiated as part of the agreement. Scale includes unlimited seats. Queryable event retention is 25 months. The ingest API rate l

• [rn-4-0:2] Queries are now served by a new columnar engine called Osprey. Osprey reads the hot store for data up to 7 days old and Parquet files on object storage for older data, and caches results for 10 minutes. Most funnel and cohort reports run two to four times faster than on the previous engine. KQL limi
```

### Citations

- `pricing-plans:1` — Plans, Pricing and Limits
- `pricing-plans:0` — Plans, Pricing and Limits
- `pricing-plans:2` — Plans, Pricing and Limits
- `rn-4-0:2` — Kestrel 4.0 Release Notes
- `pm-inc-2025-07:5` — Post-mortem INC-2025-07: Ingest API 503s during 3.6 rollout
- `eng-ingest-architecture:5` — Ingest Pipeline Architecture

### Top evidence chunks

- `pricing-plans:1` (score=0.5739): Growth costs $412 per month and includes 25,000,000 events per month. Overage is charged at $0.62 per 10,000 events. Growth includes 15 seats, and additional seats can be purchased. Queryable event re…
- `pricing-plans:0` (score=0.5525): Plans, Pricing and Limits This page is the canonical reference for Kestrel plans. It reflects pricing effective 2026-02-03. Kestrel is offered in three plans: Starter, Growth and Scale. All prices are…
- `pricing-plans:2` (score=0.5483): Scale pricing is custom and quoted by the sales team; there is no published list price. Scale is intended for 250,000,000 or more events per month, and overage terms are negotiated as part of the agre…

---

## Limitation Note

All three runs above used the **deterministic offline fallback** because
no LLM API key was found in the environment or `.env` file.

To run with a real LLM:
1. Copy `.env.example` to `.env`
2. Set one of: `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`,
   or `KESTREL_LLM_API_KEY`
3. Re-run this script

To enable LangSmith tracing additionally set:
- `LANGCHAIN_TRACING_V2=true`
- `LANGCHAIN_API_KEY=<your key from smith.langchain.com>`
- `LANGCHAIN_PROJECT=kestrel-research-assistant`

## LangSmith Status

LangSmith tracing was **not active** during these runs.
All `Trace URL` fields are `None`.

When tracing is enabled, each run produces a URL like:
`https://smith.langchain.com/projects/kestrel-research-assistant/runs/<run_id>`

The URL is obtained by querying the LangSmith API after the graph completes —
it is never fabricated by string interpolation.
