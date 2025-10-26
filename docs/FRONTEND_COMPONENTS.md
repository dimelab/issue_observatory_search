# Frontend Components Documentation

## Component Library Overview

The Issue Observatory Search frontend includes a comprehensive library of reusable UI components built with Alpine.js, Tailwind CSS, and Jinja2 macros.

All components are located in `frontend/templates/components/`.

---

## Table of Contents

1. [Modal](#modal)
2. [Toast Notifications](#toast-notifications)
3. [Tabs](#tabs)
4. [Dropdown](#dropdown)
5. [Progress Bar](#progress-bar)
6. [File Upload](#file-upload)
7. [Empty State](#empty-state)
8. [Skeleton Loaders](#skeleton-loaders)
9. [Keyboard Shortcuts Modal](#keyboard-shortcuts-modal)

---

## Modal

**File:** `components/modal.html`

### Description
Accessible modal dialog with backdrop, keyboard navigation, and multiple size options.

### Usage

```jinja
{% from 'components/modal.html' import modal %}

{% call modal('confirmation-modal', 'Confirm Action', 'md') %}
    <p>Are you sure you want to proceed?</p>

    {% call caller.footer() %}
        <button class="btn btn-primary">Confirm</button>
        <button @click="$dispatch('close-modal-confirmation-modal')">Cancel</button>
    {% endcall %}
{% endcall %}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `id` | string | required | Unique identifier for the modal |
| `title` | string | '' | Modal title |
| `size` | string | 'lg' | Size variant: 'sm', 'md', 'lg', 'xl', '2xl', 'full' |
| `show_close` | boolean | True | Show close button in header |

### Opening/Closing

```javascript
// Open modal
$dispatch('open-modal-confirmation-modal')

// Close modal
$dispatch('close-modal-confirmation-modal')

// Or use Alpine.js
this.open = true/false
```

### Accessibility

- ARIA role="dialog"
- ARIA aria-modal="true"
- ARIA aria-labelledby for title
- Keyboard: Escape to close
- Click backdrop to dismiss
- Focus management

---

## Toast Notifications

**File:** `components/toast.html`

### Description
Floating notification messages with auto-dismiss and manual close options.

### Usage

```jinja
{# Include in base.html #}
{% include 'components/toast.html' %}
```

```javascript
// JavaScript API
showToast('Operation completed successfully!', 'success', 5000);
showToast('An error occurred', 'error');
showToast('Please wait...', 'info', 3000);
showToast('Warning: Check your input', 'warning');
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `message` | string | required | Message text to display |
| `type` | string | 'info' | Toast variant: 'success', 'error', 'warning', 'info' |
| `duration` | number | 5000 | Auto-dismiss time in milliseconds (0 = no auto-dismiss) |

### Styling

Each type has distinct colors:
- **Success:** Green background, green icon
- **Error:** Red background, red icon
- **Warning:** Yellow background, yellow icon
- **Info:** Blue background, blue icon

### Features

- Stack multiple toasts
- Smooth enter/exit animations
- Auto-dismiss with countdown
- Manual close button
- Screen reader announcements
- Responsive positioning

---

## Tabs

**File:** `components/tabs.html`

### Description
Accessible tabbed interface with keyboard navigation.

### Usage

```jinja
<div x-data="{
    activeTab: 'general',
    tabs: [
        { id: 'general', label: 'General', badge: null },
        { id: 'advanced', label: 'Advanced', badge: '3' },
        { id: 'settings', label: 'Settings', badge: null }
    ]
}">
    {% from 'components/tabs.html' import tabs, tab_panel %}

    {{ tabs() }}

    {% call tab_panel('general') %}
        <p>General content here</p>
    {% endcall %}

    {% call tab_panel('advanced') %}
        <p>Advanced content here</p>
    {% endcall %}

    {% call tab_panel('settings') %}
        <p>Settings content here</p>
    {% endcall %}
</div>
```

### Tab Object Structure

```javascript
{
    id: 'unique-id',      // Tab identifier
    label: 'Tab Label',   // Display text
    badge: '5'            // Optional badge (count, status, etc.)
}
```

### Keyboard Navigation

- **Arrow Right:** Next tab
- **Arrow Left:** Previous tab
- **Home:** First tab
- **End:** Last tab

### Accessibility

- ARIA role="tablist", "tab", "tabpanel"
- ARIA aria-selected
- ARIA aria-controls / aria-labelledby
- Proper tabindex management

---

## Dropdown

**File:** `components/dropdown.html`

### Description
Context menu / dropdown component with customizable options.

### Usage

```jinja
{% from 'components/dropdown.html' import dropdown_menu, dropdown_item, dropdown_divider %}

{% call dropdown_menu('Actions', 'right', 'w-56') %}
    {% call dropdown_item('/edit') %}
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
        Edit
    {% endcall %}

    {{ dropdown_divider() }}

    {% call dropdown_item('/delete', destructive=True) %}
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
        Delete
    {% endcall %}
{% endcall %}
```

### Parameters

| Macro | Parameter | Type | Default | Description |
|-------|-----------|------|---------|-------------|
| `dropdown_menu` | `button_text` | string | 'Options' | Button text |
| | `align` | string | 'right' | Alignment: 'left', 'right' |
| | `width` | string | 'w-56' | Tailwind width class |
| | `button_class` | string | '' | Custom button classes |
| `dropdown_item` | `href` | string | '#' | Link destination |
| | `icon` | string | '' | SVG path for icon |
| | `destructive` | boolean | False | Red styling for dangerous actions |

### Features

- Click-away to close
- Keyboard navigation
- Smooth animations
- Icon support
- Dividers for grouping
- Destructive action styling

---

## Progress Bar

**File:** `components/progress.html`

### Description
Visual progress indicators for tasks and loading states.

### Usage

#### Static Progress

```jinja
{% from 'components/progress.html' import progress_bar %}

{{ progress_bar(value=75, max=100, variant='primary', size='md', show_label=True, label='Uploading...') }}
```

#### Indeterminate (Loading)

```jinja
{{ progress_bar(indeterminate=True, variant='primary', label='Processing...') }}
```

#### Alpine.js Reactive

```jinja
{% from 'components/progress.html' import progress_bar_alpine %}

<div x-data="{ progress: 0 }">
    {{ progress_bar_alpine(variant='success', label='Download Progress') }}

    <button @click="progress += 10">Increase</button>
</div>
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | number | 0 | Current progress value (0-max) |
| `max` | number | 100 | Maximum value |
| `variant` | string | 'primary' | Color: 'primary', 'success', 'warning', 'error' |
| `size` | string | 'md' | Size: 'sm', 'md', 'lg' |
| `show_label` | boolean | True | Show label and percentage |
| `label` | string | '' | Label text |
| `indeterminate` | boolean | False | Show loading animation |

### Variants

- **Primary:** Blue
- **Success:** Green
- **Warning:** Yellow
- **Error:** Red

---

## File Upload

**File:** `components/file-upload.html`

### Description
Drag-and-drop file uploader with validation and progress tracking.

### Usage

```jinja
<div x-data="fileUploader({
    accept: '.csv,.txt',
    maxSize: 10485760,  // 10MB
    uploadUrl: '/api/upload',
    onUploadComplete: (response) => {
        console.log('Upload complete:', response);
        showToast('File uploaded!', 'success');
    }
})">
    {% include 'components/file-upload.html' %}
</div>
```

### Configuration Options

```javascript
{
    accept: '.csv,.txt',           // Accepted file types
    maxSize: 10485760,             // Max file size in bytes (10MB)
    multiple: false,               // Allow multiple files
    uploadUrl: '/api/upload',      // Upload endpoint
    onUploadComplete: (response) => {}  // Callback
}
```

### Features

- Drag-and-drop support
- File type validation
- Size validation
- Upload progress bar
- Error handling
- File preview
- Remove file option
- Auto-upload (optional)

### Methods

```javascript
// Programmatic file handling
this.handleFile(file)    // Process file
this.removeFile()        // Clear file
this.uploadFile()        // Trigger upload
```

---

## Empty State

**File:** `components/empty-state.html`

### Description
Friendly empty state displays with icon, message, and call-to-action.

### Usage

```jinja
{% from 'components/empty-state.html' import empty_state, simple_empty %}

{% call empty_state('No results found', 'Try adjusting your search criteria', 'search') %}
    <a href="/search/new" class="btn btn-primary">
        New Search
    </a>
{% endcall %}
```

#### Simple Empty State

```jinja
{{ simple_empty('No items to display') }}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | string | '' | Main title |
| `description` | string | '' | Description text |
| `icon_type` | string | 'default' | Icon type (see below) |

### Icon Types

- `search` - Search icon
- `document` - Document icon
- `folder` - Folder icon
- `network` - Network/globe icon
- `chart` - Chart/graph icon
- `inbox` - Inbox icon
- `default` - Generic icon

### Styling

- Centered layout
- Large icon (24x24)
- Gray color scheme
- Responsive padding
- Call-to-action button slot

---

## Skeleton Loaders

**File:** `components/skeleton.html`

### Description
Loading placeholders that match content structure.

### Usage

#### Text Skeleton

```jinja
{% from 'components/skeleton.html' import skeleton_text %}

{{ skeleton_text(lines=3, class='mb-4') }}
```

#### Card Skeleton

```jinja
{% from 'components/skeleton.html' import skeleton_card %}

{{ skeleton_card(class='mb-4') }}
```

#### Table Skeleton

```jinja
{% from 'components/skeleton.html' import skeleton_table %}

{{ skeleton_table(rows=5, columns=4) }}
```

#### List Skeleton

```jinja
{% from 'components/skeleton.html' import skeleton_list %}

{{ skeleton_list(items=3) }}
```

#### Network Card Skeleton

```jinja
{% from 'components/skeleton.html' import skeleton_network_card %}

{{ skeleton_network_card() }}
```

#### Full Page Skeleton

```jinja
{% from 'components/skeleton.html' import skeleton_page %}

{{ skeleton_page(type='dashboard') }}
```

Types: `dashboard`, `network`, `list`, default

### Features

- Pulse animation
- Matches content structure
- Multiple variants
- Responsive design
- Accessible (aria-busy)

---

## Keyboard Shortcuts Modal

**File:** `components/shortcuts-modal.html`

### Description
Reference guide for all keyboard shortcuts in the application.

### Usage

```jinja
{# Include in base.html #}
{% include 'components/shortcuts-modal.html' %}
```

```javascript
// Show modal
window.showShortcutsModal();

// Or press '?' anywhere in the app
```

### Features

- Organized by category
- Styled keyboard keys
- Search functionality (future)
- Toggle with `?` key
- Accessible modal pattern

### Customization

Add custom shortcuts in the modal template:

```html
<div class="flex justify-between items-center py-2">
    <span class="text-sm text-gray-700">Your action</span>
    <kbd class="kbd">Y</kbd>
</div>
```

---

## Component Best Practices

### 1. Consistent Styling

Use Tailwind utility classes for consistency:
- Primary actions: `bg-blue-600 text-white`
- Secondary actions: `bg-gray-100 text-gray-700`
- Destructive actions: `bg-red-600 text-white`

### 2. Accessibility

Always include:
- ARIA roles and labels
- Keyboard navigation
- Focus indicators
- Screen reader text

### 3. Responsive Design

Test components at all breakpoints:
- Mobile: 320px - 640px
- Tablet: 640px - 1024px
- Desktop: 1024px+

### 4. Error Handling

Provide clear feedback:
- Validation errors inline
- Success messages in toasts
- Error states in modals

### 5. Performance

Optimize for performance:
- Use `x-cloak` to prevent FOUC
- Debounce input handlers
- Lazy load heavy components
- Minimize DOM manipulation

---

## Creating New Components

### Template

```jinja
<!--
    Component Name

    Description of what this component does

    Props:
    - prop1: Description
    - prop2: Description

    Usage:
    {% include 'components/your-component.html' %}
-->

{% macro your_component(prop1, prop2='default') %}
<div class="your-component">
    <!-- Component markup -->
</div>
{% endmacro %}
```

### Guidelines

1. **Documentation:** Include usage examples in comments
2. **Naming:** Use kebab-case for files, camelCase for Alpine.js
3. **Accessibility:** Follow WCAG 2.1 AA guidelines
4. **Styling:** Use Tailwind utilities first, custom CSS only when needed
5. **Testing:** Test in all supported browsers
6. **Responsiveness:** Design mobile-first

---

## Component Dependencies

### Required Libraries

- **Alpine.js 3.13+:** Reactive components
- **Tailwind CSS:** Utility-first styling
- **HTMX:** Server interactions (optional)

### Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile Safari iOS 14+
- Chrome Mobile Android 90+

---

## Troubleshooting

### Modal not opening

- Check Alpine.js is loaded
- Verify event dispatch: `$dispatch('open-modal-your-id')`
- Check z-index conflicts

### Toast not showing

- Ensure `showToast` function is available
- Check Alpine.js initialized
- Verify toast container exists

### Skeleton not animating

- Check `animate-pulse` class applied
- Verify Tailwind CSS loaded
- Check for CSS conflicts

### File upload not working

- Verify `fileUploader` function available
- Check `uploadUrl` is correct
- Verify CORS settings
- Check file size limits

---

## Further Resources

- [Alpine.js Documentation](https://alpinejs.dev/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)

---

**Last Updated:** 2025-10-25
**Component Library Version:** 1.0.0
