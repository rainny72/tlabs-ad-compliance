"""North America regional policy — FTC, FDA, MoCRA, Ad Standards Canada."""

from shared.constants import PolicyCategory, Region, Severity
from shared.regional_policies.base import RegionalPolicy, RegionalPolicyEntry, SubCategoryRule

NORTH_AMERICA_POLICY = RegionalPolicy(
    region=Region.NORTH_AMERICA,
    display_name="North America",
    regulatory_bodies=["FTC", "FDA", "MoCRA (2023)", "Ad Standards Canada"],
    policies={
        PolicyCategory.HATE_HARASSMENT: RegionalPolicyEntry(
            category=PolicyCategory.HATE_HARASSMENT,
            default_severity=Severity.CRITICAL,
            sub_rules=[
                SubCategoryRule(
                    name="racial_slur",
                    description="Racial slurs or ethnic derogatory terms",
                    severity=Severity.CRITICAL,
                    keywords=["racial slur", "n-word", "ethnic slur"],
                ),
                SubCategoryRule(
                    name="gender_discrimination",
                    description="Gender-based discrimination or sexist language",
                    severity=Severity.HIGH,
                    keywords=["sexist", "misogynist"],
                ),
                SubCategoryRule(
                    name="disability_mockery",
                    description="Mocking or belittling people with disabilities",
                    severity=Severity.CRITICAL,
                    keywords=["disability mockery", "ableist slur"],
                ),
            ],
            notes="Protected class: race, color, religion, sex, national origin, disability, age",
        ),
        PolicyCategory.PROFANITY_EXPLICIT: RegionalPolicyEntry(
            category=PolicyCategory.PROFANITY_EXPLICIT,
            default_severity=Severity.HIGH,
            sub_rules=[
                SubCategoryRule(
                    name="strong_profanity",
                    description="F-word, C-word, and other strong expletives",
                    severity=Severity.CRITICAL,
                    keywords=["fuck", "f-word", "c-word", "motherfucker"],
                ),
                SubCategoryRule(
                    name="mild_profanity",
                    description="Mild expletives: damn, hell, crap, ass",
                    severity=Severity.MEDIUM,
                    keywords=["damn", "hell", "crap", "ass", "suck"],
                ),
                SubCategoryRule(
                    name="sexual_content",
                    description="Sexually explicit or suggestive content",
                    severity=Severity.CRITICAL,
                    keywords=["sexually explicit", "nudity", "sexual content"],
                ),
            ],
            notes="FCC broadcast standards; social ad platforms generally follow similar tiers",
        ),
        PolicyCategory.DRUGS_ILLEGAL: RegionalPolicyEntry(
            category=PolicyCategory.DRUGS_ILLEGAL,
            default_severity=Severity.CRITICAL,
            sub_rules=[
                SubCategoryRule(
                    name="illegal_drugs",
                    description="Hard drug use or drug paraphernalia",
                    severity=Severity.CRITICAL,
                    keywords=["cocaine", "heroin", "meth", "drug use"],
                ),
                SubCategoryRule(
                    name="cannabis_cbd",
                    description="Cannabis/CBD in ads — federally prohibited",
                    severity=Severity.HIGH,
                    keywords=["cannabis", "marijuana", "CBD", "weed", "THC"],
                ),
                SubCategoryRule(
                    name="alcohol_glorification",
                    description="Excessive alcohol consumption glorification",
                    severity=Severity.MEDIUM,
                    keywords=["binge drinking", "alcohol abuse"],
                ),
            ],
            notes="Cannabis: Schedule I federally; CBD advertising restricted across platforms",
        ),
        PolicyCategory.UNSAFE_MISLEADING_USAGE: RegionalPolicyEntry(
            category=PolicyCategory.UNSAFE_MISLEADING_USAGE,
            default_severity=Severity.HIGH,
            sub_rules=[
                SubCategoryRule(
                    name="eye_area_misuse",
                    description="Applying non-eye-safe products near eyes",
                    severity=Severity.HIGH,
                    keywords=["eye area", "near eyes", "lip product on eyes"],
                ),
                SubCategoryRule(
                    name="diy_unsafe",
                    description="DIY cosmetics without safety warnings (MoCRA)",
                    severity=Severity.MEDIUM,
                    keywords=["DIY", "homemade cosmetic", "no safety warning"],
                ),
                SubCategoryRule(
                    name="misleading_before_after",
                    description="Misleading before/after comparisons",
                    severity=Severity.MEDIUM,
                    keywords=["before after", "retouched", "digitally altered"],
                ),
            ],
            notes="FDA MoCRA (2023): adverse event reporting mandatory; safety substantiation required",
        ),
        PolicyCategory.MEDICAL_COSMETIC_CLAIMS: RegionalPolicyEntry(
            category=PolicyCategory.MEDICAL_COSMETIC_CLAIMS,
            default_severity=Severity.HIGH,
            sub_rules=[
                SubCategoryRule(
                    name="drug_claim",
                    description="Claims that cross into drug territory (treats, cures, heals)",
                    severity=Severity.CRITICAL,
                    keywords=["cures", "treats", "heals", "removes wrinkles",
                              "anti-acne", "clears acne"],
                ),
                SubCategoryRule(
                    name="fda_approved_false",
                    description="Falsely claiming FDA approval for cosmetics",
                    severity=Severity.CRITICAL,
                    keywords=["FDA approved", "FDA certified"],
                ),
                SubCategoryRule(
                    name="unsubstantiated_efficacy",
                    description="Efficacy claims without evidence",
                    severity=Severity.MEDIUM,
                    keywords=["clinically proven", "scientifically proven",
                              "dermatologist recommended"],
                ),
            ],
            notes="FTC: substantiation required; FDA: drug vs cosmetic distinction is key",
        ),
        PolicyCategory.DISCLOSURE: RegionalPolicyEntry(
            category=PolicyCategory.DISCLOSURE,
            default_severity=Severity.MEDIUM,
            sub_rules=[
                SubCategoryRule(
                    name="missing_ad_disclosure",
                    description="No #ad or paid partnership label",
                    severity=Severity.MEDIUM,
                    keywords=["no disclosure", "missing #ad", "undisclosed sponsorship"],
                ),
                SubCategoryRule(
                    name="buried_disclosure",
                    description="Disclosure hidden in hashtag pile or below fold",
                    severity=Severity.MEDIUM,
                    keywords=["buried disclosure", "hidden #ad"],
                ),
            ],
            notes="FTC Endorsement Guide (2023 rev): up to $50,000 per violation",
        ),
    },
)
