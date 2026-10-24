import ipaddress
from dataclasses import dataclass
from itertools import combinations

VPC_CIDR = "10.20.0.0/16"
AZS = ("a", "b", "c")
TIERS = ("public", "private-app", "private-data")
AWS_RESERVED_IPS = 5  # AWS keeps 5 addresses in every subnet
MIN_APP_USABLE_IPS = 4000  # pods get VPC IPs, so the app tier needs room to grow


@dataclass(frozen=True)
class Subnet:
    """One subnet in the plan: its tier, its availability zone, and its address range."""

    tier: str
    az: str
    cidr: str

    @property
    def network(self) -> ipaddress.IPv4Network:
        return ipaddress.ip_network(self.cidr)

    # How many addresses are really usable (AWS reserves 5 per subnet).
    @property
    def usable_ips(self) -> int:
        return self.network.num_addresses - AWS_RESERVED_IPS


# Builds the subnet plan: three tiers in each of three availability zones, with room left to grow.
def build_plan() -> list[Subnet]:
    vpc = ipaddress.ip_network(VPC_CIDR)
    slash24 = list(vpc.subnets(new_prefix=24))
    slash20 = list(vpc.subnets(new_prefix=20))
    plan = []
    for i, az in enumerate(AZS):
        plan.append(Subnet("public", az, str(slash24[i])))  # 10.20.0-2.0/24: load balancers, NAT
        plan.append(Subnet("private-app", az, str(slash20[2 + i])))  # /20: nodes and pods
        plan.append(Subnet("private-data", az, str(slash24[10 + i])))  # 10.20.10-12.0/24: databases
    return plan


# Checks a plan and returns a list of problems (an empty list means the plan is sound).
def validate_plan(plan: list[Subnet]) -> list[str]:
    problems = []
    vpc = ipaddress.ip_network(VPC_CIDR)
    for subnet in plan:
        if not subnet.network.subnet_of(vpc):
            problems.append(f"{subnet.cidr} is outside the VPC {VPC_CIDR}")
    for first, second in combinations(plan, 2):
        if first.network.overlaps(second.network):
            problems.append(f"{first.cidr} overlaps {second.cidr}")
    for tier in TIERS:
        zones = {s.az for s in plan if s.tier == tier}
        if zones != set(AZS):
            problems.append(f"tier {tier} is not in every availability zone")
    for subnet in plan:
        if subnet.tier == "private-app" and subnet.usable_ips < MIN_APP_USABLE_IPS:
            problems.append(f"{subnet.cidr} has only {subnet.usable_ips} usable IPs for pods")
    return problems


# Renders the plan as a Markdown table, used in docs/ARCHITECTURE.md.
def as_table(plan: list[Subnet]) -> str:
    rows = ["| Tier | AZ | CIDR | Usable IPs |", "|---|---|---|---|"]
    for s in sorted(plan, key=lambda s: (TIERS.index(s.tier), s.az)):
        rows.append(f"| {s.tier} | {s.az} | {s.cidr} | {s.usable_ips} |")
    return "\n".join(rows)


if __name__ == "__main__":
    print(as_table(build_plan()))
