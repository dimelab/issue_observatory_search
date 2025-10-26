# Keyboard Shortcuts Reference

Complete reference for all keyboard shortcuts in the Issue Observatory Search application.

**Quick Access:** Press `?` anywhere in the application to view this reference.

---

## Global Shortcuts

These shortcuts work from any page in the application.

### Navigation

| Shortcut | Action | Description |
|----------|--------|-------------|
| `/` | Focus search | Jump to the search input field |
| `Ctrl+K` / `Cmd+K` | Command palette | Open quick actions menu (future feature) |
| `G` then `D` | Go to Dashboard | Navigate to the dashboard page |
| `G` then `N` | Go to Networks | Navigate to the networks page |
| `G` then `S` | New Search | Navigate to new search page |
| `Escape` | Close | Close open modals, dropdowns, or overlays |

### Actions

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+N` / `Cmd+N` | New session | Create a new search session |
| `Ctrl+E` / `Cmd+E` | Export | Export current view/data |
| `Ctrl+R` / `Cmd+R` | Refresh | Refresh current data |
| `?` | Help | Show keyboard shortcuts reference |

---

## Network Visualization

These shortcuts work when viewing a network visualization.

### View Controls

| Shortcut | Action | Description |
|----------|--------|-------------|
| `+` or `=` | Zoom in | Increase zoom level |
| `-` | Zoom out | Decrease zoom level |
| `0` (zero) | Reset view | Fit network to viewport |
| `P` | Toggle physics | Enable/disable physics simulation |

### Advanced Controls

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+Shift+S` | Export PNG | Save network visualization as image |
| `F` | Focus node | Focus on selected node |
| `Ctrl+F` | Search nodes | Focus search input |

### Mouse/Trackpad Controls

| Control | Action |
|---------|--------|
| Click + Drag | Pan view |
| Scroll | Zoom in/out |
| Click node | Select node |
| Double-click node | Focus on node |
| Double-click background | Reset selection |

---

## Data Table Navigation

These shortcuts work when a data table has focus.

### Row Navigation

| Shortcut | Action | Description |
|----------|--------|-------------|
| `↑` (Arrow Up) | Previous row | Move selection to previous row |
| `↓` (Arrow Down) | Next row | Move selection to next row |
| `Enter` | Activate | Open/activate selected row |
| `Space` | Toggle selection | Check/uncheck row checkbox |

### Table Actions

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+A` | Select all | Select all visible rows |
| `Ctrl+Shift+A` | Deselect all | Clear all selections |

---

## Form Inputs

### Text Input

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Tab` | Next field | Move to next input field |
| `Shift+Tab` | Previous field | Move to previous input field |
| `Enter` | Submit | Submit form (when in text input) |
| `Escape` | Cancel | Clear input or cancel operation |

### Autocomplete

| Shortcut | Action | Description |
|----------|--------|-------------|
| `↓` (Arrow Down) | Next suggestion | Move to next autocomplete suggestion |
| `↑` (Arrow Up) | Previous suggestion | Move to previous suggestion |
| `Enter` | Select | Select highlighted suggestion |
| `Escape` | Close | Close autocomplete dropdown |

---

## Modal Dialogs

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Escape` | Close modal | Dismiss active modal |
| `Tab` | Next element | Navigate forward through modal elements |
| `Shift+Tab` | Previous element | Navigate backward through modal elements |

---

## Accessibility Shortcuts

### Screen Reader

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Skip to main` | Skip navigation | Jump directly to main content (Tab from page load) |

### Focus Management

- Focus indicators are visible on all interactive elements
- Tab order follows logical page structure
- Modal dialogs trap focus until dismissed

---

## Custom Shortcuts

You can register custom keyboard shortcuts using the Shortcut Manager:

```javascript
// Register a custom shortcut
shortcutManager.register('ctrl+alt+t', () => {
    console.log('Custom shortcut triggered');
}, 'Description of action', 'Category');

// Unregister a shortcut
shortcutManager.unregister('ctrl+alt+t');

// Disable all shortcuts
shortcutManager.disable();

// Enable shortcuts
shortcutManager.enable();
```

---

## Key Sequences

Some shortcuts use key sequences (press keys in order):

- `G` + `D` = Go to Dashboard
- `G` + `N` = Go to Networks
- `G` + `S` = New Search

**How it works:** Press the first key, then the second key within 1 second.

---

## Platform Differences

### Mac (macOS)

- `Cmd` replaces `Ctrl` for most shortcuts
- `Cmd+K` for command palette
- `Cmd+N` for new session
- `Cmd+E` for export

### Windows/Linux

- `Ctrl` for all control shortcuts
- `Ctrl+K` for command palette
- `Ctrl+N` for new session
- `Ctrl+E` for export

---

## Disabling Shortcuts

Keyboard shortcuts are automatically disabled when typing in:
- Text inputs (`<input>`)
- Text areas (`<textarea>`)
- Content-editable elements

**Exception:** The `/` shortcut always focuses search, even when in an input field (unless you've started typing).

---

## Tips and Best Practices

### 1. Learn Gradually

Start with the most common shortcuts:
- `/` for search
- `Escape` to close things
- `?` to see this reference

### 2. Use Key Sequences

Key sequences are easier to remember than complex combinations:
- Think "G for Go, D for Dashboard"
- Mnemonic: **G**o to **D**ashboard

### 3. Customize for Your Workflow

Create custom shortcuts for frequently used actions:

```javascript
// Example: Quick export
shortcutManager.register('e e', exportCurrentData, 'Quick export', 'Custom');
```

### 4. Screen Readers

If using a screen reader:
- Use standard screen reader shortcuts
- Application shortcuts won't interfere
- Focus indicators are enhanced
- Live regions announce changes

---

## Troubleshooting

### Shortcut not working

**Check these common issues:**

1. **Are you typing in an input?**
   - Shortcuts are disabled in text inputs (except `/`)
   - Press `Escape` to unfocus the input

2. **Is a modal open?**
   - Some shortcuts only work in specific contexts
   - Close the modal first

3. **Browser conflict?**
   - Some browsers override certain shortcuts
   - Try the alternative shortcut (e.g., `Cmd` instead of `Ctrl`)

4. **JavaScript disabled?**
   - Keyboard shortcuts require JavaScript
   - Enable JavaScript in your browser

### Finding the right shortcut

- Press `?` to see all available shortcuts
- Shortcuts are grouped by category
- Look for the feature you want to use

### Conflicting shortcuts

If a shortcut conflicts with your browser or OS:
- Use the alternative shortcut (if available)
- Customize the shortcut in settings (future feature)
- Disable browser extension shortcuts

---

## Accessibility Considerations

### WCAG 2.1 Compliance

All keyboard shortcuts follow WCAG 2.1 Level AA guidelines:

1. **Keyboard Access:** All functionality available via keyboard
2. **Focus Indicators:** Clear visual focus indicators
3. **No Keyboard Trap:** Users can navigate away from any element
4. **Timing:** No time-sensitive shortcuts

### Screen Reader Compatibility

Tested with:
- NVDA (Windows)
- JAWS (Windows)
- VoiceOver (macOS/iOS)
- TalkBack (Android)

### Customization

Future feature: Customize keyboard shortcuts in user settings.

---

## Quick Reference Card

Print this quick reference:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         ISSUE OBSERVATORY SEARCH
            KEYBOARD SHORTCUTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NAVIGATION
  /           Focus search
  G + D       Go to Dashboard
  G + N       Go to Networks
  Esc         Close modal/dropdown

ACTIONS
  Ctrl+N      New search session
  Ctrl+E      Export data
  ?           Show shortcuts help

NETWORK VISUALIZATION
  +/-         Zoom in/out
  0           Reset view
  P           Toggle physics
  Ctrl+⇧+S    Export PNG

TABLE NAVIGATION
  ↑/↓         Navigate rows
  Enter       Activate row
  Space       Toggle selection

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Press ? anywhere to see full shortcuts list
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Feedback

Have suggestions for keyboard shortcuts?

- Missing a common action?
- Shortcut hard to remember?
- Conflict with your workflow?

Contact the development team or submit feedback through the application settings (future feature).

---

**Last Updated:** 2025-10-25
**Shortcuts Version:** 1.0.0
**Platform:** Web Browser
