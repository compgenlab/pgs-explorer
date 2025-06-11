$(document).ready(function() {
    // First check if we are loading previous image
    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('task_id');
    
    if (taskId) {
        console.log(taskId)
        // Show loading indicator
        showLoadingState();
        // Load task data
        loadTaskData(taskId);
    }

    // State variables
    let subcohorts = [];
    let baseData = null;
    let tableData = [];
    let originalTableData = []; 
    let currentSvg = null;
    let currentXScale = null;
    let currentMargin = null;
    let currentHeight = null;

    // Initialize color picker
    $('#subcohortColor').on('input', function() {
        $('#colorPreview').css('background-color', $(this).val());
    });
    
    // Fetch PGS list
    $.get('/api/pgs_list', function(data) {
        const pgsSelect = $('#pgsId');
        pgsSelect.empty();
        pgsSelect.append('<option value="" selected disabled>Select PGS ID</option>');
        
        data.pgs.forEach(function(pgsId) {
            pgsSelect.append(`<option value="${pgsId}">${pgsId}</option>`);
        });
    }).fail(function() {
        showAlert('Failed to load PGS list', 'danger');
    });
    
    // Load cohorts
    $.get('/api/permanent_cohorts', function(data) {
        const cohortSelect = $('#baseCohort');
        
        data.cohorts.forEach(function(cohort) {
            cohortSelect.append(`<option value="${cohort.name}">${cohort.name} (${cohort.sample_ids.length} samples)</option>`);
        });
    }).fail(function() {
        showAlert('Failed to load cohorts', 'danger');
    });
    
    // Handle PGS selection change
    $('#pgsId').on('change', function() {
        const pgsId = $(this).val();
        if (pgsId) {
            fetchScoreTypes(pgsId);
        }
    });
    
    // Initialize threshold type change handler
    $('#thresholdType').on('change', function() {
        const thresholdType = $(this).val();
        if (thresholdType === 'percentile') {
            $('#thresholdHint').text('Enter percentile (0-100)');
        } else {
            $('#thresholdHint').text('Enter score value');
        }
    });
    
    // Add subcohort button handler
    $('#addSubcohortBtn').on('click', function() {
        addSubcohort();
    });
    
    // Generate button handler
    $('#generateButton').on('click', function() {
        // Show the task name modal
        const taskNameModal = new bootstrap.Modal(document.getElementById('taskNameModal'));
        taskNameModal.show();
    });

    // Handle the confirm button click
    $('#confirmTaskName').on('click', function() {
        // Get the task name
        const taskName = $('#taskName').val().trim();
        
        // Hide the modal
        const taskNameModal = bootstrap.Modal.getInstance(document.getElementById('taskNameModal'));
        if (taskNameModal) {
            taskNameModal.hide();
        }
        
        // Reset modal for next use
        $('#taskNameModal .modal-body').show();
        $('#taskNameModal #confirmTaskName').prop('disabled', false);
        
        // Call the generate function with the task name
        generatePlot(taskName);
    });

    // Apply percentile filter button handler
    $('#applyFilterBtn').on('click', function() {
        applyPercentileFilter();
    });
    
    // Download SVG button handler
    $('#downloadSvgBtn').on('click', function() {
        downloadPlotAsSvg();
    });
    
    // Download table button handler
    $('#downloadTableBtn').on('click', function() {
        downloadTableAsCsv();
    });
    
    // Show/hide OR options when checkbox is toggled
    $('#displayOR').change(function() {
        if(this.checked) {
            $('#orOptionsContainer').show();
        } else {
            $('#orOptionsContainer').hide();
        }
    });
    
    // Show/hide specific OR calculation options based on radio selection
    $('input[name="orCalculationType"]').change(function() {
        // Hide all option sets first
        $('.orBinOptions, .orQuantileOptions, .orThresholdOptions, .orDecileBaselineOptions, .orDecileCumulativeOptions').hide();
        
        // Show the selected option set
        if ($('#orByBin').is(':checked')) {
            $('.orBinOptions').show();
        } else if ($('#orByQuantile').is(':checked')) {
            $('.orQuantileOptions').show();
        } else if ($('#orByThreshold').is(':checked')) {
            $('.orThresholdOptions').show();
        } else if ($('#orByDecileBaseline').is(':checked')) {
            $('.orDecileBaselineOptions').show();
        } else if ($('#orByDecileCumulative').is(':checked')) {
            $('.orDecileCumulativeOptions').show();
        }
    });
    $('input[name="orCalculationType"]:checked').change();
    
    // Function to add a subcohort
    function addSubcohort() {
        const name = $('#subcohortName').val().trim();
        const color = $('#subcohortColor').val();
        const sampleIdsText = $('#sampleIdsInput').val().trim();
        
        if (!name) {
            showAlert('Please enter a name for the subcohort', 'warning');
            return;
        }
        
        if (!sampleIdsText) {
            showAlert('Please enter at least one sample ID', 'warning');
            return;
        }
        
        const sampleIds = sampleIdsText.split('\n').map(id => id.trim()).filter(id => id);
        
        if (sampleIds.length === 0) {
            showAlert('Please enter valid sample IDs', 'warning');
            return;
        }
        
        // Check for duplicate subcohort name
        if (subcohorts.some(sc => sc.name === name)) {
            showAlert(`A subcohort with name "${name}" already exists`, 'warning');
            return;
        }
        
        // Add to subcohorts array
        subcohorts.push({
            name: name,
            color: color,
            sampleIds: sampleIds,
            active: true
        });
        
        // Update UI
        updateSubcohortsList();
        
        // Clear input fields
        $('#subcohortName').val('');
        $('#sampleIdsInput').val('');
        
        // Pick next color in preset list
        const presetColors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf'];
        $('#subcohortColor').val(presetColors[subcohorts.length % presetColors.length]);
        $('#colorPreview').css('background-color', $('#subcohortColor').val());
        
        showAlert(`Added subcohort "${name}" with ${sampleIds.length} samples`, 'success');
        updateSubcohortSelects();
    }
    
    // Function to update the subcohorts list UI
    function updateSubcohortsList() {
        const subcohortsList = $('#subcohortsList');
        subcohortsList.empty();
        
        if (subcohorts.length === 0) {
            subcohortsList.html('<div class="text-center text-muted py-3" id="noSubcohorts">No subcohorts added yet</div>');
            return;
        }
        
        subcohorts.forEach((subcohort, index) => {
            const subcohortRow = $(`
                <div class="subcohort-row" data-subcohort-id="${index}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <span class="color-indicator" style="background-color: ${subcohort.color};"></span>
                            <strong>${subcohort.name}</strong>
                        </div>
                        <div>
                            <div class="form-check form-switch d-inline-block me-2">
                                <input class="form-check-input subcohort-toggle" type="checkbox" 
                                    id="subcohort-${index}" data-subcohort-id="${index}" ${subcohort.active ? 'checked' : ''}>
                            </div>
                            <i class="fas fa-times delete-subcohort" data-subcohort-id="${index}" 
                               style="cursor: pointer; color: #dc3545;"></i>
                        </div>
                    </div>
                    <div>
                        <small class="text-muted">${subcohort.sampleIds.length} samples</small>
                    </div>
                </div>
            `);
            
            // Add event listeners
            subcohortRow.find('.subcohort-toggle').on('change', function() {
                const subcohortId = parseInt($(this).data('subcohort-id'));
                subcohorts[subcohortId].active = $(this).prop('checked');
                
                // // If we have data, regenerate the plot
                // if (baseData) {
                //     renderPlot();
                // }
            });
            
            subcohortRow.find('.delete-subcohort').on('click', function() {
                const subcohortId = parseInt($(this).data('subcohort-id'));
                deleteSubcohort(subcohortId);
            });
            
            subcohortsList.append(subcohortRow);
        });
    }
    
    // Function to delete a subcohort
    function deleteSubcohort(subcohortId) {
        subcohorts.splice(subcohortId, 1);
        updateSubcohortsList();
        
        // // If we have data, regenerate the plot
        // if (baseData) {
        //     renderPlot();
        // }
        
        showAlert('Subcohort removed', 'info');
        updateSubcohortSelects();
    }
    
    // Function to generate the plot using the backend
    function generatePlot(taskName = '') {
        const pgsId = $('#pgsId').val();
        const scoreType = $('#scoreType').val();
        const baseCohort = $('#baseCohort').val();
        
        // Validation
        if (!pgsId) {
            showAlert('Please select a PGS ID', 'warning');
            return;
        }
        
        if (!scoreType) {
            showAlert('Please select a Score Type', 'warning');
            return;
        }
        
        if (!baseCohort) {
            showAlert('Please select a Base Cohort', 'warning');
            return;
        }
        
        // Get active subcohorts and format them correctly
        const formattedSubcohorts = subcohorts.filter(sc => sc.active).map(sc => ({
            name: sc.name,
            color: sc.color,
            sample_ids: sc.sampleIds,  // Convert camelCase to snake_case
            active: sc.active
        }));
        
        // Show loading spinner
        $('#plotPlaceholder').remove();
        $('#plotSvg').hide();
        $('#plotIframe').remove();
        $('#loadingSpinner').show();
        
        // Prepare request data
        const requestData = {
            pgs_id: pgsId,
            score_type: scoreType,
            base_cohort: baseCohort,
            plot_title: $('#plotTitle').val().trim() || `Distribution of ${pgsId} - ${scoreType}`,
            normalize_bins: $('#normalizeBins').is(':checked'),
            subcohorts: formattedSubcohorts,
            display_or: $('#displayOR').is(':checked'),
            or_calculation_type: getSelectedORCalculationType(),
            bin_size: parseInt($('#binSize').val()) || 30,
            quantile_count: parseInt($('#quantileCount').val()) || 10,
            threshold_value: parseFloat($('#thresholdValue').val()) || 0,
            decile_count: parseInt($('#decileCount').val()) || 10,
            name: taskName // Add task name to the request
        };
        
        console.log("Sending request:", JSON.stringify(requestData, null, 2));
        
        // Make API request
        $.ajax({
            url: '/api/generate_subcohort_plot',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(requestData),
            success: function(response) {
                // Check if we received a task ID (background task) or direct file path
                if (response.task_id) {
                    // We got a task ID - this is the new background task system
                    const taskId = response.task_id;
                    
                    // Show task info in the alert
                    showAlert(`Subcohort plot generation started (Task ID: ${taskId}). You'll be notified when it's ready.`, 'info');
                    
                    // Start polling for task status
                    pollTaskStatus(taskId, 'subcohort_plot');
                } else if (response.plot_url) {
                    // We got a direct response - this is the old immediate response
                    // Handle as before
                    $('#loadingSpinner').hide();
                    
                    // Create iframe to display the plot
                    const iframe = $('<iframe>', {
                        id: 'plotIframe',
                        src: response.plot_url,
                        width: '100%',
                        height: '700px',
                        frameborder: 0
                    });
                    
                    // Add iframe to the container
                    $('#plotContainer').append(iframe);
                    
                    // Enable download buttons
                    $('#downloadSvgBtn').prop('disabled', false);
                    $('#downloadTableBtn').prop('disabled', false);
                    
                    // Update download SVG button to link to the plot URL
                    $('#downloadSvgBtn').off('click').on('click', function() {
                        window.open(response.plot_url, '_blank');
                    });
                    
                    // Update table data
                    tableData = response.table_data;
                    originalTableData = [...tableData]; // Keep a copy for filtering
                    renderPercentileTable(tableData);
                    
                    showAlert('Subcohort plot generated successfully.', 'success');
                } else {
                    // Unexpected response format
                    $('#loadingSpinner').hide();
                    showAlert('Error: Invalid response from server', 'danger');
                }
            },
            error: function(xhr, status, error) {
                $('#loadingSpinner').hide();
                $('#plotPlaceholder').show();
                
                console.error("Error details:", xhr.responseText);
                
                try {
                    const response = JSON.parse(xhr.responseText);
                    showAlert(response.detail || 'Error generating plot', 'danger');
                } catch (e) {
                    showAlert(`Error generating plot: ${status} - ${error}`, 'danger');
                }
            }
        });
    }

    // Extend the pollTaskStatus function to handle subcohort plots
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
            $.ajax({
                url: `/api/task_status/${taskId}`,
                type: 'GET',
                success: function(response) {
                    // Update status display
                    $('#taskStatusLabel').text(response.status.charAt(0).toUpperCase() + response.status.slice(1));
                    
                    if (response.status === 'completed') {
                        // Task is complete, stop spinner and update progress
                        $('#taskSpinner').hide();
                        $('.progress-bar').removeClass('progress-bar-animated').css('width', '100%');
                        
                        // Show success message
                        showAlert(`${taskType === 'subcohort_plot' ? 'Subcohort plot' : taskType.charAt(0).toUpperCase() + taskType.slice(1)} generated successfully!`, 'success');
                        
                        // Hide the loading spinner
                        $('#loadingSpinner').hide();
                        
                        if (taskType === 'subcohort_plot') {
                            // Create iframe to display the plot
                            const iframe = $('<iframe>', {
                                id: 'plotIframe',
                                src: response.result_path,
                                width: '100%',
                                height: '700px',
                                frameborder: 0
                            });
                            
                            // Add iframe to the container
                            $('#plotContainer').append(iframe);
                            
                            // Enable download buttons
                            $('#downloadSvgBtn').prop('disabled', false);
                            $('#downloadTableBtn').prop('disabled', false);
                            
                            // Update download SVG button to link to the plot URL
                            $('#downloadSvgBtn').off('click').on('click', function() {
                                window.open(response.result_path, '_blank');
                            });
                            
                            // Note: We can't update the table data here since the task response 
                            // doesn't include the table_data array. The backend would need to be 
                            // modified to include this data in the task result.
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
                        showAlert(`Error generating ${taskType === 'subcohort_plot' ? 'subcohort plot' : taskType}: ${response.error || 'Unknown error'}`, 'danger');
                        
                        // Hide loading spinner
                        $('#loadingSpinner').hide();
                        
                        // Show placeholder
                        $('#plotPlaceholder').show();
                        
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
    
    // Helper function to get the selected OR calculation type
    function getSelectedORCalculationType() {
        if ($('#orByBin').is(':checked')) {
            return 'bin';
        } else if ($('#orByQuantile').is(':checked')) {
            return 'quantile';
        } else if ($('#orByThreshold').is(':checked')) {
            return 'threshold';
        } else if ($('#orByDecileBaseline').is(':checked')) {
            return 'decileBaseline';
        } else if ($('#orByDecileCumulative').is(':checked')) {
            return 'decileCumulative';
        }
        return null;
    }

    // Function to render percentile table
    function renderPercentileTable(data) {
        if (data.length === 0) {
            $('#percentileTable').html('<div class="text-center text-muted py-3">No subcohort data available</div>');
            return;
        }
        
        const tableHtml = `
            <table class="table table-striped table-hover">
                <thead>
                    <tr>
                        <th data-sort="sample">Sample ID</th>
                        <th data-sort="score">Score</th>
                        <th data-sort="percentile">Percentile</th>
                        <th data-sort="subcohort">Subcohort</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.slice(0, 1000).map(row => `
                    <tr>
                        <td>${row.SAMPLE_ID}</td>
                        <td>${row.SCORE}</td>
                        <td>${row.PERCENTILE}</td>
                        <td>${row.SUBCOHORT}</td>
                    </tr>
                `).join('')}
                </tbody>
            </table>
            <div class="text-muted mt-2">
                Showing ${Math.min(data.length, 1000)} of ${data.length} records
            </div>
        `;
        
        $('#percentileTable').html(tableHtml);
        
        // Add sort functionality
        $('#percentileTable th').on('click', function() {
            const sortKey = $(this).data('sort');
            sortTable(sortKey);
        });
    }

    // Function to apply percentile filter
    function applyPercentileFilter() {
        const percentileValue = parseFloat($('#percentileInput').val());
        const filterType = $('#percentileFilter').val();
        
        if (isNaN(percentileValue) || percentileValue < 0 || percentileValue > 100) {
            showAlert('Please enter a valid percentile value between 0 and 100', 'warning');
            return;
        }
        
        // Filter the data
        const filteredData = originalTableData.filter(row => {
            const rowPercentile = parseFloat(row.PERCENTILE);
            if (filterType === 'above') {
                return rowPercentile >= percentileValue;
            } else {
                return rowPercentile <= percentileValue;
            }
        });
        
        // Update table data and re-render
        tableData = filteredData;
        renderPercentileTable(tableData);
        
        showAlert(`Showing ${filteredData.length} records ${filterType} ${percentileValue}%`, 'info');
    }

    // Function to download table as CSV
    function downloadTableAsCsv() {
        if (tableData.length === 0) {
            showAlert('No data to download', 'warning');
            return;
        }
        
        // Create CSV content
        let csvContent = 'Sample ID,Score,Percentile,Subcohort\n';
        
        tableData.forEach(row => {
            csvContent += `${row.SAMPLE_ID},${row.SCORE},${row.PERCENTILE},${row.SUBCOHORT}\n`;
        });
        
        // Create download link
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = 'subcohort_data.csv';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Clean up
        URL.revokeObjectURL(url);
    }

    // Function to sort table
    function sortTable(sortKey) {
        const sortOrder = $('#percentileTable').data('sort-order') === 'asc' ? 'desc' : 'asc';
        $('#percentileTable').data('sort-order', sortOrder);
        
        // Sort the table data
        tableData.sort((a, b) => {
            let valA, valB;
            
            if (sortKey === 'sample') {
                valA = a.SAMPLE_ID;
                valB = b.SAMPLE_ID;
            } else if (sortKey === 'score') {
                valA = parseFloat(a.SCORE);
                valB = parseFloat(b.SCORE);
            } else if (sortKey === 'percentile') {
                valA = parseFloat(a.PERCENTILE);
                valB = parseFloat(b.PERCENTILE);
            } else if (sortKey === 'subcohort') {
                valA = a.SUBCOHORT;
                valB = b.SUBCOHORT;
            }
            
            if (sortOrder === 'asc') {
                return valA > valB ? 1 : -1;
            } else {
                return valA < valB ? 1 : -1;
            }
        });
        
        // Re-render the table
        renderPercentileTable(tableData);
    }

    // Function to display loading state
    function showLoadingState() {
        $('#loadingSpinner').show();
        $('#plotContainer').hide();  // Or whichever element holds your visualization
        if($('#plotPlaceholder').length > 0) {
            $('#plotPlaceholder').remove();
        }
        $('#alertContainer').empty();
        
        // Show a loading message
        showAlert('Loading visualization...', 'info');
    }

    // Function to load and display task data
    function loadTaskData(taskId) {
        $.ajax({
            url: `/api/task_status/${taskId}`,
            type: 'GET',
            success: function(task) {
            if (task.status === 'completed' && task.result_path) {
                // Display the completed visualization
                $('#loadingSpinner').hide();
                
                // Create an iframe to display the result
                const iframe = `<iframe src="${task.result_path}" style="width:100%; height:800px; border:none;"></iframe>`;
                $('#plotContainer').html(iframe).show();  
                
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

    // Function to add appropriate placeholder based on the page
    function addPlaceholder() {
        $('#plotContainer').append(`
            <div id="plotPlaceholder" class="d-flex justify-content-center align-items-center h-100">
            <div class="text-center p-4">
                <i class="fas fa-chart-bar fa-3x text-muted mb-3"></i>
                <p class="text-muted">Select cohorts or PGS IDs, choose a chart type, and generate a distribution plot to visualize the data.</p>
            </div>
            </div>
        `);
        }

    // Utility functions for density estimation
    function kernelDensityEstimator(kernel, X) {
        return function(V) {
            return X.map(x => [x, d3.mean(V, v => kernel(x - v))]);
        };
    }
    
    function epanechnikovKernel(bandwidth) {
        return function(u) {
            return Math.abs(u /= bandwidth) <= 1 ? 0.75 * (1 - u * u) / bandwidth : 0;
        };
    }
    
    // Function to calculate percentile of a value in an array
    function calculatePercentile(value, array) {
        const sortedArray = [...array].sort((a, b) => a - b);
        const position = sortedArray.findIndex(x => x >= value);
        
        if (position === -1) {
            return 100; // Value is greater than all elements
        }
        
        return (position / sortedArray.length * 100);
    }

    // Populate subcohort selects when subcohorts are added
    function updateSubcohortSelects() {
        const subcohort1Select = $('#subcohort1Select');
        const subcohort2Select = $('#subcohort2Select');
        
        subcohort1Select.empty();
        subcohort2Select.empty();
        
        subcohort1Select.append('<option value="" selected disabled>Select subcohort</option>');
        subcohort2Select.append('<option value="" selected disabled>Select subcohort</option>');
        
        subcohorts.forEach((subcohort, index) => {
            subcohort1Select.append(`<option value="${index}">${subcohort.name}</option>`);
            subcohort2Select.append(`<option value="${index}">${subcohort.name}</option>`);
        });
    }

    // Fetch score types for a PGS ID
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
    
    // Function to show alert
    function showAlert(message, type) {
        const alert = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        
        $('#alertContainer').html(alert);
    }
});