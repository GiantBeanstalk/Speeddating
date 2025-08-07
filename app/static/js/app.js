/**
 * Speed Dating Application JavaScript Utilities
 */

// Global app object
window.SpeedDatingApp = {
    // Configuration
    config: {
        wsUrl: `ws://${window.location.host}/ws`,
        apiUrl: '/api'
    },

    // Utility functions
    utils: {
        // Format date for display
        formatDate: function(dateString) {
            const date = new Date(dateString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        },

        // Format duration in minutes to readable format
        formatDuration: function(minutes) {
            if (minutes < 60) {
                return `${minutes}m`;
            }
            const hours = Math.floor(minutes / 60);
            const mins = minutes % 60;
            return `${hours}h ${mins}m`;
        },

        // Show flash message
        showFlash: function(message, type = 'info') {
            const flashContainer = document.getElementById('flash-messages');
            if (!flashContainer) return;

            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${type} mb-4`;
            alertDiv.innerHTML = `
                <div class="flex justify-between items-center">
                    <span>${message}</span>
                    <button onclick="this.parentElement.parentElement.remove()" class="text-xl">&times;</button>
                </div>
            `;

            flashContainer.appendChild(alertDiv);

            // Auto-remove after 5 seconds
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.style.transition = 'opacity 0.5s';
                    alertDiv.style.opacity = '0';
                    setTimeout(() => alertDiv.remove(), 500);
                }
            }, 5000);
        },

        // API request wrapper
        apiRequest: async function(endpoint, options = {}) {
            const url = this.config.apiUrl + endpoint;
            const defaultOptions = {
                headers: {
                    'Content-Type': 'application/json',
                },
            };

            const config = { ...defaultOptions, ...options };
            
            try {
                const response = await fetch(url, config);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Request failed');
                }
                
                return data;
            } catch (error) {
                console.error('API request failed:', error);
                this.showFlash(error.message, 'error');
                throw error;
            }
        },

        // Confirm dialog with custom styling
        confirm: function(message, title = 'Confirm') {
            return new Promise((resolve) => {
                const modal = document.createElement('div');
                modal.className = 'modal';
                modal.innerHTML = `
                    <div class="modal-backdrop"></div>
                    <div class="flex items-center justify-center min-h-screen p-4">
                        <div class="modal-content p-6">
                            <h3 class="text-lg font-semibold mb-4">${title}</h3>
                            <p class="text-slate-300 mb-6">${message}</p>
                            <div class="flex space-x-3 justify-end">
                                <button class="btn btn-secondary" onclick="closeModal(false)">Cancel</button>
                                <button class="btn btn-primary" onclick="closeModal(true)">Confirm</button>
                            </div>
                        </div>
                    </div>
                `;

                document.body.appendChild(modal);

                window.closeModal = function(result) {
                    document.body.removeChild(modal);
                    delete window.closeModal;
                    resolve(result);
                };
            });
        },

        // Copy text to clipboard
        copyToClipboard: async function(text) {
            try {
                await navigator.clipboard.writeText(text);
                this.showFlash('Copied to clipboard!', 'success');
            } catch (err) {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                this.showFlash('Copied to clipboard!', 'success');
            }
        },

        // Debounce function
        debounce: function(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },

        // Format match response for display
        formatMatchResponse: function(response) {
            const responseMap = {
                'yes': { text: 'Yes', class: 'badge-success' },
                'no': { text: 'No', class: 'badge-warning' },
                'no_response': { text: 'No Response', class: 'badge-gray' }
            };
            return responseMap[response] || responseMap['no_response'];
        },

        // Format attendee category for display
        formatCategory: function(category) {
            const categoryMap = {
                'man_seeking_woman': 'Man seeking Woman',
                'woman_seeking_man': 'Woman seeking Man',
                'man_seeking_man': 'Man seeking Man',
                'woman_seeking_woman': 'Woman seeking Woman',
                'non_binary_seeking_any': 'Non-binary seeking Anyone',
                'any_seeking_any': 'Anyone seeking Anyone'
            };
            return categoryMap[category] || category;
        }
    },

    // Form handling
    forms: {
        // Auto-save form data to localStorage
        autoSave: function(formId, key) {
            const form = document.getElementById(formId);
            if (!form) return;

            const savedData = localStorage.getItem(key);
            if (savedData) {
                try {
                    const data = JSON.parse(savedData);
                    Object.keys(data).forEach(fieldName => {
                        const field = form.elements[fieldName];
                        if (field && field.type !== 'password') {
                            field.value = data[fieldName];
                        }
                    });
                } catch (e) {
                    console.warn('Failed to load saved form data:', e);
                }
            }

            // Save on input change
            const saveData = SpeedDatingApp.utils.debounce(() => {
                const formData = new FormData(form);
                const data = {};
                for (let [key, value] of formData.entries()) {
                    if (form.elements[key].type !== 'password') {
                        data[key] = value;
                    }
                }
                localStorage.setItem(key, JSON.stringify(data));
            }, 1000);

            form.addEventListener('input', saveData);
            
            // Clear saved data on successful submit
            form.addEventListener('htmx:afterRequest', function(event) {
                if (event.detail.successful) {
                    localStorage.removeItem(key);
                }
            });
        },

        // Validate form fields
        validate: function(formId) {
            const form = document.getElementById(formId);
            if (!form) return false;

            let isValid = true;
            const fields = form.querySelectorAll('[required]');

            fields.forEach(field => {
                if (!field.value.trim()) {
                    field.classList.add('border-red-500');
                    isValid = false;
                } else {
                    field.classList.remove('border-red-500');
                }
            });

            return isValid;
        }
    },

    // Initialize the application
    init: function() {
        console.log('Speed Dating App initialized');

        // Initialize tooltips, modals, etc.
        this.initializeComponents();

        // Set up global error handling
        window.addEventListener('error', function(event) {
            console.error('JavaScript error:', event.error);
        });

        // Handle htmx errors
        document.body.addEventListener('htmx:responseError', function(event) {
            const message = event.detail.xhr.responseJSON?.detail || 'An error occurred';
            SpeedDatingApp.utils.showFlash(message, 'error');
        });

        // Handle successful htmx requests
        document.body.addEventListener('htmx:afterSwap', function(event) {
            // Re-initialize components in new content
            SpeedDatingApp.initializeComponents();
        });
    },

    // Initialize UI components
    initializeComponents: function() {
        // Initialize auto-save for forms
        const formsToAutoSave = [
            { id: 'event-form', key: 'event-draft' },
            { id: 'registration-form', key: 'registration-draft' },
            { id: 'profile-form', key: 'profile-draft' }
        ];

        formsToAutoSave.forEach(({ id, key }) => {
            if (document.getElementById(id)) {
                this.forms.autoSave(id, key);
            }
        });

        // Add click handlers for copy buttons
        document.querySelectorAll('[data-copy]').forEach(button => {
            button.addEventListener('click', function() {
                const text = this.getAttribute('data-copy');
                SpeedDatingApp.utils.copyToClipboard(text);
            });
        });
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    SpeedDatingApp.init();
});

// Export for use in other scripts
window.App = SpeedDatingApp;