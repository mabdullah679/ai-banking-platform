from pathlib import Path

from infra.network.plan import Subnet, build_plan, validate_plan


# The shipped plan has no overlaps, nothing outside the VPC, every tier in every zone, roomy pods.
def test_plan_is_sound() -> None:
    assert validate_plan(build_plan()) == []


# Two subnets that share addresses are caught.
def test_overlap_is_caught() -> None:
    plan = build_plan() + [Subnet("public", "a", "10.20.0.128/25")]
    assert any("overlaps" in problem for problem in validate_plan(plan))


# A subnet outside the VPC range is caught.
def test_outside_vpc_is_caught() -> None:
    plan = build_plan() + [Subnet("public", "a", "192.168.0.0/24")]
    assert any("outside the VPC" in problem for problem in validate_plan(plan))


# A tier missing from a zone is caught, because losing that zone would take the tier down.
def test_missing_zone_is_caught() -> None:
    plan = [s for s in build_plan() if not (s.tier == "private-data" and s.az == "c")]
    assert any("not in every availability zone" in problem for problem in validate_plan(plan))


# An app subnet too small for pods is caught.
def test_small_app_subnet_is_caught() -> None:
    plan = [s for s in build_plan() if s.tier != "private-app"]
    plan += [Subnet("private-app", az, f"10.20.{100 + i}.0/24") for i, az in enumerate("abc")]
    assert any("usable IPs for pods" in problem for problem in validate_plan(plan))


# The architecture doc must list every subnet in the plan, so the doc cannot drift from the code.
def test_doc_matches_plan() -> None:
    doc = (Path(__file__).parent.parent / "docs" / "ARCHITECTURE.md").read_text()
    for subnet in build_plan():
        assert subnet.cidr in doc
