# Ad Compliance & Brand Safety — Submission

## Project Overview

An automated video ad compliance review system. Analyzes video content through a single API call via TwelveLabs Pegasus 1.2, generating structured compliance reports. An alternative Amazon Bedrock backend is also supported (see [Appendix B](#appendix-b-dual-backend-architecture)).

**Live Demo:** [AWS Amplify Demo](https://main.d1mjnmpj9lc6js.amplifyapp.com/)

**Repository:** [github.com/rainny72/tlabs-ad-compliance](https://github.com/rainny72/tlabs-ad-compliance)

**Demo Video:** [ad-compliance-demo-2x.mp4](demo/ad-compliance-demo-2x.mp4)

---

## Table of Contents

1. [How Decisions Are Made](#1-how-decisions-are-made)
2. [Why Outputs Are Trustworthy](#2-why-outputs-are-trustworthy)
3. [How This Would Scale in a Real Ads System](#3-how-this-would-scale-in-a-real-ads-system)
4. [Appendix A: Production Implementation Example](#appendix-a-production-implementation-example)
5. [Appendix B: Dual Backend Architecture](#appendix-b-dual-backend-architecture)

---

## 1. How Decisions Are Made

### 1.1 Single API Call-Based Analysis

Video analysis is performed through a **single API call** to the TwelveLabs Pegasus 1.2 model. All of the following information is requested in one call:

| Requested Information | Description | Output Fields |
| --- | --- | --- |
| Campaign Relevance | Evaluates whether the product is properly advertised | `relevance_score`, `is_on_brief`, `product_visible` |
| Video Description | Fact-based summary of video content in 2-5 sentences | `description` |
| Policy Violations | Violation checks across 6 policy categories | `policy_violations` (per-category `severity`, `violations[]`) |

The key benefits of this design are that the video is processed only once, keeping API costs linear, and analyzing within a single context maintains consistency across categories.

### 1.2 Three-Axis Evaluation System

The AI model's response is evaluated across three independent axes:

![3-Axis Evaluation System](docs/generated-diagrams/3-Axis%20Evaluation%20System.png)

**Axis 1: Compliance** — Checks violations across 5 policy categories (`hate_harassment`, `profanity_explicit`, `drugs_illegal`, `unsafe_misleading_usage`, `medical_cosmetic_claims`). Each violation is assigned a severity (CRITICAL/HIGH/MEDIUM/LOW/NONE), and the highest severity among all detected violations determines the compliance result.

| Severity | Compliance Result |
| --- | --- |
| CRITICAL / HIGH | BLOCK |
| MEDIUM / LOW | REVIEW |
| NONE | PASS |

**Axis 2: Product Relevance** — Evaluates a combination of the AI model's returned `relevance_score` (0.0–1.0), `is_on_brief`, and `product_visible` flags. Scores below the 0.5 threshold are classified as BORDERLINE/OFF_BRIEF, triggering a REVIEW.

**Axis 3: Disclosure** — Checks for the presence of ad disclosure labels (`#ad`, `#sponsored`, etc.). Detection uses three methods: the model's explicit violation flag, severity-only detection (severity assigned without detailed violations), and keyword analysis of the video description text.

### 1.3 Final Decision Rules

Decision priority is BLOCK > REVIEW > APPROVE:

![Final Decision Logic](docs/generated-diagrams/Final%20Decision%20Logic.png)

Multiple REVIEW reasons are combined (e.g., "REVIEW: Product: OFF-BRIEF | Disclosure: MISSING").

### 1.4 Three-Step Regional Severity Calibration

A three-step calibration mechanism is applied to reflect regional regulatory differences. The key design insight is the separation of responsibilities: the AI model is responsible for detecting what is in the video (fact extraction), while pre-researched regional policy code is responsible for determining how severe it is in each region (regulatory judgment).

![Regional Severity Calibration](docs/generated-diagrams/Regional%20Severity%20Calibration.png)

**Step 1: Prompt Regional Context Injection (Guide)** — `get_regional_prompt(region)` injects region-specific regulatory context into the prompt, providing the model with severity classification guidance. For example, the East Asia context includes "ZERO TOLERANCE — ANY drug reference including cannabis, CBD → severity CRITICAL." This guides the model's severity assignment, but the system does not rely on the model following this guidance perfectly — Steps 2 and 3 act as a safety net.

**Step 2: Sub-rule Keyword Matching (Code-Level Detection)** — `_match_sub_rule()` matches the model's returned evidence text against pre-researched regional policy keywords defined in `shared/regional_policies/`. Each region's policy file contains sub-rules with specific keywords compiled from actual regulatory research (e.g., Korea MFDS, Japan Yakujiho, China NMPA). This is deterministic code-level matching — it does not depend on the model's regulatory knowledge.

**Step 3: Severity Upgrade (Safety Net, upgrade only, never downgrade)** — `get_regional_severity()` compares the matched sub-rule's severity with the model's returned severity. If the pre-researched policy severity is higher, it upgrades. This is strictly upgrade-only — the model's severity is never lowered, because in compliance it is safer to over-flag than to miss a violation.

**Concrete Example — Drug Reference Video in East Asia Region**

The video `06-mw-230-jp-stick-drugs.mp4` (a Japanese cosmetics ad containing cannabis/CBD ingredient references) demonstrates the three-step calibration in action:

| Step | What Happens | Input | Output |
| --- | --- | --- | --- |
| 1. Prompt Guide | East Asia context appended: "ZERO TOLERANCE... cannabis, CBD → CRITICAL" | `get_regional_prompt("east_asia")` | Model receives severity guidance |
| 2. Model Detection | Pegasus 1.2 analyzes video, detects drug-related content in speech/text | Video multimodal analysis | `drugs_illegal: severity "high"`, evidence: "cannabis CBD hemp extract ingredient" |
| 3a. Sub-rule Match | Evidence text matched against East Asia policy keywords | `_match_sub_rule(DRUGS_ILLEGAL, "cannabis CBD hemp extract ingredient", east_asia_policy)` | Matched sub-rule: `illegal_drugs` (keywords: "cannabis", "CBD", "大麻", "마약") |
| 3b. Severity Upgrade | Sub-rule severity CRITICAL > model severity HIGH → upgrade | `get_regional_severity(DRUGS_ILLEGAL, "illegal_drugs", east_asia_policy)` → CRITICAL | Final severity: **CRITICAL** (upgraded from HIGH) |

In this example, the model correctly detected the drug-related content (Step 2 — this is the model's strength as a video understanding model), but assigned `severity: high` instead of the East Asia-required CRITICAL. The code-level safety net (Steps 3a-3b) caught this underestimation and upgraded the severity based on pre-researched East Asia regulations where all drug references carry zero tolerance.

**Same Video, Different Regions — Severity Comparison:**

| Region | Model Returns | Sub-rule Match | Policy Severity | Final Severity | Decision |
| --- | --- | --- | --- | --- | --- |
| North America | `high` | `cannabis_cbd` | HIGH | HIGH (no change) | BLOCK |
| Western Europe | `high` | `cannabis_cbd` | HIGH | HIGH (no change) | BLOCK |
| East Asia | `high` | `illegal_drugs` | CRITICAL | **CRITICAL** (upgraded) | BLOCK |
| Global | `high` | strictest across all | CRITICAL | **CRITICAL** (upgraded) | BLOCK |

This demonstrates the core value of the calibration mechanism: the same model output produces different final severities depending on the region, reflecting actual regulatory differences. The model only needs to detect the content accurately — the regional severity judgment is handled by pre-researched policy code.

**Why This Design — Model Detection + Code-Level Regulation:**

- Pegasus 1.2 is a video understanding model optimized for multimodal content analysis (visual, speech, text). It excels at detecting what is in the video — drug references, profanity, unsafe usage, etc.
- However, mapping detected content to region-specific regulatory severity requires domain expertise that a video understanding model may not reliably possess (e.g., "cannabis is HIGH in North America but CRITICAL in East Asia").
- The three-step design leverages each component's strength: the model detects content (its core capability), the prompt provides severity guidance (best-effort), and the code enforces pre-researched regional regulations (guaranteed accuracy).
- The upgrade-only constraint ensures that even if the model overestimates severity (e.g., returns CRITICAL when the region only requires HIGH), the system preserves the model's judgment — erring on the side of caution.

The Global region applies `get_strictest_severity()` across all regional policies, ensuring that Global-safe content is safe in every market.

---

## 2. Why Outputs Are Trustworthy

Output trustworthiness is ensured through three pillars: consistent response generation, enforced structured output, and multi-layer verification mechanisms.

### 2.1 API Parameter Settings for Deterministic Output

The TwelveLabs Analyze API is configured with parameters optimized for compliance analysis:

| Parameter | Value | Purpose |
| --- | --- | --- |
| `temperature` | `0.1` | Most deterministic setting per TwelveLabs Temperature Tuning Guide |
| `max_tokens` | `4096` | Pegasus maximum to prevent truncation |
| `response_format` | `{type: "json_schema", json_schema: ...}` | Enforces structured output |
| `stream` | `false` | Complete response in single payload |

The `temperature: 0.1` setting is the most deterministic option recommended by the TwelveLabs Temperature Tuning Guide for "law enforcement, reports" use cases. Compliance analysis requires the same video to produce reproducible results, making minimal non-determinism essential. The single API call design means non-determinism occurs only once, and cross-referencing across categories within a single context ensures consistent analysis results.

### 2.2 JSON Schema-Based Structured Output

The core principle from TwelveLabs' Structured Responses guide is applied:

> "The schema takes precedence over the prompt." — When the schema and prompt conflict, the schema wins.

Following this principle, `COMBINED_JSON_SCHEMA` enforces the output structure:

- All 6 policy categories are marked as `required` to prevent omissions
- `severity` is constrained to `enum [none|low|medium|high|critical]` to exclude arbitrary values
- `modality` is restricted to `enum [visual|speech|text_on_screen]` to clarify detection channels
- `relevance_score` is defined as `number (0.0-1.0)` to ensure quantitative evaluation

The schema and prompt output instructions are precisely aligned so the model follows the schema while reflecting the prompt's intent.

### 2.3 Prompt Architecture — COMBINED_PROMPT Design

The system uses a single unified prompt (`COMBINED_PROMPT`) that instructs the model to perform all analysis tasks in one pass. The prompt is composed of four structural layers, each serving a distinct purpose.

**Layer 1: Role Definition and Severity Judgment Guide**

The prompt opens by assigning the model a specific expert role with named regulatory bodies:

> "You are an expert ad compliance reviewer specializing in global beauty and cosmetics advertising regulations, including FTC (US), ASA (UK), EU Cosmetics Regulation, and East Asian standards (Korea MFDS, Japan Yakujiho, China NMPA)."

Instead of a generic "content moderator," naming specific regulatory bodies provides the model with a structured severity judgment framework. Pegasus 1.2 is a video understanding model optimized for multimodal analysis (visual, speech, text), not a general-purpose LLM with deep regulatory knowledge. Therefore, the prompt's regulatory references serve as severity classification guides rather than activating pre-existing domain expertise. The system does not rely solely on the model's regulatory understanding — the three-step calibration mechanism (Section 1.4) ensures accurate regional compliance through code-level sub-rule matching (`_match_sub_rule()`) and severity upgrade (`get_regional_severity()`), which act as a safety net for any gaps in the model's domain knowledge.

**Layer 2: Multi-Modality Analysis Instruction**

The prompt explicitly requires independent analysis of all three modalities before making any judgment:

> "Analyze ALL three modalities independently before making any judgment:
> 1. VISUAL: actions, products, text overlays, subtitles
> 2. SPEECH/AUDIO: transcribe ALL spoken words verbatim in any language
> 3. TEXT ON SCREEN: all overlays, captions, hashtags, watermarks
>
> Do NOT assume a video is clean based on visuals alone. Violations often appear only in audio or text."

This instruction is critical because compliance violations frequently appear in only one modality — profanity in speech, drug references in on-screen text, or unsafe usage in visual content. Without this directive, the model may default to visual-only analysis.

**Layer 3: Three Output Sections with Explicit Instructions**

The prompt defines three output sections that map directly to the JSON Schema:

1. **Campaign Relevance** — Instructs the model to score relevance (0.0–1.0), determine if the product is on-brief, and check product visibility. These fields feed directly into Axis 2 (Product Relevance) of the evaluation system.

2. **Video Description** — Requires a factual 2-5 sentence summary with verbatim transcription of all spoken dialogue (original language + English translation), all on-screen text, and any offensive language exactly as spoken. The description serves dual purposes: it provides human-readable context for reviewers, and it feeds into the keyword-based disclosure detection path (Axis 3).

3. **Policy Violations** — Defines 6 categories with per-category severity mapping. Each category includes specific examples and expected severity levels:

| Category | Key Severity Mappings in Prompt |
| --- | --- |
| `hate_harassment` | Racial slurs → critical, skin tone superiority → critical, body shaming → high |
| `profanity_explicit` | Strong profanity (F-word, 씨발, くそ, 他妈的) → critical, mild → medium |
| `drugs_illegal` | Illegal drug use → critical, cannabis/CBD → high (critical in East Asia), substance-derived cosmetic ingredients → high |
| `unsafe_misleading_usage` | Unsafe application → high, misleading before/after → high |
| `medical_cosmetic_claims` | Drug claims ("cures", "treats") → critical, "FDA approved" for cosmetics → critical, absolute claims → high |
| `disclosure` | No disclosure at all → medium, buried disclosure → low |

The per-category severity mapping is essential for consistency — it ensures the model returns the same severity for identical violations across different videos, rather than making ad-hoc judgments.

**Layer 4: Regional Context Injection (Dynamic)**

The base `COMBINED_PROMPT` is extended at runtime by `get_regional_prompt(region)`, which appends region-specific regulatory context from `REGIONAL_PROMPT_CONTEXT`. Four regional contexts are defined:

| Region | Key Directives | Regulatory Bodies |
| --- | --- | --- |
| `north_america` | CBD → HIGH, "FDA approved" for cosmetics → CRITICAL, FTC disclosure rules | FTC, FDA, MoCRA |
| `western_europe` | ASA strictest disclosure rules ("#sponsored" is inadequate → HIGH), retouched before/after banned | ASA, ARPP, EU Cosmetics Reg |
| `east_asia` | ZERO TOLERANCE for any drug reference → CRITICAL, mild profanity → HIGH, absolute claims → CRITICAL | Korea MFDS, Japan Yakujiho, China NMPA |
| `global` | No additional context (base prompt applies strictest defaults) | — |

The regional context is appended as a `## REGIONAL CONTEXT` section, not replacing the base prompt. This means the model always has the full base knowledge plus region-specific overrides. For example, the East Asia context explicitly states "ANY drug reference including cannabis, CBD, marijuana → severity CRITICAL (not high)" — overriding the base prompt's default of HIGH for cannabis.

**API Prompt Token Limit and Design Constraint**

The TwelveLabs Analyze API (`POST /v1.3/analyze`) and Amazon Bedrock `invoke_model` both impose a maximum prompt length of 2,000 tokens (`inputPrompt` / `prompt` parameter). This constraint directly shaped the prompt design — all 6 policy categories, severity mappings, multi-modality instructions, and output format specifications must fit within this budget.

| Prompt Variant | Estimated Tokens | Budget Usage |
| --- | --- | --- |
| Global (base only) | ~914 | 46% |
| North America | ~1,088 | 54% |
| Western Europe | ~1,085 | 54% |
| East Asia (longest) | ~1,137 | 57% |

The prompt was designed following the [TwelveLabs Prompt Engineering Guide](https://docs.twelvelabs.io/docs/prompt-engineering) best practices: role definition with specific context, explicit output format specification, concise and specific instructions, and temperature tuning for deterministic compliance output. The per-category severity mappings are kept concise (arrow notation: `"FDA approved" for cosmetics -> critical`) rather than verbose explanations, specifically to stay within the 2,000-token budget while maximizing the information density delivered to the model.

**Why This Prompt Structure Works**

The four-layer design ensures: (1) the model receives structured severity judgment guidance through named regulatory contexts, (2) it analyzes all modalities rather than defaulting to visual-only, (3) it produces consistent severity assignments through explicit per-category mapping, and (4) it respects regional regulatory differences through dynamic context injection. The prompt and JSON Schema are precisely aligned — the schema enforces structure while the prompt provides the judgment criteria. Importantly, the system does not depend on the model's inherent regulatory knowledge — the prompt guides severity classification, while code-level calibration (Section 1.4) guarantees accurate regional enforcement.

### 2.4 Multi-Layer Verification Mechanisms

Model output trustworthiness is further verified at the code level:

**Truncation Detection** — The API response's `finishReason` field is checked; if `"length"`, a warning is raised that the response was truncated. Truncated responses may contain incomplete JSON and are immediately flagged.

**Regional Policy Safety Net** — Even if the model underestimates regional regulations (e.g., returning `severity: high` for cannabis in East Asia instead of CRITICAL), code-level `_match_sub_rule()` + `get_regional_severity()` matches evidence text against pre-researched regional policy keywords and upgrades severity. This calibration is upgrade-only (never downgrade), preventing false negatives. The regional policies in `shared/regional_policies/` are compiled from actual regulatory research (Korea MFDS, Japan Yakujiho, China NMPA, FTC, ASA, EU Cosmetics Regulation), ensuring that the system's regulatory accuracy does not depend on the model's domain knowledge.

**Multi-Path Disclosure Detection** — Disclosure detection does not rely on a single method but uses three paths:

1. The model's explicit violation flag
2. Severity-only detection (severity assigned without detailed violations)
3. Keyword analysis of the video description text ("no disclosure", "missing #ad", etc.)

---

## 3. How This Would Scale in a Real Ads System

### 3.1 Scale Requirements of Real Ad Systems

Large ad platforms must process hundreds of thousands to millions of ad content items per day. This creates the following scaling requirements:

| Requirement | Current System | Production Scale |
| --- | --- | --- |
| Daily throughput | Tens of items (demo) | Hundreds of thousands to millions |
| Response time | 10-60s per item | SLA-based (tiered by priority) |
| Regional policies | 4 regions (code) | Dozens of regions (Policy DB) |
| Review workflow | Dashboard display | Tiered auto-routing |
| Monitoring | CloudWatch Logs | Real-time metrics + drift detection |

### 3.2 Scaling Architecture Design

The current system's core design principles naturally support large-scale expansion:

**Single API Call = Linear Cost Scaling** — All analysis is completed in one call per video, so when throughput increases 10x, cost increases only 10x. This is 8x more cost-efficient compared to individual calls per category (8 calls).

**Stateless Workers = Horizontal Scaling** — Workers hold no state, so throughput can be scaled simply by increasing the number of concurrent executions. There is zero coordination overhead between workers.

**Policy as Code = No Model Retraining Required** — When new regions or regulations are added, only policy files need to be added. There is no need to retrain or redeploy the AI model.

![Production Architecture](docs/generated-diagrams/Production%20Architecture.png)

### 3.3 Fully Automated Decision Pipeline

Every video submitted to the system receives a fully automated decision — APPROVE, REVIEW, or BLOCK — with structured evidence. No human intervention is required in the decision pipeline itself.

| Decision | Automated Action | Evidence Provided |
| --- | --- | --- |
| APPROVE | Cleared for promotion automatically | All three axes passed |
| REVIEW | Flagged with specific concerns and evidence | Violation category, severity, modality, timestamps |
| BLOCK | Rejected automatically with detailed reasoning | Critical/high severity violations with exact evidence |

All three outcomes are produced by the system automatically. The REVIEW decision is not a fallback for uncertainty — it is an intentional design choice where the system identifies borderline cases (e.g., MEDIUM severity, product BORDERLINE, disclosure MISSING) and provides the precise reasons and evidence. This fulfills the requirement for "clear explanations for any blocked or reviewed ads."

### 3.4 Continuous Quality Improvement

To maintain and improve automated decision quality at scale, the system supports feedback loops that do not interrupt the automated pipeline:

![Human-in-the-Loop Quality Control](docs/generated-diagrams/Human-in-the-Loop%20Quality%20Control.png)

**Structured Evidence for Every Decision** — Every APPROVE, REVIEW, and BLOCK decision includes the violation category, severity, detection modality, and specific evidence in a structured format. This makes decisions explainable and auditable without requiring additional analysis.

**Sampling-Based Accuracy Measurement** — A percentage of automated decisions can be randomly sampled for verification. False positive and false negative rates are measured per category, and when accuracy drops below a threshold, prompts or regional policies are adjusted — improving future automated decisions.

**Drift Detection** — Changes in decision distribution (APPROVE/REVIEW/BLOCK ratios) over time are tracked. Sudden distribution shifts signal model behavior changes or new content types, triggering policy adjustments.

**Policy Updates Without Retraining** — When regulations change, only policy files in `shared/regional_policies/` need to be updated for immediate effect. Extending this to a Policy DB + Admin UI would allow compliance officers to manage policies directly, with changes taking effect on the next video processed.

### 3.5 Serverless Architecture-Based Scaling Direction

Based on the current demo system's serverless structure, the architecture can evolve as follows for large-scale deployment:

![Video Analysis Sequence](docs/generated-diagrams/Video%20Analysis%20Sequence.png)

- **SQS Queue Introduction**: Instead of the Dispatcher directly invoking the Worker, messages are published to SQS for automatic backpressure control and retry handling
- **Reserved Concurrency**: Worker Lambda concurrent execution limits prevent exceeding Bedrock API call quotas
- **Dead Letter Queue**: Failed analyses are stored in a DLQ for reprocessing or manual review
- **Step Functions**: Complex workflows (analysis -> review routing -> notification) are orchestrated

The key advantage of this serverless architecture is automatic scaling up/down based on traffic with no infrastructure management burden, paying only for what is used.

---

## Appendix A: Production Implementation Example

> A production deployment was implemented to validate the design thinking. For details on system architecture, security design, and CDK infrastructure, see the document below.

Detailed documentation: [Application Architecture](docs/application_architecture.md) — Includes dual deployment structure (Streamlit/Amplify), Dispatcher/Worker async pattern, CDK infrastructure stacks, Lambda function structure, and security design (Cognito authentication, S3 public access blocking, least privilege principle).

---

## Appendix B: Dual Backend Architecture

The system supports two interchangeable backends for video analysis. Users can switch between them via the Settings page, and the Worker Lambda routes to the selected backend at runtime. Both backends share the same prompt (`get_regional_prompt(region)`), JSON schema (`COMBINED_JSON_SCHEMA`), and decision engine (`make_split_decision`), ensuring identical evaluation logic regardless of which backend processes the video.

| Aspect | TwelveLabs Direct API | Amazon Bedrock |
| --- | --- | --- |
| Endpoint | `POST /v1.3/analyze` | `invoke_model` (bedrock-runtime) |
| Model | Pegasus 1.2 (hosted by TwelveLabs) | `twelvelabs.pegasus-1-2-v1:0` (AWS Marketplace) |
| Authentication | API Key (`x-api-key` header) | AWS IAM (Signature V4) |
| Video Input | Indexed asset (upload → index → analyze) | Base64 or S3 URI |
| Max Video Size | Managed by TwelveLabs indexing pipeline | 25 MB (base64) / 2 GB (S3 URI) |
| Temperature | `0.1` | `0.1` |
| Best For | TwelveLabs-native workflows, rapid prototyping | Enterprise AWS environments, IAM-governed access |

**TwelveLabs Direct API Pipeline (4 Steps):**

1. **Index Creation** — `POST /v1.3/indexes` creates a named index (`ad-compliance-analysis`) with `pegasus1.2` model and `["visual", "audio"]` modalities.
2. **Asset Upload** — `POST /v1.3/assets` uploads the video via multipart/form-data. Polls until `"ready"`.
3. **Asset Indexing** — `POST /v1.3/indexes/{index_id}/indexed-assets` links the asset to the index. Polls until `"ready"`.
4. **Analysis** — `POST /v1.3/analyze` sends the prompt, JSON schema, and parameters. This single call produces the structured compliance report.

**Amazon Bedrock Pipeline (Single Step):** Bedrock simplifies to a single `invoke_model` call. The video is passed as base64 (≤25 MB) or S3 URI (≤2 GB). No pre-indexing required.

---
