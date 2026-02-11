/*document.getElementById('cohortForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('cohortName').value;
    const sampleIds = document.getElementById('sampleIds').value
        .split('\n')
        .map(id => id.trim())
        .filter(id => id.length > 0);
    
    if (sampleIds.length === 0) {
        showAlert('Please provide at least one sample ID', 'danger');
        return;
    }
    
    try {
        const response = await fetch('/api/cohorts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cohort_name: name,
                sample_ids: sampleIds
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(`Cohort "${name}" created successfully with ${result.sample_count} valid samples!`, 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showAlert('Error: ' + result.detail, 'danger');
        }
    } catch (err) {
        showAlert('Error creating cohort. Please try again.', 'danger');
    }
});
*/
document.addEventListener('DOMContentLoaded', function() {
    setupCohortAutoRefresh();
    refreshCohortsFromApi();
});

function setupCohortAutoRefresh() {
    let lastRefreshAt = Date.now();

    function refreshIfNeeded(force = false) {
        const now = Date.now();
        if (!force && now - lastRefreshAt < 5000) {
            return;
        }
        lastRefreshAt = now;
        refreshCohortsFromApi();
    }

    window.addEventListener('focus', function() {
        refreshIfNeeded();
    });

    window.addEventListener('pageshow', function() {
        refreshIfNeeded(true);
    });

    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            refreshIfNeeded();
        }
    });

    window.addEventListener('storage', function(event) {
        if (event.key === 'cohorts_updated_at') {
            refreshIfNeeded(true);
        }
    });

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('imported') === '1') {
        refreshIfNeeded(true);
    }
}

async function refreshCohortsFromApi() {
    try {
        const response = await fetch(`/api/cohorts?ts=${Date.now()}`, { cache: 'no-store' });
        if (!response.ok) {
            return;
        }

        const result = await response.json();
        const cohorts = (result && result.cohorts) ? result.cohorts : [];
        renderCohortsList(cohorts);
    } catch (err) {
        console.error('Error refreshing cohorts:', err);
    }
}

function renderCohortsList(cohorts) {
    const cohortsList = document.getElementById('cohortsList');
    if (!cohortsList) return;

    if (!cohorts.length) {
        cohortsList.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="fas fa-users fa-3x mb-3"></i>
                <p>No cohorts created yet.</p>
                <p class="small">Create your first cohort using the form on the left.</p>
            </div>
        `;
    } else {
        cohortsList.innerHTML = cohorts.map((cohort) => `
            <div class="card mb-3" id="cohort-${escapeHtml(cohort.cohort_id)}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5 class="card-title">
                                <i class="fas fa-users text-primary me-2"></i>
                                ${escapeHtml(cohort.cohort_name)}
                            </h5>
                            <p class="card-text">
                                <small class="text-muted">
                                    <i class="fas fa-hashtag me-1"></i>
                                    ${cohort.sample_id_count || 0} samples
                                </small><br>
                                <small class="text-muted">
                                    <i class="fas fa-calendar me-1"></i>
                                    Created: ${escapeHtml(cohort.created_at || '')}
                                </small>
                            </p>
                        </div>
                        <button class="btn btn-outline-danger btn-sm cohort-delete-btn"
                                data-cohort-id="${escapeHtml(cohort.cohort_id)}"
                                data-cohort-name="${escapeHtml(cohort.cohort_name)}">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    const countBadge = document.querySelector('.badge');
    if (countBadge) {
        countBadge.textContent = String(cohorts.length);
    }

    document.querySelectorAll('.cohort-delete-btn').forEach((button) => {
        button.addEventListener('click', () => {
            deleteCohort(button.dataset.cohortId, button.dataset.cohortName);
        });
    });
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

async function deleteCohort(cohortId, cohortName) {
    if (confirm(`Are you sure you want to delete the cohort "${cohortName}"?`)) {
        try {
            const response = await fetch(`/api/cohorts/${cohortId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                showAlert(`Cohort "${cohortName}" deleted successfully`, 'success');
                const cohortElement = document.getElementById(`cohort-${cohortId}`);
                if (cohortElement) {
                    cohortElement.remove();
                }
                localStorage.setItem('cohorts_updated_at', String(Date.now()));
                
                // Update cohort count in header
                const countBadge = document.querySelector('.badge');
                if (countBadge) {
                    const currentCount = parseInt(countBadge.textContent);
                    countBadge.textContent = currentCount - 1;
                }
                
                // Show empty state if no cohorts left
                const cohortsList = document.getElementById('cohortsList');
                if (cohortsList.children.length === 0) {
                    cohortsList.innerHTML = `
                        <div class="text-center text-muted py-4">
                            <i class="fas fa-users fa-3x mb-3"></i>
                            <p>No cohorts created yet.</p>
                            <p class="small">Create your first cohort using the form on the left.</p>
                        </div>
                    `;
                }
                refreshCohortsFromApi();
            } else {
                showAlert('Error deleting cohort', 'danger');
            }
        } catch (err) {
            showAlert('Error deleting cohort. Please try again.', 'danger');
        }
    }
}

function showAlert(message, type) {
    const alertContainer = document.getElementById('alertContainer');
    const alertId = 'alert-' + Date.now();
    
    const alertHtml = `
        <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show" role="alert">
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    alertContainer.innerHTML = alertHtml;
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alert = document.getElementById(alertId);
        if (alert) {
            alert.remove();
        }
    }, 5000);
}
