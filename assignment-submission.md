# Ad Compliance & Brand Safety — Submission

## Project Overview

An automated video ad compliance review system. Analyzes video content through a single API call via TwelveLabs Pegasus 1.2 or Amazon Bedrock, generating structured compliance reports.

**Live Demo:** [AWS Amplify Demo](https://main.d1mjnmpj9lc6js.amplifyapp.com/)

**Repository:** [github.com/rainny72/tlabs-ad-compliance](https://github.com/rainny72/tlabs-ad-compliance)

**Demo Video:** [ad-compliance-demo-2x.mp4](demo/ad-compliance-demo-2x.mp4)

---

## Table of Contents

1. [How Decisions Are Made](#1-how-decisions-are-made)
2. [Why Outputs Are Trustworthy](#2-why-outputs-are-trustworthy)
3. [How This Would Scale in a Real Ads System](#3-how-this-would-scale-in-a-real-ads-system)
4. [Appendix: Production Implementation Example](#appendix-production-implementation-example)

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

A three-step calibration mechanism is applied to reflect regional regulatory differences:

![Regional Severity Calibration](docs/generated-diagrams/Regional%20Severity%20Calibration.png)

**Step 1: Prompt Regional Context Injection** — `get_regional_prompt(region)` injects region-specific regulatory context into the prompt, enabling the model to recognize local regulations and make informed severity judgments. For example, East Asia + cannabis triggers a "ZERO TOLERANCE" directive.

**Step 2: Sub-rule Keyword Matching** — `_match_sub_rule()` matches violation evidence text against regional policy keywords. For example, "cannabis CBD" matches the `illegal_drugs` sub-rule in the East Asia policy (CRITICAL severity).

**Step 3: Severity Upgrade (upgrade only, never downgrade)** — `get_regional_severity()` upgrades severity when the matched sub-rule severity exceeds the model's severity. For example, if the model returns "high" but the East Asia sub-rule specifies "CRITICAL", the final severity is upgraded to CRITICAL.

Benefits of this approach:

- Step 1 ensures the model understands regional context, preventing detection gaps
- Step 2 applies precise severity through code-level sub-rule matching
- Step 3 provides a safety net that corrects the model's underestimation via regional policy

The Global region applies the strictest severity across all regions, ensuring that Global-safe content is safe in every market.

---

## 2. Why Outputs Are Trustworthy

Output trustworthiness is ensured through three pillars: consistent response generation, enforced structured output, and multi-layer verification mechanisms.

### 2.1 API Parameter Settings for Deterministic Output

| Parameter | Value | Purpose |
| --- | --- | --- |
| `temperature` | 0.1 | Minimizes non-deterministic results for the same video |
| `maxOutputTokens` | 4,096 | Pegasus maximum to prevent response truncation |
| `responseFormat` | JSON Schema | Enforces structured output, eliminates free-text |
| `stream` | false | Receives complete response in a single payload |

Temperature 0.1 is the most deterministic setting recommended by the TwelveLabs Temperature Tuning Guide for "law enforcement, reports" use cases. Compliance analysis must return identical results each time the same video is analyzed, prioritizing consistency over creativity. Additionally, the single API call design means non-determinism occurs only once, and cross-referencing across categories within a single context ensures consistent analysis results.

### 2.2 JSON Schema-Based Structured Output

The core principle from TwelveLabs' Structured Responses guide is applied:

> "The schema takes precedence over the prompt." — When the schema and prompt conflict, the schema wins.

Following this principle, `COMBINED_JSON_SCHEMA` enforces the output structure:

- All 6 policy categories are marked as `required` to prevent omissions
- `severity` is constrained to `enum [none|low|medium|high|critical]` to exclude arbitrary values
- `modality` is restricted to `enum [visual|speech|text_on_screen]` to clarify detection channels
- `relevance_score` is defined as `number (0.0-1.0)` to ensure quantitative evaluation

The schema and prompt output instructions are precisely aligned so the model follows the schema while reflecting the prompt's intent.

### 2.3 Consistency Through Prompt Engineering

Eight best practices from the TwelveLabs Prompt Engineering Guide are systematically applied:

**Role and Domain Context Setting** — Instead of a generic "content moderator," specific regulatory bodies are named (FTC, ASA, EU Cosmetics Regulation, MFDS, Yakujiho, NMPA) to activate the model's domain knowledge.

**Explicit Severity Classification Guide** — Rather than providing only the severity enum, the meaning of each level is clearly defined:

- `critical`: Content triggering immediate regulatory action or legal liability
- `high`: Clear policy violation requiring content removal
- `medium`: Borderline content requiring human review
- `low`: Minor concern with low regulatory risk

**Per-Category Severity Mapping** — Expected severity for each violation type is explicitly stated in the prompt (e.g., `"FDA approved" for cosmetics -> critical`), guiding the model to return consistent severity for identical violations.

### 2.4 Multi-Layer Verification Mechanisms

Model output trustworthiness is further verified at the code level:

**Truncation Detection** — The API response's `finishReason` field is checked; if `"length"`, a warning is raised that the response was truncated. Truncated responses may contain incomplete JSON and are immediately flagged.

**Regional Policy Safety Net** — Even if the model underestimates regional regulations, code-level `_match_sub_rule()` + `get_regional_severity()` matches evidence text against regional policy keywords and upgrades severity. This calibration is upgrade-only (never downgrade), preventing false negatives.

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

### 3.3 Tiered Processing Strategy

In real ad systems, not all content is treated equally. Processing is differentiated based on the decision result:

| Tier | Decision | Processing | Expected Ratio |
| --- | --- | --- | --- |
| Auto-approve | APPROVE (high confidence) | Automatic approval, no human review needed | 60-70% |
| Auto-block | BLOCK (CRITICAL severity) | Automatic block, advertiser notification | 5-10% |
| Human review | REVIEW | Routed to reviewer queue | 20-35% |

This tiered classification reduces the human reviewer burden by 60-70% while immediately blocking dangerous content.

### 3.4 Quality Control and Human-in-the-Loop

The system's core goal is to automate the Ads Compliance team's review process. To handle hundreds of thousands of ads per day, AI must perform first-pass decisions automatically and provide clear decision rationale. Human-in-the-Loop serves not as a full review but as a sampling-based audit to continuously verify and improve model quality.

![Human-in-the-Loop Quality Control](docs/generated-diagrams/Human-in-the-Loop%20Quality%20Control.png)

**Automated Decision + Decision Rationale** — For BLOCK/REVIEW decisions, the violation category, severity, and evidence (detection modality and specific content) are provided in a structured format. This fulfills the "Clear explanations for any blocked or reviewed ads" requirement, allowing advertisers to immediately see the reason for blocking/review.

**Sampling-Based Quality Audit** — A percentage of all decisions is randomly sampled for human auditor verification. False positive and false negative rates are measured, and when accuracy for a specific category falls below the threshold, prompts or regional policies are adjusted.

**Drift Detection** — Changes in decision distribution (APPROVE/REVIEW/BLOCK ratios) over time are tracked. Sudden distribution shifts indicate model behavior changes or new content types, signaling when policy adjustments are needed.

**Regional Policy Updates** — When regulations change, only policy files need to be updated for immediate effect. Extending code-based policy management (`shared/regional_policies/`) to a Policy DB + Admin UI would allow compliance officers to manage policies directly.

### 3.5 Serverless Architecture-Based Scaling Direction

Based on the current demo system's serverless structure, the architecture can evolve as follows for large-scale deployment:

![Video Analysis Sequence](docs/generated-diagrams/Video%20Analysis%20Sequence.png)

- **SQS Queue Introduction**: Instead of the Dispatcher directly invoking the Worker, messages are published to SQS for automatic backpressure control and retry handling
- **Reserved Concurrency**: Worker Lambda concurrent execution limits prevent exceeding Bedrock API call quotas
- **Dead Letter Queue**: Failed analyses are stored in a DLQ for reprocessing or manual review
- **Step Functions**: Complex workflows (analysis -> review routing -> notification) are orchestrated

The key advantage of this serverless architecture is automatic scaling up/down based on traffic with no infrastructure management burden, paying only for what is used.

---

## Appendix: Production Implementation Example

> A production deployment was implemented to validate the design thinking. For details on system architecture, security design, and CDK infrastructure, see the document below.

Detailed documentation: [Application Architecture](docs/application_architecture.md) — Includes dual deployment structure (Streamlit/Amplify), Dispatcher/Worker async pattern, CDK infrastructure stacks, Lambda function structure, and security design (Cognito authentication, S3 public access blocking, least privilege principle).

---
