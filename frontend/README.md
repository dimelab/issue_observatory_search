# Issue Observatory Search - Frontend

Complete frontend interface for the Issue Observatory Search application using HTMX and Tailwind CSS.

## Technology Stack

- **HTMX 1.9.10**: Dynamic interactions without JavaScript frameworks
- **Tailwind CSS 3.x**: Utility-first CSS framework (via CDN)
- **Jinja2**: Server-side templating
- **FastAPI**: Backend framework serving templates
- **Minimal JavaScript**: Only for JWT token handling and utilities

## Architecture

### Design Philosophy

- **Server-Side Rendering**: All templates rendered by FastAPI using Jinja2
- **Progressive Enhancement**: Works without JavaScript, enhanced with HTMX
- **Mobile-First**: Responsive design starting from mobile breakpoints
- **Accessibility**: WCAG 2.1 AA compliant with semantic HTML and ARIA labels
- **No Build Step**: Direct CDN dependencies for rapid development

### Directory Structure

```
frontend/
├── static/
│   ├── css/
│   │   └── custom.css          # Custom styles complementing Tailwind
│   └── js/
│       └── app.js              # JWT handling and utilities
├── templates/
│   ├── base.html               # Base template with navigation
│   ├── login.html              # Login page
│   ├── dashboard.html          # Dashboard with session list
│   ├── search/
│   │   ├── new.html            # New search form
│   │   └── session.html        # Session details with results
│   ├── scraping/
│   │   ├── jobs.html           # Scraping jobs list
│   │   └── job.html            # Job details with progress
│   └── partials/
│       ├── sessions_list.html  # Sessions list partial (HTMX)
│       ├── query_results.html  # Query results partial (HTMX)
│       ├── jobs_list.html      # Jobs list partial (HTMX)
│       └── scraped_content.html # Scraped content partial (HTMX)
└── README.md                   # This file
```

## Design System

### Colors (Tailwind Classes)

- **Primary**: `blue-600` - Buttons, links, headers
- **Secondary**: `gray-600` - Secondary text, icons
- **Success**: `green-600` - Success messages, completed states
- **Warning**: `yellow-600` - Warnings, pending states
- **Error**: `red-600` - Errors, failed states
- **Background**: `gray-50` - Page background
- **Surface**: `white` - Cards, panels

### Typography

- **Font**: System fonts (Tailwind default stack)
- **Headings**: `font-bold` with `text-3xl`, `text-2xl`, `text-xl`
- **Body**: `text-base text-gray-700`
- **Labels**: `text-sm font-medium text-gray-700`
- **Small**: `text-xs text-gray-500`

### Components

#### Cards
```html
<div class="bg-white rounded-lg shadow-md p-6">
  <!-- Card content -->
</div>
```

#### Buttons
```html
<!-- Primary -->
<button class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
  Primary Action
</button>

<!-- Secondary -->
<button class="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50">
  Secondary Action
</button>
```

#### Status Badges
```html
<span class="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
  completed
</span>
```

#### Progress Bars
```html
<div class="w-full bg-gray-200 rounded-full h-2">
  <div class="bg-blue-600 h-2 rounded-full" style="width: 75%"></div>
</div>
```

## Pages

### 1. Login Page (`/`)

- Centered card layout
- Username/password authentication
- JWT token storage in localStorage
- Auto-redirect to dashboard on success
- Error message display

**Features**:
- Form validation
- Loading state during submission
- Responsive design

### 2. Dashboard (`/dashboard`)

- Welcome message with username
- Search sessions list with stats
- Quick statistics cards
- New search button (prominent)

**HTMX Features**:
- Auto-load sessions on page load
- Refresh button to reload sessions
- Delete confirmation dialog
- Real-time stat updates

### 3. New Search (`/search/new`)

- Session name input
- Search engine selector
- Keywords textarea (one per line)
- Max results configuration
- Domain filter (optional)
- Auto-scrape option with depth selector

**Features**:
- Client-side form validation
- Dynamic scrape options
- Loading indicators
- Success/error messages
- Redirect to session details on success

### 4. Session Details (`/search/session/{id}`)

- Session header with stats
- Collapsible query sections
- Results display per query
- Start scraping button
- Scraping job creation modal

**HTMX Features**:
- Lazy-load results when query expanded
- Delete session with confirmation
- Create scraping job inline
- Real-time status updates

### 5. Scraping Jobs (`/scraping/jobs`)

- Active jobs section (auto-refresh every 5s)
- All jobs list
- Job cards with progress bars
- Filter by status

**HTMX Features**:
- Auto-refresh for active jobs
- Real-time progress updates
- Cancel running jobs
- Delete completed jobs

### 6. Job Details (`/scraping/job/{id}`)

- Job header with status
- Progress bar with percentages
- Statistics cards (total, success, failed)
- Configuration details
- Scraped content list

**HTMX Features**:
- Auto-refresh every 3s for running jobs
- Real-time progress tracking
- Lazy-load scraped content
- Cancel/delete actions

## HTMX Patterns

### Auto-Refresh for Active Content

```html
<div hx-get="/api/scraping/jobs?status=running"
     hx-trigger="every 5s"
     hx-swap="innerHTML">
  <!-- Active jobs will auto-refresh -->
</div>
```

### Lazy Loading with Revealed

```html
<div hx-get="/api/search/queries/1/results"
     hx-trigger="revealed"
     hx-swap="innerHTML">
  <!-- Load content when scrolled into view -->
</div>
```

### Delete with Confirmation

```html
<button hx-delete="/api/search/session/1"
        hx-confirm="Are you sure?"
        hx-target="closest .session-card"
        hx-swap="outerHTML">
  Delete
</button>
```

### Form Submission

```html
<form hx-post="/api/search/execute"
      hx-target="#result"
      hx-swap="innerHTML">
  <!-- Form fields -->
</form>
```

## JWT Authentication

### Token Storage

Tokens are stored in `localStorage` after successful login:

```javascript
localStorage.setItem('token', data.access_token);
localStorage.setItem('username', username);
```

### Request Authorization

All HTMX requests automatically include the JWT token:

```javascript
document.body.addEventListener('htmx:configRequest', function(evt) {
    const token = localStorage.getItem('token');
    if (token) {
        evt.detail.headers['Authorization'] = 'Bearer ' + token;
    }
});
```

### Authentication Check

Page load authentication verification:

```javascript
document.addEventListener('DOMContentLoaded', function() {
    const token = localStorage.getItem('token');
    if (!token && currentPage !== '/') {
        window.location.href = '/';
    }
});
```

### Error Handling

Automatic redirect on 401 Unauthorized:

```javascript
document.body.addEventListener('htmx:responseError', function(evt) {
    if (evt.detail.xhr.status === 401) {
        localStorage.removeItem('token');
        window.location.href = '/';
    }
});
```

## Responsive Design

### Breakpoints

- **Mobile**: Default (< 640px)
- **Tablet**: `sm:` (640px)
- **Desktop**: `md:` (768px), `lg:` (1024px)

### Responsive Patterns

#### Navigation
- Mobile: Hamburger menu (collapsible)
- Desktop: Full horizontal navbar

#### Layout
- Mobile: Single column, stacked elements
- Tablet: 2 columns for grids
- Desktop: 3 columns, wider containers

#### Cards
```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  <!-- Cards adapt to screen size -->
</div>
```

## Accessibility

### Semantic HTML

- Proper heading hierarchy (h1 → h2 → h3)
- Form labels with `for` attributes
- Button vs link semantics
- List structures for navigation

### Keyboard Navigation

- All interactive elements focusable
- Custom focus styles with `focus-visible`
- Tab order follows logical flow
- Escape closes modals

### Screen Readers

- ARIA labels for icon buttons
- Status messages announced
- Loading states communicated
- Error messages associated with inputs

### Color Contrast

- All text meets WCAG AA standards
- Interactive elements have sufficient contrast
- Focus indicators clearly visible

## Backend Integration

### FastAPI Routes

**Frontend Pages** (`backend/api/frontend.py`):
- `GET /` - Login page
- `GET /dashboard` - Dashboard
- `GET /search/new` - New search form
- `GET /search/session/{id}` - Session details
- `GET /scraping/jobs` - Jobs list
- `GET /scraping/job/{id}` - Job details

**HTML Partials** (`backend/api/partials.py`):
- `GET /api/search/sessions` - Sessions list partial
- `GET /api/search/queries/{id}/results` - Query results partial
- `GET /api/scraping/jobs` - Jobs list partial
- `GET /api/scraping/jobs/{id}/content` - Scraped content partial

### Custom Jinja2 Filters

```python
def format_datetime(value: datetime) -> str:
    """Format datetime with relative time (e.g., '2 hours ago')"""

def format_number(value: int) -> str:
    """Format number with thousand separators (e.g., '1,234')"""
```

## Development

### Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Access the application at `http://localhost:8000`

### File Locations

- **Templates**: `/Users/jakobbk/Documents/postdoc/codespace/issue_observatory_search/frontend/templates/`
- **Static Files**: `/Users/jakobbk/Documents/postdoc/codespace/issue_observatory_search/frontend/static/`
- **Backend Routes**: `/Users/jakobbk/Documents/postdoc/codespace/issue_observatory_search/backend/api/`

### Adding New Pages

1. Create template in `frontend/templates/`
2. Add route in `backend/api/frontend.py`
3. Add navigation link in `base.html`
4. Create partial templates if using HTMX
5. Add partial endpoints in `backend/api/partials.py`

### Styling Guidelines

1. **Use Tailwind utilities first**
2. Add custom CSS only when necessary
3. Follow existing color palette
4. Maintain consistent spacing (4px base unit)
5. Test on mobile, tablet, and desktop

## Testing

### Manual Testing Checklist

- [ ] Login/logout flow works
- [ ] All navigation links functional
- [ ] Forms submit correctly
- [ ] HTMX auto-refresh working
- [ ] Delete confirmations appear
- [ ] Progress bars update
- [ ] Mobile navigation works
- [ ] Keyboard navigation functional
- [ ] Screen reader compatible

### Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile Safari (iOS 14+)
- Chrome Mobile (latest)

## Performance

### Optimizations

- Tailwind CSS loaded from CDN (cached)
- HTMX loaded from CDN (cached)
- Minimal custom JavaScript
- Lazy loading for results
- Pagination for large lists
- Auto-refresh only for active content

### Best Practices

- Use `hx-indicator` for loading states
- Implement `hx-trigger="revealed"` for lazy loading
- Keep partial responses small
- Use `hx-swap` modifiers for smooth transitions
- Cache templates on server side

## Future Enhancements

- [ ] Dark mode support
- [ ] Export functionality (CSV, JSON)
- [ ] Advanced search filters
- [ ] Network visualization (D3.js)
- [ ] Bulk operations
- [ ] User preferences
- [ ] Real-time notifications (WebSockets)
- [ ] Collaborative sessions

## Troubleshooting

### Common Issues

**HTMX requests not authenticated**
- Check JWT token in localStorage
- Verify `htmx:configRequest` event listener
- Check browser console for errors

**Templates not loading**
- Verify template path in `Jinja2Templates`
- Check file permissions
- Restart FastAPI server

**Static files 404**
- Verify `StaticFiles` mount path
- Check file exists in `frontend/static/`
- Clear browser cache

**Auto-refresh not working**
- Check `hx-trigger` syntax
- Verify endpoint returns valid HTML
- Check browser console for errors

## Support

For issues or questions:
1. Check this documentation
2. Review HTMX documentation: https://htmx.org/docs/
3. Review Tailwind CSS documentation: https://tailwindcss.com/docs
4. Check FastAPI documentation: https://fastapi.tiangolo.com/

## License

This frontend is part of the Issue Observatory Search project.
