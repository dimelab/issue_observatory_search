# Playwright Installation Guide

## Why `python -m playwright` Instead of Just `playwright`?

When you install Playwright via pip in a virtual environment, the `playwright` command-line tool may not be automatically added to your PATH. This is especially common when:

- Using virtual environments (`.venv`, `venv`, `virtualenv`)
- Installing with `pip install -e .` (editable mode)
- On Windows with certain Python installations

## The Solution: Use Python Module Syntax

**Always use**:
```bash
python -m playwright install chromium
```

**Instead of**:
```bash
playwright install chromium  # ❌ May fail with "command not found"
```

## Why This Works

`python -m playwright` tells Python to:
1. Find the `playwright` module in your installed packages
2. Run its `__main__.py` file
3. Works regardless of PATH configuration

This is the **official recommended method** from Playwright documentation.

---

## Complete Playwright Installation

### Step 1: Install Playwright Python Package

```bash
# This installs the Python library
pip install playwright

# Or if installing the full project
pip install -e .[dev]
```

### Step 2: Install Browser Binaries

```bash
# Install Chromium (recommended for scraping)
python -m playwright install chromium

# Or install all browsers
python -m playwright install

# Or install specific browsers
python -m playwright install firefox
python -m playwright install webkit
```

### Step 3: Verify Installation

```bash
# Check version
python -m playwright --version

# List installed browsers
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"
```

---

## Linux: Install System Dependencies

On Linux, you need system libraries for browsers:

```bash
# Install all dependencies for all browsers
python -m playwright install-deps

# Or for specific browser
python -m playwright install-deps chromium

# Then install the browser
python -m playwright install chromium
```

**Ubuntu/Debian** - Required packages:
```bash
# These are automatically installed by playwright install-deps
libnss3
libnspr4
libatk1.0-0
libatk-bridge2.0-0
libcups2
libdrm2
libxkbcommon0
libxcomposite1
libxdamage1
libxfixes3
libxrandr2
libgbm1
libasound2
```

---

## macOS: No Special Setup Needed

```bash
# Just install the browser
python -m playwright install chromium
```

Playwright handles everything automatically on macOS.

---

## Windows: No Special Setup Needed

```bash
# Just install the browser
python -m playwright install chromium
```

Playwright handles everything automatically on Windows.

---

## Common Issues

### Issue 1: "playwright: command not found"

**Cause**: `playwright` CLI not in PATH (common in virtual environments)

**Solution**: Use `python -m playwright` instead
```bash
python -m playwright install chromium
```

---

### Issue 2: "Executable doesn't exist at /path/to/chromium"

**Cause**: Browser not installed or installation failed

**Solution**: Reinstall browsers
```bash
python -m playwright install --force chromium
```

---

### Issue 3: "Permission denied" (Linux)

**Cause**: System dependencies missing or insufficient permissions

**Solution**: Install system dependencies first
```bash
sudo python -m playwright install-deps chromium
python -m playwright install chromium
```

---

### Issue 4: Large download size

**Expected**: Chromium is ~300MB

**Why**: Full browser with rendering engine

**Cannot avoid**: This is the actual browser binary

---

### Issue 5: "Browser version mismatch"

**Cause**: Playwright package updated but browsers not

**Solution**: Reinstall browsers
```bash
pip install --upgrade playwright
python -m playwright install --force
```

---

## Where Are Browsers Installed?

Playwright installs browsers to platform-specific locations:

**Linux/macOS**:
```
~/.cache/ms-playwright/
├── chromium-1091/
├── firefox-1413/
└── webkit-1883/
```

**Windows**:
```
%USERPROFILE%\AppData\Local\ms-playwright\
```

---

## Disk Space Requirements

| Browser | Size |
|---------|------|
| Chromium | ~300MB |
| Firefox | ~90MB |
| WebKit | ~60MB |
| **All 3** | **~450MB** |

---

## Uninstalling Browsers

```bash
# Remove browser binaries
rm -rf ~/.cache/ms-playwright/  # Linux/macOS
# Or manually delete from %USERPROFILE%\AppData\Local\ms-playwright\ on Windows

# Uninstall Python package
pip uninstall playwright
```

---

## Usage in Code

After installation, use Playwright in your Python code:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('https://example.com')
    print(page.title())
    browser.close()
```

Or async (recommended for FastAPI):

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch()
    page = await browser.new_page()
    await page.goto('https://example.com')
    print(await page.title())
    await browser.close()
```

---

## Alternative: Using Docker

If you don't want to install browsers locally:

```bash
# Use Playwright Docker image
docker run -it --rm mcr.microsoft.com/playwright:v1.41.0 /bin/bash

# Inside container
python -m playwright install chromium
```

Or in docker-compose.yml:
```yaml
playwright:
  image: mcr.microsoft.com/playwright:v1.41.0
  volumes:
    - ./backend:/app/backend
  command: python -m playwright install chromium
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Install Chromium | `python -m playwright install chromium` |
| Install Firefox | `python -m playwright install firefox` |
| Install all browsers | `python -m playwright install` |
| Install dependencies (Linux) | `python -m playwright install-deps` |
| Reinstall (force) | `python -m playwright install --force chromium` |
| Check version | `python -m playwright --version` |
| Uninstall browsers | `rm -rf ~/.cache/ms-playwright/` |

---

## Documentation Links

- **Official Playwright Docs**: https://playwright.dev/python/
- **Installation Guide**: https://playwright.dev/python/docs/intro
- **System Requirements**: https://playwright.dev/python/docs/browsers
- **Docker Images**: https://playwright.dev/python/docs/docker

---

## Summary

✅ **Always use**: `python -m playwright install chromium`
❌ **Don't use**: `playwright install chromium` (may not work)

This ensures the command works in all environments, including virtual environments.
