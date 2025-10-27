# Import Conflicts Fix

## Issue

```
ImportError: cannot import name 'export_to_gexf' from 'backend.core.networks.exporters'
```

## Root Cause

Python module name conflicts. The `backend/core/networks/` directory contained both:

1. **exporters.py** (file) - Contains the actual functions
2. **exporters/** (directory) - Empty placeholder directory

When Python imports `backend.core.networks.exporters`, it prefers the **directory** over the **file**, so it tries to import from the empty `exporters/__init__.py` instead of `exporters.py`.

## Directory Structure Before Fix

```
backend/core/networks/
├── exporters.py           # Contains export_to_gexf, etc.
├── exporters/             # Empty directory (CONFLICT!)
│   └── __init__.py        # Empty placeholder
├── builders/              # Empty directory (potential conflict)
│   └── __init__.py        # Empty placeholder
└── ...other files
```

## Solution

Removed the empty conflicting directories:

```bash
rm -rf backend/core/networks/exporters/
rm -rf backend/core/networks/builders/
```

## Directory Structure After Fix

```
backend/core/networks/
├── exporters.py           # ✅ Now imports correctly
├── backboning.py
├── base.py
├── graph_utils.py
├── search_website.py
├── website_concept.py
├── website_noun.py
└── __init__.py
```

## Python Import Priority

Python's import priority (highest to lowest):
1. **Package (directory with `__init__.py`)** ⬅️ Was causing the issue
2. **Module (`.py` file)**
3. Built-in modules

When both exist with the same name, Python **always** chooses the directory.

## Why This Happened

These directories were likely created as placeholders for future code organization:

```python
# exporters/__init__.py
"""Network exporters sub-package."""
# This directory is for organization; exporters are imported from parent module
```

However, they should not exist alongside files with the same name, as this creates import conflicts.

## Verification

Test that imports work:

```bash
python -c "from backend.core.networks.exporters import export_to_gexf; print('✅ Success')"
python -c "from backend.main import app; print('✅ Application imports successfully')"
```

## Related Files Fixed

- Removed: `backend/core/networks/exporters/`
- Removed: `backend/core/networks/builders/`
- Kept: `backend/core/networks/exporters.py` (contains actual functions)

## Functions Available

From `backend.core.networks.exporters.py`:
- `export_to_gexf()` - Export to GEXF format (Gephi)
- `export_to_graphml()` - Export to GraphML format
- `export_to_edgelist()` - Export to edge list
- `export_to_json()` - Export to JSON
- `export_graph()` - Main export function

## Status

✅ Import conflicts resolved
✅ Empty placeholder directories removed
✅ All network exporter functions accessible
✅ Application can import without errors
