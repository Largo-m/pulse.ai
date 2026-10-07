---
name: security-audit
description: >-
  Single security toolkit for this repo — static analysis of Python (SAST),
  hardcoded-secret scanning, vulnerable/unpinned dependency audit,
  prompt-injection red-teaming of LLM prompts, HTTP security headers, CORS,
  JWT inspection and Dockerfile linting. Use when the user asks to "run a
  security review / audit", "scan for vulnerabilities", "find secrets / leaked
  keys", "check dependencies", "test for prompt injection", "check headers /
  CORS", "decode / audit a JWT", "review my Dockerfile", or before merging code
  that touches subprocess, SQL, file paths, the HTTP API, agent prompts or
  dependencies.
license: MIT
---

# Security Audit

Eight dependency-free (stdlib only) scanners in one skill. Pick the tool by
what changed, run it, then **verify every finding by reading the code** —
these are fast, high-signal triage tools, not verdicts.

Origin: [NovaCode37/claude-security-skills](https://github.com/NovaCode37/claude-security-skills) (MIT).

All commands run from the repo root. `T=.claude/skills/security-audit/tools`.

## 1. Pick the tool

| What changed / what was asked | Tool | Priority for Pulse |
|---|---|---|
| Python code touching `subprocess`, SQL, parsing, files, crypto | `sast-lite` | **high** |
| Before commit, before making the repo public, suspected leak | `secret-scanner` | **high** |
| `pyproject.toml` / `requirements*.txt` / `package.json` | `dependency-check` | **high** |
| Factory prompts (`pulse/store/factory/`), agent instructions, outcome/approval parsing | `prompt-injection-tester` | **high** |
| Routes or middleware in `pulse/api/` exposed over HTTP | `http-sec-audit`, `cors-auditor` | low (daemon binds to `127.0.0.1`) |
| A JWT is handed to you | `jwt-inspector` | on demand |
| A `Dockerfile` is added or changed | `dockerfile-scan` | on demand |

"Full security review" = run the four **high** tools on the whole repo.

Every tool shares the same CLI contract: `--json` for machine output,
`--min-severity {critical,high,medium,low,info}` where supported, and exit codes
**`0` clean · `1` findings · `2` usage/IO error** — usable as a CI gate.

## 2. Tools

### sast-lite — Python static analysis (AST-based)

```bash
python $T/sast-lite/analyzer.py pulse/
python $T/sast-lite/analyzer.py pulse/ --json --min-severity high
python $T/sast-lite/analyzer.py pulse/ --sarif > sast.sarif
```

| Rule | CWE | Severity |
|---|---|---|
| `eval()` / `exec()` on dynamic input | CWE-95 | critical/high |
| `os.system` / `subprocess(shell=True)` | CWE-78 | high |
| `pickle` / `marshal` deserialization | CWE-502 | high |
| `yaml.load` without SafeLoader | CWE-20 | high |
| SQL via f-string / concat / `.format` / `%` | CWE-89 | high |
| `requests(verify=False)` | CWE-295 | high |
| Hardcoded password/secret literal | CWE-798 | high |
| `random` for token/password/OTP/nonce/salt | CWE-330 | high |
| Weak hash (md5/sha1) | CWE-327 | medium |
| `tempfile.mktemp` | CWE-377 | medium |
| `Flask(debug=True)` | CWE-489 | medium |
| Jinja2 `autoescape=False` | CWE-79 | medium |
| `assert` used for a security check | CWE-617 | medium |

Single-file, no cross-function taint tracking. For each hit open `path:line`
and confirm the value is actually attacker/agent-controllable. In Pulse, the
known dynamic-SQL sites (`store/agent_settings.py`, `store/factory/__init__.py`)
build identifiers from hard-coded allowlists and carry `# noqa: S608` — confirm
the allowlist still holds rather than reporting them blindly.

Fixes: parameterized queries; `yaml.safe_load`; list-form `subprocess` without
`shell=True`; `secrets` instead of `random`; `tempfile.mkstemp`.

### secret-scanner — hardcoded credentials

```bash
python $T/secret-scanner/engine.py .
python $T/secret-scanner/engine.py . --json
python $T/secret-scanner/engine.py . --include-tests     # tests are skipped by default
python $T/secret-scanner/engine.py src/ --min-entropy 3.0  # lower = more findings
python $T/secret-scanner/engine.py . --no-entropy         # vendor regexes only
```

Vendor regexes (AWS, GitHub, GCP, Stripe, OpenAI, Anthropic, Hugging Face,
Slack, …) plus Shannon-entropy gating for generic secrets. Output shows only a
**redacted** preview. Placeholders (`example`, `<your-key>`, `xxxx`,
`changeme`, `${ENV}`) are filtered; `.git`, `node_modules`, virtualenvs and
binaries are skipped.

Severity: **critical** live key material (rotate now) · **high** access key
IDs / API keys · **medium** generic `password=` · **low** JWTs, verify first.

A confirmed leak must be **rotated** — deleting the line doesn't un-leak git
history; if it was committed, also recommend `git filter-repo` / BFG.

### dependency-check — vulnerable and unpinned dependencies

```bash
python $T/dependency-check/checker.py .                    # auto-discovers manifests
python $T/dependency-check/checker.py requirements.txt --online   # live OSV.dev lookup
python $T/dependency-check/checker.py . --json --min-severity medium
python $T/dependency-check/checker.py . --no-unpinned
```

Reads `pyproject.toml`, `requirements*.txt` and `package.json`. Pulse declares
lower bounds only (`>=`), so every dependency shows up as unpinned — to audit
what is actually installed, also scan `.venv/bin/pip freeze > /tmp/req.txt`.
The bundled advisory DB is small; use `--online` for real coverage. Unpinned
ranges are reported as LOW and also fail the exit code unless `--no-unpinned`.

For each vulnerable package, give the **minimum fixed version** and the
breaking-change risk.

### prompt-injection-tester — red-team LLM prompts

```bash
python $T/prompt-injection-tester/attacker.py --list
python $T/prompt-injection-tester/attacker.py --list --category role-play
python $T/prompt-injection-tester/attacker.py --demo [--hardened] [--json]
```

Categories: `instruction-override` · `system-prompt-leak` · `role-play` ·
`delimiter-escape` · `encoding` · `data-exfiltration` · `refusal-suppression`.
A unique **canary** goes in the system prompt; a payload "wins" if the reply
hits a success marker or leaks the canary. Output: resilience score 0–100.

Against a real model, wrap it in a callable:

```python
import sys
sys.path.insert(0, ".claude/skills/security-audit/tools/prompt-injection-tester")
import attacker

def model(system_prompt: str, user_prompt: str) -> str:
    return my_llm_app(system=system_prompt, user=user_prompt)

results = attacker.run_suite(model)
print(attacker.summarize(results))

# offline scoring of a captured response
verdict = attacker.score_response(attacker.PAYLOADS[0], response_text, canary="CANARY-abc")
```

For Pulse the more important question is structural: agent output and files
are untrusted. Verify that only the fenced blocks Pulse defines
(`pulse:outcome`, approval questionnaire, fan-out list) are parsed, with strict
parsers, and that no agent text can change policy, config or which agent runs.
Detection is heuristic; ambiguous cases are flagged "review manually".

### http-sec-audit — HTTP security headers and cookies

```bash
python $T/http-sec-audit/audit.py https://example.com [--json] [--min-severity high]
python $T/http-sec-audit/audit.py --headers-file resp.txt      # offline
python $T/http-sec-audit/audit.py https://example.com --advisory  # + COOP/COEP/CORP, Cache-Control
```

Checks CSP, HSTS, `X-Content-Type-Options`, `X-Frame-Options` /
`frame-ancestors`, `Referrer-Policy`, `Permissions-Policy`, version banners
(`Server`, `X-Powered-By`), and cookie `Secure` / `HttpOnly` / `SameSite`.
Offer ready-to-paste header snippets for the stack in use.

### cors-auditor — CORS misconfiguration

```bash
python $T/cors-auditor/auditor.py https://api.example.com [--origin https://evil.example]
python $T/cors-auditor/auditor.py --headers-file resp.txt --origin https://evil.example
```

Flags `*` + credentials, reflected arbitrary `Origin` (critical with
credentials), `null` origin, wildcard origin/methods. Recommend an explicit
origin allowlist and dropping credentials where not needed.

### jwt-inspector — decode and audit a JWT

```bash
python $T/jwt-inspector/inspector.py "<token>" [--json] [--min-severity high]
echo "<token>" | python $T/jwt-inspector/inspector.py -
python $T/jwt-inspector/inspector.py "<token>" --secret-list wordlist.txt
```

Flags `alg=none`, HS* confusion risk, missing/excessive `exp`, future `iat`,
missing `nbf`/`iss`/`aud`/`sub`, and weak HMAC secrets (wordlist crack — a
weak-key detector, not a brute-forcer). Decoding ≠ verifying. A cracked secret
is compromised: rotate, prefer RS256/ES256.

### dockerfile-scan — insecure Dockerfile patterns

```bash
python $T/dockerfile-scan/scanner.py path/to/Dockerfile
python $T/dockerfile-scan/scanner.py . --json
```

Flags missing tag / `:latest`, running as root, `curl|wget … | sh`, remote
`ADD`, secrets in `ENV`/`ARG`, `chmod 777`, `sudo`. Offer a corrected snippet
(pinned base, non-root `USER`, `COPY` over remote `ADD`, runtime secrets).

## 3. Pulse checklist (things the scanners can't see)

Read the code for these whenever the related area changes:

- **Paths from agents/API** (`locations[].path`, `rawInput`, artifact paths)
  are resolved and confined to the run's workspace/worktree — no `..` or
  symlink escape before read/open/delete.
- **Git**: `worktree remove` never uses `--force`; branches are never deleted.
- **Subprocess** calls set `cwd` explicitly and have timeouts where they can hang.
- **Network**: TCP listener stays on `127.0.0.1`; the UDS socket in `~/.pulse`
  is user-only; no permissive CORS.
- **Permission policy**: `deny_writes` with an unknown kind asks, never allows;
  terminal/`execute` stays vetoed unless explicitly allowed.
- **Secrets**: `ANTHROPIC_API_KEY`, `CURSOR_API_KEY` and env contents never reach
  `run_events`, SSE, logs or error messages.
- **ACP adapter** stays pinned (`@agentclientprotocol/claude-agent-acp@x.y.z`).

## 4. Report

1. Run the relevant tools with `--json`.
2. Confirm each finding at `path:line`; drop false positives with the reason.
3. Group confirmed findings by severity (critical → low), each with CWE when
   available, the concrete exploit path, and a one-line fix.
4. List what was **not** checked (tools not run, areas not reviewed).

Only scan URLs, tokens and systems the user owns or is authorized to test.
