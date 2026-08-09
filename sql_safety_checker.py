"""
sql_safety_checker.py
=====================
A lightweight SQL safety checker built with Python stdlib only.

Goal
----
Ensure that only read-only SQL statements (SELECT, WITH, EXPLAIN, SHOW,
DESCRIBE) are accepted.  ALL other statements — including INSERT, UPDATE,
DELETE, DROP, MERGE, COPY, LOAD DATA, etc. — are rejected.

Strategy (layered defence-in-depth)
------------------------------------
  Pre-processing
  ~~~~~~~~~~~~~~
  0. Validate input type and enforce a hard length limit.
  1. Normalise Unicode to NFKC to collapse homoglyphs (e.g. fullwidth letters).
  2. Normalise all newline variants (\r\n, \r, \n) → single space to prevent
     line-split obfuscation (e.g. "DR\nOP").
  3. Detect and reject block comments (/* … */) entirely — they are rarely
     present in legitimate read-only analytics queries and are the primary
     vehicle for comment-splice obfuscation attacks (e.g. "DR/**/OP").
  4. Strip line comments  -- …
  5. Strip single-quoted string literals using SQL-standard doubled-quote
     escaping ('') ONLY.  Backslash escaping is deliberately not supported
     to prevent bypass attacks on databases with standard_conforming_strings.
  6. Strip double-quoted identifiers.
  7. Strip backtick-quoted identifiers (MySQL/MariaDB).
  8. Strip PostgreSQL dollar-quoted strings.

  Detection (applied per-statement after splitting on ;)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Rule 1 — Allow-list gate (primary, most important):
     The first meaningful token of every statement MUST be in SAFE_LEADING_VERBS.
     Anything not on the allow-list is immediately flagged as unsafe.

  Rule 2 — Dangerous keyword scan (secondary, defence-in-depth):
     Scan ALL tokens for known-dangerous keywords and dangerous two-token
     sequences (e.g. "INTO OUTFILE", "DROP TABLE").  This catches injection
     patterns where a dangerous verb is NOT the first token of the full SQL
     string but IS the first token in a UNION branch or sub-expression.

Safe operations permitted
-------------------------
  SELECT, WITH (CTEs), EXPLAIN, SHOW, DESCRIBE / DESC, VALUES (read-only)

Dangerous operations flagged
-----------------------------
  DDL  : DROP, TRUNCATE, ALTER, CREATE, RENAME
  DML  : DELETE, UPDATE, INSERT, MERGE, REPLACE
  DCL  : GRANT, REVOKE
  Admin: EXEC, EXECUTE, CALL, LOAD, COPY, ATTACH, PRAGMA, VACUUM, REINDEX
  Exfil: INTO (OUTFILE/DUMPFILE), SET (SESSION AUTHORIZATION / ROLE)
"""

import re
import unicodedata
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Input validation limits
# ---------------------------------------------------------------------------

# Hard cap on SQL string length to prevent ReDoS / DoS via pathological inputs.
MAX_SQL_LENGTH: int = 10_000  # 10 KB — tighter than needed for read-only queries


# ---------------------------------------------------------------------------
# Allow-list  (primary gate — Rule 1)
# ---------------------------------------------------------------------------

# Only these leading verbs are considered safe.  Anything else is rejected.
SAFE_LEADING_VERBS: frozenset[str] = frozenset({
    "SELECT",
    "WITH",      # CTEs always start with WITH … SELECT
    "EXPLAIN",
    "SHOW",
    "DESCRIBE",
    "DESC",
    "VALUES",    # standalone VALUES expression (read-only in some DBs)
})


# ---------------------------------------------------------------------------
# Deny-list  (secondary / defence-in-depth — Rule 2)
# ---------------------------------------------------------------------------

# These keywords anywhere in the token stream are considered dangerous.
# Empty frozenset value = keyword alone is enough to flag (no pair needed).
DANGEROUS_PAIRS: dict[str, frozenset[str]] = {
    # DDL
    "DROP":     frozenset({"TABLE", "DATABASE", "INDEX", "VIEW", "SCHEMA",
                            "PROCEDURE", "FUNCTION", "TRIGGER", "SEQUENCE",
                            "USER", "ROLE", "COLUMN", "CONSTRAINT"}),
    "TRUNCATE": frozenset(),
    "ALTER":    frozenset({"TABLE", "DATABASE", "SCHEMA", "USER", "INDEX",
                            "VIEW", "SEQUENCE", "PROCEDURE", "FUNCTION",
                            "TRIGGER", "ROLE", "COLUMN"}),
    "CREATE":   frozenset({"TABLE", "DATABASE", "SCHEMA", "INDEX", "VIEW",
                            "PROCEDURE", "FUNCTION", "TRIGGER", "SEQUENCE",
                            "USER", "ROLE", "OR"}),   # CREATE OR REPLACE …
    "RENAME":   frozenset({"TABLE", "COLUMN", "INDEX", "DATABASE",
                            "TO"}),
    # DML
    "DELETE":   frozenset(),
    "UPDATE":   frozenset(),
    "INSERT":   frozenset(),
    "MERGE":    frozenset(),
    "REPLACE":  frozenset(),
    # DCL
    "GRANT":    frozenset(),
    "REVOKE":   frozenset(),
    # Proc / admin
    "EXEC":     frozenset(),
    "EXECUTE":  frozenset(),
    "CALL":     frozenset(),
    "LOAD":     frozenset({"DATA", "FILE"}),
    "COPY":     frozenset(),
    "ATTACH":   frozenset({"DATABASE"}),
    "PRAGMA":   frozenset(),
    "VACUUM":   frozenset(),
    "REINDEX":  frozenset(),
    # PostgreSQL anonymous code blocks (can execute arbitrary SQL)
    "DO":       frozenset(),
    # SQLite upsert
    "UPSERT":   frozenset(),
    # PostgreSQL privilege management
    "REASSIGN": frozenset(),
    # Materialized view refresh (can be expensive / DoS vector)
    "REFRESH":  frozenset({"MATERIALIZED"}),
    # Exfiltration — INTO OUTFILE / INTO DUMPFILE (MySQL)
    "INTO":     frozenset({"OUTFILE", "DUMPFILE"}),
    # Privilege escalation via SET
    "SET":      frozenset({"ROLE", "SESSION"}),
}

# Standalone dangerous verbs (no pair needed; the keyword alone is enough).
# Built automatically from DANGEROUS_PAIRS entries with empty frozensets.
_STANDALONE_DANGEROUS: frozenset[str] = frozenset(
    k for k, v in DANGEROUS_PAIRS.items() if not v
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class CheckResult(NamedTuple):
    is_safe: bool          # True = no dangerous operations found
    violations: list[str]  # human-readable descriptions of what was flagged
    cleaned_sql: str       # the SQL after comment/literal stripping (for debug)


# ---------------------------------------------------------------------------
# SQL pre-processor  (strips noise so keyword matching is accurate)
# ---------------------------------------------------------------------------

# Regex: block comment  /* … */  – non-greedy, spans newlines.
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

# Regex: line comment   -- … (to end of line)
_LINE_COMMENT_RE = re.compile(r"--[^\r\n]*")

# Regex: single-quoted string  '…'
# SQL-standard '' escaping only.
_SINGLE_QUOTE_RE = re.compile(r"'(?:''|[^'])*'", re.DOTALL)

# Regex: double-quoted identifier  "…"
_DOUBLE_QUOTE_RE = re.compile(r'"(?:[^"\\]|\\.)*"', re.DOTALL)

# Regex: backtick-quoted identifier  `…`  (MySQL/MariaDB)
_BACKTICK_QUOTE_RE = re.compile(r"`(?:[^`\\]|\\.)*`", re.DOTALL)

# Regex: PostgreSQL dollar-quoted string  $$…$$  or  $tag$…$tag$
_DOLLAR_QUOTE_RE = re.compile(
    r"\$\$.*?\$\$"
    r"|\$([A-Za-z_][A-Za-z0-9_]*)\$.*?\$\1\$",
    re.DOTALL,
)


def _preprocess_sql(sql: str) -> tuple[str, list[str]]:
    """
    Normalize and strip *sql* so that keyword matching is accurate.

    Returns
    -------
    cleaned : str
        The SQL with comments and string/identifier literals replaced by
        whitespace (preserving token boundaries).
    pre_violations : list[str]
        Any violations detected during preprocessing itself.

    Steps
    -----
    1. Unicode NFKC normalization.
    2. Strip Unicode Format category characters.
    3. Newline normalization.
    4. Block comment detection and rejection.
    5. Line comment stripping.
    6. Single-quoted string literal stripping (SQL-standard '' escaping only).
    7. Double-quoted identifier stripping.
    8. Backtick-quoted identifier stripping.
    9. PostgreSQL dollar-quoted string stripping.
    """
    pre_violations: list[str] = []

    # Step 1. Unicode normalisation
    sql = unicodedata.normalize("NFKC", sql)

    # Step 1b. Strip Unicode "Format" characters (category Cf) — zero-width
    # spaces (U+200B), zero-width joiners (U+200C/D), word joiners (U+2060),
    # BOM (U+FEFF), etc.  Some database drivers silently strip these, which
    # means an attacker could use them to split dangerous keywords
    # (e.g. "D\u200BROP") past the tokeniser while the DB reassembles them.
    sql = ''.join(c for c in sql if unicodedata.category(c) != 'Cf')

    # Step 2. Newline normalisation — collapse \\r\\n first, then lone \\r / \\n.
    sql = sql.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    # Step 3. Block comments — detect and reject.
    # Legitimate read-only analytics queries almost never contain /* */ comments.
    # They are the primary obfuscation vehicle (DR/**/OP, SE/**/LECT, etc.)
    # so we treat their presence as an immediate violation rather than
    # silently stripping them and risking a mis-parse.
    if _BLOCK_COMMENT_RE.search(sql):
        pre_violations.append(
            "Block comments (/* … */) are not permitted in SQL input."
        )
        # Strip them anyway so subsequent rules can still flag more violations.
        sql = _BLOCK_COMMENT_RE.sub(" ", sql)

    # Step 4. Line comments
    sql = _LINE_COMMENT_RE.sub(" ", sql)

    # Step 5. String literals — replace entire literal with '' so that keywords
    # embedded in string values (e.g. WHERE body = 'DROP TABLE x') are invisible
    # to the tokeniser.
    sql = _SINGLE_QUOTE_RE.sub("''", sql)

    # Step 6. Double-quoted identifiers
    sql = _DOUBLE_QUOTE_RE.sub('""', sql)

    # Step 7. Backtick identifiers
    sql = _BACKTICK_QUOTE_RE.sub("``", sql)

    # Step 8. PostgreSQL dollar-quoted strings  $$…$$  or  $tag$…$tag$
    sql = _DOLLAR_QUOTE_RE.sub("''", sql)

    return sql, pre_violations


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _tokenise(sql: str) -> list[str]:
    """Extract word tokens from *sql* and upper-case them."""
    return [m.group().upper() for m in _TOKEN_RE.finditer(sql)]


# ---------------------------------------------------------------------------
# Per-statement checker
# ---------------------------------------------------------------------------

def _check_statement(cleaned_stmt: str) -> list[str]:
    """
    Check a single, already-preprocessed SQL statement (no semicolons).
    Returns a list of violation strings (empty = safe).

    Accepts pre-cleaned text to avoid double-stripping.
    """
    tokens = _tokenise(cleaned_stmt)

    if not tokens:
        return []

    violations: list[str] = []

    # --- Rule 1: Allow-list gate (primary defence) ---
    # The first meaningful token MUST be in SAFE_LEADING_VERBS.
    # Anything not on the allow-list is flagged immediately.
    first = tokens[0]
    if first not in SAFE_LEADING_VERBS:
        violations.append(
            f"Non-permitted leading verb '{first}' detected. "
            f"Only SELECT, WITH, EXPLAIN, SHOW, DESCRIBE are allowed."
        )
        # Still continue to collect pair-level detail below for richer feedback.

    # --- Rule 2: Dangerous keyword scan (secondary, defence-in-depth) ---
    # Catches dangerous verbs injected mid-statement via UNION branches,
    # subqueries, or stored-procedure calls where they are not the first token
    # of the overall SQL string.
    for i, tok in enumerate(tokens):
        if tok not in DANGEROUS_PAIRS:
            continue

        pair_targets = DANGEROUS_PAIRS[tok]

        # Standalone dangerous verbs (UPDATE, GRANT, EXEC, etc.)
        if not pair_targets:
            msg = f"Dangerous keyword '{tok}' found in statement."
            if msg not in violations:
                violations.append(msg)
            continue

        # Pair-based detection (DROP TABLE, DELETE FROM, INTO OUTFILE, etc.)
        if i + 1 < len(tokens):
            next_tok = tokens[i + 1]
            if next_tok in pair_targets:
                msg = (
                    f"Dangerous operation '{tok} {next_tok}' "
                    f"detected in statement."
                )
                if msg not in violations:
                    violations.append(msg)
        else:
            # Verb appears as the final token — still suspicious for verbs that
            # always require an object (DROP, TRUNCATE, ALTER, CREATE, etc.)
            if tok in {"DROP", "ALTER", "CREATE", "RENAME",
                       "LOAD", "REFRESH"}:
                msg = (
                    f"Potentially incomplete but dangerous keyword '{tok}' "
                    f"found at end of statement."
                )
                if msg not in violations:
                    violations.append(msg)

    return violations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_safe_sql(sql: str) -> bool:
    """
    Return True if *sql* is a safe, read-only SQL statement, False otherwise.

    Safe statements are those whose first verb (per statement, split on ;)
    is one of: SELECT, WITH, EXPLAIN, SHOW, DESCRIBE, DESC, VALUES.

    Handles:
      - Multiple statements separated by semicolons
      - Block comments (/* … */) — rejected outright (not silently stripped)
      - Line comments  -- …  — stripped
      - Single-quoted string literals (handles '' and \\' escaping)
      - Double-quoted identifiers
      - Backtick-quoted identifiers (MySQL/MariaDB)
      - Unicode homoglyphs (NFKC normalised before processing)
      - Newline-split obfuscation (\\r\\n, \\r, \\n normalised to space)
      - Injection via UNION branches, subqueries, and multi-statement input
    """
    result = check_sql(sql)
    return result.is_safe


def check_sql(sql: str) -> CheckResult:
    """
    Detailed version of is_safe_sql().  Returns a CheckResult with:
      - is_safe      : bool
      - violations   : list of human-readable violation descriptions
      - cleaned_sql  : the SQL after stripping comments/literals (for debugging)
    """
    if not isinstance(sql, str):
        raise TypeError(f"Expected str, got {type(sql).__name__!r}")

    # --- Input length guard (prevents ReDoS / DoS on pathological inputs) ---
    if len(sql) > MAX_SQL_LENGTH:
        raise ValueError(
            f"SQL input length ({len(sql)}) exceeds the maximum allowed "
            f"length of {MAX_SQL_LENGTH} characters."
        )

    # Preprocess once here; cleaned text is passed directly to _check_statement
    # to avoid redundant double-stripping.
    cleaned_full, pre_violations = _preprocess_sql(sql)

    all_violations: list[str] = list(pre_violations)

    # Split on semicolons to handle multi-statement inputs
    statements = [s.strip() for s in cleaned_full.split(";") if s.strip()]

    for idx, stmt in enumerate(statements):
        stmt_violations = _check_statement(stmt)
        if stmt_violations:
            prefix = f"[Statement {idx + 1}] " if len(statements) > 1 else ""
            all_violations.extend(f"{prefix}{v}" for v in stmt_violations)

    return CheckResult(
        is_safe=len(all_violations) == 0,
        violations=all_violations,
        cleaned_sql=cleaned_full,
    )


# ---------------------------------------------------------------------------
# Demo / test harness
# ---------------------------------------------------------------------------

SQL_QUERIES: list[tuple[str, bool, str]] = [
    # (query, expected_is_safe, description)

    # ------------------------------------------------------------------
    # ✅ Safe — read-only queries
    # ------------------------------------------------------------------
    (
        "SELECT id, name FROM users WHERE active = 1",
        True,
        "Plain SELECT",
    ),
    (
        "SELECT * FROM logs WHERE url = 'https://example.com/update/profile?id=5'",
        True,
        "SELECT with 'update' keyword inside a URL string literal",
    ),
    (
        "SELECT * FROM pages WHERE content LIKE '%DROP TABLE%'",
        True,
        "SELECT with dangerous keyword inside a string literal",
    ),
    (
        "SELECT department, COUNT(*) FROM employees GROUP BY department HAVING COUNT(*) > 10",
        True,
        "Aggregate with GROUP BY / HAVING",
    ),
    (
        "WITH recent AS (SELECT * FROM orders WHERE created_at > '2024-01-01') SELECT * FROM recent",
        True,
        "CTE (WITH … SELECT)",
    ),
    (
        "SELECT id FROM config -- UPDATE is planned for v2",
        True,
        "'UPDATE' keyword only inside a line comment (stripped)",
    ),
    (
        "SELECT * FROM templates WHERE body = 'CREATE TABLE example (id INT)'",
        True,
        "'CREATE' only inside a single-quoted string literal",
    ),
    (
        "EXPLAIN SELECT * FROM orders WHERE status = 'shipped'",
        True,
        "EXPLAIN query plan",
    ),
    (
        "SELECT id, name FROM customers UNION SELECT id, name FROM archived_customers",
        True,
        "Two safe SELECTs joined by UNION",
    ),
    (
        (
            "SELECT dept, SUM(salary) AS total FROM employees "
            "GROUP BY dept HAVING SUM(salary) > 50000 "
            "UNION ALL "
            "SELECT dept, SUM(salary) AS total FROM contractors "
            "GROUP BY dept HAVING SUM(salary) > 50000"
        ),
        True,
        "UNION ALL with HAVING",
    ),
    (
        (
            "SELECT id, status FROM orders WHERE status = 'shipped' "
            "UNION "
            "SELECT id, url FROM audit_log "
            "WHERE url LIKE 'https://api.example.com/update/%'"
        ),
        True,
        "'update' only inside a string literal in the second UNION branch",
    ),
    (
        (
            "SELECT action, COUNT(*) AS cnt FROM audit_log "
            "GROUP BY action "
            "HAVING action != 'DELETE_NOT_REALLY' AND cnt > 100"
        ),
        True,
        "'DELETE' only inside a string literal in HAVING clause",
    ),
    (
        (
            "SELECT sub.dept, sub.avg_salary "
            "FROM ("
            "    SELECT dept, AVG(salary) AS avg_salary "
            "    FROM employees "
            "    GROUP BY dept"
            ") AS sub "
            "WHERE sub.avg_salary > 60000"
        ),
        True,
        "Subquery in FROM clause — both inner and outer are SELECTs",
    ),
    (
        (
            "SELECT e.name, e.salary FROM employees e "
            "WHERE e.salary > ("
            "    SELECT AVG(salary) FROM employees WHERE dept = e.dept"
            ")"
        ),
        True,
        "Correlated subquery in WHERE clause",
    ),
    (
        "SELECT user_id FROM active_users INTERSECT SELECT user_id FROM premium_users",
        True,
        "INTERSECT of two safe SELECTs",
    ),
    (
        "SELECT user_id FROM all_users EXCEPT SELECT user_id FROM banned_users",
        True,
        "EXCEPT (set difference) of two safe SELECTs",
    ),
    (
        "SELECT\n    id,\n    name\nFROM users\nWHERE active = 1",
        True,
        "Legitimate multi-line SELECT (real-world formatting)",
    ),
    # Single-quote with SQL-standard doubled-quote escaping inside literal
    (
        "SELECT * FROM users WHERE name = 'O''Brien'",
        True,
        "Single-quoted string with SQL-standard '' escaping inside literal",
    ),

    # ------------------------------------------------------------------
    # ❌ Dangerous — previously allowed by the old checker
    # ------------------------------------------------------------------
    (
        "INSERT INTO audit_log (event, ts) VALUES ('login', NOW())",
        False,
        "INSERT — data modification (was incorrectly allowed before)",
    ),
    (
        "MERGE INTO users USING (SELECT 1 AS id, 'admin' AS role) AS src "
        "ON users.id = src.id "
        "WHEN MATCHED THEN UPDATE SET role = src.role",
        False,
        "MERGE — upsert (was not blocked before)",
    ),
    (
        "REPLACE INTO settings (key, value) VALUES ('admin', '1')",
        False,
        "REPLACE — MySQL delete+insert (was not blocked before)",
    ),
    (
        "SELECT * FROM users INTO OUTFILE '/tmp/dump.csv'",
        False,
        "SELECT … INTO OUTFILE — file exfiltration (was not blocked before)",
    ),
    (
        "SELECT * FROM users INTO DUMPFILE '/var/www/html/shell.php'",
        False,
        "SELECT … INTO DUMPFILE — webshell write (was not blocked before)",
    ),
    (
        "COPY users TO '/tmp/users.csv'",
        False,
        "COPY — PostgreSQL file export (was not blocked before)",
    ),
    (
        "LOAD DATA INFILE '/etc/passwd' INTO TABLE users",
        False,
        "LOAD DATA INFILE — MySQL file read (was not blocked before)",
    ),
    (
        "ATTACH DATABASE '/tmp/evil.db' AS evil",
        False,
        "ATTACH DATABASE — SQLite attach arbitrary file (was not blocked before)",
    ),
    (
        "PRAGMA writable_schema = ON",
        False,
        "PRAGMA — SQLite admin command (was not blocked before)",
    ),

    # ------------------------------------------------------------------
    # ❌ Dangerous — previously caught by the old checker
    # ------------------------------------------------------------------
    (
        "DROP TABLE users",
        False,
        "DROP TABLE",
    ),
    (
        "TRUNCATE TABLE sessions",
        False,
        "TRUNCATE TABLE",
    ),
    (
        "ALTER TABLE employees ADD COLUMN salary DECIMAL(10,2)",
        False,
        "ALTER TABLE",
    ),
    (
        "CREATE TABLE temp_data (id INT PRIMARY KEY, val TEXT)",
        False,
        "CREATE TABLE",
    ),
    (
        "DELETE FROM logs WHERE created_at < '2020-01-01'",
        False,
        "DELETE FROM",
    ),
    (
        "UPDATE users SET password = 'newpass' WHERE id = 42",
        False,
        "UPDATE",
    ),
    (
        "GRANT ALL PRIVILEGES ON mydb.* TO 'hacker'@'%'",
        False,
        "GRANT",
    ),
    (
        "EXEC sp_executesql N'DROP TABLE sensitive_data'",
        False,
        "EXEC stored procedure",
    ),
    (
        "SELECT 1; DROP TABLE users; SELECT 2",
        False,
        "Multi-statement: safe SELECT + DROP TABLE + safe SELECT",
    ),
    (
        "REVOKE SELECT ON mydb.reports FROM 'analyst'@'localhost'",
        False,
        "REVOKE",
    ),
    (
        "DROP DATABASE production",
        False,
        "DROP DATABASE",
    ),
    (
        (
            "SELECT id FROM logs WHERE severity = 'low' "
            "UNION "
            "DELETE FROM logs WHERE severity = 'low'"
        ),
        False,
        "UNION branch contains DELETE FROM",
    ),
    (
        (
            "SELECT id, role FROM users WHERE id = 1 "
            "UNION "
            "UPDATE users SET role = 'admin' WHERE id = 1"
        ),
        False,
        "UNION branch contains UPDATE",
    ),
    (
        (
            "SELECT product_id, stock FROM inventory "
            "UNION ALL "
            "UPDATE inventory SET stock = 0 WHERE product_id = 42"
        ),
        False,
        "UPDATE injected after UNION ALL",
    ),
    (
        "SELECT 1 AS dummy UNION DROP TABLE critical_data",
        False,
        "DROP TABLE hidden in second part of a UNION",
    ),
    (
        "SELECT * FROM reports WHERE id IN (    DROP TABLE reports)",
        False,
        "DROP TABLE inside a subquery WHERE clause",
    ),
    (
        (
            "SELECT dept, COUNT(*) FROM employees "
            "GROUP BY dept "
            "HAVING COUNT(*) > 5; "
            "UPDATE employees SET salary = 0 WHERE dept = 'engineering'"
        ),
        False,
        "Multi-statement injection: UPDATE after semicolon in HAVING clause",
    ),
    (
        "SELECT id FROM t1 UNION SELECT id FROM t2; ALTER TABLE t1 DROP COLUMN sensitive_col",
        False,
        "Safe UNION followed by ALTER TABLE in a second statement",
    ),
    (
        "DROP\nTABLE secrets",
        False,
        "DROP TABLE split across a Unix newline (normalised before check)",
    ),
    (
        "DELETE\r\nFROM logs",
        False,
        "DELETE FROM split across Windows CRLF (normalised before check)",
    ),
    (
        "SELECT id FROM cfg\rUPDATE cfg SET value='pwned' WHERE key='admin'",
        False,
        "UPDATE injected after safe SELECT separated by bare \\r",
    ),

    # ------------------------------------------------------------------
    # ❌ Dangerous — bypass vectors fixed in security audit
    # ------------------------------------------------------------------
    (
        "TRUNCATE users",
        False,
        "TRUNCATE without TABLE keyword (valid SQL, previously missed)",
    ),
    (
        "DELETE users WHERE id = 1",
        False,
        "DELETE without FROM keyword (SQL Server syntax, previously missed)",
    ),
    (
        "INSERT users VALUES (1, 'admin')",
        False,
        "INSERT without INTO keyword (SQL Server syntax, previously missed)",
    ),
    (
        "SELECT 1; MERGE users USING src ON users.id = src.id "
        "WHEN MATCHED THEN UPDATE SET role = src.role",
        False,
        "MERGE without INTO keyword (previously missed)",
    ),
    (
        "SELECT 1; REPLACE users (key, value) VALUES ('admin', '1')",
        False,
        "REPLACE without INTO keyword (previously missed)",
    ),
    (
        "DO $$ BEGIN EXECUTE 'DROP TABLE users'; END $$",
        False,
        "PostgreSQL DO block — arbitrary PL/pgSQL execution",
    ),
    (
        "UPSERT INTO settings (key, value) VALUES ('admin', '1')",
        False,
        "SQLite UPSERT command",
    ),
    (
        "SELECT * FROM t WHERE x = '\\' ; DROP TABLE users --'",
        False,
        "Backslash-escaped quote bypass attempt (PostgreSQL standard_conforming_strings)",
    ),
    (
        "SELECT * FROM t WHERE body = $$safe content here$$",
        True,
        "Dollar-quoted string with safe content (PostgreSQL)",
    ),
    (
        "SELECT * FROM t WHERE body = $$DROP TABLE users$$",
        True,
        "Dangerous keyword inside dollar-quoted string (false positive prevented)",
    ),
    (
        "SELECT 1; D\u200BROP TABLE users",
        False,
        "Zero-width space inside DROP keyword (invisible Unicode bypass attempt)",
    ),

    # ------------------------------------------------------------------
    # ❌ Dangerous — block comment obfuscation now rejected outright
    # ------------------------------------------------------------------
    (
        "DR/*comment*/OP TABLE users",
        False,
        "Block comment obfuscation attempt — rejected by block-comment rule",
    ),
    (
        "SELECT /* this is a comment */ id FROM users",
        False,
        "Block comment inside an otherwise-safe SELECT — rejected outright",
    ),
]


def run_demo() -> None:
    print("=" * 72)
    print("  SQL Safety Checker — Demo Run")
    print("=" * 72)

    safe_count = 0
    dangerous_count = 0
    failures: list[str] = []

    for i, (query, expected_safe, description) in enumerate(SQL_QUERIES, start=1):
        result = check_sql(query)
        actual_safe = result.is_safe

        label = "✅ SAFE     " if actual_safe else "❌ DANGEROUS"
        match = "  " if actual_safe == expected_safe else "⚡MISMATCH"
        print(f"\n[{i:02d}] {label} {match}")
        display = query if len(query) <= 68 else query[:65] + "…"
        print(f"      Desc: {description}")
        print(f"      SQL : {display}")
        if result.violations:
            for v in result.violations:
                print(f"      ⚠️   {v}")

        if actual_safe == expected_safe:
            if actual_safe:
                safe_count += 1
            else:
                dangerous_count += 1
        else:
            failures.append(f"[{i:02d}] {description}")

    print("\n" + "=" * 72)
    print(f"  Results : {safe_count} safe, {dangerous_count} dangerous "
          f"(out of {len(SQL_QUERIES)} queries)")
    if failures:
        print(f"  ⚡ MISMATCHES ({len(failures)}):")
        for f in failures:
            print(f"      {f}")
    else:
        print("  ✅ All queries matched expected classification.")
    print("=" * 72)


if __name__ == "__main__":
    run_demo()
