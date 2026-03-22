"""Western Europe regional policy — EU Cosmetics Regulation, ASA (UK), ARPP (France)."""

from shared.constants import PolicyCategory, Region, Severity
from shared.regional_policies.base import (
    RegionalPolicy, RegionalPolicyEntry, SubCategoryRule,
)

WESTERN_EUROPE_POLICY = RegionalPolicy(
    region=Region.WESTERN_EUROPE,
    display_name="Western Europe",
    regulatory_bodies=[
        "EU Cosmetics Regulation (EC 1223/2009)",
        "ASA (UK)",
        "ARPP (France)",
        "EU Unfair Commercial Practices Directive",
    ],
    policies={
        PolicyCategory.HATE_HARASSMENT: RegionalPolicyEntry(
            category=PolicyCategory.HATE_HARASSMENT,
            default_severity=Severity.CRITICAL,
            sub_rules=[
                SubCategoryRule(
                    name="racial_discrimination",
                    description="Racial/ethnic discrimination — criminal offence in DE, FR",
                    severity=Severity.CRITICAL,
                    keywords=["racial discrimination", "ethnic slur", "Volksverhetzung"],
                ),
                SubCategoryRule(
                    name="gender_stereotyping",
                    description="Ads reinforcing harmful gender stereotypes — ASA actively enforces",
                    severity=Severity.HIGH,
                    keywords=["gender stereotype", "sexist portrayal",
                              "women must be beautiful", "body shaming"],
                ),
                SubCategoryRule(
                    name="sexual_objectification",
                    description="Sexual objectification in advertising — FR ARPP strict",
                    severity=Severity.HIGH,
                    keywords=["sexual objectification", "objectifying"],
                ),
            ],
            notes="DE Volksverhetzung law; FR racial discrimination = criminal; ASA gender stereotyping ban (2019)",
        ),
        PolicyCategory.PROFANITY_EXPLICIT: RegionalPolicyEntry(
            category=PolicyCategory.PROFANITY_EXPLICIT,
            default_severity=Severity.HIGH,
            sub_rules=[
                SubCategoryRule(
                    name="strong_profanity",
                    description="Strong expletives in any language",
                    severity=Severity.CRITICAL,
                    keywords=["fuck", "f-word", "c-word", "strong expletive"],
                ),
                SubCategoryRule(
                    name="mild_profanity",
                    description="Mild expletives — context dependent, generally tolerated",
                    severity=Severity.MEDIUM,
                    keywords=["damn", "hell", "merde", "Scheiße"],
                ),
                SubCategoryRule(
                    name="sexual_content",
                    description="Sexually explicit content in ads",
                    severity=Severity.CRITICAL,
                    keywords=["sexually explicit", "pornographic"],
                ),
            ],
            notes="ASA: 'generally offensive' standard; more tolerant of nudity in art context, strict in ads",
        ),
        PolicyCategory.DRUGS_ILLEGAL: RegionalPolicyEntry(
            category=PolicyCategory.DRUGS_ILLEGAL,
            default_severity=Severity.CRITICAL,
            sub_rules=[
                SubCategoryRule(
                    name="illegal_drugs",
                    description="Drug use or promotion",
                    severity=Severity.CRITICAL,
                    keywords=["drug use", "cocaine", "heroin", "ecstasy"],
                ),
                SubCategoryRule(
                    name="cbd_novel_food",
                    description="CBD cosmetics — conditionally permitted in EU: synthetic or permitted-part-derived CBD, THC undetected, CPSR safety assessment required. Country-level enforcement varies.",
                    severity=Severity.MEDIUM,
                    keywords=["CBD", "cannabidiol", "hemp extract",
                              "CBD cream", "CBD oil", "CBD serum"],
                ),
                SubCategoryRule(
                    name="hemp_cosmetic",
                    description="Hemp seed-based cosmetics without CBD — generally permitted in EU",
                    severity=Severity.LOW,
                    keywords=["hemp cream", "hemp oil", "hemp seed",
                              "hemp seed oil", "hemp cosmetic"],
                ),
                SubCategoryRule(
                    name="alcohol_excessive",
                    description="Excessive alcohol consumption in ads",
                    severity=Severity.MEDIUM,
                    keywords=["binge drinking", "alcohol excess"],
                ),
            ],
            notes="CBD cosmetics: conditionally permitted (synthetic/permitted-part CBD, THC undetected, CPSR required, country-level enforcement varies); Hemp seed cosmetics without CBD generally permitted",
        ),
        PolicyCategory.UNSAFE_MISLEADING_USAGE: RegionalPolicyEntry(
            category=PolicyCategory.UNSAFE_MISLEADING_USAGE,
            default_severity=Severity.HIGH,
            sub_rules=[
                SubCategoryRule(
                    name="excessive_retouching",
                    description="Digitally altered before/after — ASA has banned multiple ads",
                    severity=Severity.HIGH,
                    keywords=["retouched", "digitally altered", "photoshopped",
                              "before after manipulated"],
                ),
                SubCategoryRule(
                    name="eye_area_misuse",
                    description="Unsafe product application near eyes",
                    severity=Severity.HIGH,
                    keywords=["eye area misuse", "unsafe application"],
                ),
                SubCategoryRule(
                    name="banned_ingredients",
                    description="Use or mention of EU banned ingredients (1,600+ list)",
                    severity=Severity.HIGH,
                    keywords=["banned ingredient", "prohibited substance"],
                ),
            ],
            notes="ASA: multiple rulings against L'Oreal, Maybelline for retouched images; EU CPSR mandatory",
        ),
        PolicyCategory.MEDICAL_COSMETIC_CLAIMS: RegionalPolicyEntry(
            category=PolicyCategory.MEDICAL_COSMETIC_CLAIMS,
            default_severity=Severity.HIGH,
            sub_rules=[
                SubCategoryRule(
                    name="drug_claim",
                    description="Claims crossing into medicinal territory",
                    severity=Severity.CRITICAL,
                    keywords=["cures", "treats", "heals", "therapeutic"],
                ),
                SubCategoryRule(
                    name="unsubstantiated_clinical",
                    description="'Clinically proven' without evidence — violates EU Common Criteria",
                    severity=Severity.HIGH,
                    keywords=["clinically proven", "scientifically tested",
                              "laboratory confirmed"],
                ),
                SubCategoryRule(
                    name="false_natural_organic",
                    description="'100% natural/organic' without certification",
                    severity=Severity.MEDIUM,
                    keywords=["100% natural", "all natural", "organic",
                              "certified organic"],
                ),
                SubCategoryRule(
                    name="anti_aging_exaggerated",
                    description="Exaggerated anti-aging claims beyond cosmetic scope",
                    severity=Severity.MEDIUM,
                    keywords=["removes wrinkles", "eliminates fine lines",
                              "reverses aging"],
                ),
            ],
            notes="EU 6 Common Criteria: legal compliance, truthfulness, evidence-based, honesty, fairness, informed decision",
        ),
        PolicyCategory.DISCLOSURE: RegionalPolicyEntry(
            category=PolicyCategory.DISCLOSURE,
            default_severity=Severity.HIGH,
            sub_rules=[
                SubCategoryRule(
                    name="missing_ad_label",
                    description="No #ad label — ASA requires upfront placement",
                    severity=Severity.HIGH,
                    keywords=["no #ad", "missing disclosure", "undisclosed"],
                ),
                SubCategoryRule(
                    name="inadequate_label",
                    description="Using #sponsored/#gifted instead of #ad (UK: inadequate)",
                    severity=Severity.MEDIUM,
                    keywords=["#sponsored", "#gifted", "#collab",
                              "#brandambassador"],
                ),
            ],
            notes="ASA: only '#ad'/'Ad'/'Advertisement' acceptable; '#sponsored' ruled inadequate",
        ),
    },
)
