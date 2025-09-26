$(document).ready(function() {
    // 1. Check if we are loading previous image
    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('task_id');
    
    if (taskId) {
        console.log(taskId)
        // Show loading indicator
        showLoadingState();
        // Load task data
        loadTaskData(taskId);
    }
    
    // 2. Set variables to store cohorts and data
    let cohorts = [];
    let plotData = null;
    let pgsScores = [];
    let tableData = [];
    let originalTableData = []; 
    const PRESET_COLORS = [
        "#e41a1c",  // Red
        "#377eb8",  // Blue
        "#4daf4a",  // Green
        "#984ea3",  // Purple
        "#ff7f00",  // Orange
        "#FFD700",  // Gold
        "#a65628",  // Brown
        "#f781bf",  // Pink
        "#999999"   // Gray
    ];

    // 3. Fetch PGS IDs and permanent cohorts on page load
    fetchPgsList();
    loadPermanentCohorts(); 

    ////////// EVENT LISTENERS //////////
    // Initialize color picker
    $('#cohortColor').on('input', function() {
        $('#colorPreview').css('background-color', $(this).val());
    });
    
    // Set initial color
    $('#colorPreview').css('background-color', $('#cohortColor').val());
    
    // Handle analysis type change
    $('#analysisType').on('change', function() {
        const type = $(this).val();
        if (type === 'cohort') {
            // Cohort comparison mode
            $('#pgsSelectionDiv').show();
            $('#scoreType').closest('.mb-3').show();  // Show score type in config
            $('#cohortSelectionDiv').hide();         // Hide cohort selector in config
            $('#cohortManagementCard').show();
            $('#pgsManagementCard').hide();
        } else {
            // PGS comparison mode
            $('#pgsSelectionDiv').hide();
            $('#scoreType').closest('.mb-3').hide();  // Hide score type in config
            $('#cohortSelectionDiv').show();         // Show cohort selector in config
            $('#cohortManagementCard').hide();
            $('#pgsManagementCard').show();
        }
    });

    // Add PGS button
    $('#addPgsBtn').on('click', function(e) {
        e.preventDefault();
        addPgsIds();
    });
    
    // Handle PGS selection change
    $('#pgsId').on('change', function() {
        const pgsId = $(this).val();
        if (pgsId) {
            fetchScoreTypes(pgsId);
            loadMetadata(pgsId);
        } else {
            // Hide metadata card if no PGS ID is selected
            $('#metadataCard').hide();
        }
    });
    
    // Add cohort button
    $('#addCohortBtn').on('click', function(e) {
        e.preventDefault();
        addCohort();
    });
    
    // Form submission
    $('#distributionForm').on('submit', function(e) {
        e.preventDefault();

        // Update modal title based on chart type
        const chartType = $('input[name="chartType"]:checked').val();
        const plotTitle = chartType === 'density' ? 'Density Plot' : 
                        (chartType === 'histogram' ? 'Histogram' : 'Box Plot');
        
        $('#taskNameModalLabel').text(`Name Your ${plotTitle}`);
        $('#taskName').attr('placeholder', `My ${plotTitle}`);
        
        // Show the modal
        const taskNameModal = new bootstrap.Modal(document.getElementById('taskNameModal'));
        taskNameModal.show();
    });

    $('#confirmTaskName').on('click', function() {
        // Get the task name
        const taskName = $('#taskName').val().trim();
        
        // Hide the modal
        const taskNameModal = bootstrap.Modal.getInstance(document.getElementById('taskNameModal'));
        if (taskNameModal) {
            taskNameModal.hide();
        }
        
        // Reset modal for future use
        $('#taskNameModal .modal-body').show();
        $('#taskNameModal #confirmTaskName').prop('disabled', false);
        
        // Call the generate function with the task name
        generateDistribution(taskName);
    });

    // Changes metadata display
    $('#analysisType').on('change', function(){
        const analysisType = $(this).val();
        if (analysisType === 'cohort') {
            $('#metadataCard').show();  
        } else {
            $('#metadataCard').hide();  
        }
    });

    // Open in new window button
    $('#downloadPngBtn').on('click', function() {
        const filePath = $(this).attr('data-filepath');
        if (!filePath) return;
        window.open(filePath, '_blank');
    });
    
    // Download HTML button
    $('#downloadHtmlBtn').on('click', function() {
        const filePath = $(this).attr('data-filepath');
        if (!filePath) return;
        
        // Create a link to download the file
        const link = document.createElement('a');
        link.href = filePath;
        link.download = `dist_${$('#scoreType').val()}_${new Date().toISOString().slice(0, 10)}.html`;
        link.click();
    });

    ////////// GENERAL FUNCTIONS //////////
    function showAlert(message, type) {
        const alert = '<div class="alert alert-' + type + ' alert-dismissible fade show" role="alert">' +
            message +
            '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>' +
            '</div>';
        $('#alertContainer').html(alert);
    }
    
    // Function to add appropriate placeholder based on the page
    function addPlaceholder() {
        $('#distributionContainer').append(`
            <div id="plotPlaceholder" class="d-flex justify-content-center align-items-center h-100">
            <div class="text-center p-4">
                <i class="fas fa-chart-bar fa-3x text-muted mb-3"></i>
                <p class="text-muted">Select cohorts or PGS IDs, choose a chart type, and generate a distribution plot to visualize the data.</p>
            </div>
            </div>
        `);
    }
    
    // Function to display loading state
    function showLoadingState() {
        $('#loadingSpinner').show();
        $('#distributionContainer').hide();  
        if($('#plotPlaceholder').length > 0) {
            $('#plotPlaceholder').remove();
        }
        $('#alertContainer').empty();
        
        // Show a loading message
        showAlert('Loading visualization...', 'info');
    }

    ////////// PGS FUNCTIONS //////////
    // Loads PGS metadata 
    async function loadMetadata(pgsId) {
        try {
            // Show loading indicator
            $('#metadataDisplay').html('<div class="text-center"><div class="spinner-border text-primary" role="status"></div><p>Loading metadata...</p></div>');
            $('#metadataCard').show();
            
            // Fetch metadata
            let response = await fetch(`/api/metadata/${pgsId}`);
            let data = await response.json();
            
            if (!data.metadata) {
                $('#metadataDisplay').html('<div class="alert alert-warning">No metadata available for this PGS ID.</div>');
                return;
            }
            
            // Create a nicely formatted table
            let table = $('<table class="table table-striped table-hover"></table>');
            let tbody = $('<tbody></tbody>');
            
            // Sort keys for consistent display
            const sortedKeys = Object.keys(data.metadata).sort();
            
            sortedKeys.forEach(key => {
                const value = data.metadata[key];
                // Skip null or empty values
                if (value === null || value === "") return;
                
                // Format the key name for display (convert from snake_case to Title Case)
                const formattedKey = key
                    .split('_')
                    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                    .join(' ');
                
                // Create the row
                let row = $('<tr></tr>');
                row.append($('<td class="fw-bold" style="width: 30%"></td>').text(formattedKey));
                
                // Format value based on type (boolean, array, etc.)
                let cellValue = value;
                if (typeof value === 'boolean') {
                    cellValue = value ? 'Yes' : 'No';
                } else if (Array.isArray(value)) {
                    cellValue = value.join(', ');
                }
                
                row.append($('<td></td>').text(cellValue));
                tbody.append(row);
            });
            
            table.append(tbody);
            $('#metadataDisplay').empty().append(table);
        } catch (error) {
            console.error("Error loading metadata:", error);
            $('#metadataDisplay').html('<div class="alert alert-danger">Failed to load metadata. Please try again later.</div>');
        }
    }

    // Add PGS IDs from textarea
    function addPgsIds() {
        const pgsIdsText = $('#pgsIdsInput').val().trim();
        if (!pgsIdsText) {
            showAlert('Please enter at least one PGS ID', 'warning');
            return;
        }
        
        const pgsIds = pgsIdsText.split('\n').map(id => id.trim()).filter(id => id);
        if (pgsIds.length === 0) {
            showAlert('Please enter valid PGS IDs', 'warning');
            return;
        }
        
        // Process each PGS ID
        processPgsIds(pgsIds);
    }

    // Process PGS ids
    async function processPgsIds(pgsIds) {
        // Show loading indicator
        $('#pgsListStatus').show();
        $('#pgsListStatus').html('<div class="text-center"><div class="spinner-border text-primary" role="status"></div><p>Validating PGS IDs...</p></div>');
        
        const validPgsIds = [];
        const invalidPgsIds = [];
        
        // Check each PGS ID
        for (const pgsId of pgsIds) {
            try {
                const response = await fetch(`/api/score_types/${pgsId}`);
                if (!response.ok) {
                    invalidPgsIds.push(pgsId);
                    continue;
                }
                
                const data = await response.json();
                if (!data.score_types || data.score_types.length === 0) {
                    invalidPgsIds.push(pgsId);
                    continue;
                }
                
                validPgsIds.push({
                    id: pgsId,
                    scoreTypes: data.score_types
                });
            } catch (error) {
                console.error(`Error validating PGS ID ${pgsId}:`, error);
                invalidPgsIds.push(pgsId);
            }
        }
        
        // Add valid PGS IDs
        if (validPgsIds.length > 0) {
            addValidPgsIds(validPgsIds);
        }
        
        // Show results
        if (invalidPgsIds.length > 0) {
            showAlert(`Added ${validPgsIds.length} PGS IDs. ${invalidPgsIds.length} invalid IDs: ${invalidPgsIds.join(', ')}`, 'warning');
            $('#pgsListStatus').html(`<div class="alert alert-danger">Invalid PGS IDs found: ${invalidPgsIds.join(', ')}</div>`);
        } else {
            showAlert(`Added ${validPgsIds.length} PGS IDs successfully`, 'success');
            $('#pgsListStatus').html('');
            $('#pgsListStatus').hide();
            

        }
        
        // Clear input
        $('#pgsIdsInput').val('');
        
        // Update score types dropdown
        updateScoreTypesForPgs();
        updatePgsCounter();
    }

    // Add valid PGS IDs to the UI and array
    function addValidPgsIds(validPgsIds) {
        const pgsList = $('#pgsList');
        
        // Clear "No PGS IDs" message if it's the first PGS
        if (pgsScores.length === 0) {
            pgsList.empty();
        }
        
        validPgsIds.forEach((pgs, index) => {
            const pgsId = pgs.id;
            const color = PRESET_COLORS[pgsScores.length % PRESET_COLORS.length];
            
            // Create UI element
            const pgsRow = $(`
                <div class="cohort-row" data-pgs-id="${pgsId}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <span class="badge rounded-pill me-2" style="background-color: ${color};">&nbsp;</span>
                            <strong>${pgsId}</strong>
                        </div>
                        <div>
                            <i class="fas fa-times delete-pgs" data-pgs-id="${pgsId}"></i>
                        </div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <small class="text-muted">${pgs.scoreTypes.length} score types</small>
                        <div class="form-check form-switch">
                            <input class="form-check-input pgs-toggle" type="checkbox" id="pgsActive${pgsScores.length}" data-pgs-id="${pgsId}" checked>
                            <label class="form-check-label" for="pgsActive${pgsScores.length}">Active</label>
                        </div>
                    </div>
                </div>
            `);
            
            // Add to UI
            pgsList.append(pgsRow);
            
            // Add to array
            pgsScores.push({
                id: pgsId,
                color: color,
                scoreTypes: pgs.scoreTypes,
                active: true
            });

            pgsRow.find('.delete-pgs').on('click', function() {
                deletePgs(pgsId);
            });
            
            pgsRow.find('.pgs-toggle').on('change', function() {
                const isActive = $(this).prop('checked');
                togglePgs(pgsId, isActive);
            });
        });
    }

    // Function to delete a PGS ID
    function deletePgs(pgsId) {
        $(`.cohort-row[data-pgs-id="${pgsId}"]`).remove();
        
        // Remove from array
        pgsScores = pgsScores.filter(p => p.id !== pgsId);
        
        // Show "no PGS" message if no PGS left
        if (pgsScores.length === 0) {
            $('#pgsList').html('<div class="text-center text-muted py-3" id="noPgs">No PGS IDs added yet</div>');
        }
        
        // Update score types dropdown
        updateScoreTypesForPgs();
        updatePgsCounter();
        showAlert('PGS ID removed', 'info');
    }

    // Function to toggle PGS active state
    function togglePgs(pgsId, isActive) {
        const pgs = pgsScores.find(p => p.id === pgsId);
        if (pgs) {
            pgs.active = isActive;
        }
    }

    // Updates the common score types across PGS IDs
    function updateScoreTypesForPgs() {
        const scoreTypeSelect = $('#scoreTypeForPgs');
        scoreTypeSelect.empty();
        
        if (pgsScores.length === 0) {
            scoreTypeSelect.append('<option value="" selected disabled>Select Score Type</option>');
            return;
        }
        
        // Find common score types across all PGS IDs
        let commonScoreTypes = [...pgsScores[0].scoreTypes];
        
        for (let i = 1; i < pgsScores.length; i++) {
            commonScoreTypes = commonScoreTypes.filter(scoreType => 
                pgsScores[i].scoreTypes.includes(scoreType)
            );
        }
        
        if (commonScoreTypes.length === 0) {
            scoreTypeSelect.append('<option value="" selected disabled>No common score types</option>');
            return;
        }
        
        scoreTypeSelect.append('<option value="" selected disabled>Select Score Type</option>');
        
        commonScoreTypes.forEach(scoreType => {
            scoreTypeSelect.append(`<option value="${scoreType}">${scoreType}</option>`);
        });
    }

    // Gets list of all PGS
    function fetchPgsList() {
        $.get('/api/pgs_and_trait_list', function(data) {
            const pgsSelect = $('#pgsId');
            pgsSelect.empty();
            pgsSelect.append('<option value="" selected disabled>Select PGS</option>');
            
            data.pgs.forEach(function(pgs) {
                // Display format: "PGS000001 - Height"
                const displayText = `${pgs.id} - ${pgs.trait}`;
                pgsSelect.append(`<option value="${pgs.id}">${displayText}</option>`);
            });
        }).fail(function() {
            showAlert('Failed to load PGS list', 'danger');
        });
    }

    
    // Gets score types for a single PGS ID
    function fetchScoreTypes(pgsId) {
        $.get(`/api/score_types/${pgsId}`, function(data) {
            const scoreSelect = $('#scoreType');
            scoreSelect.empty();
            scoreSelect.append('<option value="" selected disabled>Select Score Type</option>');
            
            data.score_types.forEach(function(scoreType) {
                scoreSelect.append(`<option value="${scoreType}">${scoreType}</option>`);
            });
        }).fail(function() {
            showAlert('Failed to load score types', 'danger');
        });
    }
    
    // Updates total number of PGS
    function updatePgsCounter() {
        $('#pgsCounter').text(`(${pgsScores.length})`);
    }

    ////////// COHORT FUNCTIONS //////////
    // Calls backend to pull stored permanent cohorts
    function loadPermanentCohorts() {
        $.ajax({
            url: '/api/permanent_cohorts',
            type: 'GET',
            success: function(data) {
                if (data.cohorts && data.cohorts.length > 0) {
                    // Populate cohorts for regular cohort management
                    data.cohorts.forEach(function(cohort, index) {
                        const color = PRESET_COLORS[index % PRESET_COLORS.length];
                        addPermanentCohort(cohort.name, cohort.id, cohort.sample_id_count, color);
                    });
                    
                    // Populate cohort dropdown for PGS comparison mode
                    const cohortSelect = $('#cohortForConfig');
                    cohortSelect.empty();
                    cohortSelect.append('<option value="" selected disabled>Select Cohort</option>');
                    
                    data.cohorts.forEach(function(cohort) {
                        cohortSelect.append(`<option value="${cohort.id}" data-samples="${cohort.sample_id_count}">${cohort.name} (${cohort.sample_id_count} samples)</option>`);
                    });
                    
                    // Hide "no cohorts" message since we have permanent cohorts
                    $('#noCohorts').hide();
                }
            },
            error: function(xhr) {
                console.log('No permanent cohorts available or error loading them:', xhr.status);
            }
        });
    }
    
    // Adds permanent cohort items
    function addPermanentCohort(name, cohort_id, sample_id_count, color) {
        const cohortId = cohorts.length + 1;
        
        // Create cohort entry
        const cohortItem = createCohortItem(cohortId, name, cohort_id, color, sample_id_count, true);
        $('#cohortsList').append(cohortItem);
        
        // Add to cohorts array
        cohorts.push({
            id: cohortId,
            name: name,
            color: color,
            sample_id_count: sample_id_count,
            cohort_id: cohort_id,
            active: true,
            permanent: true
        });
    }

    // // Adds page-specific cohort 
    // function addCohort() {
    //     const cohortName = $('#cohortName').val() || `Cohort ${cohorts.length + 1}`;
    //     const cohortColor = $('#cohortColor').val();
    //     const sampleIdsText = $('#sampleIdsInput').val().trim();
        
    //     if (!sampleIdsText) {
    //         showAlert('Please enter at least one sample ID', 'warning');
    //         return;
    //     }
        
    //     const sampleIds = sampleIdsText.split('\n').map(id => id.trim()).filter(id => id);
        
    //     if (sampleIds.length === 0) {
    //         showAlert('Please enter valid sample IDs', 'warning');
    //         return;
    //     }
        
    //     const cohortId = cohorts.length + 1;
        
    //     // Create cohort entry
    //     const cohortItem = createCohortItem(cohortId, cohortName, cohortColor, sampleIds, false);
    //     $('#cohortsList').append(cohortItem);
        
    //     // Hide "no cohorts" message if visible
    //     $('#noCohorts').hide();
        
    //     // Add to cohorts array
    //     cohorts.push({
    //         id: cohortId,
    //         name: cohortName,
    //         color: cohortColor,
    //         sampleIds: sampleIds,
    //         active: true,
    //         permanent: false
    //     });
        
    //     // Reset inputs
    //     $('#cohortName').val('');
    //     $('#sampleIdsInput').val('');
    //     $('#cohortColor').val(PRESET_COLORS[cohortId % PRESET_COLORS.length]);
    //     $('#colorPreview').css('background-color', $('#cohortColor').val());
        
    //     showAlert(`Added cohort "${cohortName}" with ${sampleIds.length} samples`, 'success');
    // }
    
    // Stores page-specific cohort information
    function createCohortItem(id, name, cohort_id, color, sample_id_count, isPermanent) {
        const cohortDiv = document.createElement('div');
        cohortDiv.className = 'cohort-row';
        cohortDiv.dataset.cohortId = id;
        
        let html = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <div>
                    <span class="badge rounded-pill me-2" style="background-color: ${color};">&nbsp;</span>
                    <strong>${name}</strong>
                </div>
                <div>
        `;
        
        if (!isPermanent) {
            html += `<i class="fas fa-times delete-cohort" data-cohort-id="${id}"></i>`;
        }
        
        html += `
                </div>
            </div>
            <div class="d-flex justify-content-between align-items-center">
                <small class="text-muted">${sample_id_count} samples</small>
                <div class="form-check form-switch">
                    <input class="form-check-input cohort-toggle" type="checkbox" id="cohortActive${id}" data-cohort-id="${id}" checked>
                    <label class="form-check-label" for="cohortActive${id}">Active</label>
                </div>
            </div>
        `;
        
        cohortDiv.innerHTML = html;
        
        // Add event listeners
        $(cohortDiv).find('.delete-cohort').on('click', function() {
            const cohortId = parseInt($(this).data('cohort-id'));
            deleteCohort(cohortId);
        });
        
        $(cohortDiv).find('.cohort-toggle').on('change', function() {
            const cohortId = parseInt($(this).data('cohort-id'));
            const isActive = $(this).prop('checked');
            toggleCohort(cohortId, isActive);
        });
        
        return cohortDiv;
    }
    
    // Removes page-specific cohort
    function deleteCohort(cohortId) {
        // Remove from DOM
        $(`.cohort-row[data-cohort-id="${cohortId}"]`).remove();
        
        // Remove from array
        cohorts = cohorts.filter(c => c.id !== cohortId);
        
        // Show "no cohorts" message if no cohorts left
        if (cohorts.length === 0) {
            $('#noCohorts').show();
        }
        
        showAlert('Cohort removed', 'info');
    }
    
    // Toggles page-specific cohort
    function toggleCohort(cohortId, isActive) {
        // Update in array
        const cohort = cohorts.find(c => c.id === cohortId);
        if (cohort) {
            cohort.active = isActive;
        }
    }

    ////////// TASK FUNCTIONS //////////
    // Submits distribution job to backend 
    function generateDistribution(taskName = '') {
        const analysisType = $('#analysisType').val();
        const chartType = $('input[name="chartType"]:checked').val();
        const defPlotTitle = chartType === 'density' ? 'Density Plot' : 
                        (chartType === 'histogram' ? 'Histogram' : 'Box Plot');
        
        // Show loading spinner
        $('#plotPlaceholder').remove();
        $('#plotSvg').hide();
        $('#loadingSpinner').show();
        $('#distributionContainer').find('iframe').remove(); // Remove any existing iframe

        // Update plot title
        var plotTitle = $('#plotTitle').val()
        if (plotTitle=="") {
            $('#plotTitle').text(defPlotTitle);
            plotTitle = $('#plotTitle').val()
        }
        if (analysisType === 'cohort') {
            // Get vars and validate
            const pgsId = $('#pgsId').val();
            const scoreType = $('#scoreType').val();
            const activeCohorts = cohorts.filter(c => c.active);

            if (!pgsId) {
                showAlert('Please select a PGS ID', 'warning');
                return;
            }
            if (!scoreType) {
                showAlert('Please select a Score Type', 'warning');
                return;
            }
            if (activeCohorts.length === 0) {
                showAlert('Please add at least one active cohort', 'warning');
                return;
            }

            // Prepare request data for the new endpoint
            const requestData = {
                analysis_type: 'cohort',
                chart_type: chartType,
                plot_title: plotTitle,
                score_type: scoreType,
                pgs_id: pgsId,
                cohorts: cohorts
                    .filter(c => c.active)
                    .map(c => ({
                        color: c.color,
                        name: c.name,
                        id: c.cohort_id
                    })),
                name: taskName // Add task name
            };
            
            // Send API request to the new endpoint
            $.ajax({
                url: '/api/generate_distribution',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(requestData),
                success: function(response) {

                    // Check if we received a task ID (background task) or direct file path
                    if (response.task_id) {
                        const taskId = response.task_id;
                        showAlert(`Distribution plot generation started (Task ID: ${taskId}). You'll be notified when it's ready.`, 'info');
                        
                        // Start polling for task status
                        pollTaskStatus(taskId, 'distribution');
                    } else if (response.plot_path) {
                        // Handle as before
                        $('#loadingSpinner').hide();
                        
                        // Enable download button
                        $('#downloadPngBtn').prop('disabled', false).attr('data-filepath', response.plot_path);
                        $('#downloadHtmlBtn').prop('disabled', false).attr('data-filepath', response.plot_path);
                        
                        // Create iframe to display the Plotly HTML
                        const iframe = $('<iframe>')
                            .attr('src', response.plot_path)
                            .attr('width', '100%')
                            .attr('height', '600px')
                            .attr('frameBorder', '0')
                            .attr('scrolling', 'no');
                        
                        $('#distributionContainer').append(iframe);

                        // Store the data
                        sampleData = response.data.cohorts;
                        populateSampleTable(sampleData);
                        
                        showAlert('Distribution plot generated successfully.', 'success');
                    } else {
                        // Unexpected response format
                        $('#loadingSpinner').hide();
                        showAlert('Error: Invalid response from server', 'danger');
                    }
                },
                error: function(xhr) {
                    $('#loadingSpinner').hide();
                    $('#plotPlaceholder').show();
                    
                    try {
                        console.log(xhr);
                        const response = JSON.parse(xhr.responseText);
                        showAlert(response.detail || 'Error generating plot', 'danger');
                    } catch (e) {
                        showAlert('Error generating plot. Please try again.', 'danger');
                    }
                }
            });
        } else {
            const cohortId = $('#cohortForConfig').val();
            const scoreType = $('#scoreTypeForPgs').val();
            
            // Validation
            if (!cohortId) {
                showAlert('Please select a cohort', 'warning');
                return;
            }
            
            if (!scoreType) {
                showAlert('Please select a Score Type', 'warning');
                return;
            }
            const activePgsIds = pgsScores.filter(p => p.active);
            console.log(pgsScores)
            if (activePgsIds.length === 0) {
                showAlert('Please add at least one active PGS ID', 'warning');
                return;
            }

            // Fetch cohort data first
            $.ajax({
                url: '/api/permanent_cohorts',
                type: 'GET',
                success: function(cohortsData) {
                    const selectedCohort = cohortsData.cohorts.find(c => c.id === cohortId);
                
                    if (!selectedCohort) {
                        showAlert('Selected cohort not found', 'danger');
                        $('#loadingSpinner').hide();
                        $('#plotPlaceholder').show();
                        return;
                    }
                    
                    // Prepare request data for PGS comparison
                    const requestData = {
                        analysis_type: 'score',
                        chart_type: chartType,
                        plot_title: plotTitle,
                        score_type: scoreType,
                        cohort_id: selectedCohort.id,
                        pgs_comparison: {
                            pgs_ids: activePgsIds.map(p => p.id),
                            colors: activePgsIds.map(p => p.color),
                            names: activePgsIds.map(p => p.id)
                        },
                        name: taskName // Add task name
                    };
                    console.log(requestData);
                    
                    // Send API request to the endpoint
                    $.ajax({
                        url: '/api/generate_distribution',
                        type: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify(requestData),
                        success: function(response) {
                            // Check if we received a task ID or direct response
                            if (response.task_id) {
                                // New background task system
                                const taskId = response.task_id;
                                
                                // Show task info in the alert
                                showAlert(`Distribution plot generation started (Task ID: ${taskId}). You'll be notified when it's ready.`, 'info');
                                
                                // Start polling for task status
                                pollTaskStatus(taskId, 'distribution');
                            } else if (response.plot_path) {
                                // Hide loading spinner
                                $('#loadingSpinner').hide();
                                
                                // Enable download button
                                $('#downloadPngBtn').prop('disabled', false).attr('data-filepath', response.plot_path);
                                $('#downloadHtmlBtn').prop('disabled', false).attr('data-filepath', response.plot_path);
                                
                                // Create iframe to display the Plotly HTML
                                const iframe = $('<iframe>')
                                    .attr('src', response.plot_path)
                                    .attr('width', '100%')
                                    .attr('height', '600px')
                                    .attr('frameBorder', '0')
                                    .attr('scrolling', 'no');
                                
                                $('#distributionContainer').append(iframe);

                                // Store the data
                                sampleData = response.data.pgs_data;
                                populateSampleTable(sampleData);
                                
                                showAlert('Distribution plot generated successfully.', 'success');
                            } else {
                                // Unexpected response format
                                $('#loadingSpinner').hide();
                                showAlert('Error: Invalid response from server', 'danger');
                            }
                        },
                        error: function(xhr) {
                            $('#loadingSpinner').hide();
                            $('#plotPlaceholder').show();
                            
                            try {
                                const response = JSON.parse(xhr.responseText);
                                showAlert(response.detail || 'Error generating plot', 'danger');
                            } catch (e) {
                                showAlert('Error generating plot. Please try again.', 'danger');
                            }
                        }
                    });
                },
                error: function() {
                    $('#loadingSpinner').hide();
                    $('#plotPlaceholder').show();
                    showAlert('Error retrieving cohort data', 'danger');
                }
            });
        }
    }

    // Checks task status
    function pollTaskStatus(taskId, taskType) {
        // Create a status area if it doesn't exist
        if ($('#taskStatusArea').length === 0) {
            $('body').append(`
                <div id="taskStatusArea" class="position-fixed bottom-0 end-0 p-3" style="z-index: 5">
                    <div class="toast show" role="alert" aria-live="assertive" aria-atomic="true">
                        <div class="toast-header">
                            <strong class="me-auto">Task Status: <span id="taskStatusLabel">Processing</span></strong>
                            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                        </div>
                        <div class="toast-body">
                            <div class="d-flex align-items-center mb-2">
                                <div class="spinner-border spinner-border-sm text-primary me-2" id="taskSpinner" role="status">
                                    <span class="visually-hidden">Processing...</span>
                                </div>
                                <div>Task ID: <span id="taskIdLabel">${taskId}</span></div>
                            </div>
                            <div class="progress" style="height: 5px;">
                                <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 100%"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `);
        } else {
            // Update existing status area
            $('#taskIdLabel').text(taskId);
            $('#taskStatusLabel').text('Processing');
            $('#taskSpinner').show();
            $('.progress-bar').addClass('progress-bar-animated').css('width', '100%');
            $('.toast').toast('show');
        }
        
        const checkStatus = function() {
            const currentTimeInMilliseconds = Date.now();
            $.ajax({
                url: `/api/task_status/${taskId}?${currentTimeInMilliseconds}`,
                type: 'GET',
                success: function(response) {
                    // Update status display
                    $('#taskStatusLabel').text(response.status.charAt(0).toUpperCase() + response.status.slice(1));
                    
                    if (response.status === 'completed') {
                        // Task is complete, stop spinner and update progress
                        $('#taskSpinner').hide();
                        $('.progress-bar').removeClass('progress-bar-animated').css('width', '100%');
                        
                        // Show success message
                        showAlert(`${taskType.charAt(0).toUpperCase() + taskType.slice(1)} generated successfully!`, 'success');
                        
                        // Hide the loading spinner
                        $('#loadingSpinner').hide();
                        
                        if (taskType === 'distribution') {
                            // console.log(response)

                            // Create iframe to display the Plotly HTML
                            const iframe = $('<iframe>')
                                .attr('src', response.result_path)
                                .attr('width', '100%')
                                .attr('height', '600px')
                                .attr('frameBorder', '0')
                                .attr('scrolling', 'no');
                            
                            $('#distributionContainer').append(iframe);
                            
                            // Enable download buttons
                            $('#downloadPngBtn').prop('disabled', false).attr('data-filepath', response.result_path);
                            $('#downloadHtmlBtn').prop('disabled', false).attr('data-filepath', response.result_path);

                        } else {
                            // Load the visualization for other plot types
                            const iframe = `<iframe src="${response.result_path}" style="width:100%; height:800px; border:none;"></iframe>`;
                            $('#heatmapPlot').html(iframe).show();
                            
                            // Enable download buttons
                            $('#downloadPngBtn').prop('disabled', false).attr('data-filepath', response.result_path);
                            $('#downloadHtmlBtn').prop('disabled', false).attr('data-filepath', response.result_path);
                            $('#generateInteractive').prop('disabled', false).attr('data-filepath', response.result_path).attr('plot-type', taskType);
                        }
                        
                        // Auto-dismiss the status toast after 5 seconds
                        setTimeout(() => {
                            $('.toast').toast('hide');
                        }, 5000);
                        
                    } else if (response.status === 'failed') {
                        // Task failed
                        $('#taskSpinner').hide();
                        $('.progress-bar').removeClass('progress-bar-animated').addClass('bg-danger').css('width', '100%');
                        $('#taskStatusLabel').text('Failed');
                        
                        // Show error message
                        showAlert(`Error generating ${taskType}: ${response.error || 'Unknown error'}`, 'danger');
                        
                        // Hide loading spinner
                        $('#loadingSpinner').hide();
                        
                        if (taskType === 'distribution') {
                            // Show placeholder for distribution
                            $('#plotPlaceholder').show();
                        } else {
                            // Restore placeholder for other visualizations
                            if($('#plotPlaceholder').length === 0) {
                                $('#heatmapContainer').append(`
                                    <div id="plotPlaceholder" class="d-flex justify-content-center align-items-center h-100">
                                        <div class="text-center p-4">
                                            <i class="fas fa-chart-area fa-3x text-muted mb-3"></i>
                                            <p class="text-muted">Select parameters and try again.</p>
                                        </div>
                                    </div>
                                `);
                            }
                            $('#plotPlaceholder').show();
                        }
                        
                    } else {
                        // Task is still processing, check again in 2 seconds
                        setTimeout(checkStatus, 2000);
                    }
                },
                error: function(xhr, status, error) {
                    // Handle error
                    console.error("Error checking task status:", status, error);
                    // Try again after a delay
                    setTimeout(checkStatus, 5000);
                }
            });
        };
        
        // Start checking status
        checkStatus();
    }

    // Function to load and display task data
    function loadTaskData(taskId) {
        const currentTimeInMilliseconds = Date.now();
        $.ajax({
            url: `/api/task_status/${taskId}?${currentTimeInMilliseconds}`,
            type: 'GET',
            success: function(task) {
            if (task.status === 'completed' && task.result_path) {
                // Display the completed visualization
                $('#loadingSpinner').hide();
                
                // Create an iframe to display the result
                const iframe = `<iframe src="${task.result_path}" style="width:100%; height:800px; border:none;"></iframe>`;
                $('#distributionContainer').html(iframe).show();  
                
                // Enable download buttons
                $('#downloadPngBtn').prop('disabled', false).attr('data-filepath', task.result_path);
                $('#downloadHtmlBtn').prop('disabled', false).attr('data-filepath', task.result_path);
                $('#generateInteractive').prop('disabled', false).attr('data-filepath', task.result_path);
                
                // Show success message
                const taskName = task.name || `${task.task_type.charAt(0).toUpperCase() + task.task_type.slice(1)}`;
                showAlert(`${taskName} visualization loaded successfully.`, 'success');
                
            } else if (task.status === 'processing' || task.status === 'queued') {
                // Task is still processing, show status and set up polling
                showAlert(`Visualization is still being generated (${task.status})...`, 'info');
                
                // Poll for updates
                setTimeout(function() {
                loadTaskData(taskId);
                }, 5000);
                
            } else {
                // Task failed
                $('#loadingSpinner').hide();
                
                // Show error message
                showAlert(`Error generating visualization: ${task.error || 'Unknown error'}`, 'danger');
                
                // Restore placeholder if needed
                if($('#plotPlaceholder').length === 0) {
                // Add placeholder appropriate for current page
                addPlaceholder();
                }
                $('#plotPlaceholder').show();
            }
            },
            error: function(xhr, status, error) {
            $('#loadingSpinner').hide();
            
            console.error("Error loading task:", status, error);
            showAlert('Error loading visualization. Please try again.', 'danger');
            
            // Restore placeholder
            if($('#plotPlaceholder').length === 0) {
                addPlaceholder();
            }
            $('#plotPlaceholder').show();
            }
        });
    }
});