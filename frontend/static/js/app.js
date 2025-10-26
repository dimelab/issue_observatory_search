/**
 * Issue Observatory Search - Frontend Application
 * Handles JWT authentication and HTMX request configuration
 */

// Check authentication on page load
document.addEventListener('DOMContentLoaded', function() {
    const currentPage = window.location.pathname;
    const token = localStorage.getItem('token');
    const username = localStorage.getItem('username');

    // Redirect to login if not authenticated (except on login page)
    if (!token && currentPage !== '/' && !currentPage.includes('login')) {
        window.location.href = '/';
        return;
    }

    // Redirect to dashboard if already authenticated and on login page
    if (token && (currentPage === '/' || currentPage.includes('login'))) {
        window.location.href = '/dashboard';
        return;
    }

    // Set username in navigation if authenticated
    if (username) {
        const usernameElements = document.querySelectorAll('#username, #mobile-username, #dashboard-username');
        usernameElements.forEach(el => {
            if (el) el.textContent = username;
        });
    }
});

// Add JWT token to all HTMX requests
document.body.addEventListener('htmx:configRequest', function(evt) {
    const token = localStorage.getItem('token');
    if (token) {
        evt.detail.headers['Authorization'] = 'Bearer ' + token;
    }
});

// Handle authentication errors (401)
document.body.addEventListener('htmx:responseError', function(evt) {
    if (evt.detail.xhr.status === 401) {
        // Clear token and redirect to login
        localStorage.removeItem('token');
        localStorage.removeItem('username');
        window.location.href = '/';
    } else if (evt.detail.xhr.status === 403) {
        showFlashMessage('error', 'You do not have permission to perform this action.');
    } else if (evt.detail.xhr.status === 404) {
        showFlashMessage('error', 'The requested resource was not found.');
    } else if (evt.detail.xhr.status >= 500) {
        showFlashMessage('error', 'A server error occurred. Please try again later.');
    }
});

// Handle successful requests
document.body.addEventListener('htmx:afterRequest', function(evt) {
    // Auto-dismiss flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('#flash-messages > div');
    flashMessages.forEach(msg => {
        setTimeout(() => {
            msg.style.opacity = '0';
            msg.style.transition = 'opacity 0.5s';
            setTimeout(() => msg.remove(), 500);
        }, 5000);
    });
});

/**
 * Show a flash message to the user
 * @param {string} type - Message type: 'success', 'error', 'warning', 'info'
 * @param {string} message - Message text to display
 */
function showFlashMessage(type, message) {
    const flashContainer = document.getElementById('flash-messages');
    if (!flashContainer) return;

    const colors = {
        success: {
            bg: 'bg-green-50',
            border: 'border-green-200',
            text: 'text-green-800',
            icon: 'text-green-400',
            path: 'M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z'
        },
        error: {
            bg: 'bg-red-50',
            border: 'border-red-200',
            text: 'text-red-800',
            icon: 'text-red-400',
            path: 'M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z'
        },
        warning: {
            bg: 'bg-yellow-50',
            border: 'border-yellow-200',
            text: 'text-yellow-800',
            icon: 'text-yellow-400',
            path: 'M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z'
        },
        info: {
            bg: 'bg-blue-50',
            border: 'border-blue-200',
            text: 'text-blue-800',
            icon: 'text-blue-400',
            path: 'M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z'
        }
    };

    const config = colors[type] || colors.info;

    const flashElement = document.createElement('div');
    flashElement.className = `rounded-md ${config.bg} border ${config.border} p-4 shadow-lg transition-opacity duration-500`;
    flashElement.innerHTML = `
        <div class="flex">
            <div class="flex-shrink-0">
                <svg class="h-5 w-5 ${config.icon}" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="${config.path}" clip-rule="evenodd" />
                </svg>
            </div>
            <div class="ml-3">
                <p class="text-sm ${config.text}">${message}</p>
            </div>
            <div class="ml-auto pl-3">
                <button onclick="this.parentElement.parentElement.parentElement.remove()" class="inline-flex ${config.text} hover:opacity-75">
                    <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                    </svg>
                </button>
            </div>
        </div>
    `;

    flashContainer.appendChild(flashElement);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        flashElement.style.opacity = '0';
        setTimeout(() => flashElement.remove(), 500);
    }, 5000);
}

/**
 * Format a number with thousand separators
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Format a datetime string to a readable format
 * @param {string} dateString - ISO datetime string
 * @returns {string} Formatted datetime
 */
function formatDateTime(dateString) {
    if (!dateString) return 'N/A';

    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
        const hours = Math.floor(diff / (1000 * 60 * 60));
        if (hours === 0) {
            const minutes = Math.floor(diff / (1000 * 60));
            if (minutes === 0) return 'Just now';
            return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        }
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    } else if (days === 1) {
        return 'Yesterday';
    } else if (days < 7) {
        return `${days} days ago`;
    } else {
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showFlashMessage('success', 'Copied to clipboard!');
    }).catch(() => {
        showFlashMessage('error', 'Failed to copy to clipboard');
    });
}

/**
 * Download data as JSON file
 * @param {Object} data - Data to download
 * @param {string} filename - Filename for download
 */
function downloadJSON(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showFlashMessage('success', 'Download started');
}

/**
 * Confirm action with user
 * @param {string} message - Confirmation message
 * @param {Function} callback - Callback function if confirmed
 */
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Export utility functions for use in templates
window.showFlashMessage = showFlashMessage;
window.formatNumber = formatNumber;
window.formatDateTime = formatDateTime;
window.copyToClipboard = copyToClipboard;
window.downloadJSON = downloadJSON;
window.confirmAction = confirmAction;
