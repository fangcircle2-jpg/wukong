"""
Command risk analyzer.

Classifies shell commands into risk levels (SAFE / MODERATE / DANGEROUS)
using pattern matching rules. Supports chained and piped commands.
"""

import re
import shlex

from wukong.core.sandbox.models import RiskAssessment, RiskLevel

_RISK_SEVERITY: dict[RiskLevel, int] = {
    RiskLevel.SAFE: 0,
    RiskLevel.MODERATE: 1,
    RiskLevel.DANGEROUS: 2,
}

# ---------------------------------------------------------------------------
# Pattern tables
# ---------------------------------------------------------------------------

DANGEROUS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brm\s+.*-.*[rR].*f", re.S), "recursive force delete"),
    (re.compile(r"\brm\s+-rf\s+/\s*$"), "rm -rf /"),
    (re.compile(r"\bsudo\b"), "sudo usage"),
    (re.compile(r"\bchmod\s+[0-7]*[sS]"), "setuid/setgid chmod"),
    (re.compile(r"\bchmod\s+[2467]\d{3}\b"), "numeric setuid/setgid chmod"),
    (re.compile(r"\bchown\b"), "ownership change"),
    (re.compile(r"\bmkfs\b"), "filesystem format"),
    (re.compile(r"\bdd\b\s+"), "raw disk operation"),
    (re.compile(r">\s*/dev/"), "write to device"),
    (re.compile(r">\s*/etc/"), "write to /etc"),
    (re.compile(r">\s*/proc/"), "write to /proc"),
    (re.compile(r"\bcurl\b.*\|\s*(ba)?sh"), "pipe remote script to shell"),
    (re.compile(r"\bwget\b.*\|\s*(ba)?sh"), "pipe remote script to shell"),
    (re.compile(r":\(\)\s*\{.*\|.*&\s*\}\s*;"), "fork bomb"),
    (re.compile(r"\bkill\s+-9\b"), "force kill"),
    (re.compile(r"\bkillall\b"), "killall"),
    (re.compile(r"\bshutdown\b"), "system shutdown"),
    (re.compile(r"\breboot\b"), "system reboot"),
    (re.compile(r"\bsystemctl\s+(stop|disable|mask)\b"), "systemctl stop/disable"),
    (re.compile(r"\biptables\b"), "firewall modification"),
    (re.compile(r"\bufw\b"), "firewall modification"),
    (re.compile(r"\bpasswd\b"), "password change"),
    (re.compile(r"\buseradd\b"), "user creation"),
    (re.compile(r"\buserdel\b"), "user deletion"),
    (re.compile(r"\beval\b.*\$"), "eval with variable expansion"),
    (re.compile(r"\bexport\s+(PATH|LD_PRELOAD|LD_LIBRARY_PATH)\s*="), "critical env override"),
]

MODERATE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brm\b"), "file deletion"),
    (re.compile(r"\bmv\b"), "file move/rename"),
    (re.compile(r"\bchmod\b"), "permission change"),
    (re.compile(r"\bgit\s+(push|reset|rebase|merge|checkout)\b"), "git write operation"),
    (re.compile(r"\bnpm\s+(install|uninstall|update|publish)\b"), "npm write operation"),
    (re.compile(r"\bpip\s+(install|uninstall)\b"), "pip write operation"),
    (re.compile(r"\bcargo\s+(install|publish)\b"), "cargo write operation"),
    (re.compile(r"\bapt(-get)?\s+(install|remove|purge)\b"), "apt package operation"),
    (re.compile(r"\byum\s+(install|remove)\b"), "yum package operation"),
    (re.compile(r"\bcurl\b"), "network download"),
    (re.compile(r"\bwget\b"), "network download"),
    (re.compile(r"\bdocker\s+(rm|rmi|stop|kill|prune)\b"), "docker destructive"),
    (re.compile(r"\bmkdir\b"), "directory creation"),
    (re.compile(r"\bcp\b"), "file copy"),
    (re.compile(r"\btar\s+.*x"), "archive extraction"),
    (re.compile(r"\bunzip\b"), "archive extraction"),
    (re.compile(r">\s*\S+"), "file output redirection"),
    (re.compile(r">>\s*\S+"), "file append redirection"),
    (re.compile(r"\bsed\s+-i\b"), "in-place file edit"),
]

SAFE_PREFIXES: list[str] = [
    "ls", "dir", "cat", "head", "tail", "less", "more",
    "echo", "printf", "pwd", "whoami", "id", "uname",
    "date", "cal", "uptime",
    "wc", "sort", "uniq", "tr", "cut", "awk", "grep", "rg", "ag",
    "find", "locate", "which", "whereis", "type", "file",
    "env", "printenv", "set",
    "git status", "git log", "git diff", "git show", "git branch",
    "git remote -v", "git tag",
    "python --version", "python3 --version", "node --version",
    "npm --version", "pip --version", "cargo --version",
    "docker ps", "docker images", "docker version",
    "df", "du", "free", "top", "htop", "ps",
    "tree", "stat", "realpath", "basename", "dirname",
]

# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

_CHAIN_SPLIT_RE = re.compile(r"\s*(?:&&|\|\|?|;)\s*")


class RiskAnalyzer:
    """Stateless command risk analyzer.

    Splits chained/piped commands and returns the highest risk level found.
    """

    def analyze(self, command: str) -> RiskAssessment:
        cmd = command.strip()
        if not cmd:
            return RiskAssessment(level=RiskLevel.SAFE, reason="empty command")

        # Check the full (unsplit) command first for cross-subcommand
        # patterns like "curl ... | sh" where the pipe is significant.
        for pattern, reason in DANGEROUS_PATTERNS:
            if pattern.search(cmd):
                return RiskAssessment(
                    level=RiskLevel.DANGEROUS,
                    reason=reason,
                    matched_pattern=pattern.pattern,
                )

        sub_commands = _CHAIN_SPLIT_RE.split(cmd)
        worst = RiskAssessment(level=RiskLevel.SAFE, reason="no risky pattern found")

        for sub in sub_commands:
            sub = sub.strip()
            if not sub:
                continue
            assessment = self._analyze_single(sub)
            if _RISK_SEVERITY[assessment.level] > _RISK_SEVERITY[worst.level]:
                worst = assessment
            if worst.level == RiskLevel.DANGEROUS:
                break

        return worst

    # ------------------------------------------------------------------

    def _analyze_single(self, command: str) -> RiskAssessment:
        for pattern, reason in DANGEROUS_PATTERNS:
            if pattern.search(command):
                return RiskAssessment(
                    level=RiskLevel.DANGEROUS,
                    reason=reason,
                    matched_pattern=pattern.pattern,
                )

        for pattern, reason in MODERATE_PATTERNS:
            if pattern.search(command):
                return RiskAssessment(
                    level=RiskLevel.MODERATE,
                    reason=reason,
                    matched_pattern=pattern.pattern,
                )

        base_cmd = self._extract_base_command(command)
        for prefix in SAFE_PREFIXES:
            if command.startswith(prefix) or base_cmd == prefix.split()[0]:
                return RiskAssessment(
                    level=RiskLevel.SAFE,
                    reason=f"matches safe prefix: {prefix}",
                )

        return RiskAssessment(
            level=RiskLevel.MODERATE,
            reason="unknown command defaults to moderate",
        )

    @staticmethod
    def _extract_base_command(command: str) -> str:
        """Extract the first token as the base command name."""
        try:
            tokens = shlex.split(command)
            return tokens[0] if tokens else ""
        except ValueError:
            return command.split()[0] if command.split() else ""
