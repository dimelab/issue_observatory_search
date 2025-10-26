/**
 * Data Table Component with Sorting, Filtering, and Pagination
 *
 * Alpine.js component for interactive data tables
 *
 * Usage:
 *   <div x-data="dataTable(data, columns)">
 *     <table>...</table>
 *   </div>
 */

/**
 * Create a data table Alpine.js component
 * @param {Array} initialData - Initial table data
 * @param {Array} columns - Column definitions
 * @returns {Object} Alpine.js component data
 */
function dataTable(initialData = [], columns = []) {
    return {
        // Data
        data: initialData,
        columns: columns,

        // Sorting
        sortColumn: '',
        sortDirection: 'asc',

        // Filtering
        filters: {},
        globalSearch: '',

        // Pagination
        currentPage: 1,
        perPage: 25,
        perPageOptions: [10, 25, 50, 100],

        // Selection
        selectedRows: [],
        selectAll: false,

        // Visibility
        columnVisibility: {},

        /**
         * Initialize the data table
         */
        init() {
            // Initialize column visibility (all visible by default)
            this.columns.forEach(col => {
                this.columnVisibility[col.key] = col.visible !== false;
            });

            // Initialize filters
            this.columns.forEach(col => {
                if (col.filterable !== false) {
                    this.filters[col.key] = '';
                }
            });
        },

        /**
         * Get filtered data
         */
        get filteredData() {
            let result = [...this.data];

            // Apply column filters
            Object.keys(this.filters).forEach(key => {
                const filterValue = this.filters[key];
                if (filterValue) {
                    result = result.filter(row => {
                        const cellValue = String(row[key] || '').toLowerCase();
                        return cellValue.includes(filterValue.toLowerCase());
                    });
                }
            });

            // Apply global search
            if (this.globalSearch) {
                const searchLower = this.globalSearch.toLowerCase();
                result = result.filter(row => {
                    return this.columns.some(col => {
                        const cellValue = String(row[col.key] || '').toLowerCase();
                        return cellValue.includes(searchLower);
                    });
                });
            }

            return result;
        },

        /**
         * Get sorted data
         */
        get sortedData() {
            const filtered = this.filteredData;

            if (!this.sortColumn) return filtered;

            return [...filtered].sort((a, b) => {
                let aVal = a[this.sortColumn];
                let bVal = b[this.sortColumn];

                // Handle null/undefined
                if (aVal == null) return 1;
                if (bVal == null) return -1;

                // Type-specific sorting
                if (typeof aVal === 'number' && typeof bVal === 'number') {
                    return this.sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
                }

                // String sorting
                aVal = String(aVal).toLowerCase();
                bVal = String(bVal).toLowerCase();

                const comparison = aVal.localeCompare(bVal);
                return this.sortDirection === 'asc' ? comparison : -comparison;
            });
        },

        /**
         * Get paginated data
         */
        get paginatedData() {
            const sorted = this.sortedData;
            const start = (this.currentPage - 1) * this.perPage;
            const end = start + this.perPage;
            return sorted.slice(start, end);
        },

        /**
         * Get total pages
         */
        get totalPages() {
            return Math.ceil(this.filteredData.length / this.perPage);
        },

        /**
         * Get visible columns
         */
        get visibleColumns() {
            return this.columns.filter(col => this.columnVisibility[col.key] !== false);
        },

        /**
         * Sort by column
         * @param {string} columnKey - Column key to sort by
         */
        sort(columnKey) {
            if (this.sortColumn === columnKey) {
                // Toggle direction
                this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                // New column
                this.sortColumn = columnKey;
                this.sortDirection = 'asc';
            }
        },

        /**
         * Filter by column
         * @param {string} columnKey - Column key to filter
         * @param {string} value - Filter value
         */
        filter(columnKey, value) {
            this.filters[columnKey] = value;
            this.currentPage = 1; // Reset to first page
        },

        /**
         * Clear all filters
         */
        clearFilters() {
            Object.keys(this.filters).forEach(key => {
                this.filters[key] = '';
            });
            this.globalSearch = '';
            this.currentPage = 1;
        },

        /**
         * Go to page
         * @param {number} page - Page number
         */
        goToPage(page) {
            if (page >= 1 && page <= this.totalPages) {
                this.currentPage = page;
            }
        },

        /**
         * Go to next page
         */
        nextPage() {
            this.goToPage(this.currentPage + 1);
        },

        /**
         * Go to previous page
         */
        previousPage() {
            this.goToPage(this.currentPage - 1);
        },

        /**
         * Change items per page
         * @param {number} perPage - Items per page
         */
        changePerPage(perPage) {
            this.perPage = perPage;
            this.currentPage = 1;
        },

        /**
         * Toggle row selection
         * @param {Object} row - Row data
         */
        toggleRow(row) {
            const index = this.selectedRows.indexOf(row);
            if (index > -1) {
                this.selectedRows.splice(index, 1);
            } else {
                this.selectedRows.push(row);
            }
            this.updateSelectAll();
        },

        /**
         * Toggle select all rows
         */
        toggleSelectAll() {
            if (this.selectAll) {
                this.selectedRows = [...this.paginatedData];
            } else {
                this.selectedRows = [];
            }
        },

        /**
         * Update select all checkbox state
         */
        updateSelectAll() {
            const pageRows = this.paginatedData;
            this.selectAll = pageRows.length > 0 &&
                pageRows.every(row => this.selectedRows.includes(row));
        },

        /**
         * Check if row is selected
         * @param {Object} row - Row data
         * @returns {boolean} True if selected
         */
        isRowSelected(row) {
            return this.selectedRows.includes(row);
        },

        /**
         * Toggle column visibility
         * @param {string} columnKey - Column key
         */
        toggleColumn(columnKey) {
            this.columnVisibility[columnKey] = !this.columnVisibility[columnKey];
        },

        /**
         * Export visible data to CSV
         */
        exportToCSV() {
            const data = this.filteredData;
            const columns = this.visibleColumns.map(col => col.key);
            const csv = window.utils.arrayToCSV(data, columns);
            const filename = `export-${new Date().toISOString().split('T')[0]}.csv`;
            window.utils.downloadFile(csv, filename, 'text/csv');
            showToast('Data exported successfully', 'success');
        },

        /**
         * Get pagination info text
         * @returns {string} Pagination info
         */
        get paginationInfo() {
            const start = (this.currentPage - 1) * this.perPage + 1;
            const end = Math.min(this.currentPage * this.perPage, this.filteredData.length);
            const total = this.filteredData.length;
            return `Showing ${start} to ${end} of ${total} entries`;
        },

        /**
         * Get page numbers for pagination
         * @returns {Array} Array of page numbers
         */
        get pageNumbers() {
            const pages = [];
            const maxVisible = 5;
            const halfVisible = Math.floor(maxVisible / 2);

            let startPage = Math.max(1, this.currentPage - halfVisible);
            let endPage = Math.min(this.totalPages, startPage + maxVisible - 1);

            // Adjust start if we're near the end
            if (endPage - startPage < maxVisible - 1) {
                startPage = Math.max(1, endPage - maxVisible + 1);
            }

            for (let i = startPage; i <= endPage; i++) {
                pages.push(i);
            }

            return pages;
        }
    };
}

// Export to window
window.dataTable = dataTable;
