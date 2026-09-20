"""
Many communities, one deployment.

Section 3.1 of the roadmap: the platform is already community-agnostic, since a
new deployment is a configuration file, a constitution and a source list. What
was missing is tenancy, meaning the guarantees that make it safe to run
Brookline and Cambridge on the same server.

The interesting part is not technical. It is that **each community keeps its own
constitution, its own corpus, its own evaluation set, its own ratifiers and its
own release history**, while sharing infrastructure. Brookline and Cambridge can
disagree about what the assistant should do and both be right. A tenancy model
that collapsed them onto one set of rules would defeat the point of the project.

So the rule here is stricter than ordinary multi-tenancy: **nothing is shared by
default except code.** A tenant's constitution falls back to the repository's
only when that tenant has not adopted its own, and when it does the fallback is
reported rather than hidden, because "whose rules are governing this answer" is
never allowed to be ambiguous.

Three mechanisms:

* **Resolution.** A request arrives on a hostname, a path prefix, or with an API
  key. Any of the three identifies the tenant.
* **Isolation.** Every filesystem path a request touches is checked to be inside
  that tenant's directory. Path checks are cheap and a cross-tenant read of a
  municipal archive is the kind of incident that ends a project.
* **Fair sharing.** Per-tenant quotas, so one community's traffic cannot starve
  another's on hardware they are both paying for.
"""

from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_DATA_ROOT = os.getenv("COMMUNITY_DATA_ROOT", "./data")
TENANTS_FILE = os.getenv("COMMUNITY_TENANTS_FILE", "tenants.yaml")

# A tenant id becomes a directory name and a URL path segment. Keep it boring.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


class TenancyError(RuntimeError):
    """A tenancy problem an operator needs to see."""


class IsolationError(TenancyError):
    """A path or resource outside the requesting tenant. Never ignore one."""


@dataclass
class TenantBranding:
    display_name: str = ""
    tagline: str = ""
    primary_color: str = "#22c55e"
    logo_url: str = ""
    contact: str = ""
    operator: str = ""


@dataclass
class TenantQuota:
    """What one community may consume on shared hardware.

    Zero means unlimited. The defaults are generous because the common case is
    a handful of communities on one box, not a marketplace.
    """

    requests_per_minute: int = 0
    requests_per_day: int = 0
    max_corpus_chunks: int = 0
    max_sources: int = 0
    inference_enabled: bool = True


@dataclass
class Tenant:
    """One community on this deployment."""

    tenant_id: str
    project_id: str = ""
    community: str = ""
    hostnames: List[str] = field(default_factory=list)
    path_prefix: str = ""
    branding: TenantBranding = field(default_factory=TenantBranding)
    quota: TenantQuota = field(default_factory=TenantQuota)
    enabled: bool = True
    admins: List[str] = field(default_factory=list)
    created_at: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        self.tenant_id = (self.tenant_id or "").strip().lower()
        if not _SLUG_RE.match(self.tenant_id):
            raise TenancyError(
                f"tenant id {self.tenant_id!r} must be lowercase letters, digits, "
                f"hyphens or underscores, starting with a letter or digit"
            )
        self.project_id = self.project_id or self.tenant_id
        self.hostnames = [h.strip().lower() for h in self.hostnames if h.strip()]
        if not self.branding.display_name:
            self.branding.display_name = self.community or self.tenant_id

    # --- the directories this tenant owns --------------------------------

    def data_root(self, base: str = DEFAULT_DATA_ROOT) -> Path:
        return (Path(base) / self.project_id).resolve()

    def constitution_dir(self, base: str = DEFAULT_DATA_ROOT) -> Path:
        return self.data_root(base) / "constitution"

    def evals_dir(self, base: str = DEFAULT_DATA_ROOT) -> Path:
        return self.data_root(base) / "evals"

    def logs_dir(self, base: str = DEFAULT_DATA_ROOT) -> Path:
        return self.data_root(base) / "logs"

    def has_own_constitution(self, base: str = DEFAULT_DATA_ROOT) -> bool:
        directory = self.constitution_dir(base)
        if not directory.is_dir():
            return False
        return any(directory.glob("constitution-v*.md")) or \
            (directory / "constitution.md").is_file()

    def has_own_evals(self, base: str = DEFAULT_DATA_ROOT) -> bool:
        directory = self.evals_dir(base)
        return directory.is_dir() and any(directory.glob("*.jsonl"))

    # --- isolation --------------------------------------------------------

    def contains(self, path: Any, base: str = DEFAULT_DATA_ROOT) -> bool:
        """Is this path inside the tenant's own directory?"""
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError):
            return False
        root = self.data_root(base)
        return resolved == root or root in resolved.parents

    def assert_contains(self, path: Any, base: str = DEFAULT_DATA_ROOT) -> Path:
        """Refuse a path outside this tenant. Raises rather than returning False.

        Returning a boolean invites a caller to forget the check. A cross-tenant
        read of a municipal archive is the kind of incident that ends a project,
        so this fails closed and loudly.
        """
        if not self.contains(path, base):
            raise IsolationError(
                f"{path} is outside tenant {self.tenant_id!r}'s data directory. "
                f"This is refused rather than logged, because reading another "
                f"community's records is not a recoverable mistake."
            )
        return Path(path).resolve()

    def to_public(self, base: str = DEFAULT_DATA_ROOT) -> Dict[str, Any]:
        """What a resident may see about this tenant."""
        return {
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "community": self.community,
            "display_name": self.branding.display_name,
            "tagline": self.branding.tagline,
            "primary_color": self.branding.primary_color,
            "logo_url": self.branding.logo_url,
            "operator": self.branding.operator,
            "contact": self.branding.contact,
            "hostnames": self.hostnames,
            "path_prefix": self.path_prefix,
            "governance": {
                "own_constitution": self.has_own_constitution(base),
                "own_evaluation_set": self.has_own_evals(base),
            },
        }

    def to_stored(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


# --- the registry ---------------------------------------------------------


class TenantRegistry:
    """Every community this deployment serves."""

    def __init__(self, tenants: Optional[Iterable[Tenant]] = None,
                 data_root: str = DEFAULT_DATA_ROOT,
                 single_tenant: bool = True) -> None:
        self._tenants: Dict[str, Tenant] = {}
        self._by_host: Dict[str, str] = {}
        self._by_prefix: Dict[str, str] = {}
        self.data_root = data_root
        # A deployment with no tenants file is one community, which is the
        # common case and must keep working with no configuration at all.
        self.single_tenant = single_tenant
        self._lock = threading.Lock()
        self.problems: List[str] = []

        for tenant in tenants or []:
            self.register(tenant)

    def register(self, tenant: Tenant) -> None:
        with self._lock:
            if tenant.tenant_id in self._tenants:
                raise TenancyError(f"duplicate tenant id {tenant.tenant_id!r}")
            self._tenants[tenant.tenant_id] = tenant

            for host in tenant.hostnames:
                existing = self._by_host.get(host)
                if existing and existing != tenant.tenant_id:
                    raise TenancyError(
                        f"hostname {host!r} is claimed by both {existing!r} and "
                        f"{tenant.tenant_id!r}. A hostname must identify exactly "
                        f"one community."
                    )
                self._by_host[host] = tenant.tenant_id

            if tenant.path_prefix:
                prefix = "/" + tenant.path_prefix.strip("/")
                existing = self._by_prefix.get(prefix)
                if existing and existing != tenant.tenant_id:
                    raise TenancyError(
                        f"path prefix {prefix!r} is claimed by both {existing!r} "
                        f"and {tenant.tenant_id!r}"
                    )
                self._by_prefix[prefix] = tenant.tenant_id

    # --- lookup -----------------------------------------------------------

    def get(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get((tenant_id or "").strip().lower())

    def by_project(self, project_id: str) -> Optional[Tenant]:
        for tenant in self._tenants.values():
            if tenant.project_id == project_id:
                return tenant
        return None

    def by_hostname(self, host: str) -> Optional[Tenant]:
        if not host:
            return None
        host = host.split(":")[0].strip().lower()
        tenant_id = self._by_host.get(host)
        if tenant_id:
            return self._tenants.get(tenant_id)

        # A wildcard entry like "*.civicai.org" lets a deployment add a
        # community by creating its directory, with no config change.
        for pattern, candidate in self._by_host.items():
            if pattern.startswith("*.") and host.endswith(pattern[1:]):
                return self._tenants.get(candidate)
        return None

    def by_path(self, path: str) -> Tuple[Optional[Tenant], str]:
        """Match a path prefix. Returns the tenant and the remaining path."""
        if not path:
            return None, path
        normalized = "/" + path.lstrip("/")
        for prefix, tenant_id in sorted(self._by_prefix.items(),
                                        key=lambda kv: len(kv[0]), reverse=True):
            if normalized == prefix or normalized.startswith(prefix + "/"):
                return self._tenants.get(tenant_id), normalized[len(prefix):] or "/"
        return None, path

    def resolve(self, hostname: str = "", path: str = "",
                explicit: str = "", project_id: str = "") -> Optional[Tenant]:
        """Identify the community a request belongs to.

        Order matters. An explicit tenant header is the most specific signal and
        wins; hostname is next, because that is how a community's residents
        actually arrive; a path prefix serves deployments on one domain.
        """
        if explicit:
            tenant = self.get(explicit)
            if tenant:
                return tenant
        if project_id:
            tenant = self.by_project(project_id)
            if tenant:
                return tenant
        if hostname:
            tenant = self.by_hostname(hostname)
            if tenant:
                return tenant
        if path:
            tenant, _ = self.by_path(path)
            if tenant:
                return tenant

        # One community on this deployment: every request is theirs.
        if self.single_tenant and len(self._tenants) == 1:
            return next(iter(self._tenants.values()))
        return None

    def all(self, enabled_only: bool = True) -> List[Tenant]:
        return [t for t in self._tenants.values() if t.enabled or not enabled_only]

    def __len__(self) -> int:
        return len(self._tenants)

    def to_public(self) -> Dict[str, Any]:
        return {
            "tenant_count": len(self._tenants),
            "single_tenant": self.single_tenant and len(self._tenants) <= 1,
            "tenants": [t.to_public(self.data_root) for t in self.all()],
            "problems": self.problems,
        }


# --- loading --------------------------------------------------------------


def _tenant_from_dict(raw: Dict[str, Any]) -> Tenant:
    branding = TenantBranding(**{
        k: v for k, v in (raw.get("branding") or {}).items()
        if k in TenantBranding.__dataclass_fields__  # type: ignore[attr-defined]
    })
    quota = TenantQuota(**{
        k: v for k, v in (raw.get("quota") or {}).items()
        if k in TenantQuota.__dataclass_fields__  # type: ignore[attr-defined]
    })
    return Tenant(
        tenant_id=str(raw.get("id") or raw.get("tenant_id") or ""),
        project_id=str(raw.get("project_id") or ""),
        community=str(raw.get("community") or ""),
        hostnames=list(raw.get("hostnames") or []),
        path_prefix=str(raw.get("path_prefix") or ""),
        branding=branding,
        quota=quota,
        enabled=bool(raw.get("enabled", True)),
        admins=list(raw.get("admins") or []),
        created_at=str(raw.get("created_at") or ""),
        notes=str(raw.get("notes") or ""),
    )


def load_registry(path: Optional[str] = None,
                  data_root: str = DEFAULT_DATA_ROOT,
                  discover: bool = True) -> TenantRegistry:
    """Build the registry from tenants.yaml, then from projects on disk.

    A deployment with no tenants file still gets a working registry: every
    project directory becomes a tenant serving itself. That keeps a single
    community running with zero configuration, which is the setup most
    communities will have and the one that must never require reading this file.
    """
    registry = TenantRegistry(data_root=data_root)
    config_path = Path(path or TENANTS_FILE)

    configured: List[str] = []
    if config_path.is_file():
        try:
            import yaml
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except ImportError:
            registry.problems.append(
                "PyYAML is not installed, so tenants.yaml was skipped. "
                "Install it with: pip install pyyaml"
            )
            data = {}
        except Exception as exc:
            registry.problems.append(f"{config_path} could not be read: {exc}")
            data = {}

        registry.single_tenant = bool(data.get("single_tenant", False))
        for entry in data.get("tenants", []) or []:
            try:
                tenant = _tenant_from_dict(entry)
                registry.register(tenant)
                configured.append(tenant.project_id)
            except TenancyError as exc:
                registry.problems.append(str(exc))

    if discover:
        root = Path(data_root)
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if not (child / "config.json").is_file():
                    continue
                project_id = child.name
                if project_id in configured:
                    continue
                if not _SLUG_RE.match(project_id.lower()):
                    registry.problems.append(
                        f"project directory {project_id!r} is not a usable tenant id"
                    )
                    continue
                community = ""
                try:
                    config = json.loads((child / "config.json").read_text(encoding="utf-8"))
                    community = config.get("municipality_name", "")
                except (OSError, json.JSONDecodeError):
                    pass
                try:
                    registry.register(Tenant(
                        tenant_id=project_id.lower(),
                        project_id=project_id,
                        community=community,
                        notes="discovered from the data directory",
                    ))
                except TenancyError as exc:
                    registry.problems.append(str(exc))

    return registry


# --- per-tenant governance -------------------------------------------------


def tenant_constitution(tenant: Tenant, version: str = "latest",
                        data_root: str = DEFAULT_DATA_ROOT):
    """Load the constitution governing one community.

    A tenant's own constitution wins. The repository's is a fallback, and when
    it is used the result says so through ``origin``, because a resident asking
    whose rules govern an answer must never get an ambiguous reply.
    """
    from community.constitution import load_constitution

    own = tenant.constitution_dir(data_root)
    if tenant.has_own_constitution(data_root):
        return load_constitution(version=version, directory=own)

    constitution = load_constitution(version=version)
    if constitution:
        constitution.ledger_problems = list(constitution.ledger_problems) + [
            f"{tenant.branding.display_name} has not adopted its own constitution; "
            f"this deployment's default is in force. A community running on shared "
            f"infrastructure should adopt its own rules."
        ]
    return constitution


def tenant_eval_files(tenant: Tenant, data_root: str = DEFAULT_DATA_ROOT) -> List[str]:
    """The evaluation set that defines 'good' for this community.

    Falls back to the shipped seed set, which is explicitly a starting point.
    Two communities sharing an evaluation set are not really separate
    deployments, so this is worth surfacing in the console.
    """
    own = tenant.evals_dir(data_root)
    if tenant.has_own_evals(data_root):
        return sorted(str(p) for p in own.glob("*.jsonl"))

    repo_evals = Path(__file__).resolve().parent / "evals"
    return sorted(str(p) for p in repo_evals.glob("*.jsonl"))


def scaffold_tenant(tenant: Tenant, data_root: str = DEFAULT_DATA_ROOT,
                    copy_constitution: bool = True) -> Dict[str, Any]:
    """Create a community's own governance directories.

    Copying the default constitution in rather than symlinking it is deliberate.
    The copy is theirs to amend, and the moment they amend it their ledger
    diverges from everyone else's, which is exactly what is supposed to happen.
    """
    created: List[str] = []
    root = tenant.data_root(data_root)

    for directory in (root, tenant.constitution_dir(data_root),
                      tenant.evals_dir(data_root), tenant.logs_dir(data_root)):
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(str(directory))

    if copy_constitution and not tenant.has_own_constitution(data_root):
        source_dir = Path(__file__).resolve().parent / "constitution"
        target_dir = tenant.constitution_dir(data_root)
        for name in ("constitution-v1.0.md", "governance.md", "changelog.md",
                     "signers.json"):
            source = source_dir / name
            target = target_dir / name
            if source.is_file() and not target.exists():
                target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                created.append(str(target))

    return {
        "tenant_id": tenant.tenant_id,
        "created": created,
        "next_steps": [
            f"Edit data/{tenant.project_id}/constitution/constitution-v1.0.md "
            f"with {tenant.branding.display_name}'s own rules.",
            f"Seal it: python3 -m community.ledger seal 1.0 "
            f"--directory data/{tenant.project_id}/constitution",
            f"Write evaluation questions against "
            f"{tenant.branding.display_name}'s own records in "
            f"data/{tenant.project_id}/evals/.",
        ],
    }


def _cmd_list(registry: TenantRegistry) -> int:
    print(f"{len(registry)} community/communities on this deployment")
    print()
    if not registry.all():
        print("  none yet. Create a project, or copy tenants.example.yaml.")
        return 0
    print(f"  {'id':<18}{'community':<24}{'hostnames':<30}{'governance'}")
    print("  " + "-" * 86)
    for tenant in registry.all():
        own = "own rules" if tenant.has_own_constitution(registry.data_root) \
            else "deployment default"
        evals = "own evals" if tenant.has_own_evals(registry.data_root) else "seed evals"
        hosts = ", ".join(tenant.hostnames) or "-"
        print(f"  {tenant.tenant_id:<18}{(tenant.community or '-')[:22]:<24}"
              f"{hosts[:28]:<30}{own}, {evals}")
    for problem in registry.problems:
        print(f"\n  problem: {problem}")
    return 0


def _cmd_scaffold(registry: TenantRegistry, tenant_id: str) -> int:
    tenant = registry.get(tenant_id)
    if not tenant:
        print(f"no such community: {tenant_id!r}")
        print(f"known: {', '.join(t.tenant_id for t in registry.all()) or 'none'}")
        return 1

    result = scaffold_tenant(tenant, registry.data_root)
    print(f"Gave {tenant.branding.display_name} its own governance directories.")
    for path in result["created"]:
        print(f"  created {path}")
    if not result["created"]:
        print("  nothing to do; it already has them")
    print()
    print("Next:")
    for step in result["next_steps"]:
        print(f"  - {step}")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Communities served by this deployment.")
    parser.add_argument("--tenants-file", default=None)
    parser.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="show every community (the default)")
    scaffold = sub.add_parser(
        "scaffold", help="give a community its own constitution and evaluation set")
    scaffold.add_argument("tenant_id")

    args = parser.parse_args()
    reg = load_registry(path=args.tenants_file, data_root=args.data_root)

    if args.command == "scaffold":
        raise SystemExit(_cmd_scaffold(reg, args.tenant_id))
    raise SystemExit(_cmd_list(reg))
