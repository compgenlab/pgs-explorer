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
    cohorts = []
    let baseData = null;
    let tableData = [];
    let originalTableData = []; 
    let currentSvg = null;
    let currentXScale = null;
    let currentMargin = null;
    let currentHeight = null;
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

    // 3. Populate data on page load
    fetchPgsList()
    loadPermanentCohorts()
    
    ////////// EVENT LISTENERS //////////
    // Handle PGS selection change
    $('#pgsId').on('change', function() {
        const pgsId = $(this).val();
        if (pgsId) {
            fetchScoreTypes(pgsId);
        }
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
    
    ////////// GENERAL FUNCTIONS //////////
    // Function to add appropriate placeholder based on the page
    function addPlaceholder() {
        $('#plotContainer').append(`
            <div id="plotPlaceholder" class="d-flex justify-content-center align-items-center h-100">
            <div class="text-center p-4">
                <i class="fas fa-chart-bar fa-3x text-muted mb-3"></i>
                <p class="text-muted">Select a PGS ID, score type, and two cohorts to generate comparison visualizations.</p>
            </div>
            </div>
        `);
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

    ////////// PGS FUNCTIONS //////////
    // Get all PGS to populate dropdown
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

    ////////// COHORT FUNCTIONS //////////
    function loadPermanentCohorts() {
        console.log("DEBUG: Starting loadPermanentCohorts function");
        
        // First, let's check if the dropdown elements exist
        console.log("DEBUG: Checking if dropdown elements exist...");
        const cohort1Check = document.getElementById('cohort1');
        const cohort2Check = document.getElementById('cohort2');
        console.log("DEBUG: cohort1 element:", cohort1Check);
        console.log("DEBUG: cohort2 element:", cohort2Check);
        
        $.ajax({
            url: '/api/permanent_cohorts',
            type: 'GET',
            success: function(data) {
                console.log("DEBUG: AJAX SUCCESS - Full cohorts response:", data);
                console.log("DEBUG: Response type:", typeof data);
                console.log("DEBUG: Response keys:", Object.keys(data));
                
                // Check if data has the expected structure
                if (!data) {
                    console.log("ERROR: No data received from API");
                    showAlert('No data received from cohorts API', 'danger');
                    return;
                }
                
                if (!data.cohorts) {
                    console.log("ERROR: No 'cohorts' property in response");
                    console.log("DEBUG: Available properties:", Object.keys(data));
                    showAlert('Invalid cohorts data structure', 'danger');
                    return;
                }
                
                console.log("DEBUG: Cohorts array:", data.cohorts);
                console.log("DEBUG: Cohorts length:", data.cohorts.length);
                console.log("DEBUG: Cohorts type:", Array.isArray(data.cohorts));
                
                if (data.cohorts && data.cohorts.length > 0) {
                    // Debug each cohort
                    data.cohorts.forEach(function(cohort, index) {
                        console.log(`DEBUG: Cohort ${index}:`, cohort);
                        console.log(`DEBUG: Cohort properties:`, Object.keys(cohort));
                        console.log(`DEBUG: Cohort name: ${cohort.name}, samples: ${cohort.sample_ids ? cohort.sample_ids.length : 'no sample_ids'}`);
                    });
                    
                    // Get both dropdown elements using jQuery
                    console.log("DEBUG: Getting dropdown elements with jQuery...");
                    const cohort1Select = $('#cohort1');
                    const cohort2Select = $('#cohort2');
                    
                    console.log("DEBUG: Cohort1 jQuery object:", cohort1Select);
                    console.log("DEBUG: Cohort1 length:", cohort1Select.length);
                    console.log("DEBUG: Cohort1 element:", cohort1Select[0]);
                    
                    console.log("DEBUG: Cohort2 jQuery object:", cohort2Select);
                    console.log("DEBUG: Cohort2 length:", cohort2Select.length);
                    console.log("DEBUG: Cohort2 element:", cohort2Select[0]);
                    
                    if (cohort1Select.length === 0) {
                        console.log("ERROR: #cohort1 dropdown not found in DOM!");
                        showAlert('Cohort 1 dropdown element not found', 'danger');
                        return;
                    }
                    
                    if (cohort2Select.length === 0) {
                        console.log("ERROR: #cohort2 dropdown not found in DOM!");
                        showAlert('Cohort 2 dropdown element not found', 'danger');
                        return;
                    }
                    
                    console.log("DEBUG: Both dropdowns found, proceeding with population...");
                    
                    // Clear both dropdowns and add default options
                    console.log("DEBUG: Clearing dropdowns...");
                    cohort1Select.empty();
                    cohort2Select.empty();
                    
                    console.log("DEBUG: Adding default options...");
                    cohort1Select.append('<option value="" selected disabled>Select First Cohort</option>');
                    cohort2Select.append('<option value="" selected disabled>Select Second Cohort</option>');
                    
                    console.log("DEBUG: Default options added. Current HTML:");
                    console.log("Cohort1:", cohort1Select.html());
                    console.log("Cohort2:", cohort2Select.html());
                    
                    // Populate both dropdowns with cohort data
                    console.log("DEBUG: Starting to populate dropdowns with cohort data...");
                    data.cohorts.forEach(function(cohort, index) {
                        console.log(`DEBUG: Processing cohort ${index}: ${cohort.name}`);
                        
                        // Validate cohort data
                        if (!cohort.name) {
                            console.log(`WARNING: Cohort ${index} has no name, skipping`);
                            return;
                        }
                        
                        if (!cohort.sample_ids || !Array.isArray(cohort.sample_ids)) {
                            console.log(`WARNING: Cohort ${index} has invalid sample_ids, using 0 count`);
                            cohort.sample_ids = [];
                        }
                        
                        const sampleCount = cohort.sample_ids.length;
                        const optionText = `${cohort.name} (${sampleCount} samples)`;
                        const optionHtml = `<option value="${cohort.name}">${optionText}</option>`;
                        
                        console.log(`DEBUG: Creating option - Value: "${cohort.name}", Text: "${optionText}"`);
                        console.log(`DEBUG: Option HTML: ${optionHtml}`);
                        
                        // Add to both dropdowns
                        cohort1Select.append(optionHtml);
                        cohort2Select.append(optionHtml);
                        
                        console.log(`DEBUG: Added option ${index} to both dropdowns`);
                    });
                    
                    console.log("DEBUG: Finished populating dropdowns");
                    console.log("DEBUG: Final cohort1 HTML:", cohort1Select.html());
                    console.log("DEBUG: Final cohort2 HTML:", cohort2Select.html());
                    console.log("DEBUG: Final cohort1 children count:", cohort1Select.children().length);
                    console.log("DEBUG: Final cohort2 children count:", cohort2Select.children().length);
                    
                    // Setup validation
                    console.log("DEBUG: Setting up cohort validation...");
                    setupCohortValidation();
                    
                    // Store cohorts globally
                    console.log("DEBUG: Storing cohorts globally...");
                    cohorts = data.cohorts.map(function(cohort, index) {
                        const color = PRESET_COLORS[index % PRESET_COLORS.length];
                        return {
                            id: index + 1,
                            name: cohort.name,
                            color: color,
                            sampleIds: cohort.sample_ids,
                            active: true,
                            permanent: true
                        };
                    });
                    
                    console.log("DEBUG: Successfully loaded", data.cohorts.length, "cohorts");
                    showAlert(`Successfully loaded ${data.cohorts.length} cohorts`, 'success');
                    
                } else {
                    console.log("DEBUG: No cohorts found or cohorts array is empty");
                    showAlert('No cohorts available', 'warning');
                }
            },
            error: function(xhr, status, error) {
                console.log('ERROR: AJAX failed');
                console.log('Status:', status);
                console.log('Error:', error);
                console.log('Response Status:', xhr.status);
                console.log('Response Text:', xhr.responseText);
                
                showAlert(`Failed to load cohorts: ${status} - ${error}`, 'danger');
            }
        });
    }
    
    // Setup validation to prevent selecting the same cohort in both dropdowns
    function setupCohortValidation() {
        console.log("DEBUG: Setting up cohort validation");
        
        // Remove any existing event handlers to prevent duplicates
        $('#cohort1').off('change.validation');
        $('#cohort2').off('change.validation');
        
        $('#cohort1').on('change.validation', function() {
            const cohort1Value = $(this).val();
            const cohort2Select = $('#cohort2');
            
            console.log(`DEBUG: Cohort1 changed to: ${cohort1Value}`);
            console.log(`DEBUG: Current cohort2 value: ${cohort2Select.val()}`);
            
            // If cohort2 has the same value, clear it
            if (cohort2Select.val() === cohort1Value && cohort1Value !== '') {
                cohort2Select.val('');
                showAlert('Cannot select the same cohort twice. Please choose a different second cohort.', 'warning');
                console.log("DEBUG: Cleared cohort2 because it matched cohort1");
            }
        });
        
        $('#cohort2').on('change.validation', function() {
            const cohort2Value = $(this).val();
            const cohort1Select = $('#cohort1');
            
            console.log(`DEBUG: Cohort2 changed to: ${cohort2Value}`);
            console.log(`DEBUG: Current cohort1 value: ${cohort1Select.val()}`);
            
            // If cohort1 has the same value, clear it
            if (cohort1Select.val() === cohort2Value && cohort2Value !== '') {
                cohort1Select.val('');
                showAlert('Cannot select the same cohort twice. Please choose a different first cohort.', 'warning');
                console.log("DEBUG: Cleared cohort1 because it matched cohort2");
            }
        });
        
        console.log("DEBUG: Cohort validation setup complete");
    }

    ////////// TASK FUNCTIONS - UPDATED FOR TWO COHORTS //////////
    // Function to generate the plot using the backend
    function generatePlot(taskName = '') {
        const pgsId = $('#pgsId').val();
        const scoreType = $('#scoreType').val();
        const cohort1 = $('#cohort1').val();  // Changed from baseCohort
        const cohort2 = $('#cohort2').val();  // New field
        
        // Updated validation
        if (!pgsId) {
            showAlert('Please select a PGS ID', 'warning');
            return;
        }
        
        if (!scoreType) {
            showAlert('Please select a Score Type', 'warning');
            return;
        }
        
        if (!cohort1) {
            showAlert('Please select the first cohort', 'warning');
            return;
        }
        
        if (!cohort2) {
            showAlert('Please select the second cohort', 'warning');
            return;
        }
        
        if (cohort1 === cohort2) {
            showAlert('Please select two different cohorts for comparison', 'warning');
            return;
        }
        
        // Show loading spinner
        $('#plotPlaceholder').remove();
        $('#plotSvg').hide();
        $('#plotIframe').remove();
        $('#loadingSpinner').show();
        
        // Prepare request data with new structure
        const requestData = {
            pgs_id: pgsId,
            score_type: scoreType,
            cohort_1: cohort1,  // Changed from base_cohort
            cohort_2: cohort2,  // New field
            plot_title: $('#plotTitle').val().trim() || `${cohort1} vs ${cohort2} - ${pgsId}`,
            normalize_bins: $('#normalizeBins').is(':checked'),
            display_or: $('#displayOR').is(':checked'),
            or_calculation_type: getSelectedORCalculationType(),
            bin_size: parseInt($('#binSize').val()) || 30,
            quantile_count: parseInt($('#quantileCount').val()) || 10,
            threshold_value: parseFloat($('#thresholdValue').val()) || 0,
            decile_count: parseInt($('#decileCount').val()) || 10,
            name: taskName
        };
        
        console.log("Sending cohort comparison request:", JSON.stringify(requestData, null, 2));
        
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
                    showAlert(`Cohort comparison generation started (Task ID: ${taskId}). You'll be notified when it's ready.`, 'info');
                    
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
                    
                    showAlert('Cohort comparison generated successfully.', 'success');
                } else {
                    // Unexpected response format
                    $('#loadingSpinner').hide();
                    showAlert('Error: Invalid response from server', 'danger');
                }
            },
            error: function(xhr, status, error) {
                $('#loadingSpinner').hide();
                addPlaceholder();
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
                        showAlert(`Cohort comparison generated successfully!`, 'success');
                        
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
                        showAlert(`Error generating cohort comparison: ${response.error || 'Unknown error'}`, 'danger');
                        
                        // Hide loading spinner
                        $('#loadingSpinner').hide();
                        
                        // Show placeholder
                        addPlaceholder();
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
                $('#downloadSvgBtn').prop('disabled', false);
                $('#downloadTableBtn').prop('disabled', false);
                
                // Update download button to open the plot
                $('#downloadSvgBtn').off('click').on('click', function() {
                    window.open(task.result_path, '_blank');
                });
                
                // Show success message
                const taskName = task.name || 'Cohort comparison';
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

    ////////// ODDS RATIO CONTROLS //////////
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

    ////////// TABLE FUNCTIONS (placeholders for if you implement them) //////////
    // Apply percentile filter
    function applyPercentileFilter() {
        const percentileValue = parseFloat($('#percentileInput').val());
        const filterType = $('#percentileFilter').val();
        
        if (isNaN(percentileValue) || percentileValue < 0 || percentileValue > 100) {
            showAlert('Please enter a valid percentile value between 0 and 100', 'warning');
            return;
        }
        
        console.log(`Filtering by percentile ${filterType} ${percentileValue}`);
        // Add your filtering logic here if needed
        
        if (!originalTableData || originalTableData.length === 0) {
            showAlert('No table data to filter', 'warning');
            return;
        }
        
        // Filter the data based on percentile
        let filteredData;
        if (filterType === 'above') {
            filteredData = originalTableData.filter(row => 
                parseFloat(row.PERCENTILE) >= percentileValue
            );
        } else {
            filteredData = originalTableData.filter(row => 
                parseFloat(row.PERCENTILE) <= percentileValue
            );
        }
        
        // Update the table display
        renderPercentileTable(filteredData);
        
        showAlert(`Filtered to ${filteredData.length} samples ${filterType} ${percentileValue}th percentile`, 'info');
    }

    // Download table as CSV
    function downloadTableAsCsv() {
        if (!tableData || tableData.length === 0) {
            showAlert('No table data available to download', 'warning');
            return;
        }
        
        // Create CSV content
        const headers = Object.keys(tableData[0]);
        const csvContent = [
            headers.join(','), // Header row
            ...tableData.map(row => 
                headers.map(header => `"${row[header]}"`).join(',')
            )
        ].join('\n');
        
        // Create and trigger download
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'cohort_comparison_data.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showAlert('CSV file downloaded successfully', 'success');
    }

    // Render percentile table
    function renderPercentileTable(data) {
        if (!data || data.length === 0) {
            $('#percentileTable').html('<p class="text-muted">No data available</p>');
            return;
        }
        
        // Create table HTML
        const headers = Object.keys(data[0]);
        let tableHtml = `
            <div class="table-responsive">
                <table class="table table-striped table-hover">
                    <thead class="table-dark">
                        <tr>
                            ${headers.map(header => `<th>${header}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        data.forEach(row => {
            tableHtml += `
                <tr>
                    ${headers.map(header => `<td>${row[header]}</td>`).join('')}
                </tr>
            `;
        });
        
        tableHtml += `
                    </tbody>
                </table>
            </div>
        `;
        
        $('#percentileTable').html(tableHtml);
        
        // Enable download button
        $('#downloadTableBtn').prop('disabled', false);
    }

    // Download plot as SVG (handled by download button)
    function downloadPlotAsSvg() {
        // This is typically handled by the download button click handler
        // which opens the plot URL in a new window
        const iframe = $('#plotIframe');
        if (iframe.length > 0) {
            window.open(iframe.attr('src'), '_blank');
        } else {
            showAlert('No plot available to download', 'warning');
        }
    }
});