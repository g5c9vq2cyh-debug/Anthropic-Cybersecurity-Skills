#!/usr/bin/env python3
"""
Ransomware Recovery Orchestration and Tracking Tool

Tracks recovery progress across multiple systems and phases:
- Recovery phase tracking with dependency management
- RTO compliance monitoring
- System validation checklists
- Recovery status reporting
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class RecoverableSystem:
    name: str
    tier: int
    system_type: str  # dc, database, application, fileserver, web, other
    dependencies: list = field(default_factory=list)
    rto_hours: float = 24.0
    status: str = "pending"  # pending, restoring, validating, online, failed
    backup_source: str = ""
    backup_timestamp: Optional[str] = None
    restore_start: Optional[str] = None
    restore_end: Optional[str] = None
    validation_checks: dict = field(default_factory=dict)
    notes: str = ""


@dataclass
class RecoveryPlan:
    incident_id: str
    organization: str
    recovery_start: str
    compromise_date: str
    systems: list = field(default_factory=list)
    phases: dict = field(default_factory=dict)
    overall_status: str = "in_progress"


class RecoveryOrchestrator:
    """Manages and tracks ransomware recovery across all systems."""

    def __init__(self, incident_id: str, org_name: str, compromise_date: str):
        self.plan = RecoveryPlan(
            incident_id=incident_id,
            organization=org_name,
            recovery_start=datetime.now().isoformat(),
            compromise_date=compromise_date,
        )

    def add_system(self, system: RecoverableSystem):
        self.plan.systems.append(system)

    def start_restore(self, system_name: str, backup_source: str):
        for system in self.plan.systems:
            if system.name == system_name:
                # Check dependencies are online
                for dep in system.dependencies:
                    dep_sys = next((s for s in self.plan.systems if s.name == dep), None)
                    if dep_sys and dep_sys.status != "online":
                        raise ValueError(
                            f"Cannot restore {system_name}: dependency {dep} "
                            f"is {dep_sys.status}, must be 'online'"
                        )
                system.status = "restoring"
                system.backup_source = backup_source
                system.restore_start = datetime.now().isoformat()
                return
        raise ValueError(f"System not found: {system_name}")

    def complete_restore(self, system_name: str):
        for system in self.plan.systems:
            if system.name == system_name:
                system.status = "validating"
                system.restore_end = datetime.now().isoformat()
                return
        raise ValueError(f"System not found: {system_name}")

    def validate_system(self, system_name: str, checks: dict):
        """Record validation check results for a restored system."""
        for system in self.plan.systems:
            if system.name == system_name:
                system.validation_checks = checks
                all_passed = all(checks.values())
                system.status = "online" if all_passed else "failed"
                return all_passed
        raise ValueError(f"System not found: {system_name}")

    def check_rto_compliance(self) -> list:
        """Check which systems are at risk of exceeding their RTO."""
        violations = []
        recovery_start = datetime.fromisoformat(self.plan.recovery_start)

        for system in self.plan.systems:
            rto_deadline = recovery_start + timedelta(hours=system.rto_hours)

            if system.status in ("pending", "restoring", "validating"):
                if datetime.now() > rto_deadline:
                    violations.append({
                        "system": system.name,
                        "tier": system.tier,
                        "rto_hours": system.rto_hours,
                        "deadline": rto_deadline.isoformat(),
                        "status": system.status,
                        "exceeded_by_hours": round(
                            (datetime.now() - rto_deadline).total_seconds() / 3600, 1
                        ),
                    })
        return violations

    def get_recovery_progress(self) -> dict:
        """Calculate overall recovery progress."""
        total = len(self.plan.systems)
        if total == 0:
            return {"progress": 0, "by_status": {}, "by_tier": {}}

        by_status = {}
        by_tier = {}
        for system in self.plan.systems:
            by_status[system.status] = by_status.get(system.status, 0) + 1
            tier_key = f"tier_{system.tier}"
            if tier_key not in by_tier:
                by_tier[tier_key] = {"total": 0, "online": 0}
            by_tier[tier_key]["total"] += 1
            if system.status == "online":
                by_tier[tier_key]["online"] += 1

        online = by_status.get("online", 0)
        return {
            "progress": round((online / total) * 100, 1),
            "total_systems": total,
            "by_status": by_status,
            "by_tier": by_tier,
        }

    def get_next_recoverable(self) -> list:
        """Get list of systems ready for recovery (dependencies met)."""
        ready = []
        for system in self.plan.systems:
            if system.status != "pending":
                continue
            deps_met = all(
                next((s for s in self.plan.systems if s.name == dep), None) is not None
                and next((s for s in self.plan.systems if s.name == dep)).status == "online"
                for dep in system.dependencies
            )
            if deps_met or not system.dependencies:
                ready.append(system)
        return sorted(ready, key=lambda s: s.tier)

    def generate_report(self) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("RANSOMWARE RECOVERY STATUS REPORT")
        lines.append("=" * 70)
        lines.append(f"Incident: {self.plan.incident_id}")
        lines.append(f"Organization: {self.plan.organization}")
        lines.append(f"Recovery Started: {self.plan.recovery_start}")
        lines.append(f"Compromise Date: {self.plan.compromise_date}")

        progress = self.get_recovery_progress()
        lines.append(f"\nOverall Progress: {progress['progress']}%")
        lines.append(f"Total Systems: {progress['total_systems']}")

        for status, count in progress["by_status"].items():
            lines.append(f"  {status}: {count}")

        lines.append("\nBy Tier:")
        for tier, data in sorted(progress["by_tier"].items()):
            lines.append(f"  {tier}: {data['online']}/{data['total']} online")

        # RTO violations
        violations = self.check_rto_compliance()
        if violations:
            lines.append(f"\nRTO VIOLATIONS ({len(violations)}):")
            for v in violations:
                lines.append(f"  {v['system']} (Tier {v['tier']}): "
                           f"RTO {v['rto_hours']}h exceeded by {v['exceeded_by_hours']}h")

        # System details
        lines.append("\nSystem Recovery Status:")
        lines.append("-" * 50)
        for tier in sorted(set(s.tier for s in self.plan.systems)):
            tier_systems = [s for s in self.plan.systems if s.tier == tier]
            lines.append(f"\n  Tier {tier}:")
            for system in tier_systems:
                status_icon = {"pending": "[ ]", "restoring": "[~]", "validating": "[?]",
                              "online": "[+]", "failed": "[X]"}.get(system.status, "[?]")
                lines.append(f"    {status_icon} {system.name} ({system.system_type}) - {system.status}")
                if system.restore_start and system.restore_end:
                    start = datetime.fromisoformat(system.restore_start)
                    end = datetime.fromisoformat(system.restore_end)
                    duration = (end - start).total_seconds() / 3600
                    lines.append(f"        Restore time: {duration:.1f} hours")
                if system.validation_checks:
                    for check, passed in system.validation_checks.items():
                        result = "PASS" if passed else "FAIL"
                        lines.append(f"        {check}: {result}")

        # Next recoverable systems
        ready = self.get_next_recoverable()
        if ready:
            lines.append(f"\nReady for Recovery ({len(ready)}):")
            for system in ready:
                lines.append(f"  - {system.name} (Tier {system.tier}, {system.system_type})")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)

    def export_plan(self, output_path: str):
        with open(output_path, "w") as f:
            json.dump(asdict(self.plan), f, indent=2)


def main():
    """Demo recovery orchestration."""
    orch = RecoveryOrchestrator(
        incident_id="INC-2026-0042",
        org_name="Acme Manufacturing",
        compromise_date="2026-02-20T03:00:00",
    )

    # Define systems with dependencies
    orch.add_system(RecoverableSystem(
        name="DC01", tier=1, system_type="dc", rto_hours=4,
    ))
    orch.add_system(RecoverableSystem(
        name="DC02", tier=1, system_type="dc", rto_hours=4,
    ))
    orch.add_system(RecoverableSystem(
        name="DNS01", tier=1, system_type="dns", rto_hours=4,
        dependencies=["DC01"],
    ))
    orch.add_system(RecoverableSystem(
        name="SQL-ERP", tier=1, system_type="database", rto_hours=8,
        dependencies=["DC01", "DNS01"],
    ))
    orch.add_system(RecoverableSystem(
        name="ERP-APP", tier=1, system_type="application", rto_hours=12,
        dependencies=["SQL-ERP", "DC01"],
    ))
    orch.add_system(RecoverableSystem(
        name="Exchange", tier=2, system_type="email", rto_hours=12,
        dependencies=["DC01", "DC02"],
    ))
    orch.add_system(RecoverableSystem(
        name="FileServer01", tier=2, system_type="fileserver", rto_hours=24,
        dependencies=["DC01"],
    ))
    orch.add_system(RecoverableSystem(
        name="WebApp01", tier=2, system_type="web", rto_hours=24,
        dependencies=["SQL-ERP"],
    ))
    orch.add_system(RecoverableSystem(
        name="DevServer", tier=3, system_type="other", rto_hours=48,
        dependencies=["DC01"],
    ))

    # Simulate recovery progress
    orch.start_restore("DC01", "Immutable Veeam Hardened Repo")
    orch.complete_restore("DC01")
    orch.validate_system("DC01", {
        "dcdiag": True, "repadmin": True, "dns_resolution": True,
        "krbtgt_reset": True, "persistence_scan": True,
    })

    orch.start_restore("DC02", "Immutable Veeam Hardened Repo")
    orch.complete_restore("DC02")
    orch.validate_system("DC02", {
        "dcdiag": True, "repadmin": True, "replication": True,
    })

    orch.start_restore("DNS01", "Immutable Veeam Hardened Repo")

    print(orch.generate_report())

    output_path = str(Path(__file__).parent / "recovery_plan.json")
    orch.export_plan(output_path)
    print(f"\nRecovery plan exported to: {output_path}")


if __name__ == "__main__":
    main()
