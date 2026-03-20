/**
 * Firewatch UI - Redesigned with new design system
 */

// API Configuration
const API_BASE = '/api';
const API_KEY = localStorage.getItem('firewatch_api_key') || '';

// State
let selectedCampground = null;
let searchTimeout = null;

// Fetch wrapper
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

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeCampgroundSearch();
    initializeDateInputs();
    loadWatches();
    updateStats();
    
    // Update stats every 30 seconds
    setInterval(updateStats, 30000);
});

// Update stats
async function updateStats() {
    try {
        const health = await apiFetch(`${API_BASE}/health`);
        
        if (health.database && health.database.watches) {
            document.getElementById('activeCount').textContent = health.database.watches.active;
        }
    } catch (err) {
        console.error('Failed to update stats:', err);
    }
}

// Campground Search
function initializeCampgroundSearch() {
    const searchInput = document.getElementById('campgroundSearch');
    const resultsContainer = document.getElementById('searchResults');

    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value;

        if (query.length < 2) {
            resultsContainer.classList.add('hidden');
            return;
        }

        searchTimeout = setTimeout(() => {
            searchCampgrounds(query);
        }, 300);
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.autocomplete')) {
            resultsContainer.classList.add('hidden');
        }
    });
}

async function searchCampgrounds(query) {
    const resultsContainer = document.getElementById('searchResults');

    try {
        const results = await apiFetch(`${API_BASE}/campgrounds/search?q=${encodeURIComponent(query)}&limit=10`);

        if (results.length === 0) {
            resultsContainer.innerHTML = '<div class="autocomplete-item"><div style="color: #78716c;">No campgrounds found</div></div>';
            resultsContainer.classList.remove('hidden');
            return;
        }

        resultsContainer.innerHTML = results.map(campground => {
            const initials = campground.name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
            
            return `
                <div class="autocomplete-item" data-id="${campground.id}" data-name="${campground.name}" 
                     data-location="${campground.location}" data-image="${campground.preview_image_url || ''}">
                    <div class="autocomplete-item-image">${initials}</div>
                    <div class="autocomplete-item-details">
                        <div class="autocomplete-item-name">${campground.name}</div>
                        <div class="autocomplete-item-location">${campground.location}</div>
                    </div>
                </div>
            `;
        }).join('');

        resultsContainer.querySelectorAll('.autocomplete-item').forEach(item => {
            item.addEventListener('click', () => {
                selectCampground({
                    id: item.getAttribute('data-id'),
                    name: item.getAttribute('data-name'),
                    location: item.getAttribute('data-location'),
                    preview_image_url: item.getAttribute('data-image')
                });
            });
        });

        resultsContainer.classList.remove('hidden');
    } catch (err) {
        console.error('Search failed:', err);
    }
}

function selectCampground(campground) {
    selectedCampground = campground;

    document.getElementById('searchResults').classList.add('hidden');
    document.getElementById('detailsForm').classList.remove('hidden');
    document.getElementById('selectedName').textContent = campground.name;
    document.getElementById('selectedLocation').textContent = campground.location;

    loadCampgroundSites(campground.id);
}

async function loadCampgroundSites(campgroundId) {
    const loadingEl = document.getElementById('siteSelectionLoading');
    const containerEl = document.getElementById('siteSelectionContainer');
    const listEl = document.getElementById('siteSelectionList');

    loadingEl.classList.remove('hidden');
    containerEl.classList.add('hidden');

    try {
        const sites = await apiFetch(`${API_BASE}/campgrounds/${campgroundId}/sites`);

        if (sites.length === 0) {
            loadingEl.textContent = 'No sites found';
            return;
        }

        listEl.innerHTML = sites.map(site => `
            <label class="site-checkbox-label">
                <input type="checkbox" class="site-checkbox" value="${site.site_id}">
                <span>${site.site_name}</span>
            </label>
        `).join('');

        loadingEl.classList.add('hidden');
        containerEl.classList.remove('hidden');

    } catch (err) {
        console.error('Failed to load sites:', err);
        loadingEl.textContent = 'Failed to load sites';
    }
}

function selectAllSites() {
    document.querySelectorAll('.site-checkbox').forEach(cb => cb.checked = true);
}

function clearAllSites() {
    document.querySelectorAll('.site-checkbox').forEach(cb => cb.checked = false);
}

function getSelectedSites() {
    return Array.from(document.querySelectorAll('.site-checkbox:checked'))
        .map(cb => parseInt(cb.value));
}

function backToSearch() {
    selectedCampground = null;
    document.getElementById('detailsForm').classList.add('hidden');
    document.getElementById('campgroundSearch').value = '';
    document.getElementById('campgroundSearch').focus();
}

function showSearch() {
    document.getElementById('searchCard').classList.remove('hidden');
}

// Date inputs
function initializeDateInputs() {
    const checkinInput = document.getElementById('checkinDate');
    const checkoutInput = document.getElementById('checkoutDate');
    
    const today = new Date().toISOString().split('T')[0];
    checkinInput.min = today;
    checkoutInput.min = today;
    
    checkinInput.addEventListener('change', () => {
        const checkin = new Date(checkinInput.value);
        checkin.setDate(checkin.getDate() + 1);
        checkoutInput.min = checkin.toISOString().split('T')[0];
        
        if (checkoutInput.value && new Date(checkoutInput.value) <= new Date(checkinInput.value)) {
            checkoutInput.value = '';
        }
    });
}

// Create watch
async function createWatch() {
    const checkin = document.getElementById('checkinDate').value;
    const checkout = document.getElementById('checkoutDate').value;
    const siteType = document.getElementById('siteType').value;
    const selectedSites = getSelectedSites();

    if (!checkin || !checkout) {
        alert('Please select check-in and check-out dates');
        return;
    }

    if (new Date(checkout) <= new Date(checkin)) {
        alert('Check-out must be after check-in');
        return;
    }

    const email = prompt('Enter your email for alerts:');
    if (!email || !email.includes('@')) {
        alert('Valid email required');
        return;
    }

    const watchData = {
        campground_id: parseInt(selectedCampground.id),
        campground_name: selectedCampground.name,
        checkin_date: checkin,
        checkout_date: checkout,
        site_type: siteType,
        site_numbers: selectedSites.length > 0 ? selectedSites : null,
        alert_email: email
    };
    
    try {
        await apiFetch(`${API_BASE}/watches`, {
            method: 'POST',
            body: JSON.stringify(watchData)
        });
        
        alert('Watch created! We\'ll check for availability and email you.');
        
        backToSearch();
        loadWatches();
        updateStats();
    } catch (err) {
        alert('Failed to create watch: ' + err.message);
    }
}

// Load watches
async function loadWatches() {
    try {
        const watches = await apiFetch(`${API_BASE}/watches`);
        const container = document.getElementById('watchesList');

        if (watches.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-title">No watches yet</div>
                    <div class="empty-state-text">Search for a campground above to get started</div>
                </div>
            `;
            return;
        }

        container.innerHTML = watches.map(watch => renderWatchCard(watch)).join('');
    } catch (err) {
        console.error('Failed to load watches:', err);
    }
}

function renderWatchCard(watch) {
    const initials = watch.campground_name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
    const checkin = new Date(watch.checkin_date);
    const checkout = new Date(watch.checkout_date);
    const nights = Math.ceil((checkout - checkin) / (1000 * 60 * 60 * 24));
    
    const statusClass = watch.alerted ? 'status-alerted' : 'status-active';
    const statusText = watch.alerted ? 'Sites Found' : 'Monitoring';
    
    const location = 'CA'; // TODO: Parse from campground data
    
    // Generate mini calendar (14 days around check-in)
    const calendarDays = [];
    const startDate = new Date(checkin);
    startDate.setDate(startDate.getDate() - 3);
    
    for (let i = 0; i < 14; i++) {
        const date = new Date(startDate);
        date.setDate(date.getDate() + i);
        const dateStr = date.toISOString().split('T')[0];
        const day = date.getDate();
        
        let dayClass = 'calendar-day ';
        if (dateStr < watch.checkin_date || dateStr >= watch.checkout_date) {
            dayClass += 'day-disabled';
        } else if (watch.alerted) {
            dayClass += 'day-available';
        } else {
            dayClass += 'day-sold-out';
        }
        
        calendarDays.push(`<div class="${dayClass}">${day}</div>`);
    }
    
    const sitesText = watch.site_numbers && watch.site_numbers.length > 0
        ? `Sites ${watch.site_numbers.join(', ')}`
        : 'Any site';
    
    return `
        <div class="campground-card">
            <div class="campground-header-img" style="background: linear-gradient(135deg, #059669 0%, #0891b2 100%);">
                ${initials}
                <span class="status-badge ${statusClass}">${statusText}</span>
            </div>
            <div class="campground-content">
                <div class="campground-title">${watch.campground_name}</div>
                <div class="campground-location">${location}</div>
                
                <div class="campground-dates">
                    <span>${watch.checkin_date}</span>
                    <span>—</span>
                    <span>${watch.checkout_date}</span>
                    <span>•</span>
                    <span>${nights} night${nights > 1 ? 's' : ''}</span>
                </div>
                
                <div class="calendar-mini">
                    ${calendarDays.join('')}
                </div>
                
                <div class="campground-sites">
                    ${sitesText} • ${watch.site_type}
                </div>
                
                <div class="card-actions">
                    <button class="btn btn-secondary" onclick="deleteWatch(${watch.id})">Delete</button>
                </div>
            </div>
        </div>
    `;
}

async function deleteWatch(id) {
    if (!confirm('Delete this watch?')) return;

    try {
        await apiFetch(`${API_BASE}/watches/${id}`, {
            method: 'DELETE'
        });
        loadWatches();
        updateStats();
    } catch (err) {
        alert('Failed to delete watch: ' + err.message);
    }
}
