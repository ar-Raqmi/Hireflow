from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hireflow.config import SETTINGS


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def ago(posted_at: Any) -> str:
    """Human "posted X ago" label for a job; 'date unknown' when absent."""
    parsed = _parse_dt(posted_at)
    if parsed is None:
        return "date unknown"
    delta = datetime.now(timezone.utc) - _as_utc(parsed)
    days = delta.days
    if days < 0:
        days = 0
    if days == 0:
        return "today"
    if days < 7:
        return f"{days}d ago"
    if days < 30:
        return f"{days // 7}w ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


def is_expired(posted_at: Any, recency_days: int) -> bool:
    parsed = _parse_dt(posted_at)
    if parsed is None:
        return False
    if recency_days <= 0:
        return False
    delta = datetime.now(timezone.utc) - _as_utc(parsed)
    return delta.days > recency_days


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


class HtmlExporter:
    """Client-side exporter: a full pipeline result rendered to one self-contained HTML file.

    The output embeds all CSS inline (no CDN/fonts/scripts), is UTF-8, and never
    truncates anything: titles, URLs, reasons, research summaries, application
    rows and drafts all render in full, with every post_url as a real clickable
    link. Pure stdlib - no backend or Gemini involvement.
    """

    def export(self, result: dict[str, Any], out_path: str | Path) -> str:
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.render(result), encoding="utf-8")
        return str(target)

    def save_json(self, result: dict[str, Any], out_path: str | Path) -> str:
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)

    def render(self, result: dict[str, Any]) -> str:
        body = "".join(
            [
                self._header(result),
                self._matches(result),
                self._jobs(result),
                self._applications(result),
                self._needs_human(result),
                self._drafts(result),
                self._errors(result),
            ]
        )
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            "<title>Hireflow · Pipeline Result</title>\n"
            "<style>\n"
            f"{self._css()}\n"
            "</style>\n"
            "</head>\n"
            "<body>\n"
            f"{body}"
            "</body>\n"
            "</html>\n"
        )

    @staticmethod
    def _esc(value: Any) -> str:
        return html.escape(str(value if value is not None else ""), quote=True)

    @staticmethod
    def _section(title: str, body: str) -> str:
        return f'<section class="card"><h2>{title}</h2>{body}</section>\n'

    def _header(self, result: dict[str, Any]) -> str:
        return (
            '<header class="card">\n'
            "<h1>Hireflow · Pipeline Result</h1>\n"
            f'<p class="meta">profile <code>{self._esc(result.get("profile_id", ""))}</code>'
            f' · run <code>{self._esc(result.get("run_id", ""))}</code></p>\n'
            f'<p class="meta">status: {self._esc(result.get("status", "completed"))}'
            f' · jobs found: {self._esc(result.get("jobs_found", 0))}</p>\n'
            "</header>\n"
        )

    def _matches(self, result: dict[str, Any]) -> str:
        matches = result.get("matches") or []
        if not matches:
            return self._section("Top Matches", '<p class="empty">no matches yet (either no jobs found or all below score 60).</p>')
        rows: list[str] = []
        details: list[str] = []
        for match in matches:
            url = self._esc(match.get("post_url", ""))
            when = ago(match.get("posted_at"))
            if is_expired(match.get("posted_at"), SETTINGS.job_recency_days):
                when += " · ⚠ expired"
            rows.append(
                "<tr>"
                f'<td class="num">{self._esc(match.get("rank", ""))}</td>'
                f'<td class="num">{self._esc(match.get("score", ""))}</td>'
                f'<td>{self._esc(match.get("title", ""))}</td>'
                f'<td>{self._esc(match.get("company", ""))}</td>'
                f'<td>{self._esc(match.get("location", ""))}</td>'
                f'<td>{self._esc(when)}</td>'
                f'<td>{self._esc(match.get("source", ""))}</td>'
                f'<td><a href="{url}">{url}</a></td>'
                "</tr>"
            )
            blocks: list[str] = []
            reasons = match.get("reasons") or []
            if reasons:
                items = "".join(f"<li>{self._esc(reason)}</li>" for reason in reasons)
                blocks.append(f'<div class="reasons"><strong>Why this fit:</strong><ul>{items}</ul></div>')
            research = match.get("research") or {}
            summary = research.get("summary", "") if isinstance(research, dict) else ""
            if summary:
                blocks.append(f'<div class="research"><strong>Company research:</strong><p>{self._esc(summary)}</p></div>')
            if blocks:
                label = f"#{self._esc(match.get('rank', ''))} {self._esc(match.get('title', ''))}"
                details.append(f'<div class="match-detail"><h4>{label}</h4>{"".join(blocks)}</div>')
        table = (
            "<table>"
            "<thead><tr><th>#</th><th>Score</th><th>Title</th><th>Company</th>"
            "<th>Location</th><th>Posted</th><th>Source</th><th>Link</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
        return self._section(f"Top Matches ({len(matches)})", table + "\n" + "\n".join(details))

    def _jobs(self, result: dict[str, Any]) -> str:
        jobs = result.get("jobs") or []
        if not jobs:
            return ""
        rows: list[str] = []
        for job in jobs:
            url = self._esc(job.get("post_url", ""))
            when = ago(job.get("posted_at"))
            if is_expired(job.get("posted_at"), SETTINGS.job_recency_days):
                when += " · ⚠ expired"
            rows.append(
                "<tr>"
                f'<td>{self._esc(job.get("title", ""))}</td>'
                f'<td>{self._esc(job.get("company", ""))}</td>'
                f'<td>{self._esc(job.get("location", ""))}</td>'
                f'<td>{self._esc(when)}</td>'
                f'<td>{self._esc(job.get("source", ""))}</td>'
                f'<td><a href="{url}">{url}</a></td>'
                "</tr>"
            )
        table = (
            "<table><thead><tr><th>Title</th><th>Company</th><th>Location</th>"
            "<th>Posted</th><th>Source</th><th>Link</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
        return self._section(f"All Found Jobs ({len(jobs)})", table)

    def _applications(self, result: dict[str, Any]) -> str:
        apps = result.get("applications") or []
        if not apps:
            return self._section("Applications", '<p class="empty">none queued (nothing scored high enough).</p>')
        rows: list[str] = []
        for app in apps:
            rows.append(
                "<tr>"
                f'<td><code>{self._esc(app.get("id", ""))}</code></td>'
                f'<td>{self._esc(app.get("status", ""))}</td>'
                f'<td class="num">{self._esc(app.get("score", ""))}</td>'
                f'<td>{self._esc(app.get("title", ""))}</td>'
                f'<td>{self._esc(app.get("company", ""))}</td>'
                f'<td>{"yes" if app.get("human_handoff") else ""}</td>'
                f'<td>{"yes" if app.get("drafted") else ""}</td>'
                f'<td>{self._submission_cell(app)}</td>'
                "</tr>"
            )
        table = (
            "<table><thead><tr><th>ID</th><th>Status</th><th>Score</th><th>Title</th>"
            "<th>Company</th><th>Needs human</th><th>Draft</th><th>ATS submission</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
        return self._section(f"Applications ({len(apps)})", table)

    def _submission_cell(self, app: dict[str, Any]) -> str:
        confirmation = str(app.get("ats_confirmation", "") or "")
        submitted_at = str(app.get("submitted_at", "") or "")
        if not confirmation and not submitted_at:
            return ""
        parts = [confirmation] if confirmation else []
        if submitted_at:
            parts.append(submitted_at[:16].replace("T", " "))
        return self._esc(" · ".join(parts))

    def _needs_human(self, result: dict[str, Any]) -> str:
        items = result.get("needs_human") or []
        if not items:
            return ""
        lis: list[str] = []
        for item in items:
            lis.append(
                "<li>"
                f'<strong>{self._esc(item.get("company", ""))}</strong>'
                f' · {self._esc(item.get("title", ""))}'
                f' - {self._esc(item.get("reason", ""))}'
                f' <code>({self._esc(item.get("application_id", ""))})</code>'
                "</li>"
            )
        return self._section(f"Needs Human ({len(items)})", f"<ul>{''.join(lis)}</ul>")

    def _drafts(self, result: dict[str, Any]) -> str:
        drafts = result.get("drafts") or {}
        if not drafts:
            return ""
        by_id = {str(match.get("job_id", "")): match for match in result.get("matches") or []}
        blocks: list[str] = []
        for job_id, package in drafts.items():
            match = by_id.get(str(job_id), {})
            heading = self._esc(match.get("title", "") or f"job {job_id}")
            if match.get("company"):
                heading += f" @ {self._esc(match.get('company', ''))}"
            heading += f" <small>({self._esc(job_id)})</small>"
            blocks.append(
                '<div class="draft">'
                f"<h3>{heading}</h3>"
                "<h4>CV</h4>"
                f'<pre>{self._esc(package.get("cv", ""))}</pre>'
                "<h4>Cover letter</h4>"
                f'<pre>{self._esc(package.get("cover_letter", ""))}</pre>'
                "</div>"
            )
        return self._section(f"Drafts ({len(drafts)})", "\n".join(blocks))

    def _errors(self, result: dict[str, Any]) -> str:
        errors = result.get("errors") or []
        if not errors:
            return ""
        lis = "".join(f"<li>{self._esc(message)}</li>" for message in errors)
        return self._section("Source Notes (non-fatal)", f"<ul>{lis}</ul>")

    @staticmethod
    def _css() -> str:
        return (
            "body{font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
            "margin:0;padding:32px;background:#f6f7f9;color:#1a1a2e;line-height:1.5}"
            ".card{background:#fff;border:1px solid #e2e5ea;border-radius:10px;"
            "padding:20px 24px;margin:0 0 24px;max-width:1100px}"
            "h1{margin:0 0 6px;font-size:1.5rem}h2{margin:0 0 12px;font-size:1.15rem;"
            "border-bottom:2px solid #e2e5ea;padding-bottom:8px}"
            "h3{margin:0 0 6px}h4{margin:14px 0 4px;color:#3c4451}"
            ".meta{color:#5b6472;margin:4px 0}code{background:#eef0f4;padding:1px 5px;"
            "border-radius:4px;font-size:0.9em;word-break:break-all}"
            "table{border-collapse:collapse;width:100%;font-size:0.92rem}"
            "th,td{border:1px solid #e2e5ea;padding:8px 10px;text-align:left;vertical-align:top}"
            "th{background:#f0f2f5}td.num{white-space:nowrap}tr:nth-child(even) td{background:#fafbfc}"
            "a{color:#0b57d0;word-break:break-all}ul{margin:8px 0 8px 20px;padding:0}"
            ".match-detail{margin:14px 0 0;padding:12px 14px;background:#fafbfc;"
            "border-radius:8px;border:1px solid #e2e5ea}"
            ".reasons,.research{margin:8px 0 0}.draft{margin:0 0 20px;padding:14px 16px;"
            "background:#fafbfc;border-radius:8px;border:1px solid #e2e5ea}"
            "pre{white-space:pre-wrap;word-wrap:break-word;background:#fff;border:1px solid #e2e5ea;"
            "border-radius:6px;padding:12px;margin:6px 0 0;font-size:0.88rem}"
            ".empty{color:#5b6472}"
        )
