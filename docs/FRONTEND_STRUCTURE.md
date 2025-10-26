# Frontend Structure & Component Hierarchy

Visual reference for the Issue Observatory Search frontend architecture.

## Application Flow

```
┌─────────────┐
│   Login     │ (Public)
│  /          │
└──────┬──────┘
       │ Authenticate
       ▼
┌─────────────┐
│  Dashboard  │ (Protected)
│ /dashboard  │
└──────┬──────┘
       │
       ├─────────────────────┬─────────────────────┐
       ▼                     ▼                     ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ New Search  │      │  Session    │      │ Scraping    │
│/search/new  │      │   Details   │      │    Jobs     │
└──────┬──────┘      │ /search/    │      │ /scraping/  │
       │             │ session/{id}│      │    jobs     │
       │             └──────┬──────┘      └──────┬──────┘
       │                    │                    │
       │                    ▼                    ▼
       │             ┌─────────────┐      ┌─────────────┐
       │             │  Start      │      │ Job Details │
       └────────────▶│  Scraping   │◀─────│ /scraping/  │
                     │   Modal     │      │   job/{id}  │
                     └─────────────┘      └─────────────┘
```

## Template Hierarchy

```
base.html (Root Template)
│
├─ Navigation Bar
│  ├─ Logo / App Name
│  ├─ Dashboard Link
│  ├─ New Search Link
│  ├─ Scraping Jobs Link
│  └─ User Menu (Username, Logout)
│
├─ Flash Messages Container
│
├─ Main Content Block
│  │
│  ├─ login.html
│  │  └─ Login Form
│  │     ├─ Username Input
│  │     ├─ Password Input
│  │     ├─ Remember Me Checkbox
│  │     └─ Submit Button
│  │
│  ├─ dashboard.html
│  │  ├─ Header (Welcome + New Search Button)
│  │  ├─ Sessions List (HTMX)
│  │  │  └─ partials/sessions_list.html
│  │  │     └─ Session Cards
│  │  │        ├─ Name + Status Badge
│  │  │        ├─ Statistics (Queries, Results, Domains)
│  │  │        └─ Actions (View, Delete)
│  │  └─ Quick Stats Cards
│  │     ├─ Total Searches
│  │     ├─ Completed
│  │     └─ Processing
│  │
│  ├─ search/new.html
│  │  └─ Search Form
│  │     ├─ Session Name
│  │     ├─ Search Engine Selector
│  │     ├─ Keywords Textarea
│  │     ├─ Max Results
│  │     ├─ Domain Filter
│  │     ├─ Auto-Scrape Checkbox
│  │     └─ Scrape Depth Selector
│  │
│  ├─ search/session.html
│  │  ├─ Session Header
│  │  │  ├─ Name + Status Badge
│  │  │  ├─ Timestamps
│  │  │  └─ Actions (Back, Start Scraping, Delete)
│  │  ├─ Statistics Cards
│  │  │  ├─ Queries Count
│  │  │  ├─ Results Count
│  │  │  ├─ Unique Domains
│  │  │  └─ Search Engine
│  │  ├─ Queries Section
│  │  │  └─ Query Cards (Collapsible)
│  │  │     ├─ Query Text
│  │  │     ├─ Result Count
│  │  │     ├─ Status Badge
│  │  │     └─ Results (HTMX)
│  │  │        └─ partials/query_results.html
│  │  │           └─ Result Items
│  │  │              ├─ Title (Link)
│  │  │              ├─ URL
│  │  │              ├─ Description
│  │  │              ├─ Domain
│  │  │              └─ Scraped Status
│  │  └─ Scraping Modal
│  │     ├─ Job Name Input
│  │     ├─ Depth Selector
│  │     └─ Actions (Cancel, Start)
│  │
│  ├─ scraping/jobs.html
│  │  ├─ Header (Refresh, Dashboard)
│  │  ├─ Active Jobs Section (Auto-refresh)
│  │  │  └─ partials/jobs_list.html (filtered)
│  │  └─ All Jobs Section
│  │     └─ partials/jobs_list.html
│  │        └─ Job Cards
│  │           ├─ Name + Status Badge
│  │           ├─ Session Link
│  │           ├─ Progress Bar
│  │           ├─ Statistics (Depth, Success, Failed)
│  │           ├─ Timestamps
│  │           └─ Actions (View, Cancel/Delete)
│  │
│  └─ scraping/job.html
│     ├─ Job Header
│     │  ├─ Name + Status Badge
│     │  ├─ Session Link
│     │  ├─ Progress Bar (Real-time)
│     │  └─ Actions (Back, Cancel/Delete)
│     ├─ Statistics Cards
│     │  ├─ Total URLs
│     │  ├─ Successful
│     │  ├─ Failed
│     │  └─ Depth
│     ├─ Configuration Details
│     │  ├─ Depth
│     │  ├─ Domain Filter
│     │  ├─ Request Delay
│     │  ├─ Respect Robots.txt
│     │  └─ Timestamps
│     └─ Scraped Content Section
│        └─ partials/scraped_content.html
│           └─ Content Items
│              ├─ Title (Link)
│              ├─ URL
│              ├─ Domain
│              ├─ Status Badge
│              ├─ Word Count
│              ├─ Language
│              ├─ Scraped At
│              └─ Error Message (if failed)
│
└─ Footer
   ├─ Copyright
   └─ Links (Documentation, API Docs)
```

## Component Library

### Layout Components

#### Navigation Bar
```html
<nav class="bg-white shadow-md border-b">
  - Logo/Brand
  - Navigation Links (Desktop)
  - User Menu
  - Hamburger Menu (Mobile)
  - Mobile Menu (Collapsible)
</nav>
```

#### Page Container
```html
<main class="py-10">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <!-- Page content -->
  </div>
</main>
```

#### Card
```html
<div class="bg-white rounded-lg shadow-md p-6">
  <!-- Card content -->
</div>
```

### UI Components

#### Status Badge
```html
<span class="px-2 py-1 rounded-full text-xs font-medium bg-{color}-100 text-{color}-800">
  {status}
</span>
```

Colors:
- `green`: completed, success
- `yellow`: processing, pending
- `red`: failed, error
- `gray`: cancelled, neutral
- `blue`: pending, info

#### Progress Bar
```html
<div class="w-full bg-gray-200 rounded-full h-2">
  <div class="bg-blue-600 h-2 rounded-full" style="width: {percent}%"></div>
</div>
```

#### Button
```html
<!-- Primary -->
<button class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
  Action
</button>

<!-- Secondary -->
<button class="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50">
  Action
</button>

<!-- Danger -->
<button class="px-4 py-2 border border-red-300 text-red-700 rounded-md hover:bg-red-50">
  Delete
</button>
```

#### Loading Spinner
```html
<svg class="animate-spin h-5 w-5 text-blue-600">
  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
</svg>
```

#### Flash Message
```html
<div class="rounded-md bg-{color}-50 border border-{color}-200 p-4">
  <div class="flex">
    <svg class="h-5 w-5 text-{color}-400">...</svg>
    <p class="ml-3 text-sm text-{color}-800">{message}</p>
  </div>
</div>
```

### Form Components

#### Text Input
```html
<div>
  <label for="name" class="block text-sm font-medium text-gray-700">
    Label
  </label>
  <input
    type="text"
    id="name"
    class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
  />
</div>
```

#### Select
```html
<select class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500">
  <option value="">Select option</option>
  <option value="1">Option 1</option>
</select>
```

#### Textarea
```html
<textarea
  rows="4"
  class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
></textarea>
```

#### Checkbox
```html
<div class="flex items-center">
  <input
    type="checkbox"
    id="check"
    class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
  />
  <label for="check" class="ml-2 block text-sm text-gray-700">
    Label
  </label>
</div>
```

### Data Display Components

#### Statistics Card
```html
<div class="bg-white rounded-lg shadow-md p-6">
  <div class="flex items-center">
    <div class="flex-shrink-0 bg-blue-100 rounded-md p-3">
      <svg class="h-6 w-6 text-blue-600">...</svg>
    </div>
    <div class="ml-4">
      <p class="text-sm font-medium text-gray-500">Label</p>
      <p class="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  </div>
</div>
```

#### Data List
```html
<div class="divide-y divide-gray-200">
  <div class="p-6 hover:bg-gray-50">
    <!-- Item content -->
  </div>
  <div class="p-6 hover:bg-gray-50">
    <!-- Item content -->
  </div>
</div>
```

#### Empty State
```html
<div class="p-12 text-center">
  <svg class="mx-auto h-12 w-12 text-gray-400">...</svg>
  <h3 class="mt-2 text-sm font-medium text-gray-900">Title</h3>
  <p class="mt-1 text-sm text-gray-500">Description</p>
  <div class="mt-6">
    <button>Action</button>
  </div>
</div>
```

### Modal Components

#### Modal Container
```html
<div class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
  <div class="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
    <h3 class="text-lg font-bold mb-4">Title</h3>
    <!-- Modal content -->
    <div class="flex justify-end space-x-3 mt-6">
      <button>Cancel</button>
      <button>Confirm</button>
    </div>
  </div>
</div>
```

## HTMX Integration Points

### Auto-Refresh Elements
- Active scraping jobs (5s interval)
- Running job details (3s interval)

### Lazy-Load Elements
- Session query results (on expand)
- Scraped content list (on scroll)

### Dynamic Updates
- Sessions list (on dashboard)
- Jobs list (on jobs page)
- Query results (on session page)
- Scraped content (on job page)

### User Actions
- Delete session (confirmation + removal)
- Delete job (confirmation + removal)
- Cancel job (confirmation + status update)
- Load more (pagination)

## Responsive Breakpoints

```
Mobile:  320px - 639px  (1 column, stacked)
Tablet:  640px - 1023px (2 columns, compact)
Desktop: 1024px+        (3 columns, spacious)
```

### Layout Changes

#### Navigation
- **Mobile**: Hamburger menu, vertical links
- **Desktop**: Horizontal links, inline user menu

#### Cards Grid
- **Mobile**: `grid-cols-1` (full width)
- **Tablet**: `grid-cols-2` (2 columns)
- **Desktop**: `grid-cols-3` (3 columns)

#### Statistics
- **Mobile**: `grid-cols-2` (2×2 grid)
- **Desktop**: `grid-cols-4` (single row)

#### Actions
- **Mobile**: Stacked buttons (full width)
- **Desktop**: Inline buttons (auto width)

## State Management

### Client-Side State (localStorage)
```javascript
{
  "token": "JWT_TOKEN_STRING",
  "username": "user123"
}
```

### Server-Side State (Database)
- User sessions
- Search sessions
- Search queries
- Search results
- Scraping jobs
- Scraped content

### Transient State (Page)
- Form input values
- Expanded/collapsed sections
- Modal visibility
- Loading indicators

## File Size Reference

```
Template Files:
- base.html           ~5 KB
- login.html          ~8 KB
- dashboard.html      ~6 KB
- search/new.html     ~10 KB
- search/session.html ~12 KB
- scraping/jobs.html  ~7 KB
- scraping/job.html   ~14 KB
- Partials (4 files)  ~12 KB total

Static Files:
- app.js              ~8 KB
- custom.css          ~6 KB

Total: ~88 KB (uncompressed)
```

## Performance Characteristics

### Initial Page Load
- HTML: ~5-15 KB (gzipped)
- CSS (Tailwind CDN): ~3 MB (cached)
- JS (HTMX CDN): ~30 KB (cached)
- Custom JS/CSS: ~14 KB (cacheable)

### HTMX Partial Loads
- Sessions list: ~2-10 KB
- Query results: ~1-5 KB
- Jobs list: ~3-15 KB
- Scraped content: ~5-25 KB

### Auto-Refresh Bandwidth
- Active jobs (5s): ~3 KB every 5s
- Job details (3s): ~5 KB every 3s

## Browser Compatibility Matrix

```
Feature             Chrome  Firefox  Safari  Edge   Mobile
─────────────────────────────────────────────────────────
HTMX                ✅      ✅       ✅      ✅     ✅
Tailwind CSS        ✅      ✅       ✅      ✅     ✅
localStorage        ✅      ✅       ✅      ✅     ✅
CSS Grid            ✅      ✅       ✅      ✅     ✅
Flexbox             ✅      ✅       ✅      ✅     ✅
Custom Properties   ✅      ✅       ✅      ✅     ✅
fetch() API         ✅      ✅       ✅      ✅     ✅
async/await         ✅      ✅       ✅      ✅     ✅
```

## Accessibility Features Matrix

```
Feature                     Implementation
──────────────────────────────────────────────
Semantic HTML               ✅ All pages
ARIA Labels                 ✅ Icon buttons
Keyboard Navigation         ✅ Tab order
Focus Indicators            ✅ 2px blue outline
Screen Reader Support       ✅ Status announcements
Color Contrast (AA)         ✅ 4.5:1 minimum
Form Labels                 ✅ All inputs
Error Messages              ✅ Associated with inputs
Skip Links                  ❌ Future enhancement
Alt Text                    ✅ SVG icons have titles
```

---

This structure provides a complete reference for understanding and maintaining the frontend codebase.
