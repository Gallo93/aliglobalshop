# Favicon generation TODO

The binary files `favicon.ico` and `apple-touch-icon.png` cannot be generated via the
text-only push pipeline. Run this command locally after cloning to produce them from
the existing `favicon.svg`:

```
python _scripts/generate_favicons.py
```

Or use https://realfavicongenerator.net/ with `assets/img/favicon.svg` as input.

Required outputs to commit afterwards:
- `assets/img/favicon.ico` (32x32)
- `assets/img/apple-touch-icon.png` (180x180)

Until these are added, browsers will fall back to `favicon.svg` (already present).
