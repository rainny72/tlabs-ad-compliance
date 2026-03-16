from shared.regional_policies.base import get_regional_severity, get_strictest_severity
from shared.regional_policies.north_america import NORTH_AMERICA_POLICY
from shared.regional_policies.western_europe import WESTERN_EUROPE_POLICY
from shared.regional_policies.east_asia import EAST_ASIA_POLICY

REGIONAL_POLICIES = {
    "north_america": NORTH_AMERICA_POLICY,
    "western_europe": WESTERN_EUROPE_POLICY,
    "east_asia": EAST_ASIA_POLICY,
}
