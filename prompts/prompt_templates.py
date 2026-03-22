"""Prompt templates for TwelveLabs analyze API calls."""

RELEVANCE_PROMPT = """You are an ad compliance reviewer for a global makeup and cosmetics brand campaign.

Evaluate whether this video is suitable as a paid ad for a beauty/cosmetics campaign.

Check the following:
1. Does a makeup, skincare, or beauty product appear in the video?
2. Is the product actually used, demonstrated, or reviewed?
3. Is this beauty/cosmetics content, or is it unrelated (cooking, gaming, etc.)?
4. Is the brand or product name mentioned or visible?

Return your evaluation as JSON with these fields:
- relevance_score: float 0.0 to 1.0 (1.0 = perfectly on-brief)
- is_on_brief: boolean
- product_visible: boolean
- reasoning: string explaining your assessment
"""

DESCRIPTION_PROMPT = """Summarize this video in 2 to 5 sentences for an ad compliance review report.

Include:
- Who appears and what they are doing
- What products are shown or used (brand names if visible)
- Key visual scenes and actions
- Any notable audio content (speech, music)

Write as a factual, objective description.
"""

POLICY_PROMPTS = {
    "hate_harassment": """You are an ad compliance reviewer. Analyze this video for:
- Hate speech, racial slurs, or ethnic derogatory language
- Gender-based discrimination or harmful gender stereotypes
- Body shaming, appearance mockery, or disability mockery
- Skin tone superiority claims (e.g., implying lighter skin is "better")
- Bullying or harassment of any kind

For each violation found, provide:
- description: what was said or shown
- timestamp_start: approximate start time in seconds
- timestamp_end: approximate end time in seconds
- modality: "visual", "speech", or "text_on_screen"
- evidence: specific quote or visual description
- severity: "critical", "high", "medium", or "low"

Return JSON with: has_violation (bool), severity (worst found), violations (array).
If no violations, return has_violation: false, severity: "none", violations: [].
""",

    "profanity_explicit": """You are an ad compliance reviewer. Analyze this video for:
- Strong profanity (F-word, C-word, and equivalents in any language)
- Mild profanity (damn, hell, crap, ass, and equivalents)
- Sexually explicit or suggestive content
- Vulgar or crude language
- Profanity in any language including Korean, Japanese, Chinese

Classify severity:
- "critical": strong profanity, sexual content
- "high": moderate profanity, suggestive content
- "medium": mild profanity (damn, hell)
- "low": borderline expressions

For each instance, provide timestamp, modality, evidence, and the exact words used.
Return JSON with: has_violation (bool), severity (worst found), violations (array).
""",

    "drugs_illegal": """You are an ad compliance reviewer. Analyze this video for:
- Illegal drug use, drug paraphernalia, or drug references
- Cannabis/marijuana/CBD product usage or promotion
- Cosmetic or skincare products containing ingredients derived from controlled or regulated substances. Identify ALL product ingredient names spoken or shown in ANY language, then evaluate whether each ingredient originates from a controlled or regulated drug plant or substance. Cosmetic use does NOT exempt a product from drug compliance.
- Prescription drug misuse or promotion
- Excessive alcohol consumption or alcohol glorification
- Any illegal behavior

For each violation, provide timestamp, modality, and evidence.
Return JSON with: has_violation (bool), severity (worst found), violations (array).
""",

    "unsafe_misleading_usage": """You are an ad compliance reviewer for a cosmetics brand. Analyze this video for:
- Unsafe product application (e.g., lip products used near eyes, products on broken skin)
- DIY cosmetics without safety warnings
- Misleading before/after comparisons with obvious digital retouching
- Products containing banned or restricted ingredients
- Missing safety disclaimers for potentially hazardous use
- Exaggerated visual manipulation (skin smoothing, reshaping)

For each violation, provide timestamp, modality, and evidence.
Return JSON with: has_violation (bool), severity (worst found), violations (array).
""",

    "medical_cosmetic_claims": """You are an ad compliance reviewer. Analyze this video for:
- Drug claims: "cures", "treats", "heals", "removes wrinkles"
- False regulatory claims: "FDA approved" for cosmetics
- Unsubstantiated efficacy: "clinically proven" without citing studies
- Absolute claims: "100% effective", "guaranteed results", "immediate effect"
- Medical terminology used for cosmetics
- "Cosmeceutical" or "medicated cosmetic" claims
- Whitening/brightening claims that exceed cosmetic scope
- "100% natural/organic" without certification

For each claim found, provide the exact quote, timestamp, and severity.
Return JSON with: has_violation (bool), severity (worst found), violations (array).
""",

    "disclosure": """You are an ad compliance reviewer. Analyze this video for advertising disclosure compliance.

IMPORTANT: First determine if ANY form of ad disclosure IS present. Acceptable disclosures include:
- "#ad", "#AD", "Ad", "Advertisement", "Paid partnership", "Sponsored"
- "#광고", "유료광고", "협찬" (Korean)
- "#PR", "広告", "プロモーション" (Japanese)
- "广告", "推广" (Chinese)
- Any text overlay, caption, hashtag, or verbal statement identifying the content as advertising
- Platform-native "Paid partnership" labels or similar built-in disclosure features

If ANY acceptable disclosure is found anywhere in the video (text, speech, overlay), return:
has_violation: false, severity: "none", violations: []

Only flag violations when disclosure is genuinely absent:
- No ad disclosure of any kind visible or spoken throughout the entire video
- Disclosure present but buried (only mid-video, small text, <2 seconds)
- Inadequate labels under strict UK ASA rules ("#sponsored", "#gifted" are NOT sufficient in UK)

For each issue, provide timestamp and evidence.
Return JSON with: has_violation (bool), severity (worst found), violations (array).
""",
}

VIOLATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "has_violation": {"type": "boolean"},
        "severity": {
            "type": "string",
            "enum": ["none", "low", "medium", "high", "critical"],
        },
        "violations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "timestamp_start": {"type": "number"},
                    "timestamp_end": {"type": "number"},
                    "modality": {
                        "type": "string",
                        "enum": ["visual", "speech", "text_on_screen"],
                    },
                    "evidence": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                },
                "required": ["description", "timestamp_start", "timestamp_end", "modality", "evidence"],
            },
        },
    },
    "required": ["has_violation", "severity", "violations"],
}

RELEVANCE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "relevance_score": {"type": "number"},
        "is_on_brief": {"type": "boolean"},
        "product_visible": {"type": "boolean"},
        "reasoning": {"type": "string"},
    },
    "required": ["relevance_score", "is_on_brief", "reasoning"],
}


# --- Combined single-call prompt (saves API quota) ---

COMBINED_PROMPT = """You are an expert ad compliance reviewer specializing in global beauty and cosmetics advertising regulations, including FTC (US), ASA (UK), EU Cosmetics Regulation, and East Asian standards (Korea MFDS, Japan Yakujiho, China NMPA).

Your task: analyze this video ad and return a structured JSON assessment covering campaign relevance, video description, and policy violations across 6 categories.

Analyze ALL three modalities independently before making any judgment:
1. VISUAL: actions, products, text overlays, subtitles
2. SPEECH/AUDIO: transcribe ALL spoken words verbatim in any language
3. TEXT ON SCREEN: all overlays, captions, hashtags, watermarks

Do NOT assume a video is clean based on visuals alone. Violations often appear only in audio or text.

## 1. CAMPAIGN RELEVANCE
- relevance_score: 0.0 (completely unrelated) to 1.0 (perfectly on-brief)
- is_on_brief: true only if a beauty/cosmetics product is clearly featured and used
- product_visible: true if a specific product is visually identifiable

## 2. VIDEO DESCRIPTION
Write a factual summary (2-5 sentences) covering: who appears, products shown/used, key scenes, and audio content.
CRITICAL: You MUST carefully read and report ALL on-screen text visible in the video, including hashtags (#ad, #sponsored, etc.), watermarks, captions, subtitles, overlay text, and any text graphics. Scan every frame for text.
Include verbatim transcription of all spoken dialogue (original language + English translation), all on-screen text, and any offensive/inappropriate language exactly as spoken.

## 3. POLICY VIOLATIONS
For each of the 6 categories: set has_violation and severity (worst found). If none, return has_violation: false, severity: "none", violations: [].

### Severity guide:
- critical: immediate regulatory action or legal liability
- high: clear policy breach requiring content removal
- medium: borderline, requires human review
- low: minor concern

### hate_harassment
- Hate speech, racial slurs, ethnic derogatory language (any language) -> critical
- Gender discrimination, harmful stereotypes -> high
- Body shaming, appearance mockery -> high
- Skin tone superiority claims -> critical (cosmetics-specific)
- Derogatory terms about race, ethnicity, nationality, religion -> critical

### profanity_explicit
- Strong profanity: F-word, C-word, equivalents in any language -> critical
  Including: 씨발, 개새끼 (KR), くそ, ファック (JP), 他妈的, 操 (CN)
- Mild profanity: damn, hell, crap, ass -> medium
- Sexually explicit content -> critical
- Sexually suggestive content -> high

### drugs_illegal
IMPORTANT: Cosmetic or skincare products containing ingredients derived from controlled or regulated substances are NOT exempt from drug compliance. If a product's ingredient originates from a regulated drug plant or substance, it MUST be flagged under drugs_illegal regardless of its cosmetic context.
- Illegal drug use, paraphernalia, or references -> critical
- Cannabis/marijuana references -> critical
- CBD-containing products (CBD cream, CBD oil, CBD serum, cannabidiol) -> SEVERITY DEPENDS ON REGION. You MUST check the REGIONAL CONTEXT section below and use the exact severity specified there. Do NOT default to a fixed severity.
- Hemp products WITHOUT CBD (hemp seed oil, hemp cream without CBD mention) -> SEVERITY DEPENDS ON REGION. You MUST check the REGIONAL CONTEXT section below and use the exact severity specified there. Do NOT default to a fixed severity.
  CRITICAL: Distinguish CBD-containing hemp products from CBD-free hemp products. If "CBD" or "cannabidiol" is explicitly mentioned, classify as CBD product. If only "hemp" without CBD context, classify as hemp cosmetic. These two categories have DIFFERENT severities.
- Regulated substance-derived ingredients in cosmetics: identify ALL product ingredient names spoken or shown in ANY language, then evaluate whether each ingredient is derived from a controlled or regulated substance. Flag if yes -> high
- Prescription drug misuse -> high
- Excessive alcohol glorification -> medium

### unsafe_misleading_usage
- Unsafe product application (near eyes, on broken skin) -> high
- Misleading before/after with digital retouching -> high
- DIY cosmetics without safety warnings -> medium
- Verbal instructions for unsafe use -> high

### medical_cosmetic_claims
- Drug claims: "cures", "treats", "heals", "removes wrinkles" -> critical
- "FDA approved" for cosmetics -> critical
- "Clinically proven" without studies -> high
- Absolute claims: "100% effective", "guaranteed results" -> high
- "Cosmeceutical" or "medicated cosmetic" -> high
- "100% natural/organic" without certification -> medium
- Whitening claims exceeding cosmetic scope -> high

### disclosure
CRITICAL: Before flagging a disclosure violation, you MUST carefully examine ALL on-screen text, overlays, hashtags, captions, and watermarks throughout EVERY frame of the video. Disclosure hashtags like "#ad" are often small or appear briefly — scan thoroughly.
Acceptable disclosures: "#ad", "Ad", "Advertisement", "Paid partnership", "Sponsored", "#광고", "유료광고", "협찬", "#PR", "広告", "广告", "推广", or equivalent in any language.
If ANY disclosure is found anywhere in the video (text, speech, overlay), set has_violation: false.
Flag only when genuinely absent:
- No disclosure at all -> medium
- Buried disclosure (mid-video, small text, <2s) -> low

## OUTPUT RULES
For each violation provide: description (English), timestamp_start, timestamp_end, modality ("visual"/"speech"/"text_on_screen"), evidence (English), evidence_original (non-English source text, omit if English), severity.
"""

# --- Regional context to be appended to COMBINED_PROMPT ---

REGIONAL_PROMPT_CONTEXT = {
    "global": "",
    "north_america": """
## REGIONAL CONTEXT: North America (FTC / FDA / MoCRA)
You are evaluating this video for the North American market. Apply these region-specific rules.
CRITICAL: The severity values below are MANDATORY for this region. You MUST use these exact severities in your output.

- **drugs_illegal / cannabis_cbd**: Cannabis remains Schedule I at the federal level. However, hemp-derived CBD cosmetics are conditionally legal: THC <0.3%, no drug/efficacy claims, state law compliance required. CBD cosmetic without drug claims -> severity MEDIUM. YOU MUST USE MEDIUM.
- **drugs_illegal / hemp_cosmetic**: Hemp seed/oil cosmetics without CBD are legal under 2018 Farm Bill (THC <0.3%). Hemp cosmetic without CBD -> severity LOW. YOU MUST USE LOW.
- **medical_cosmetic_claims / drug_claim**: FDA distinguishes cosmetics from drugs. Claims like "cures", "treats", "heals" cross into drug territory -> severity CRITICAL. "FDA approved" for cosmetics is always false -> CRITICAL.
- **medical_cosmetic_claims / unsubstantiated**: FTC requires substantiation for efficacy claims. "Clinically proven" without cited studies -> HIGH.
- **disclosure**: FTC Endorsement Guide (2023 rev) requires clear "#ad" or "Paid partnership". Penalty up to $50,000 per violation.
- **unsafe_misleading_usage**: MoCRA (2023) mandates adverse event reporting and safety substantiation.
""",
    "western_europe": """
## REGIONAL CONTEXT: Western Europe (EU Cosmetics Regulation / ASA / ARPP)
You are evaluating this video for the Western European market. Apply these region-specific rules.
CRITICAL: The severity values below are MANDATORY for this region. You MUST use these exact severities in your output.

- **drugs_illegal / cannabis_cbd**: CBD is regulated under Novel Food Regulation (EU 2015/2283) for food, but CBD cosmetics are conditionally permitted: synthetic or permitted-part-derived CBD, THC undetected, CPSR safety assessment required. Country-level enforcement varies. CBD cosmetic -> severity MEDIUM. YOU MUST USE MEDIUM.
- **drugs_illegal / hemp_cosmetic**: Hemp seed-based cosmetics without CBD are generally permitted in EU. Hemp cosmetic without CBD -> severity LOW. YOU MUST USE LOW.
- **unsafe_misleading_usage / misleading_before_after**: ASA (UK) has specifically banned retouched before/after images in cosmetic ads (L'Oreal, Maybelline rulings) -> severity HIGH.
- **medical_cosmetic_claims / unsubstantiated**: EU 6 Common Criteria for cosmetic claims require evidence. "Clinically proven" without evidence -> HIGH.
- **disclosure**: ASA rules are the strictest -- ONLY "#ad", "Ad", or "Advertisement" are acceptable. "#sponsored", "#gifted", "#collab" are ruled INADEQUATE -> severity HIGH (not medium).
- **hate_harassment**: DE Volksverhetzung law; FR racial discrimination = criminal; ASA gender stereotyping ban (2019).
""",
    "east_asia": """
## REGIONAL CONTEXT: East Asia (Korea MFDS / Japan Yakujiho / China NMPA)
You are evaluating this video for the East Asian market. Apply these region-specific rules.
CRITICAL: The severity values below are MANDATORY for this region. You MUST use these exact severities in your output.

- **drugs_illegal**: ZERO TOLERANCE for drugs across KR, JP, CN. Cannabis, marijuana -> severity CRITICAL.
- **drugs_illegal / cbd_product**: Korea classifies CBD as narcotic under Narcotics Control Act. ANY CBD-containing product (CBD cream, CBD oil, cannabidiol) -> severity CRITICAL. YOU MUST USE CRITICAL. Note: hemp seed oil WITHOUT CBD is permitted as cosmetic ingredient in Korea.
- **drugs_illegal / hemp_cosmetic**: Hemp seed/oil cosmetics without CBD are permitted in Korea if THC/CBD is below detection limit -> severity LOW. YOU MUST USE LOW.
- **profanity_explicit / mild_profanity**: East Asia treats mild profanity more strictly than the West. Mild expletives -> severity HIGH (not medium).
- **medical_cosmetic_claims / absolute_claims**: China bans ALL absolute expressions: "100% effective", "immediate effect", "guaranteed results" -> CRITICAL.
- **medical_cosmetic_claims / cosmeceutical_term**: China explicitly banned the term cosmeceutical/medicated cosmetic in 2021 -> HIGH.
- **medical_cosmetic_claims / whitening_claim**: Korea functional cosmetic requiring separate MFDS approval. Japan allows spot prevention but NOT spot removal.
- **disclosure**: Korea KFTC fines for hidden ads; Japan stealth marketing ban effective Oct 2023; China Ad Law Art.14 requires clear identification.
- **profanity_explicit / vulgar_content**: China NRTA "vulgar content" ban is very broadly defined -> HIGH.
""",
}


def get_regional_prompt(region: str) -> str:
    """Return COMBINED_PROMPT with regional context appended."""
    context = REGIONAL_PROMPT_CONTEXT.get(region, "")
    if context:
        return COMBINED_PROMPT + context
    return COMBINED_PROMPT


_VIOLATION_ITEMS_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "timestamp_start": {"type": "number"},
        "timestamp_end": {"type": "number"},
        "modality": {
            "type": "string",
            "enum": ["visual", "speech", "text_on_screen"],
        },
        "evidence": {"type": "string"},
        "evidence_original": {"type": "string"},
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
    },
    "required": ["description", "timestamp_start", "timestamp_end", "modality", "evidence"],
}

_CATEGORY_SCHEMA = {
    "type": "object",
    "properties": {
        "has_violation": {"type": "boolean"},
        "severity": {
            "type": "string",
            "enum": ["none", "low", "medium", "high", "critical"],
        },
        "violations": {
            "type": "array",
            "items": _VIOLATION_ITEMS_SCHEMA,
        },
    },
    "required": ["has_violation", "severity", "violations"],
}

COMBINED_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "relevance": {
            "type": "object",
            "properties": {
                "relevance_score": {"type": "number"},
                "is_on_brief": {"type": "boolean"},
                "product_visible": {"type": "boolean"},
                "reasoning": {"type": "string"},
            },
            "required": ["relevance_score", "is_on_brief", "reasoning"],
        },
        "description": {"type": "string"},
        "policy_violations": {
            "type": "object",
            "properties": {
                "hate_harassment": _CATEGORY_SCHEMA,
                "profanity_explicit": _CATEGORY_SCHEMA,
                "drugs_illegal": _CATEGORY_SCHEMA,
                "unsafe_misleading_usage": _CATEGORY_SCHEMA,
                "medical_cosmetic_claims": _CATEGORY_SCHEMA,
                "disclosure": _CATEGORY_SCHEMA,
            },
            "required": [
                "hate_harassment", "profanity_explicit", "drugs_illegal",
                "unsafe_misleading_usage", "medical_cosmetic_claims", "disclosure",
            ],
        },
    },
    "required": ["relevance", "description", "policy_violations"],
}
