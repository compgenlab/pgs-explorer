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
async function deleteCohort(cohortId, cohortName) {
    if (confirm(`Are you sure you want to delete the cohort "${cohortName}"?`)) {
        try {
            const response = await fetch(`/api/cohorts/${cohortId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                showAlert(`Cohort "${cohortName}" deleted successfully`, 'success');
                document.getElementById(`cohort-${cohortId}`).remove();
                
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