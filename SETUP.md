# Setup

This repository is designed to be used as the profile repository for `aryankr01`.

## 1. Repository name

Create/use the special GitHub profile repository:

`aryankr01/aryankr01`

## 2. Upload

Upload everything in this repository while preserving the folders:

- `README.md`
- `assets/`
- `scripts/`
- `.github/workflows/`

## 3. GitHub Actions

The workflow uses GitHub's built-in `GITHUB_TOKEN`; no personal access token is required.

It updates the generated SVG cards weekly and can also be run manually from **Actions → Update Profile Stats → Run workflow**.

## 4. Theme support

The profile uses `<picture>` elements with separate dark/light SVGs. GitHub automatically selects the matching asset based on the viewer's color scheme.

## 5. Local generation

From the repository root:

```bash
python scripts/generate_stats.py
```

The script needs `GITHUB_TOKEN` for live GitHub statistics. LeetCode statistics are fetched without a token.
