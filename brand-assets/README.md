# BYD-HA brand assets

Original artwork for the BYD Home Assistant integration. The rendered PNGs are
also shipped inside the integration at `custom_components/byd/brand/`, which
Home Assistant (2026.x) and the Marketplace read directly, so no
[`home-assistant/brands`](https://github.com/home-assistant/brands) PR is
needed. Re-copy them there after running `render_brand.py`.

## Contents

| File | Purpose |
|------|---------|
| `icon.svg`, `logo.svg` | editable vector masters (design source) |
| `render_brand.py` | regenerates the PNGs below with Pillow (`pip install pillow`) |
| `custom_integrations/byd/icon.png` (256×256) + `icon@2x.png` (512×512) | square app icon, full-bleed |
| `custom_integrations/byd/logo.png` (512×120) + `logo@2x.png` (1024×240) | wordmark, light theme |
| `custom_integrations/byd/dark_logo.png` + `dark_logo@2x.png` | wordmark, dark theme |

All PNGs are transparent, tightly trimmed, and each `@2x` is an exact 2× of its base — the checks the brands repo enforces.

## Submitting to home-assistant/brands

1. Fork and clone `home-assistant/brands`.
2. Copy the `custom_integrations/byd/` folder from here into the repo root
   (final path: `custom_integrations/byd/icon.png`, etc.).
3. `python -m script.validate` (or `hassfest`) locally if you have it, to
   confirm sizing/trim.
4. Open a PR. Once merged, the logo appears automatically in the
   *Add Integration* list, on the integration page, and on the device — no
   change to this integration is needed.

## Trademark note

This is **original artwork** (a blue EV badge + wordmark), not BYD's official
trademarked logo, so it is safe to publish. Using it to identify the product
the integration works with is nominative use; it does not imply BYD built or
endorsed the integration. If you later swap in BYD's official logo, that is the
brands convention for manufacturer integrations, but review BYD's trademark
terms first.
