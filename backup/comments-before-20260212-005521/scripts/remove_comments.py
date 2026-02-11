#!/usr/bin/env python3
"""
Safely remove comments from text files in the workspace.
Creates a backup copy at backup/comments-before-<timestamp>/
Processes file types: .html, .htm, .css, .js, .scss, .map, .txt, .json, .xml, .svg

WARNING: This will remove license headers and third-party attributions.
Use the backup directory to restore if needed.
"""
import os
import shutil
import sys
import time
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = time.strftime('%Y%m%d-%H%M%S')
BACKUP_DIR = ROOT / 'backup' / f'comments-before-{TIMESTAMP}'

# File extensions to process
EXTS = {'.html', '.htm', '.css', '.js', '.scss', '.map', '.txt', '.json', '.xml', '.svg'}

# Binary file size cutoff: skip files larger than 5MB to avoid processing huge binaries
MAX_SIZE = 5 * 1024 * 1024

changed_files = []
skipped_files = []

def remove_html_comments(s: str) -> str:
    # Remove <!-- ... --> including across lines
    return re.sub(r'<!--([\s\S]*?)-->', '', s)

def remove_css_comments(s: str) -> str:
    return re.sub(r'/\*([\s\S]*?)\*/', '', s)

def remove_js_comments(s: str) -> str:
    # Basic JS comment stripper using state machine to avoid removing // inside strings
    out = []
    i = 0
    L = len(s)
    in_s = False
    in_d = False
    in_b = False
    in_block_comment = False
    in_line_comment = False
    escape = False
    while i < L:
        ch = s[i]
        nxt = s[i+1] if i+1 < L else ''

        if in_block_comment:
            if ch == '*' and nxt == '/':
                in_block_comment = False
                i += 2
                continue
            else:
                i += 1
                continue

        if in_line_comment:
            if ch == '\n':
                in_line_comment = False
                out.append(ch)
                i += 1
                continue
            else:
                i += 1
                continue

        if in_s:
            out.append(ch)
            if not escape and ch == "'":
                in_s = False
            escape = (ch == '\\' and not escape)
            i += 1
            continue

        if in_d:
            out.append(ch)
            if not escape and ch == '"':
                in_d = False
            escape = (ch == '\\' and not escape)
            i += 1
            continue

        if in_b:
            out.append(ch)
            if not escape and ch == '`':
                in_b = False
            # template literals can contain ${ ... } with strings; we'll not parse them specially
            escape = (ch == '\\' and not escape)
            i += 1
            continue

        # not in string or comment
        if ch == '/' and nxt == '*':
            in_block_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '/':
            in_line_comment = True
            i += 2
            continue

        if ch == "'":
            in_s = True
            out.append(ch)
            escape = False
            i += 1
            continue
        if ch == '"':
            in_d = True
            out.append(ch)
            escape = False
            i += 1
            continue
        if ch == '`':
            in_b = True
            out.append(ch)
            escape = False
            i += 1
            continue

        out.append(ch)
        i += 1
    return ''.join(out)

def should_process(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.stat().st_size > MAX_SIZE:
        return False
    if path.suffix.lower() in EXTS:
        return True
    return False

def main():
    print(f'Workspace root: {ROOT}')
    print('Creating backup...')
    try:
        shutil.copytree(ROOT, BACKUP_DIR)
    except Exception as e:
        print('Backup failed:', e)
        sys.exit(1)
    print('Backup created at', BACKUP_DIR)

    for dirpath, dirnames, filenames in os.walk(ROOT):
        # skip backup folder itself
        if BACKUP_DIR.parts[-1] in Path(dirpath).parts:
            continue
        for fname in filenames:
            fpath = Path(dirpath) / fname
            # skip the script itself
            if fpath.resolve() == Path(__file__).resolve():
                continue
            if not should_process(fpath):
                skipped_files.append(str(fpath.relative_to(ROOT)))
                continue
            try:
                txt = fpath.read_text(encoding='utf-8')
            except Exception:
                skipped_files.append(str(fpath.relative_to(ROOT)))
                continue

            original = txt
            ext = fpath.suffix.lower()
            if ext in {'.html', '.htm', '.xml', '.svg'}:
                cleaned = remove_html_comments(txt)
                # also remove CSS/JS style block comments inside these? they are part of markup; but HTML removal will remove <!-- --> only
            elif ext in {'.css', '.scss'}:
                cleaned = remove_css_comments(txt)
            elif ext in {'.js', '.map'}:
                # For .map and minified vendor files which may be mostly JS-like, apply block comment removal first
                cleaned = re.sub(r'/\*([\s\S]*?)\*/', '', txt)
                # then attempt to remove // style comments carefully
                cleaned = remove_js_comments(cleaned)
            elif ext in {'.txt', '.json'}:
                # Remove C-style blocks and line comments starting with // and HTML comments
                cleaned = re.sub(r'/\*([\s\S]*?)\*/', '', txt)
                cleaned = re.sub(r'<!--([\s\S]*?)-->', '', cleaned)
                cleaned = re.sub(r'//.*', '', cleaned)
            else:
                cleaned = txt

            if cleaned != original:
                fpath.write_text(cleaned, encoding='utf-8')
                changed_files.append(str(fpath.relative_to(ROOT)))

    print('\nDone. Files changed:')
    for p in changed_files:
        print(' -', p)
    print('\nFiles skipped (binary/large/unprocessed):')
    for p in skipped_files[:50]:
        print(' -', p)
    if len(skipped_files) > 50:
        print(' - ...', len(skipped_files) - 50, 'more')

    print('\nBackup retained at', BACKUP_DIR)

if __name__ == '__main__':
    main()
