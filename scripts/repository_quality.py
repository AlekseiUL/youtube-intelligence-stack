#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', '.venv', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
TEXT_SUFFIXES = {'.py', '.md', '.txt', '.yaml', '.yml', '.json', '.toml', '.ini', '.cfg', '.gitignore'}
PUBLIC_ASSET_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp'}
RUNTIME_MEDIA_SUFFIXES = {'.webm', '.wav', '.mp4', '.mkv', '.ogg'}
PRIVATE_PATTERNS = {
    'absolute_user_path': re.compile(r'/(Users|home)/[^\s]+'),
    'secret_shape': re.compile(
        r'(ghp_|gho_|github_pat_|glpat-|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-|AIza[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{16})'
    ),
}


def iter_files():
    for p in ROOT.rglob('*'):
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        if p.is_file():
            yield p


def iter_tracked_files():
    try:
        output = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files'], text=True)
    except Exception:
        yield from iter_files()
        return
    for rel in output.splitlines():
        p = ROOT / rel
        if p.is_file():
            yield p


def is_text_file(p: Path) -> bool:
    if p.name == '.gitignore':
        return True
    return p.suffix.lower() in TEXT_SUFFIXES


def check_python_syntax(errors: list[str]) -> None:
    for p in iter_files():
        if p.suffix == '.py':
            try:
                ast.parse(p.read_text(encoding='utf-8'), filename=str(p.relative_to(ROOT)))
            except SyntaxError as e:
                errors.append(f'python syntax: {p.relative_to(ROOT)}:{e.lineno}: {e.msg}')


def check_json(errors: list[str]) -> None:
    for p in iter_files():
        if p.suffix == '.json':
            try:
                json.loads(p.read_text(encoding='utf-8'))
            except Exception as e:
                errors.append(f'json parse: {p.relative_to(ROOT)}: {e}')


def check_privacy(errors: list[str]) -> None:
    scanner_self = Path('scripts/repository_quality.py')
    for p in iter_files():
        rel = p.relative_to(ROOT)
        if rel in {scanner_self, Path('.gitignore')}:
            continue
        if not is_text_file(p):
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        for idx, line in enumerate(text.splitlines(), 1):
            for kind, rx in PRIVATE_PATTERNS.items():
                if rx.search(line):
                    errors.append(f'{kind}: {rel}:{idx}')


def check_markdown_links(errors: list[str]) -> None:
    link_rx = re.compile(r'\[[^\]]+\]\(([^)]+)\)')
    for p in iter_files():
        if p.suffix != '.md':
            continue
        text = p.read_text(encoding='utf-8')
        for idx, match in enumerate(link_rx.finditer(text), 1):
            target = match.group(1).split('#', 1)[0]
            if not target or '://' in target or target.startswith('mailto:'):
                continue
            candidate = (p.parent / target).resolve()
            if ROOT not in candidate.parents and candidate != ROOT:
                errors.append(f'markdown link escapes repo: {p.relative_to(ROOT)} -> {target}')
            elif not candidate.exists():
                errors.append(f'markdown broken link: {p.relative_to(ROOT)} -> {target}')


def check_generated_artifacts(errors: list[str]) -> None:
    forbidden = []
    for p in iter_tracked_files():
        rel = p.relative_to(ROOT)
        if any(part in {'build', 'cache', 'data', 'dist', 'outputs', 'reports'} for part in rel.parts):
            forbidden.append(str(rel))
        if p.suffix in {'.pyc', '.pyo'} or '__pycache__' in rel.parts:
            forbidden.append(str(rel))
        if p.suffix.lower() in PUBLIC_ASSET_SUFFIXES and not str(rel).startswith('docs/assets/'):
            forbidden.append(f'unexpected public image outside docs/assets: {rel}')
        if p.suffix.lower() in RUNTIME_MEDIA_SUFFIXES:
            forbidden.append(f'runtime media artifact committed: {rel}')
    for item in forbidden:
        errors.append(f'generated artifact committed: {item}')


def main() -> int:
    errors: list[str] = []
    check_python_syntax(errors)
    check_json(errors)
    check_privacy(errors)
    check_markdown_links(errors)
    check_generated_artifacts(errors)
    if errors:
        print('repository quality: FAIL')
        for item in errors[:100]:
            print('-', item)
        print(f'findings: {len(errors)}')
        return 1
    print('repository quality: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
