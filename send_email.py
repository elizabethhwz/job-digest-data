#!/usr/bin/env python3
"""Send the job digest email from summarized_jobs.json (written by the Claude agent)."""

import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).parent
SUMMARIZED_JOBS_FILE = BASE_DIR / "summarized_jobs.json"
CONFIG_FILE = BASE_DIR / "config.yaml"


def load_config():
    with open(CONFIG_FILE) as f:
        cfg = yaml.safe_load(f)
    cfg["gmail_app_password"] = os.environ.get("GMAIL_APP_PASSWORD") or cfg.get("gmail_app_password", "")
    return cfg


def build_html(jobs, today):
    if not jobs:
        body = "<p style='color:#6b7280;'>No new matching roles today. Check back tomorrow.</p>"
    else:
        cards = ""
        for job in jobs:
            score = job.get("score", 0)
            badge_color = "#22c55e" if score >= 8 else "#f59e0b" if score >= 6 else "#6b7280"
            summary_html = (
                f"<p style='margin:10px 0 6px;color:#374151;'>{job['summary']}</p>"
                if job.get("summary") else ""
            )
            highlights_html = (
                f"<p style='margin:0;color:#6b7280;font-size:13px;'>"
                f"<b>Highlights:</b> {job['highlights']}</p>"
                if job.get("highlights") else ""
            )
            cards += f"""
<div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:16px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
    <div>
      <a href="{job['url']}" style="font-size:16px;font-weight:600;color:#1d4ed8;text-decoration:none;">{job['title']}</a>
      <div style="color:#374151;margin-top:4px;">{job.get('company', '')} &middot; {job.get('location', '')}</div>
      <div style="color:#9ca3af;font-size:12px;">via {job.get('source', '')}</div>
    </div>
    <span style="background:{badge_color};color:white;border-radius:9999px;padding:2px 10px;font-size:13px;font-weight:600;white-space:nowrap;flex-shrink:0;">{score}/10</span>
  </div>
  {summary_html}{highlights_html}
</div>"""
        body = cards

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:680px;margin:0 auto;padding:24px;color:#111827;">
  <h1 style="font-size:22px;font-weight:700;margin-bottom:4px;">AI Job Digest</h1>
  <p style="color:#6b7280;margin-bottom:24px;">{today} &middot; {len(jobs)} new matching roles</p>
  {body}
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:32px 0 16px;">
  <p style="color:#9ca3af;font-size:12px;margin:0;">Filters: AI roles &middot; Startups &middot; San Francisco or Remote</p>
</body></html>"""


def main():
    cfg = load_config()

    if not SUMMARIZED_JOBS_FILE.exists():
        print(f"Error: {SUMMARIZED_JOBS_FILE} not found. Run the Claude agent first.")
        sys.exit(1)

    with open(SUMMARIZED_JOBS_FILE) as f:
        jobs = json.load(f)

    today = datetime.now().strftime("%B %d, %Y")
    html = build_html(jobs, today)
    subject = f"AI Job Digest · {today} · {len(jobs)} new roles"

    if not cfg.get("gmail_app_password"):
        # Save locally for preview if email isn't configured
        out = BASE_DIR / f"digest_{datetime.now().strftime('%Y%m%d')}.html"
        out.write_text(html)
        print(f"No email password set — saved digest to {out}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["email_from"]
    msg["To"] = cfg["email_to"]
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(cfg["email_from"], cfg["gmail_app_password"])
        server.sendmail(cfg["email_from"], cfg["email_to"], msg.as_string())

    print(f"Email sent: {len(jobs)} jobs to {cfg['email_to']}")


if __name__ == "__main__":
    main()
