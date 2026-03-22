"""East Asia regional policy — Korea MFDS, Japan PMDA/Yakujiho, China NMPA."""

from shared.constants import PolicyCategory, Region, Severity
from shared.regional_policies.base import RegionalPolicy, RegionalPolicyEntry, SubCategoryRule

EAST_ASIA_POLICY = RegionalPolicy(
    region=Region.EAST_ASIA,
    display_name="East Asia",
    regulatory_bodies=[
        "Korea MFDS (식약처)",
        "Korea KCC (방통위) / KFTC (공정위)",
        "Japan PMDA / Yakujiho (薬機法)",
        "Japan JARO / BPO",
        "China NMPA (国家药监局)",
        "China NRTA (广电总局)",
    ],
    policies={
        PolicyCategory.HATE_HARASSMENT: RegionalPolicyEntry(
            category=PolicyCategory.HATE_HARASSMENT,
            default_severity=Severity.CRITICAL,
            sub_rules=[
                SubCategoryRule(
                    name="ethnic_discrimination",
                    description="Ethnic/national discrimination — CN: criminal offence for undermining ethnic unity",
                    severity=Severity.CRITICAL,
                    keywords=["ethnic discrimination", "racial slur",
                              "민족 비하", "民族歧视"],
                ),
                SubCategoryRule(
                    name="appearance_shaming",
                    description="Body/appearance shaming — particularly sensitive in KR",
                    severity=Severity.HIGH,
                    keywords=["body shaming", "appearance mockery", "외모 비하",
                              "체형 비하", "容貌歧视"],
                ),
                SubCategoryRule(
                    name="skin_tone_supremacy",
                    description="Linking lighter skin tone to superiority",
                    severity=Severity.HIGH,
                    keywords=["skin tone superiority", "white skin better",
                              "피부색 우월", "肤色优越"],
                ),
            ],
            notes="CN: undermining ethnic unity = criminal; KR: appearance discrimination increasingly regulated",
        ),
        PolicyCategory.PROFANITY_EXPLICIT: RegionalPolicyEntry(
            category=PolicyCategory.PROFANITY_EXPLICIT,
            default_severity=Severity.HIGH,
            sub_rules=[
                SubCategoryRule(
                    name="strong_profanity",
                    description="Strong expletives in any language",
                    severity=Severity.CRITICAL,
                    keywords=["fuck", "f-word", "씨발", "ファック", "他妈的"],
                ),
                SubCategoryRule(
                    name="mild_profanity",
                    description="Mild expletives — STRICTER than West; KR/CN treat as HIGH",
                    severity=Severity.HIGH,
                    keywords=["damn", "hell", "shit", "젠장", "씨", "くそ",
                              "该死", "妈的"],
                ),
                SubCategoryRule(
                    name="sexual_content",
                    description="Any sexually suggestive content — CN most strict",
                    severity=Severity.CRITICAL,
                    keywords=["sexual content", "nudity", "suggestive",
                              "선정적", "性暗示", "露出"],
                ),
                SubCategoryRule(
                    name="vulgar_content",
                    description="CN 'vulgar content' catch-all — broadly defined",
                    severity=Severity.HIGH,
                    keywords=["vulgar", "低俗", "庸俗"],
                ),
            ],
            notes="EA is strictest region for profanity; CN NRTA 'vulgar content' ban is very broad; KR broadcast standards apply to social ads",
        ),
        PolicyCategory.DRUGS_ILLEGAL: RegionalPolicyEntry(
            category=PolicyCategory.DRUGS_ILLEGAL,
            default_severity=Severity.CRITICAL,
            sub_rules=[
                SubCategoryRule(
                    name="illegal_drugs",
                    description="Any drug reference — zero tolerance across EA",
                    severity=Severity.CRITICAL,
                    keywords=["drug use", "marijuana", "cannabis", "cocaine",
                              "마약", "大麻", "薬物", "대마"],
                ),
                SubCategoryRule(
                    name="cbd_product",
                    description="CBD-containing products — KR: CBD classified as narcotic (마약류관리법), cosmetic use prohibited",
                    severity=Severity.CRITICAL,
                    keywords=["CBD", "cannabidiol", "CBD cream", "CBD oil",
                              "CBD serum", "CBD cosmetic", "CBD skincare"],
                ),
                SubCategoryRule(
                    name="hemp_cosmetic",
                    description="Hemp seed/oil cosmetics without CBD — permitted in KR if THC/CBD below detection limit",
                    severity=Severity.LOW,
                    keywords=["hemp cream", "hemp oil", "hemp seed",
                              "hemp seed oil", "hemp cosmetic", "hemp extract"],
                ),
                SubCategoryRule(
                    name="alcohol_glorification",
                    description="Alcohol glorification — KR restricts alcohol-positive ads",
                    severity=Severity.MEDIUM,
                    keywords=["alcohol glorification", "drinking", "음주 미화",
                              "饮酒"],
                ),
            ],
            notes="All 3 countries: zero tolerance for drug content; KR: CBD = narcotic under Narcotics Control Act; hemp seed oil (CBD-free, THC/CBD below detection limit) is permitted as cosmetic ingredient",
        ),
        PolicyCategory.UNSAFE_MISLEADING_USAGE: RegionalPolicyEntry(
            category=PolicyCategory.UNSAFE_MISLEADING_USAGE,
            default_severity=Severity.HIGH,
            sub_rules=[
                SubCategoryRule(
                    name="eye_area_misuse",
                    description="Unsafe product application near eyes",
                    severity=Severity.HIGH,
                    keywords=["eye area misuse", "unsafe application"],
                ),
                SubCategoryRule(
                    name="unregistered_product",
                    description="Promoting unregistered cosmetic products (CN: mandatory registration)",
                    severity=Severity.HIGH,
                    keywords=["unregistered product", "미신고 제품",
                              "未注册产品", "未届出"],
                ),
                SubCategoryRule(
                    name="misleading_before_after",
                    description="Exaggerated before/after imagery",
                    severity=Severity.MEDIUM,
                    keywords=["before after exaggerated", "비포 애프터 과장"],
                ),
            ],
            notes="CN 2021: all imported cosmetics must be registered; KR: custom cosmetics require notification",
        ),
        PolicyCategory.MEDICAL_COSMETIC_CLAIMS: RegionalPolicyEntry(
            category=PolicyCategory.MEDICAL_COSMETIC_CLAIMS,
            default_severity=Severity.HIGH,
            sub_rules=[
                SubCategoryRule(
                    name="drug_claim",
                    description="Claims crossing into drug territory",
                    severity=Severity.CRITICAL,
                    keywords=["cures", "treats", "heals", "치료", "治疗",
                              "治す"],
                ),
                SubCategoryRule(
                    name="absolute_claims",
                    description="CN: absolute expressions banned ('100% effective', 'immediate effect')",
                    severity=Severity.CRITICAL,
                    keywords=["100% effective", "immediate effect", "guaranteed",
                              "100% 효과", "즉시 효과", "100%有效", "立即见效"],
                ),
                SubCategoryRule(
                    name="cosmeceutical_term",
                    description="CN 2021: '药妆' (cosmeceutical/medicated cosmetic) term explicitly banned",
                    severity=Severity.HIGH,
                    keywords=["药妆", "cosmeceutical", "medicated cosmetic",
                              "약용 화장품"],
                ),
                SubCategoryRule(
                    name="medical_terminology",
                    description="CN: medical terminology prohibited in cosmetics advertising",
                    severity=Severity.HIGH,
                    keywords=["medical term", "의학 용어", "医学术语",
                              "处方", "prescription"],
                ),
                SubCategoryRule(
                    name="whitening_claim_excess",
                    description="KR: '미백' is functional cosmetic requiring separate approval; JP: '시미 방지' allowed, '시미 제거' not",
                    severity=Severity.MEDIUM,
                    keywords=["whitening", "미백", "美白", "removes spots",
                              "기미 제거", "シミを消す"],
                ),
                SubCategoryRule(
                    name="jp_beyond_56_claims",
                    description="JP Yakujiho: only 56 permitted efficacy claims for cosmetics",
                    severity=Severity.HIGH,
                    keywords=["beyond permitted claims", "효능 초과",
                              "認められた効能を超える"],
                ),
            ],
            notes="CN: strictest — no absolute terms, no medical terms, no 药妆; KR: functional cosmetics need MFDS approval; JP: 56 permitted claims only",
        ),
        PolicyCategory.DISCLOSURE: RegionalPolicyEntry(
            category=PolicyCategory.DISCLOSURE,
            default_severity=Severity.MEDIUM,
            sub_rules=[
                SubCategoryRule(
                    name="kr_hidden_ad",
                    description="KR '뒷광고' (hidden ad) regulation — economic relationship must be disclosed",
                    severity=Severity.MEDIUM,
                    keywords=["뒷광고", "hidden ad", "undisclosed sponsorship",
                              "유료광고 미표기"],
                ),
                SubCategoryRule(
                    name="jp_stealth_marketing",
                    description="JP stealth marketing regulation (2023.10~) — must label 'PR' or '広告'",
                    severity=Severity.MEDIUM,
                    keywords=["ステルスマーケティング", "stealth marketing",
                              "PR未表示", "広告未表示"],
                ),
                SubCategoryRule(
                    name="cn_ad_identification",
                    description="CN Ad Law Article 14 — ads must be clearly identifiable",
                    severity=Severity.MEDIUM,
                    keywords=["广告标识", "ad identification", "广告未标注"],
                ),
            ],
            notes="KR: KFTC fines for 뒷광고; JP: stealth marketing ban effective Oct 2023; CN: Ad Law Art.14",
        ),
    },
)
