#!/usr/bin/env python3
"""
Builds the profile README by pulling from:
  - GitHub API: recently active repos (public + private)
  - GitHub API: recently starred repos
  - GitHub API: recently modified learning notes from obsidian-notes
"""
import os
import re
import sys
import requests
from datetime import datetime

TOKEN = os.environ.get('GH_TOKEN')
if not TOKEN:
    print("GH_TOKEN not set", file=sys.stderr)
    sys.exit(1)

SESSION = requests.Session()
SESSION.headers.update({
    'Authorization': f'token {TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'X-GitHub-Api-Version': '2022-11-28',
})

OWNER = 'TimothyEastvold'

# ── Config ─────────────────────────────────────────────────────────────────────

# Repo names to never surface on the public profile (e.g. sensitive client work)
REPO_BLOCKLIST = set()

# How to handle private repos:
#   'descriptions' — show description only, no repo name or link (safe default)
#   'names'        — show name + link + description
#   'exclude'      — omit private repos entirely
PRIVATE_REPO_MODE = 'descriptions'


# ── Helpers ────────────────────────────────────────────────────────────────────

def replace_chunk(content, marker, chunk):
    pattern = re.compile(
        rf'<!-- {marker} starts -->.*?<!-- {marker} ends -->',
        re.DOTALL,
    )
    return pattern.sub(
        f'<!-- {marker} starts -->\n{chunk}\n<!-- {marker} ends -->',
        content,
    )


# ── Data sources ───────────────────────────────────────────────────────────────

def get_recent_repos(count=5):
    resp = SESSION.get(
        'https://api.github.com/user/repos',
        params={'type': 'owner', 'sort': 'pushed', 'per_page': 50},
    )
    repos = resp.json()

    lines = []
    for repo in repos:
        if len(lines) >= count:
            break
        name = repo['name']
        if name in REPO_BLOCKLIST or name == OWNER:
            continue

        is_private = repo['private']
        desc = (repo.get('description') or '').strip()
        pushed = repo['pushed_at'][:10]

        if is_private:
            if PRIVATE_REPO_MODE == 'exclude':
                continue
            elif PRIVATE_REPO_MODE == 'descriptions':
                if desc:
                    lines.append(f'- {desc} `private` — {pushed}')
            else:  # names
                entry = f'- [{name}]({repo["html_url"]})' + (f': {desc}' if desc else '')
                lines.append(entry + f' — {pushed}')
        else:
            entry = f'- [{name}]({repo["html_url"]})' + (f': {desc}' if desc else '')
            lines.append(entry + f' — {pushed}')

    return '\n'.join(lines) if lines else '*No recent activity*'


def get_recent_stars(count=5):
    resp = SESSION.get(
        f'https://api.github.com/users/{OWNER}/starred',
        params={'per_page': count, 'sort': 'created', 'direction': 'desc'},
    )
    stars = resp.json()

    lines = []
    for repo in stars[:count]:
        name = repo['full_name']
        url  = repo['html_url']
        desc = (repo.get('description') or '').strip()
        entry = f'- [{name}]({url})' + (f': {desc}' if desc else '')
        lines.append(entry)

    return '\n'.join(lines) if lines else '*No recent stars*'


def get_recent_notes(count=5):
    """
    Surfaces recently modified .md files from the learning/ folder
    in the private obsidian-notes repo by scanning recent commits.
    """
    resp = SESSION.get(
        f'https://api.github.com/repos/{OWNER}/obsidian-notes/commits',
        params={'per_page': 30},
    )
    if resp.status_code != 200:
        return '*Notes unavailable*'

    seen  = set()
    notes = []

    for commit in resp.json():
        if len(notes) >= count:
            break
        sha  = commit['sha']
        date = commit['commit']['author']['date'][:10]
        detail = SESSION.get(
            f'https://api.github.com/repos/{OWNER}/obsidian-notes/commits/{sha}'
        ).json()

        for f in detail.get('files', []):
            path = f['filename']
            if (
                path.startswith('learning/')
                and path.endswith('.md')
                and path not in seen
            ):
                seen.add(path)
                parts = path.replace('learning/', '').replace('.md', '').split('/')
                title = parts[-1].replace('-', ' ').title()
                topic = parts[-2] if len(parts) > 1 else 'general'
                notes.append(f'- **{title}** `{topic}` — {date}')
                if len(notes) >= count:
                    break

    return '\n'.join(notes) if notes else '*No recent notes*'


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with open('README.md', 'r') as fh:
        readme = fh.read()

    readme = replace_chunk(readme, 'recent_repos',  get_recent_repos())
    readme = replace_chunk(readme, 'recent_stars',  get_recent_stars())
    readme = replace_chunk(readme, 'recent_notes',  get_recent_notes())

    with open('README.md', 'w') as fh:
        fh.write(readme)

    print('README.md updated.')
