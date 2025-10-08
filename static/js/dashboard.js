/**
 * INET Dashboard - Real-time WebSocket Updates
 */

// Initialize Socket.IO connection
const socket = io();

// Connection status tracking
let isConnected = false;
const connectionStatus = document.getElementById('connection-status');

// Update connection status badge
function updateConnectionStatus(connected) {
    isConnected = connected;
    
    if (connected) {
        connectionStatus.className = 'badge bg-success connected';
        connectionStatus.innerHTML = '<i class="bi bi-wifi"></i> Connected';
    } else {
        connectionStatus.className = 'badge bg-danger disconnected';
        connectionStatus.innerHTML = '<i class="bi bi-wifi-off"></i> Disconnected';
    }
}

// Socket.IO event handlers
socket.on('connect', () => {
    console.log('Connected to server');
    updateConnectionStatus(true);
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    updateConnectionStatus(false);
});

socket.on('connect_error', (error) => {
    console.error('Connection error:', error);
    updateConnectionStatus(false);
});

// Handle equipment updates
socket.on('equipment_update', (data) => {
    console.log('Received equipment update:', data);
    
    // Update instruments table
    updateInstrumentsTable(data.instruments);
    
    // Update docking stations list
    updateDockingStationsList(data.docking_stations);
    
    // Update last update timestamp
    if (data.last_update) {
        updateLastUpdateTime(data.last_update);
    }
    
    // Update statistics
    updateStatistics(data.instruments);
});

/**
 * Update the instruments table with new data
 */
function updateInstrumentsTable(instruments) {
    const tbody = document.getElementById('instruments-body');
    
    if (!instruments || instruments.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center text-muted py-5">
                    <i class="bi bi-inbox fs-1"></i>
                    <p class="mt-2">No instruments found</p>
                </td>
            </tr>
        `;
        return;
    }
    
    // Sort instruments by Equipment Group (Unit), then by Type (Model)
    instruments.sort((a, b) => {
        const groupA = a['Equipment Group'] || '';
        const groupB = b['Equipment Group'] || '';
        const typeA = a['Type'] || '';
        const typeB = b['Type'] || '';
        
        if (groupA !== groupB) {
            return groupA.localeCompare(groupB);
        }
        return typeA.localeCompare(typeB);
    });
    
    let html = '';
    
    instruments.forEach(instrument => {
        const rowClass = getRowClass(instrument._calibration_status);
        const statusBadge = getStatusBadge(instrument._calibration_status);
        const daysRemaining = instrument._days_until_calibration !== null 
            ? `${instrument._days_until_calibration} days` 
            : 'N/A';
        const upgradeIcon = getUpgradeIcon(instrument['Upgrade Available']);
        
        html += `
            <tr class="${rowClass}">
                <td>${escapeHtml(instrument['Equipment Group'] || 'N/A')}</td>
                <td>${escapeHtml(instrument['Type'] || 'N/A')}</td>
                <td>${escapeHtml(instrument['Serial Number'] || 'N/A')}</td>
                <td class="text-center">${upgradeIcon}</td>
                <td>${escapeHtml(instrument['Last Calibration Time'] || 'N/A')}</td>
                <td>${escapeHtml(instrument['Next Calibration Date'] || 'N/A')}</td>
                <td>${daysRemaining}</td>
                <td>${statusBadge}</td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
    
    // Update total count
    document.getElementById('total-instruments').textContent = instruments.length;
}

/**
 * Update the docking stations list with new data
 */
function updateDockingStationsList(dockingStations) {
    const container = document.getElementById('docking-stations-container');
    
    if (!dockingStations || dockingStations.length === 0) {
        container.innerHTML = `
            <div class="card bg-dark border-secondary">
                <div class="card-body text-center text-muted py-5">
                    <i class="bi bi-inbox fs-1"></i>
                    <p class="mt-2">No docking stations found</p>
                </div>
            </div>
        `;
        return;
    }
    
    let html = '';
    
    dockingStations.forEach(station => {
        const gasStatus = station['Gas Status'] || '';
        const isFull = gasStatus.toLowerCase() === 'full';
        
        let statusIndicator = '';
        if (isFull) {
            statusIndicator = '<i class="bi bi-check-circle-fill text-success ms-1"></i>';
        } else if (gasStatus) {
            statusIndicator = `<i class="bi bi-exclamation-circle-fill text-warning ms-1"></i><small class="text-warning ms-1">${escapeHtml(gasStatus)}</small>`;
        }
        
        // Helper function to generate gas inlet list item HTML
        const generateGasInletHtml = (inletNumber) => {
            const inletKey = `Gas Inlet ${inletNumber}`;
            const pressureKey = `Gas Inlet ${inletNumber} Pressure`;
            
            if (!station[inletKey]) {
                return '';
            }
            
            const inletPressure = station[pressureKey] || '';
            const isPressureFull = inletPressure.toLowerCase() === 'full';
            
            let pressureIndicator = '';
            if (isPressureFull) {
                pressureIndicator = '<i class="bi bi-check-circle-fill text-success ms-1"></i>';
            } else if (inletPressure) {
                pressureIndicator = `<i class="bi bi-exclamation-circle-fill text-warning ms-1"></i><span class="text-warning"> ${escapeHtml(inletPressure)}</span>`;
            }
            
            return `<li class="text-muted">Gas Inlet ${inletNumber}: ${escapeHtml(station[inletKey])} ${pressureIndicator}</li>`;
        };
        
        // Generate HTML for all gas inlets (1-6) as a list
        const gasInletItems = [1, 2, 3, 4, 5, 6]
            .map(num => generateGasInletHtml(num))
            .filter(html => html !== '')
            .join('');
        
        const gasInletsHtml = gasInletItems ? `<ul class="list-unstyled mt-2 mb-0 small">${gasInletItems}</ul>` : '';
        
        // Generate docked instrument HTML
        let dockedInstrumentHtml = '';
        if (station['Instrument Currently Docked']) {
            const dockedSerial = station['Instrument Currently Docked'];
            const dockedUnit = station['_docked_unit'];
            
            if (dockedUnit) {
                dockedInstrumentHtml = `
                    <div class="mt-2 mb-2 docked-instrument-info">
                        <small class="text-muted d-block mb-1">Docked:</small>
                        <strong class="text-info d-block" style="font-size: 1.1rem;">${escapeHtml(dockedUnit)}</strong>
                        <strong class="text-muted d-block" style="font-size: 0.9rem;">SN: ${escapeHtml(dockedSerial)}</strong>
                    </div>
                `;
            } else {
                dockedInstrumentHtml = `
                    <div class="mt-2 mb-2 docked-instrument-info">
                        <small class="text-muted d-block mb-1">Docked:</small>
                        <strong class="text-warning">${escapeHtml(dockedSerial)}</strong>
                    </div>
                `;
            }
        }
        
        html += `
            <div class="card bg-dark border-secondary docking-station-card">
                <div class="card-header bg-secondary py-2">
                    <h6 class="mb-0">
                        ${escapeHtml(station['Type'] || 'N/A')}
                        ${statusIndicator}
                    </h6>
                </div>
                <div class="card-body p-3">
                    ${station['Equipment Number'] ? `<p class="mb-1 small text-muted">Equip #: ${escapeHtml(station['Equipment Number'])}</p>` : ''}
                    <strong class="d-block mb-1">${escapeHtml(station['Last Known State'] || 'Idle')}</strong>
                    ${station['Serial Number'] ? `<small class="text-muted d-block">SN: ${escapeHtml(station['Serial Number'])}</small>` : ''}
                    ${dockedInstrumentHtml}
                    ${gasInletsHtml}
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

/**
 * Update the last update timestamp
 */
function updateLastUpdateTime(timestamp) {
    const updateTimeElement = document.getElementById('update-time');
    
    if (timestamp) {
        const date = new Date(timestamp);
        const formattedTime = formatDateTime(date);
        updateTimeElement.textContent = formattedTime;
    }
}

/**
 * Update statistics (overdue and warning counts)
 */
function updateStatistics(instruments) {
    if (!instruments) return;
    
    let overdueCount = 0;
    let warningCount = 0;
    
    instruments.forEach(instrument => {
        if (instrument._calibration_status === 'danger') {
            overdueCount++;
        } else if (instrument._calibration_status === 'warning') {
            warningCount++;
        }
    });
    
    document.getElementById('overdue-count').textContent = overdueCount;
    document.getElementById('warning-count').textContent = warningCount;
}

/**
 * Get table row class based on calibration status
 */
function getRowClass(status) {
    switch (status) {
        case 'danger':
            return 'table-danger';
        case 'warning':
            return 'table-warning';
        default:
            return '';
    }
}

/**
 * Get status badge HTML based on calibration status
 */
function getStatusBadge(status) {
    switch (status) {
        case 'danger':
            return '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Overdue</span>';
        case 'warning':
            return '<span class="badge bg-warning text-dark"><i class="bi bi-exclamation-triangle"></i> Due Soon</span>';
        default:
            return '<span class="badge bg-success"><i class="bi bi-check-circle"></i> OK</span>';
    }
}

/**
 * Get upgrade icon HTML based on upgrade available status
 */
function getUpgradeIcon(upgradeStatus) {
    if (!upgradeStatus) {
        return '<span class="text-muted">-</span>';
    }
    
    const status = upgradeStatus.trim();
    
    if (status.toLowerCase() === 'no') {
        return `<i class="bi bi-check-circle-fill text-success" title="No upgrade needed"></i>`;
    } else if (status.startsWith('YesPending')) {
        return `<i class="bi bi-clock-fill text-warning" title="${escapeHtml(status)}"></i>`;
    } else {
        return `<i class="bi bi-exclamation-circle-fill text-danger" title="${escapeHtml(status)}"></i>`;
    }
}

/**
 * Format datetime for display
 */
function formatDateTime(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) {
        return 'Just now';
    } else if (diffMins < 60) {
        return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    } else if (diffMins < 1440) {
        const hours = Math.floor(diffMins / 60);
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    } else {
        return date.toLocaleString();
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Request manual update from server
 */
function requestUpdate() {
    socket.emit('request_update');
}

// Auto-refresh timestamp every minute
setInterval(() => {
    const updateTimeElement = document.getElementById('update-time');
    const currentText = updateTimeElement.textContent;
    
    // Only update if it's a relative time format
    if (currentText.includes('ago') || currentText === 'Just now') {
        const lastUpdate = updateTimeElement.getAttribute('data-timestamp');
        if (lastUpdate) {
            const date = new Date(lastUpdate);
            updateTimeElement.textContent = formatDateTime(date);
        }
    }
}, 60000);

// Store timestamp as data attribute when updating
const originalUpdateLastUpdateTime = updateLastUpdateTime;
updateLastUpdateTime = function(timestamp) {
    originalUpdateLastUpdateTime(timestamp);
    const updateTimeElement = document.getElementById('update-time');
    if (timestamp) {
        updateTimeElement.setAttribute('data-timestamp', timestamp);
    }
};

console.log('Dashboard WebSocket client initialized');

