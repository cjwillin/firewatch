/**
 * Firewatch UI - New Availability-First Workflow
 *
 * Flow: Search → Dates → Availability → Book/Watch
 */

// API Configuration
const API_BASE = '/api';
const API_KEY = localStorage.getItem('firewatch_api_key') || '';

// State
let selectedCampground = null;
let availabilityData = null;
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

    // Handle 204 No Content
    if (response.status === 204) {
        return null;
    }

    return response.json();
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeCampgroundSearch();
    initializeDateInputs();
    updateHealthStatus();
    loadWatches();
    
    // Update health every 30 seconds
    setInterval(updateHealthStatus, 30000);
});

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
        }

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

// Step 1: Campground Search
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

    // Hide results when clicking outside
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
            resultsContainer.innerHTML = '<div class="autocomplete-item"><div class="text-gray-500">No campgrounds found</div></div>';
            resultsContainer.classList.remove('hidden');
            return;
        }

        resultsContainer.innerHTML = results.map(campground => `
            <div class="autocomplete-item" data-id="${campground.id}" data-name="${campground.name}" 
                 data-location="${campground.location}" data-image="${campground.preview_image_url || ''}">
                ${campground.preview_image_url ? 
                    `<img src="${campground.preview_image_url}" alt="${campground.name}">` : 
                    '<div class="w-16 h-16 bg-gray-200 rounded-lg flex items-center justify-center text-2xl">🏕️</div>'
                }
                <div class="autocomplete-item-details">
                    <div class="autocomplete-item-name">${campground.name}</div>
                    <div class="autocomplete-item-location">${campground.location}</div>
                </div>
            </div>
        `).join('');

        // Add click handlers
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
    
    // Hide search results
    document.getElementById('searchResults').classList.add('hidden');
    
    // Move to step 2
    document.getElementById('searchStep').classList.add('hidden');
    document.getElementById('datesStep').classList.remove('hidden');
    
    // Update progress
    document.getElementById('step1').classList.remove('step-active');
    document.getElementById('step1').classList.add('step-complete');
    document.getElementById('step2').classList.remove('step-inactive');
    document.getElementById('step2').classList.add('step-active');
    
    // Display selected campground
    document.getElementById('selectedCampgroundName').textContent = campground.name;
    document.getElementById('selectedCampgroundLocation').textContent = campground.location;
    
    const imgEl = document.getElementById('selectedCampgroundImage');
    if (campground.preview_image_url) {
        imgEl.src = campground.preview_image_url;
        imgEl.style.display = 'block';
    }
}

function backToSearch() {
    selectedCampground = null;
    
    // Reset to step 1
    document.getElementById('datesStep').classList.add('hidden');
    document.getElementById('searchStep').classList.remove('hidden');
    
    // Update progress
    document.getElementById('step2').classList.remove('step-active');
    document.getElementById('step2').classList.add('step-inactive');
    document.getElementById('step1').classList.remove('step-complete');
    document.getElementById('step1').classList.add('step-active');
    
    // Clear search
    document.getElementById('campgroundSearch').value = '';
}

// Step 2: Date Selection
function initializeDateInputs() {
    const checkinInput = document.getElementById('checkinDate');
    const checkoutInput = document.getElementById('checkoutDate');
    
    // Set minimum dates to today
    const today = new Date().toISOString().split('T')[0];
    checkinInput.min = today;
    checkoutInput.min = today;
    
    // When checkin changes, update checkout minimum
    checkinInput.addEventListener('change', () => {
        const checkin = new Date(checkinInput.value);
        checkin.setDate(checkin.getDate() + 1);
        checkoutInput.min = checkin.toISOString().split('T')[0];
        
        // Clear checkout if it's before new minimum
        if (checkoutInput.value && new Date(checkoutInput.value) <= new Date(checkinInput.value)) {
            checkoutInput.value = '';
        }
    });
}

async function checkAvailability() {
    const checkin = document.getElementById('checkinDate').value;
    const checkout = document.getElementById('checkoutDate').value;
    const siteType = document.getElementById('siteType').value;
    
    if (!checkin || !checkout) {
        alert('Please select both check-in and check-out dates');
        return;
    }
    
    if (new Date(checkout) <= new Date(checkin)) {
        alert('Check-out must be after check-in');
        return;
    }
    
    // Move to step 3
    document.getElementById('datesStep').classList.add('hidden');
    document.getElementById('availabilityStep').classList.remove('hidden');
    document.getElementById('availabilityLoading').classList.remove('hidden');
    document.getElementById('availabilityResults').classList.add('hidden');
    
    // Update progress
    document.getElementById('step2').classList.remove('step-active');
    document.getElementById('step2').classList.add('step-complete');
    document.getElementById('step3').classList.remove('step-inactive');
    document.getElementById('step3').classList.add('step-active');
    
    try {
        const response = await apiFetch(
            `${API_BASE}/campgrounds/${selectedCampground.id}/availability?checkin=${checkin}&checkout=${checkout}&site_type=${siteType}`
        );
        
        availabilityData = response;
        renderAvailabilityResults(response);
    } catch (err) {
        document.getElementById('availabilityLoading').classList.add('hidden');
        document.getElementById('availabilityResults').classList.remove('hidden');
        document.getElementById('availabilityResults').innerHTML = `
            <div class="text-center py-8">
                <div class="text-red-600 text-lg font-semibold mb-2">⚠️ Failed to check availability</div>
                <p class="text-gray-600">${err.message}</p>
                <button onclick="backToDates()" class="mt-4 text-blue-600 hover:underline">Try again</button>
            </div>
        `;
    }
}

function renderAvailabilityResults(data) {
    document.getElementById('availabilityLoading').classList.add('hidden');
    const resultsContainer = document.getElementById('availabilityResults');
    resultsContainer.classList.remove('hidden');
    
    const checkin = document.getElementById('checkinDate').value;
    const checkout = document.getElementById('checkoutDate').value;
    
    if (data.has_availability) {
        // Available! Show booking option
        resultsContainer.innerHTML = `
            <div class="text-center py-8">
                <div class="text-6xl mb-4">✅</div>
                <h3 class="text-2xl font-bold text-green-600 mb-2">Sites Available!</h3>
                <p class="text-gray-600 mb-6">${data.available_sites.length} site(s) available for your dates</p>
                
                <div class="mb-6">
                    ${renderCalendar(data.availability, checkin, checkout)}
                </div>
                
                <div class="flex gap-4 justify-center">
                    <a href="${data.booking_url}" target="_blank" rel="noopener"
                       class="bg-green-600 text-white px-8 py-3 rounded-lg hover:bg-green-700 font-semibold inline-block">
                        Book Now on Recreation.gov →
                    </a>
                    <button onclick="backToDates()" class="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300">
                        Change Dates
                    </button>
                </div>
                
                <div class="mt-6 text-left border-t pt-4">
                    <h4 class="font-semibold mb-2">Available Sites:</h4>
                    <div class="space-y-2">
                        ${data.available_sites.slice(0, 5).map(site => `
                            <div class="text-sm text-gray-600">
                                <span class="font-medium">${site.site_name}</span> - ${site.site_type}
                            </div>
                        `).join('')}
                        ${data.available_sites.length > 5 ? `
                            <div class="text-sm text-gray-500">+ ${data.available_sites.length - 5} more sites</div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    } else {
        // Sold out! Show watch creation option
        resultsContainer.innerHTML = `
            <div class="text-center py-8">
                <div class="text-6xl mb-4">😞</div>
                <h3 class="text-2xl font-bold text-red-600 mb-2">Sold Out</h3>
                <p class="text-gray-600 mb-6">No sites available for your selected dates</p>
                
                <div class="mb-6">
                    ${renderCalendar(data.availability, checkin, checkout)}
                </div>
                
                <div class="bg-blue-50 border-2 border-blue-200 rounded-lg p-6 mb-4">
                    <h4 class="font-semibold text-blue-900 mb-2">🔔 Get notified when sites become available</h4>
                    <p class="text-sm text-blue-700 mb-4">
                        We'll check every 5 minutes and email you immediately if a site opens up.
                    </p>
                    
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-1">Your Email</label>
                        <input type="email" id="watchEmail" placeholder="you@example.com"
                               class="w-full border rounded-lg px-3 py-2">
                    </div>
                    
                    <button onclick="createWatchFromAvailability()" 
                            class="w-full bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 font-semibold">
                        Create Availability Watch
                    </button>
                </div>
                
                <button onclick="backToDates()" class="text-blue-600 hover:underline">
                    Try Different Dates
                </button>
            </div>
        `;
    }
}

function renderCalendar(availability, checkin, checkout) {
    // Generate calendar view
    const dates = Object.keys(availability).sort();
    
    if (dates.length === 0) {
        return '<p class="text-gray-500">No availability data</p>';
    }
    
    return `
        <div class="calendar-grid">
            <div class="calendar-day-header">Su</div>
            <div class="calendar-day-header">Mo</div>
            <div class="calendar-day-header">Tu</div>
            <div class="calendar-day-header">We</div>
            <div class="calendar-day-header">Th</div>
            <div class="calendar-day-header">Fr</div>
            <div class="calendar-day-header">Sa</div>
            
            ${dates.map(dateStr => {
                const date = new Date(dateStr);
                const day = date.getDate();
                const dayData = availability[dateStr];
                const status = dayData.status;
                const count = dayData.sites_count;
                
                let className = 'calendar-day ';
                if (status === 'available') {
                    className += 'calendar-day-available';
                } else {
                    className += 'calendar-day-sold-out';
                }
                
                return `
                    <div class="${className}" title="${status === 'available' ? count + ' sites available' : 'Sold out'}">
                        <div>${day}</div>
                        <div class="text-xs">${status === 'available' ? count : '—'}</div>
                    </div>
                `;
            }).join('')}
        </div>
        <div class="mt-2 flex items-center gap-4 justify-center text-xs">
            <div class="flex items-center gap-1">
                <div class="w-4 h-4 rounded calendar-day-available"></div>
                <span>Available</span>
            </div>
            <div class="flex items-center gap-1">
                <div class="w-4 h-4 rounded calendar-day-sold-out"></div>
                <span>Sold Out</span>
            </div>
        </div>
    `;
}

function backToDates() {
    availabilityData = null;
    
    // Reset to step 2
    document.getElementById('availabilityStep').classList.add('hidden');
    document.getElementById('datesStep').classList.remove('hidden');
    
    // Update progress
    document.getElementById('step3').classList.remove('step-active');
    document.getElementById('step3').classList.add('step-inactive');
    document.getElementById('step2').classList.remove('step-complete');
    document.getElementById('step2').classList.add('step-active');
}

async function createWatchFromAvailability() {
    const email = document.getElementById('watchEmail').value;
    
    if (!email || !email.includes('@')) {
        alert('Please enter a valid email address');
        return;
    }
    
    const checkin = document.getElementById('checkinDate').value;
    const checkout = document.getElementById('checkoutDate').value;
    const siteType = document.getElementById('siteType').value;
    
    const watchData = {
        campground_id: parseInt(selectedCampground.id),
        campground_name: selectedCampground.name,
        checkin_date: checkin,
        checkout_date: checkout,
        site_type: siteType,
        alert_email: email
    };
    
    try {
        await apiFetch(`${API_BASE}/watches`, {
            method: 'POST',
            body: JSON.stringify(watchData)
        });
        
        alert('✓ Watch created! We\'ll email you when sites become available.');
        
        // Reload watches list
        loadWatches();
        
        // Reset to start
        backToSearch();
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
            container.innerHTML = '<div class="text-center text-gray-500 py-4 text-sm">No watches yet</div>';
            return;
        }

        container.innerHTML = watches.map(watch => `
            <div class="border rounded-lg p-4 mb-3">
                <div class="flex items-center justify-between mb-2">
                    <div class="font-semibold">${watch.campground_name}</div>
                    <button onclick="deleteWatch(${watch.id})" class="text-red-600 hover:text-red-700 text-sm">Delete</button>
                </div>
                <div class="text-sm text-gray-600">
                    ${watch.checkin_date} to ${watch.checkout_date} • ${watch.site_type}
                </div>
                <div class="text-xs text-gray-500 mt-1">
                    ${watch.active ? '✓ Active' : '⏸ Paused'} • 
                    ${watch.alerted ? 'Alert sent ✉️' : 'Monitoring...'}
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Failed to load watches:', err);
    }
}

async function deleteWatch(id) {
    if (!confirm('Delete this watch?')) return;

    try {
        await apiFetch(`${API_BASE}/watches/${id}`, {
            method: 'DELETE'
        });
        loadWatches();
        updateHealthStatus();
    } catch (err) {
        alert('Failed to delete watch: ' + err.message);
    }
}
