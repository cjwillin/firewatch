/**
 * Firewatch UI - JavaScript client
 *
 * Handles API interactions and UI updates.
 */

// API Configuration
const API_BASE = '/api';
const API_KEY = localStorage.getItem('firewatch_api_key') || '';

// Fetch wrapper with API key
async function apiFetch(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (API_KEY) {
        headers['X-API-Key'] = API_KEY;
    }

    const response = await fetch(url, {
        ...options,
        headers
    });

    if (response.status === 401) {
        // API key required
        const key = prompt('Enter API Key:');
        if (key) {
            localStorage.setItem('firewatch_api_key', key);
            location.reload();
        }
        throw new Error('API key required');
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || 'Request failed');
    }

    return response.json();
}

// Health check
async function updateHealthStatus() {
    try {
        const health = await apiFetch(`${API_BASE}/health`);
        const statusEl = document.getElementById('healthStatus');

        if (health.status === 'healthy') {
            const nextRun = health.scheduler.next_check
                ? new Date(health.scheduler.next_check).toLocaleTimeString()
                : 'Not scheduled';

            statusEl.innerHTML = `
                <span class="status-dot status-active"></span>
                <span>Active • Next check: ${nextRun}</span>
            `;
        } else {
            statusEl.innerHTML = `
                <span class="status-dot status-error"></span>
                <span>Error: ${health.error || 'Unknown'}</span>
            `;
        }

        // Update active count
        if (health.database && health.database.watches) {
            document.getElementById('activeCount').textContent = health.database.watches.active;
        }
    } catch (err) {
        document.getElementById('healthStatus').innerHTML = `
            <span class="status-dot status-error"></span>
            <span>Disconnected</span>
        `;
    }
}

// Load watches
async function loadWatches() {
    try {
        const watches = await apiFetch(`${API_BASE}/watches`);
        const container = document.getElementById('watchesList');

        if (watches.length === 0) {
            container.innerHTML = '<div class="text-center text-gray-500 py-8">No watches yet. Create one to get started!</div>';
            return;
        }

        container.innerHTML = watches.map(watch => renderWatch(watch)).join('');
    } catch (err) {
        showError('Failed to load watches: ' + err.message);
    }
}

// Render a single watch
function renderWatch(watch) {
    const statusClass = watch.alerted ? 'status-alerted' :
                       !watch.active ? 'status-paused' :
                       watch.last_status === 'error' ? 'status-error' :
                       'status-active';

    const statusText = watch.alerted ? 'Alerted' :
                       !watch.active ? 'Paused' :
                       watch.last_status === 'error' ? 'Error' :
                       'Active';

    const lastChecked = watch.last_checked_at
        ? new Date(watch.last_checked_at).toLocaleString()
        : 'Never';

    return `
        <div class="border rounded-lg p-4 hover:shadow-md transition">
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="status-dot ${statusClass}"></span>
                        <h3 class="font-semibold text-gray-900">${watch.campground_name}</h3>
                        <span class="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">${watch.site_type}</span>
                    </div>
                    <p class="text-sm text-gray-600 mb-2">
                        ${watch.checkin_date} to ${watch.checkout_date}
                    </p>
                    <div class="text-xs text-gray-500 space-y-1">
                        <div>Status: <span class="font-medium">${statusText}</span></div>
                        <div>Last checked: ${lastChecked}</div>
                        ${watch.last_error_message ? `<div class="text-red-600">Error: ${watch.last_error_message}</div>` : ''}
                    </div>
                </div>
                <div class="flex flex-col gap-2">
                    <button onclick="checkNow(${watch.id})" class="text-blue-600 hover:text-blue-800 text-sm font-medium">
                        Check Now
                    </button>
                    ${watch.alerted ? `
                        <button onclick="resetAlert(${watch.id})" class="text-green-600 hover:text-green-800 text-sm font-medium">
                            Reset Alert
                        </button>
                    ` : ''}
                    <button onclick="toggleActive(${watch.id}, ${!watch.active})" class="text-gray-600 hover:text-gray-800 text-sm font-medium">
                        ${watch.active ? 'Pause' : 'Resume'}
                    </button>
                    <button onclick="deleteWatch(${watch.id})" class="text-red-600 hover:text-red-800 text-sm font-medium">
                        Delete
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Check availability now
async function checkNow(watchId) {
    try {
        const result = await apiFetch(`${API_BASE}/watches/${watchId}/check-now`, {
            method: 'POST'
        });

        if (result.status === 'available') {
            showSuccess('Sites available! Alert sent.');
        } else if (result.status === 'not_available') {
            showInfo('No sites available yet.');
        } else {
            showError('Check failed: ' + result.message);
        }

        loadWatches();
    } catch (err) {
        showError('Check failed: ' + err.message);
    }
}

// Reset alert flag
async function resetAlert(watchId) {
    try {
        await apiFetch(`${API_BASE}/watches/${watchId}/reset-alert`, {
            method: 'POST'
        });
        showSuccess('Alert reset successfully');
        loadWatches();
    } catch (err) {
        showError('Failed to reset alert: ' + err.message);
    }
}

// Toggle active status
async function toggleActive(watchId, active) {
    try {
        await apiFetch(`${API_BASE}/watches/${watchId}`, {
            method: 'PUT',
            body: JSON.stringify({ active })
        });
        showSuccess(`Watch ${active ? 'resumed' : 'paused'}`);
        loadWatches();
    } catch (err) {
        showError('Failed to update watch: ' + err.message);
    }
}

// Delete watch
async function deleteWatch(watchId) {
    if (!confirm('Delete this watch?')) return;

    try {
        await apiFetch(`${API_BASE}/watches/${watchId}`, {
            method: 'DELETE'
        });
        showSuccess('Watch deleted');
        loadWatches();
    } catch (err) {
        showError('Failed to delete watch: ' + err.message);
    }
}

// Load templates
async function loadTemplates() {
    try {
        const templates = await apiFetch(`${API_BASE}/templates`);
        const container = document.getElementById('templatesList');

        if (templates.length === 0) {
            container.innerHTML = '<div class="text-center text-gray-500 py-8">No templates yet.</div>';
            return;
        }

        container.innerHTML = templates.map(template => renderTemplate(template)).join('');
    } catch (err) {
        showError('Failed to load templates: ' + err.message);
    }
}

// Render a single template
function renderTemplate(template) {
    const daysOfWeek = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const selectedDays = template.days_of_week.map(d => daysOfWeek[d]).join(', ');

    return `
        <div class="border rounded-lg p-4">
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <h3 class="font-semibold text-gray-900 mb-2">${template.campground_name}</h3>
                    <div class="text-sm text-gray-600 space-y-1">
                        <div>Date range: ${template.date_range_start} to ${template.date_range_end}</div>
                        <div>Days: ${selectedDays}</div>
                        <div>Site type: ${template.site_type}</div>
                        ${template.last_expanded_at ? `<div>Last expanded: ${new Date(template.last_expanded_at).toLocaleString()}</div>` : ''}
                    </div>
                </div>
                <div class="flex flex-col gap-2">
                    <button onclick="expandTemplate(${template.id})" class="text-blue-600 hover:text-blue-800 text-sm font-medium">
                        Expand
                    </button>
                    <button onclick="deleteTemplate(${template.id})" class="text-red-600 hover:text-red-800 text-sm font-medium">
                        Delete
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Expand template
async function expandTemplate(templateId) {
    try {
        const result = await apiFetch(`${API_BASE}/templates/${templateId}/expand`, {
            method: 'POST'
        });

        showSuccess(`Created ${result.created} watches, skipped ${result.skipped} duplicates`);
        loadWatches();
        loadTemplates();
    } catch (err) {
        showError('Failed to expand template: ' + err.message);
    }
}

// Delete template
async function deleteTemplate(templateId) {
    if (!confirm('Delete this template? (Existing watches will remain)')) return;

    try {
        await apiFetch(`${API_BASE}/templates/${templateId}`, {
            method: 'DELETE'
        });
        showSuccess('Template deleted');
        loadTemplates();
    } catch (err) {
        showError('Failed to delete template: ' + err.message);
    }
}

// Load alert logs
async function loadLogs() {
    try {
        const result = await apiFetch(`${API_BASE}/logs?limit=50`);
        const container = document.getElementById('logsList');

        if (result.logs.length === 0) {
            container.innerHTML = '<div class="text-center text-gray-500 py-8">No alerts yet.</div>';
            return;
        }

        container.innerHTML = result.logs.map(log => `
            <div class="border-l-4 border-blue-500 bg-blue-50 p-3 rounded">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="font-medium text-gray-900">${log.watch.campground_name}</div>
                        <div class="text-sm text-gray-600">${log.message}</div>
                        <div class="text-xs text-gray-500 mt-1">${log.watch.checkin_date} to ${log.watch.checkout_date}</div>
                    </div>
                    <div class="text-xs text-gray-500">${new Date(log.triggered_at).toLocaleString()}</div>
                </div>
            </div>
        `).join('');
    } catch (err) {
        showError('Failed to load logs: ' + err.message);
    }
}

// Tab switching
function switchTab(tab) {
    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    document.getElementById(`tab-${tab}`).classList.add('active');

    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    document.getElementById(`content-${tab}`).classList.remove('hidden');

    // Load data
    if (tab === 'watches') loadWatches();
    if (tab === 'templates') loadTemplates();
    if (tab === 'logs') loadLogs();
}

// Campground autocomplete
let searchTimeout;
let selectedCampground = null;

async function searchCampgrounds(query) {
    if (query.length < 2) {
        document.getElementById('campgroundResults').classList.add('hidden');
        return;
    }

    try {
        const results = await apiFetch(`${API_BASE}/campgrounds/search?q=${encodeURIComponent(query)}&limit=10`);
        const resultsContainer = document.getElementById('campgroundResults');

        if (results.length === 0) {
            resultsContainer.innerHTML = '<div class="autocomplete-item text-gray-500">No campgrounds found</div>';
            resultsContainer.classList.remove('hidden');
            return;
        }

        resultsContainer.innerHTML = results.map(campground => `
            <div class="autocomplete-item" data-id="${campground.id}" data-name="${campground.name}" data-location="${campground.location}">
                <div class="autocomplete-item-name">${campground.name}</div>
                <div class="autocomplete-item-location">${campground.location}</div>
            </div>
        `).join('');

        // Add click handlers
        resultsContainer.querySelectorAll('.autocomplete-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = item.getAttribute('data-id');
                const name = item.getAttribute('data-name');
                const location = item.getAttribute('data-location');

                selectCampground(id, name, location);
            });
        });

        resultsContainer.classList.remove('hidden');
    } catch (err) {
        console.error('Search failed:', err);
    }
}

function selectCampground(id, name, location) {
    selectedCampground = { id, name, location };

    // Update form
    document.getElementById('selectedCampgroundId').value = id;
    document.getElementById('selectedCampgroundName').value = name;
    document.getElementById('campgroundSearch').value = name;
    document.getElementById('selectedCampgroundDisplay').textContent = `Selected: ${name} (${location})`;

    // Hide results
    document.getElementById('campgroundResults').classList.add('hidden');
}

// Initialize autocomplete when modal opens
function initCampgroundSearch() {
    const searchInput = document.getElementById('campgroundSearch');

    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            searchCampgrounds(e.target.value);
        }, 300); // Debounce 300ms
    });

    // Hide results when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.autocomplete')) {
            document.getElementById('campgroundResults').classList.add('hidden');
        }
    });

    // Clear selection when input is manually changed
    searchInput.addEventListener('focus', () => {
        if (selectedCampground && searchInput.value === selectedCampground.name) {
            // Don't clear if they're refocusing on already-selected campground
        } else {
            selectedCampground = null;
            document.getElementById('selectedCampgroundId').value = '';
            document.getElementById('selectedCampgroundName').value = '';
            document.getElementById('selectedCampgroundDisplay').textContent = '';
        }
    });
}

// Modal management
function showCreateWatchModal() {
    document.getElementById('createWatchModal').classList.remove('hidden');
    initCampgroundSearch();
}

function hideCreateWatchModal() {
    document.getElementById('createWatchModal').classList.add('hidden');
    document.getElementById('createWatchForm').reset();
}

function showCreateTemplateModal() {
    document.getElementById('createTemplateModal').classList.remove('hidden');
}

function hideCreateTemplateModal() {
    document.getElementById('createTemplateModal').classList.add('hidden');
    document.getElementById('createTemplateForm').reset();
}

// Form submissions
document.getElementById('createWatchForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData);

    // Convert numeric values
    data.campground_id = parseInt(data.campground_id);

    try {
        await apiFetch(`${API_BASE}/watches`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
        showSuccess('Watch created successfully');
        hideCreateWatchModal();
        loadWatches();
    } catch (err) {
        showError('Failed to create watch: ' + err.message);
    }
});

document.getElementById('createTemplateForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData);

    // Convert numeric values
    data.campground_id = parseInt(data.campground_id);

    // Collect days of week
    const daysOfWeek = [];
    document.querySelectorAll('.days-of-week:checked').forEach(checkbox => {
        daysOfWeek.push(parseInt(checkbox.value));
    });
    data.days_of_week = daysOfWeek;

    try {
        await apiFetch(`${API_BASE}/templates`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
        showSuccess('Template created successfully');
        hideCreateTemplateModal();
        loadTemplates();
    } catch (err) {
        showError('Failed to create template: ' + err.message);
    }
});

// Toast notifications
function showSuccess(message) {
    showToast(message, 'green');
}

function showError(message) {
    showToast(message, 'red');
}

function showInfo(message) {
    showToast(message, 'blue');
}

function showToast(message, color) {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 bg-${color}-600 text-white px-6 py-3 rounded-lg shadow-lg z-50`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    updateHealthStatus();
    loadWatches();

    // Refresh health status every 30 seconds
    setInterval(updateHealthStatus, 30000);
});
