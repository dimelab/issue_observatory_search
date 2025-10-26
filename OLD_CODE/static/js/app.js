// Main application JavaScript

// Handle HTMX events
document.addEventListener('htmx:afterRequest', function(event) {
    if (event.detail.xhr.status === 200) {
        // Success handling
        if (event.detail.target.id === 'login-response') {
            // Redirect to dashboard after successful login
            window.location.href = '/api/dashboard';
        }
    } else if (event.detail.xhr.status >= 400) {
        // Error handling
        console.error('Request failed:', event.detail.xhr.responseText);
    }
});

// Handle form responses
document.addEventListener('htmx:responseError', function(event) {
    console.error('HTMX Response Error:', event.detail);
    
    // Show error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger alert-dismissible fade show';
    errorDiv.innerHTML = `
        <strong>Error:</strong> ${event.detail.xhr.responseText || 'An error occurred'}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insert error message at the top of the page
    const container = document.querySelector('.container');
    container.insertBefore(errorDiv, container.firstChild);
});

// Utility functions
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div>';
    }
}

function hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '';
    }
}

// Auto-refresh for scrape status
function startScrapeStatusRefresh() {
    setInterval(function() {
        const scrapeElements = document.querySelectorAll('[data-scrape-status="running"]');
        scrapeElements.forEach(function(element) {
            element.dispatchEvent(new Event('htmx:refresh'));
        });
    }, 5000); // Refresh every 5 seconds
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Start scrape status refresh if on scrapes page
    if (window.location.pathname.includes('/scrapes')) {
        startScrapeStatusRefresh();
    }
    
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Network creation helpers
function validateNetworkForm() {
    const scrapeIds = document.getElementById('scrape-ids').value;
    if (!scrapeIds) {
        alert('Please select at least one scrape for network creation.');
        return false;
    }
    return true;
}

// File upload helpers
function handleFileUpload(input, callback) {
    const file = input.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            callback(e.target.result);
        };
        reader.readAsText(file);
    }
}