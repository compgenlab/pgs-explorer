// Task list state
let currentPage = 1;
let pageSize = 20;
let totalTasks = 0;
let currentTaskType = 'all';
let currentTaskStatus = 'all';

// Load tasks on page load and start periodic refresh
$(document).ready(function() {
  loadTasks();
  
  // Auto-refresh every 10 seconds
  const refreshInterval = setInterval(loadTasks, 10000);
  
  // Stop refreshing when the page is hidden to save resources
  document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
      clearInterval(refreshInterval);
    } else {
      loadTasks();
      setInterval(loadTasks, 10000);
    }
  });
  
  // Button event handlers
  $('#refreshTasksBtn').on('click', loadTasks);
  $('#prevPageBtn').on('click', prevPage);
  $('#nextPageBtn').on('click', nextPage);
  
  // Filter event handlers
  $('#taskTypeFilter').on('click', 'a', function(e) {
    e.preventDefault();
    $('#taskTypeFilter a').removeClass('active');
    $(this).addClass('active');
    currentTaskType = $(this).data('type');
    currentPage = 1;
    loadTasks();
  });
  
  $('#taskStatusFilter').on('click', 'a', function(e) {
    e.preventDefault();
    $('#taskStatusFilter a').removeClass('active');
    $(this).addClass('active');
    currentTaskStatus = $(this).data('status');
    currentPage = 1;
    loadTasks();
  });
  
  // View result button event handler
  $('#viewResultBtn').on('click', function() {
    const taskId = $('#detailsTaskId').text();
    const taskType = $('#detailsTaskType').text();  // You'll need to add this element to store the task type
    window.location.href = getTaskPageUrl(taskType, taskId);
    });

  $('.view-task-btn').on('click', function() {
    const taskId = $(this).data('task-id');
    const taskType = $(this).data('task-type');
    window.location.href = getTaskPageUrl(taskType, taskId);
    });
});

// Function to load tasks
function loadTasks() {
  let url = `/api/list_tasks?limit=${pageSize}&offset=${(currentPage - 1) * pageSize}`;
  
  if (currentTaskType !== 'all') {
    url += `&task_type=${currentTaskType}`;
  }
  
  if (currentTaskStatus !== 'all') {
    url += `&status=${currentTaskStatus}`;
  }
  
  $.ajax({
    url: url,
    type: 'GET',
    success: function(response) {
      renderTasksTable(response);
    },
    error: function(error) {
      console.error('Error loading tasks:', error);
      $('#tasksTableBody').html(`
        <tr>
          <td colspan="6" class="text-center text-danger py-4">
            <i class="fas fa-exclamation-triangle me-2"></i>
            Failed to load tasks. Please try again.
          </td>
        </tr>
      `);
    }
  });
}

// Function to render the tasks table
function renderTasksTable(data) {
  const tasks = data.tasks || data;
  totalTasks = data.total || tasks.length;
  
  const $tableBody = $('#tasksTableBody');
  $tableBody.empty();
  
  if (tasks.length === 0) {
    $tableBody.html(`
      <tr>
        <td colspan="7" class="text-center text-muted py-4"><!-- Update colspan to 7 -->
          <i class="fas fa-search me-2"></i>
          No tasks found
        </td>
      </tr>
    `);
  } else {
    tasks.forEach((task, index) => {
      // Format dates
      const createdDate = new Date(task.created_at);
      const formattedCreatedDate = createdDate.toLocaleString();
      
      let formattedCompletedDate = '-';
      if (task.completed_at) {
        const completedDate = new Date(task.completed_at);
        formattedCompletedDate = completedDate.toLocaleString();
      }
      
      // Status badge
      let statusBadge = '';
      if (task.status === 'completed') {
        statusBadge = '<span class="badge bg-success">Completed</span>';
      } else if (task.status === 'processing') {
        statusBadge = '<span class="badge bg-warning text-dark">Processing</span>';
      } else if (task.status === 'queued') {
        statusBadge = '<span class="badge bg-info text-dark">Queued</span>';
      } else {
        statusBadge = '<span class="badge bg-danger">Failed</span>';
      }

      // Task ID - get first 8 characters for display
      const shortTaskId = task.task_id.substring(0, 8);

      // Task name - use provided name or a default if none
      const taskName = task.name || '(Unnamed task)';
      
      // Create row
      const $row = $(`
        <tr data-task-id="${task.task_id}" data-task-type="${task.task_type}">
            <td class="text-monospace">${shortTaskId}</td>
            <td class="text-truncate" style="max-width: 200px;">${taskName}</td>
            <td>${task.task_type.charAt(0).toUpperCase() + task.task_type.slice(1).replace('_', ' ')}</td>
            <td>${statusBadge}</td>
            <td>${formattedCreatedDate}</td>
            <td>${formattedCompletedDate}</td>
            <td>
            <div class="btn-group">
                <button type="button" class="btn btn-sm btn-outline-primary view-task-btn" 
                        data-task-id="${task.task_id}" 
                        data-task-type="${task.task_type}">
                <i class="fas fa-eye"></i>
                </button>
                <button type="button" class="btn btn-sm btn-outline-info task-details-btn" 
                        data-task-id="${task.task_id}"
                        data-task-type="${task.task_type}">
                <i class="fas fa-info-circle"></i>
                </button>
            </div>
            </td>
        </tr>
        `);
      
      $tableBody.append($row);
    });
    
    // View result button event handler
    $('#viewResultBtn').on('click', function() {
        const taskId = $('#detailsTaskId').text();
        const taskType = $('#detailsTaskType').text();  
        window.location.href = getTaskPageUrl(taskType, taskId);
    });

    $('.view-task-btn').on('click', function() {
        const taskId = $(this).data('task-id');
        const taskType = $(this).data('task-type');
        window.location.href = getTaskPageUrl(taskType, taskId);
    });
    
    // Add task details button handler if not already added
    $('.task-details-btn').on('click', function() {
        const taskId = $(this).data('task-id');
        showTaskDetails(taskId);
    });
  }
  
  // Update pagination
  updatePagination();
}

// Function to update pagination controls
function updatePagination() {
  const totalPages = Math.ceil(totalTasks / pageSize);
  $('#taskCount').text(`${totalTasks} task${totalTasks !== 1 ? 's' : ''}`);
  $('#pageInfo').text(`Page ${currentPage} of ${totalPages || 1}`);
  
  $('#prevPageBtn').prop('disabled', currentPage <= 1);
  $('#nextPageBtn').prop('disabled', currentPage >= totalPages);
}

// Previous page function
function prevPage() {
  if (currentPage > 1) {
    currentPage--;
    loadTasks();
  }
}

// Next page function
function nextPage() {
  const totalPages = Math.ceil(totalTasks / pageSize);
  if (currentPage < totalPages) {
    currentPage++;
    loadTasks();
  }
}

// Function to show task details
function showTaskDetails(taskId) {
  const currentTimeInMilliseconds = Date.now();
  $.ajax({
    url: `/api/task_status/${taskId}?${currentTimeInMilliseconds}`,
    type: 'GET',
    success: function(task) {
      $('#detailsTaskId').text(task.task_id);
      
      try {
        const requestData = JSON.parse(task.request_data);
        $('#detailsRequestData').text(JSON.stringify(requestData, null, 2));
      } catch (e) {
        $('#detailsRequestData').text(task.request_data || 'No request data available');
      }
      
      if (task.error) {
        $('#detailsErrorContainer').removeClass('d-none');
        $('#detailsError').text(task.error);
      } else {
        $('#detailsErrorContainer').addClass('d-none');
      }
      
      $('#viewResultBtn').prop('disabled', task.status !== 'completed');
      
      const taskDetailsModal = new bootstrap.Modal(document.getElementById('taskDetailsModal'));
      taskDetailsModal.show();
    },
    error: function(error) {
      console.error('Error loading task details:', error);
      alert('Failed to load task details. Please try again.');
    }
  });
}

// Helper function to get the correct page URL for a task
function getTaskPageUrl(taskType, taskId) {
  switch (taskType) {
    case 'heatmap':
    case 'umap':
    case 'svd':
      return `/multivariate?task_id=${taskId}`;
    case 'distribution':
      return `/distribution?task_id=${taskId}`;
    case 'subcohort_plot':
      return `/subcohorts?task_id=${taskId}`;
    default:
      return `/tasks?task_id=${taskId}`;
  }
}
