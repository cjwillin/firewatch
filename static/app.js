/**
 * Firewatch UI - Redesigned with new design system
 */

// API Configuration
const API_BASE = '/api';
const API_KEY = localStorage.getItem('firewatch_api_key') || '';

// State
let selectedCampground = null;
let searchTimeout = null;
let availabilityData = null;
let currentMonth = new Date();
let selectedStartDate = null;
let selectedEndDate = null;

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
    currentMonth = new Date();
    selectedStartDate = null;
    selectedEndDate = null;

    document.getElementById('searchResults').classList.add('hidden');
    document.getElementById('detailsForm').classList.remove('hidden');
    document.getElementById('selectedName').textContent = campground.name;
    document.getElementById('selectedLocation').textContent = campground.location;

    // Load sites for filtering
    loadCampgroundSites(campground.id);

    // Show monthly calendar immediately
    loadMonthlyAvailability();

    // Add site type change listener
    const siteTypeSelect = document.getElementById('siteType');
    siteTypeSelect.addEventListener('change', () => {
        loadMonthlyAvailability();
    });
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

        // Add change listeners to checkboxes
        document.querySelectorAll('.site-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                if (selectedCampground) {
                    loadMonthlyAvailability();
                }
            });
        });

        loadingEl.classList.add('hidden');
        containerEl.classList.remove('hidden');
        listEl.classList.remove('hidden');

    } catch (err) {
        console.error('Failed to load sites:', err);
        loadingEl.textContent = 'Failed to load sites';
    }
}

function selectAllSites() {
    document.querySelectorAll('.site-checkbox').forEach(cb => cb.checked = true);
    if (selectedCampground) {
        loadMonthlyAvailability();
    }
}

function clearAllSites() {
    document.querySelectorAll('.site-checkbox').forEach(cb => cb.checked = false);
    if (selectedCampground) {
        loadMonthlyAvailability();
    }
}

function getSelectedSites() {
    return Array.from(document.querySelectorAll('.site-checkbox:checked'))
        .map(cb => parseInt(cb.value));
}

function backToSearch() {
    selectedCampground = null;
    availabilityData = null;
    selectedStartDate = null;
    selectedEndDate = null;
    currentMonth = new Date();
    document.getElementById('detailsForm').classList.add('hidden');
    document.getElementById('campgroundSearch').value = '';
    document.getElementById('campgroundSearch').focus();
    document.getElementById('monthlyCalendar').classList.add('hidden');
}

function showSearch() {
    document.getElementById('searchCard').classList.remove('hidden');
}

// Load monthly availability calendar
async function loadMonthlyAvailability() {
    if (!selectedCampground) return;

    const calendarContainer = document.getElementById('monthlyCalendar');
    calendarContainer.classList.remove('hidden');
    calendarContainer.innerHTML = '<div class="loading">Loading availability...</div>';

    try {
        const siteType = document.getElementById('siteType').value;
        const selectedSites = getSelectedSites();

        // Get first and last day of current month
        const firstDay = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1);
        const lastDay = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0);

        // Build query params
        const params = new URLSearchParams({
            checkin: firstDay.toISOString().split('T')[0],
            checkout: lastDay.toISOString().split('T')[0],
            site_type: siteType || 'Any'
        });

        if (selectedSites.length > 0) {
            params.set('site_numbers', selectedSites.join(','));
        }

        const data = await apiFetch(`${API_BASE}/campgrounds/${selectedCampground.id}/availability?${params}`);
        availabilityData = data;

        renderMonthlyCalendar(data);

    } catch (err) {
        console.error('Failed to load availability:', err);
        calendarContainer.innerHTML = `
            <div class="availability-error">
                <p><strong>Failed to load availability</strong></p>
                <p style="font-size: 13px; color: #78716c; margin-top: 4px;">${err.message}</p>
            </div>
        `;
    }
}

function renderMonthlyCalendar(data) {
    const container = document.getElementById('monthlyCalendar');
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Month header with navigation
    const monthName = currentMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    const canGoPrev = currentMonth > today;

    let calendarHTML = `
        <div class="calendar-header">
            <button onclick="prevMonth()" class="btn btn-secondary btn-sm" ${!canGoPrev ? 'disabled' : ''}>← Prev</button>
            <h3>${monthName}</h3>
            <button onclick="nextMonth()" class="btn btn-secondary btn-sm">Next →</button>
        </div>
        <div class="calendar-legend">
            <div class="legend-item">
                <div class="legend-dot available"></div>
                <span>Available (click to book)</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot sold-out"></div>
                <span>Sold out (click to watch)</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot past"></div>
                <span>Past dates</span>
            </div>
        </div>
        <div class="calendar-grid-full">
            <div class="calendar-weekday">Sun</div>
            <div class="calendar-weekday">Mon</div>
            <div class="calendar-weekday">Tue</div>
            <div class="calendar-weekday">Wed</div>
            <div class="calendar-weekday">Thu</div>
            <div class="calendar-weekday">Fri</div>
            <div class="calendar-weekday">Sat</div>
    `;

    // Get first day of month and number of days
    const firstDay = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1);
    const lastDay = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0);
    const firstDayOfWeek = firstDay.getDay();
    const numDays = lastDay.getDate();

    // Add empty cells for days before month starts
    for (let i = 0; i < firstDayOfWeek; i++) {
        calendarHTML += '<div class="calendar-day-cell empty"></div>';
    }

    // Add days of month
    for (let day = 1; day <= numDays; day++) {
        const date = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), day);
        const dateStr = date.toISOString().split('T')[0];
        const dayData = data.availability[dateStr];
        const isPast = date < today;

        let cellClass = 'calendar-day-cell';
        let sitesText = '';
        let clickable = false;

        if (isPast) {
            cellClass += ' past';
        } else if (dayData) {
            if (dayData.status === 'available' && dayData.sites_count > 0) {
                cellClass += ' available clickable';
                sitesText = `${dayData.sites_count} ${dayData.sites_count === 1 ? 'site' : 'sites'}`;
                clickable = true;
            } else {
                cellClass += ' sold-out clickable';
                sitesText = 'Sold out';
                clickable = true;
            }
        }

        // Check if this date is in selection range
        if (selectedStartDate || selectedEndDate) {
            const dateMs = date.getTime();
            if (selectedStartDate && dateMs === selectedStartDate.getTime()) {
                cellClass += ' selected-start';
            }
            if (selectedEndDate && dateMs === selectedEndDate.getTime()) {
                cellClass += ' selected-end';
            }
            if (selectedStartDate && selectedEndDate &&
                dateMs > selectedStartDate.getTime() && dateMs < selectedEndDate.getTime()) {
                cellClass += ' selected-range';
            }
        }

        const onclickAttr = clickable ? `onclick="handleDateClick('${dateStr}', ${dayData.status === 'available'})"` : '';

        calendarHTML += `
            <div class="${cellClass}" ${onclickAttr} data-date="${dateStr}">
                <div class="day-number">${day}</div>
                ${sitesText ? `<div class="day-info">${sitesText}</div>` : ''}
            </div>
        `;
    }

    calendarHTML += '</div>';

    // Selection summary
    if (selectedStartDate && selectedEndDate) {
        const nights = Math.ceil((selectedEndDate - selectedStartDate) / (1000 * 60 * 60 * 24));
        const startStr = selectedStartDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const endStr = selectedEndDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

        // Check if selected range has availability
        const rangeHasAvailability = checkRangeAvailability(selectedStartDate, selectedEndDate, data);

        calendarHTML += `
            <div class="selection-summary">
                <div class="selection-dates">
                    <strong>${startStr} - ${endStr}</strong> (${nights} ${nights === 1 ? 'night' : 'nights'})
                    <button onclick="clearSelection()" class="btn-link" style="margin-left: 12px;">Clear</button>
                </div>
                ${rangeHasAvailability ? `
                    <div class="selection-actions">
                        <a href="${getBookingUrl(selectedStartDate, selectedEndDate)}" target="_blank" class="btn btn-primary">
                            Book on Recreation.gov →
                        </a>
                    </div>
                ` : `
                    <div class="selection-actions">
                        <button onclick="createWatchForSelection()" class="btn btn-primary">
                            Create Watch for These Dates
                        </button>
                    </div>
                `}
            </div>
        `;
    } else if (selectedStartDate) {
        const startStr = selectedStartDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        calendarHTML += `
            <div class="selection-summary">
                <div class="selection-dates">
                    Check-in: <strong>${startStr}</strong> (click another date for check-out)
                    <button onclick="clearSelection()" class="btn-link" style="margin-left: 12px;">Clear</button>
                </div>
            </div>
        `;
    }

    container.innerHTML = calendarHTML;
}

function checkRangeAvailability(startDate, endDate, data) {
    let currentDate = new Date(startDate);
    while (currentDate < endDate) {
        const dateStr = currentDate.toISOString().split('T')[0];
        const dayData = data.availability[dateStr];
        if (dayData && dayData.status === 'available' && dayData.sites_count > 0) {
            return true;
        }
        currentDate.setDate(currentDate.getDate() + 1);
    }
    return false;
}

function handleDateClick(dateStr, isAvailable) {
    const clickedDate = new Date(dateStr + 'T00:00:00');

    if (!selectedStartDate) {
        // First click - set start date
        selectedStartDate = clickedDate;
        selectedEndDate = null;
        loadMonthlyAvailability(); // Re-render to show selection
    } else if (!selectedEndDate) {
        // Second click - set end date
        if (clickedDate > selectedStartDate) {
            selectedEndDate = clickedDate;
            loadMonthlyAvailability(); // Re-render to show full selection
        } else {
            // Clicked earlier date, reset
            selectedStartDate = clickedDate;
            selectedEndDate = null;
            loadMonthlyAvailability();
        }
    } else {
        // Already have both dates, reset selection
        selectedStartDate = clickedDate;
        selectedEndDate = null;
        loadMonthlyAvailability();
    }
}

function clearSelection() {
    selectedStartDate = null;
    selectedEndDate = null;
    loadMonthlyAvailability();
}

function getBookingUrl(startDate, endDate) {
    const nights = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24));
    const checkinStr = startDate.toISOString().split('T')[0];
    return `https://www.recreation.gov/camping/campgrounds/${selectedCampground.id}/availability?date=${checkinStr}&length=${nights}`;
}

async function createWatchForSelection() {
    if (!selectedStartDate || !selectedEndDate) {
        alert('Please select check-in and check-out dates');
        return;
    }

    const email = prompt('Enter your email for availability alerts:');
    if (!email || !email.includes('@')) {
        alert('Valid email required');
        return;
    }

    const siteType = document.getElementById('siteType').value;
    const selectedSites = getSelectedSites();

    const watchData = {
        campground_id: parseInt(selectedCampground.id),
        campground_name: selectedCampground.name,
        checkin_date: selectedStartDate.toISOString().split('T')[0],
        checkout_date: selectedEndDate.toISOString().split('T')[0],
        site_type: siteType,
        site_numbers: selectedSites.length > 0 ? selectedSites : null,
        alert_email: email
    };

    try {
        await apiFetch(`${API_BASE}/watches`, {
            method: 'POST',
            body: JSON.stringify(watchData)
        });

        alert('Watch created! We\'ll check every 5 minutes and email you when sites become available.');

        backToSearch();
        loadWatches();
        updateStats();
    } catch (err) {
        alert('Failed to create watch: ' + err.message);
    }
}

function prevMonth() {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const newMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1);
    if (newMonth >= today) {
        currentMonth = newMonth;
        loadMonthlyAvailability();
    }
}

function nextMonth() {
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1);
    loadMonthlyAvailability();
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
