import os
import re
import json
from bs4 import BeautifulSoup

def add_interactive_filter_tsne(html_file_path, output_filepath=None):
    """
    Add interactive cohort controls to a Plotly scatterplot HTML with Bootstrap styling.
    """
    # Read the HTML file
    with open(html_filepath, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create a BeautifulSoup object
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the div that contains the Plotly graph
    plotly_div = soup.find('div', class_='plotly-graph-div')
    
    if not plotly_div:
        raise ValueError("Could not find Plotly graph div in the HTML file")
    
    div_id = plotly_div.get('id')
    
    # Extract PGS IDs directly from the HTML content
    pgs_matches = re.findall(r'PGS ID: (PGS\d+)', html_content)
    if not pgs_matches:
        raise ValueError("Could not find PGS IDs in the HTML content")
    
    print(f"Found {len(pgs_matches)} PGS ID mentions in the HTML")
    
    # Get unique PGS IDs while preserving order
    unique_pgs_ids = []
    for pgs_id in pgs_matches:
        if pgs_id not in unique_pgs_ids:
            unique_pgs_ids.append(pgs_id)
    
    print(f"Found {len(unique_pgs_ids)} unique PGS IDs")
    
    # Add Bootstrap CSS if not already present
    bootstrap_css = soup.find('link', href=lambda x: x and 'bootstrap' in x)
    if not bootstrap_css:
        bootstrap_link = soup.new_tag('link')
        bootstrap_link.attrs['rel'] = 'stylesheet'
        bootstrap_link.attrs['href'] = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'
        bootstrap_link.attrs['integrity'] = 'sha384-9ndCyUaIbzAi2FUVXJi0CjmCapSmO7SnpJef0486qhLnuZ2cdeRhO02iuK6FUUVM'
        bootstrap_link.attrs['crossorigin'] = 'anonymous'
        soup.head.append(bootstrap_link)
    
    # Add FontAwesome for icons
    fontawesome_link = soup.new_tag('link')
    fontawesome_link.attrs['rel'] = 'stylesheet'
    fontawesome_link.attrs['href'] = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
    soup.head.append(fontawesome_link)
    
    # Add Bootstrap JS if not already present
    bootstrap_js = soup.find('script', src=lambda x: x and 'bootstrap' in x)
    if not bootstrap_js:
        bootstrap_script = soup.new_tag('script')
        bootstrap_script.attrs['src'] = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
        bootstrap_script.attrs['integrity'] = 'sha384-geWF76RCwLtnZ8qwWowPQNguL3RmwHVBC9FhGdlKrxdiJJigb/j/68SIy3Te4Bkz'
        bootstrap_script.attrs['crossorigin'] = 'anonymous'
        soup.body.append(bootstrap_script)
    
    # Create a modal for the control panel
    modal_div = soup.new_tag('div')
    modal_div.attrs['class'] = 'modal fade'
    modal_div.attrs['id'] = 'cohortControlModal'
    modal_div.attrs['tabindex'] = '-1'
    modal_div.attrs['aria-labelledby'] = 'cohortControlModalLabel'
    modal_div.attrs['aria-hidden'] = 'true'
    
    modal_dialog = soup.new_tag('div')
    modal_dialog.attrs['class'] = 'modal-dialog modal-lg'
    
    modal_content = soup.new_tag('div')
    modal_content.attrs['class'] = 'modal-content'
    
    # Modal header
    modal_header = soup.new_tag('div')
    modal_header.attrs['class'] = 'modal-header bg-primary text-white'
    
    modal_title = soup.new_tag('h5')
    modal_title.attrs['class'] = 'modal-title'
    modal_title.attrs['id'] = 'cohortControlModalLabel'
    modal_title.string = 'PGS Cohort Manager'
    modal_header.append(modal_title)
    
    close_button = soup.new_tag('button')
    close_button.attrs['type'] = 'button'
    close_button.attrs['class'] = 'btn-close btn-close-white'
    close_button.attrs['data-bs-dismiss'] = 'modal'
    close_button.attrs['aria-label'] = 'Close'
    modal_header.append(close_button)
    
    modal_content.append(modal_header)
    
    # Modal body
    modal_body = soup.new_tag('div')
    modal_body.attrs['class'] = 'modal-body'
    
    # Add tabs for organization
    tabs_nav = soup.new_tag('ul')
    tabs_nav.attrs['class'] = 'nav nav-tabs mb-3'
    tabs_nav.attrs['id'] = 'cohortTabs'
    tabs_nav.attrs['role'] = 'tablist'
    
    # Create tab items
    create_tab = soup.new_tag('li')
    create_tab.attrs['class'] = 'nav-item'
    create_tab.attrs['role'] = 'presentation'
    create_tab_button = soup.new_tag('button')
    create_tab_button.attrs['class'] = 'nav-link active'
    create_tab_button.attrs['id'] = 'create-tab'
    create_tab_button.attrs['data-bs-toggle'] = 'tab'
    create_tab_button.attrs['data-bs-target'] = '#create-tab-pane'
    create_tab_button.attrs['type'] = 'button'
    create_tab_button.attrs['role'] = 'tab'
    create_tab_button.attrs['aria-controls'] = 'create-tab-pane'
    create_tab_button.attrs['aria-selected'] = 'true'
    create_tab_button.string = 'Create Cohort'
    create_tab.append(create_tab_button)
    tabs_nav.append(create_tab)
    
    manage_tab = soup.new_tag('li')
    manage_tab.attrs['class'] = 'nav-item'
    manage_tab.attrs['role'] = 'presentation'
    manage_tab_button = soup.new_tag('button')
    manage_tab_button.attrs['class'] = 'nav-link'
    manage_tab_button.attrs['id'] = 'manage-tab'
    manage_tab_button.attrs['data-bs-toggle'] = 'tab'
    manage_tab_button.attrs['data-bs-target'] = '#manage-tab-pane'
    manage_tab_button.attrs['type'] = 'button'
    manage_tab_button.attrs['role'] = 'tab'
    manage_tab_button.attrs['aria-controls'] = 'manage-tab-pane'
    manage_tab_button.attrs['aria-selected'] = 'false'
    manage_tab_button.string = 'Manage Cohorts'
    manage_tab.append(manage_tab_button)
    tabs_nav.append(manage_tab)
    
    settings_tab = soup.new_tag('li')
    settings_tab.attrs['class'] = 'nav-item'
    settings_tab.attrs['role'] = 'presentation'
    settings_tab_button = soup.new_tag('button')
    settings_tab_button.attrs['class'] = 'nav-link'
    settings_tab_button.attrs['id'] = 'settings-tab'
    settings_tab_button.attrs['data-bs-toggle'] = 'tab'
    settings_tab_button.attrs['data-bs-target'] = '#settings-tab-pane'
    settings_tab_button.attrs['type'] = 'button'
    settings_tab_button.attrs['role'] = 'tab'
    settings_tab_button.attrs['aria-controls'] = 'settings-tab-pane'
    settings_tab_button.attrs['aria-selected'] = 'false'
    settings_tab_button.string = 'Import/Export'
    settings_tab.append(settings_tab_button)
    tabs_nav.append(settings_tab)
    
    modal_body.append(tabs_nav)
    
    # Tab content
    tab_content = soup.new_tag('div')
    tab_content.attrs['class'] = 'tab-content'
    tab_content.attrs['id'] = 'cohortTabContent'
    
    # Create Cohort Tab
    create_pane = soup.new_tag('div')
    create_pane.attrs['class'] = 'tab-pane fade show active'
    create_pane.attrs['id'] = 'create-tab-pane'
    create_pane.attrs['role'] = 'tabpanel'
    create_pane.attrs['aria-labelledby'] = 'create-tab'
    create_pane.attrs['tabindex'] = '0'
    
    # Cohort name and color
    create_form = soup.new_tag('form')
    create_form.attrs['id'] = 'cohort-form'
    
    # Cohort Name
    name_row = soup.new_tag('div')
    name_row.attrs['class'] = 'mb-3 row'
    
    name_label = soup.new_tag('label')
    name_label.attrs['for'] = 'cohort-name'
    name_label.attrs['class'] = 'col-sm-3 col-form-label'
    name_label.string = 'Cohort Name:'
    name_row.append(name_label)
    
    name_col = soup.new_tag('div')
    name_col.attrs['class'] = 'col-sm-9'
    
    name_input = soup.new_tag('input')
    name_input.attrs['type'] = 'text'
    name_input.attrs['class'] = 'form-control'
    name_input.attrs['id'] = 'cohort-name'
    name_input.attrs['placeholder'] = 'Enter cohort name'
    name_col.append(name_input)
    name_row.append(name_col)
    create_form.append(name_row)
    
    # Cohort Color
    color_row = soup.new_tag('div')
    color_row.attrs['class'] = 'mb-3 row'
    
    color_label = soup.new_tag('label')
    color_label.attrs['for'] = 'cohort-color'
    color_label.attrs['class'] = 'col-sm-3 col-form-label'
    color_label.string = 'Cohort Color:'
    color_row.append(color_label)
    
    color_col = soup.new_tag('div')
    color_col.attrs['class'] = 'col-sm-9'
    
    # Create color presets
    color_presets = soup.new_tag('div')
    color_presets.attrs['class'] = 'mb-2 d-flex gap-2'
    
    preset_colors = ['#FF5733', '#33FF57', '#3357FF', '#FF33A8', '#33FFF5', '#FFC133', '#8A33FF', '#FF3333', '#33FFBE', '#FF33EB']
    for color in preset_colors:
        preset_btn = soup.new_tag('button')
        preset_btn.attrs['type'] = 'button'
        preset_btn.attrs['class'] = 'btn btn-sm color-preset'
        preset_btn.attrs['style'] = f'background-color: {color}; width: 24px; height: 24px; border-radius: 50%;'
        preset_btn.attrs['data-color'] = color
        color_presets.append(preset_btn)
    
    color_col.append(color_presets)
    
    color_input = soup.new_tag('input')
    color_input.attrs['type'] = 'color'
    color_input.attrs['class'] = 'form-control form-control-color'
    color_input.attrs['id'] = 'cohort-color'
    color_input.attrs['value'] = '#FF5733'
    color_input.attrs['title'] = 'Choose cohort color'
    color_col.append(color_input)
    color_row.append(color_col)
    create_form.append(color_row)
    
    # File upload for PGS IDs
    file_row = soup.new_tag('div')
    file_row.attrs['class'] = 'mb-3'
    
    file_label = soup.new_tag('label')
    file_label.attrs['for'] = 'pgs-file-upload'
    file_label.attrs['class'] = 'form-label'
    file_label.string = 'Upload PGS IDs (text file, one per line or comma-separated):'
    file_row.append(file_label)
    
    file_input = soup.new_tag('input')
    file_input.attrs['type'] = 'file'
    file_input.attrs['class'] = 'form-control'
    file_input.attrs['id'] = 'pgs-file-upload'
    file_input.attrs['accept'] = '.txt,.csv'
    file_row.append(file_input)
    create_form.append(file_row)
    
    # Textarea for direct input
    textarea_row = soup.new_tag('div')
    textarea_row.attrs['class'] = 'mb-3'
    
    textarea_label = soup.new_tag('label')
    textarea_label.attrs['for'] = 'pgs-textarea'
    textarea_label.attrs['class'] = 'form-label'
    textarea_label.string = 'Or paste PGS IDs (one per line or comma-separated):'
    textarea_row.append(textarea_label)
    
    textarea = soup.new_tag('textarea')
    textarea.attrs['class'] = 'form-control'
    textarea.attrs['id'] = 'pgs-textarea'
    textarea.attrs['rows'] = '4'
    textarea.attrs['placeholder'] = 'Paste PGS IDs here...'
    textarea_row.append(textarea)
    create_form.append(textarea_row)
    
    # Selected PGS IDs info
    selection_info = soup.new_tag('div')
    selection_info.attrs['class'] = 'card mb-3'
    
    selection_header = soup.new_tag('div')
    selection_header.attrs['class'] = 'card-header d-flex justify-content-between align-items-center'
    
    selection_title = soup.new_tag('span')
    selection_title.string = 'Selected PGS IDs'
    selection_header.append(selection_title)
    
    selection_count = soup.new_tag('span')
    selection_count.attrs['id'] = 'selected-count'
    selection_count.attrs['class'] = 'badge bg-primary'
    selection_count.string = '0 IDs'
    selection_header.append(selection_count)
    
    selection_info.append(selection_header)
    
    selection_body = soup.new_tag('div')
    selection_body.attrs['class'] = 'card-body'
    
    selected_list = soup.new_tag('div')
    selected_list.attrs['id'] = 'selected-pgs-ids'
    selected_list.attrs['class'] = 'small'
    selected_list.attrs['style'] = 'max-height: 120px; overflow-y: auto;'
    selection_body.append(selected_list)
    
    selection_footer = soup.new_tag('div')
    selection_footer.attrs['class'] = 'card-footer text-end'
    
    clear_btn = soup.new_tag('button')
    clear_btn.attrs['type'] = 'button'
    clear_btn.attrs['id'] = 'clear-selection-btn'
    clear_btn.attrs['class'] = 'btn btn-sm btn-outline-secondary'
    clear_btn.string = 'Clear Selection'
    selection_footer.append(clear_btn)
    
    selection_info.append(selection_body)
    selection_info.append(selection_footer)
    create_form.append(selection_info)
    
    # Add cohort button
    submit_row = soup.new_tag('div')
    submit_row.attrs['class'] = 'text-end'
    
    add_btn = soup.new_tag('button')
    add_btn.attrs['type'] = 'button'
    add_btn.attrs['id'] = 'add-cohort-btn'
    add_btn.attrs['class'] = 'btn btn-primary'
    add_icon = soup.new_tag('i')
    add_icon.attrs['class'] = 'fas fa-plus me-1'
    add_btn.append(add_icon)
    add_btn.append(' Add Cohort')
    submit_row.append(add_btn)
    create_form.append(submit_row)
    
    create_pane.append(create_form)
    tab_content.append(create_pane)
    
    # Manage Cohorts Tab
    manage_pane = soup.new_tag('div')
    manage_pane.attrs['class'] = 'tab-pane fade'
    manage_pane.attrs['id'] = 'manage-tab-pane'
    manage_pane.attrs['role'] = 'tabpanel'
    manage_pane.attrs['aria-labelledby'] = 'manage-tab'
    manage_pane.attrs['tabindex'] = '0'
    
    cohort_list_card = soup.new_tag('div')
    cohort_list_card.attrs['class'] = 'card'
    
    cohort_card_header = soup.new_tag('div')
    cohort_card_header.attrs['class'] = 'card-header'
    cohort_card_header.string = 'Defined Cohorts'
    cohort_list_card.append(cohort_card_header)
    
    cohort_card_body = soup.new_tag('div')
    cohort_card_body.attrs['class'] = 'card-body p-0'
    
    cohort_list = soup.new_tag('div')
    cohort_list.attrs['id'] = 'cohort-list'
    cohort_list.attrs['class'] = 'list-group list-group-flush'
    cohort_card_body.append(cohort_list)
    
    cohort_list_card.append(cohort_card_body)
    
    cohort_empty = soup.new_tag('div')
    cohort_empty.attrs['id'] = 'no-cohorts-message'
    cohort_empty.attrs['class'] = 'alert alert-info m-3'
    cohort_empty.string = 'No cohorts defined yet. Create a cohort in the "Create Cohort" tab.'
    cohort_list_card.append(cohort_empty)
    
    manage_pane.append(cohort_list_card)
    tab_content.append(manage_pane)
    
    # Settings Tab (Import/Export)
    settings_pane = soup.new_tag('div')
    settings_pane.attrs['class'] = 'tab-pane fade'
    settings_pane.attrs['id'] = 'settings-tab-pane'
    settings_pane.attrs['role'] = 'tabpanel'
    settings_pane.attrs['aria-labelledby'] = 'settings-tab'
    settings_pane.attrs['tabindex'] = '0'
    
    # Export section
    export_card = soup.new_tag('div')
    export_card.attrs['class'] = 'card mb-3'
    
    export_header = soup.new_tag('div')
    export_header.attrs['class'] = 'card-header'
    export_header.string = 'Export Cohorts'
    export_card.append(export_header)
    
    export_body = soup.new_tag('div')
    export_body.attrs['class'] = 'card-body'
    
    export_text = soup.new_tag('p')
    export_text.string = 'Save your current cohort definitions to a JSON file.'
    export_body.append(export_text)
    
    export_btn = soup.new_tag('button')
    export_btn.attrs['type'] = 'button'
    export_btn.attrs['id'] = 'export-cohorts-btn'
    export_btn.attrs['class'] = 'btn btn-primary'
    export_icon = soup.new_tag('i')
    export_icon.attrs['class'] = 'fas fa-download me-1'
    export_btn.append(export_icon)
    export_btn.append(' Export Cohorts')
    export_body.append(export_btn)
    
    export_card.append(export_body)
    settings_pane.append(export_card)
    
    # Import section
    import_card = soup.new_tag('div')
    import_card.attrs['class'] = 'card'
    
    import_header = soup.new_tag('div')
    import_header.attrs['class'] = 'card-header'
    import_header.string = 'Import Cohorts'
    import_card.append(import_header)
    
    import_body = soup.new_tag('div')
    import_body.attrs['class'] = 'card-body'
    
    import_text = soup.new_tag('p')
    import_text.string = 'Load previously exported cohort definitions from a JSON file.'
    import_body.append(import_text)
    
    import_file_row = soup.new_tag('div')
    import_file_row.attrs['class'] = 'mb-3'
    
    import_file_input = soup.new_tag('input')
    import_file_input.attrs['type'] = 'file'
    import_file_input.attrs['class'] = 'form-control'
    import_file_input.attrs['id'] = 'import-file-input'
    import_file_input.attrs['accept'] = '.json'
    import_file_row.append(import_file_input)
    
    import_body.append(import_file_row)
    
    import_btn = soup.new_tag('button')
    import_btn.attrs['type'] = 'button'
    import_btn.attrs['id'] = 'import-cohorts-btn'
    import_btn.attrs['class'] = 'btn btn-primary'
    import_icon = soup.new_tag('i')
    import_icon.attrs['class'] = 'fas fa-upload me-1'
    import_btn.append(import_icon)
    import_btn.append(' Import Cohorts')
    import_body.append(import_btn)
    
    import_card.append(import_body)
    settings_pane.append(import_card)
    
    tab_content.append(settings_pane)
    
    modal_body.append(tab_content)
    
    # Modal footer
    modal_footer = soup.new_tag('div')
    modal_footer.attrs['class'] = 'modal-footer'
    
    close_btn = soup.new_tag('button')
    close_btn.attrs['type'] = 'button'
    close_btn.attrs['class'] = 'btn btn-secondary'
    close_btn.attrs['data-bs-dismiss'] = 'modal'
    close_btn.string = 'Close'
    modal_footer.append(close_btn)
    
    modal_content.append(modal_body)
    modal_content.append(modal_footer)
    
    modal_dialog.append(modal_content)
    modal_div.append(modal_dialog)
    
    # Add the modal to the body
    soup.body.append(modal_div)
    
    # Add a button to open the modal
    button_container = soup.new_tag('div')
    button_container.attrs['style'] = 'position: fixed; top: 20px; right: 20px; z-index: 1000;'
    
    open_button = soup.new_tag('button')
    open_button.attrs['type'] = 'button'
    open_button.attrs['class'] = 'btn btn-primary'
    open_button.attrs['data-bs-toggle'] = 'modal'
    open_button.attrs['data-bs-target'] = '#cohortControlModal'
    open_button.attrs['style'] = 'box-shadow: 0 2px 5px rgba(0,0,0,0.2);'
    
    button_icon = soup.new_tag('i')
    button_icon.attrs['class'] = 'fas fa-layer-group me-1'
    open_button.append(button_icon)
    open_button.append(' Manage Cohorts')
    
    button_container.append(open_button)
    soup.body.append(button_container)
    
    # Add the JavaScript to make it interactive
    script = soup.new_tag('script')
    script.string = """
    document.addEventListener('DOMContentLoaded', function() {
        // Setup variables
        const plotlyDiv = document.getElementById('%s');
        const selectedPgsList = document.getElementById('selected-pgs-ids');
        const selectedCount = document.getElementById('selected-count');
        const pgsFileUpload = document.getElementById('pgs-file-upload');
        const pgsTextarea = document.getElementById('pgs-textarea');
        const addCohortBtn = document.getElementById('add-cohort-btn');
        const clearSelectionBtn = document.getElementById('clear-selection-btn');
        const cohortList = document.getElementById('cohort-list');
        const noCohortMessage = document.getElementById('no-cohorts-message');
        const exportCohortsBtn = document.getElementById('export-cohorts-btn');
        const importCohortsBtn = document.getElementById('import-cohorts-btn');
        const importFileInput = document.getElementById('import-file-input');
        const colorPresets = document.querySelectorAll('.color-preset');
        
        // PGS IDs from the plot
        const allPgsIds = %s;
        let selectedPgsIds = [];
        let cohorts = {};
        
        // Setup color preset buttons
        colorPresets.forEach(btn => {
            btn.addEventListener('click', function() {
                document.getElementById('cohort-color').value = this.dataset.color;
            });
        });
        
        // Handle file upload
        pgsFileUpload.addEventListener('change', function(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = function(e) {
                const content = e.target.result;
                processInputText(content);
            };
            reader.readAsText(file);
        });
        
        // Handle text area input
        pgsTextarea.addEventListener('input', function() {
            processInputText(pgsTextarea.value);
        });
        
        // Process input text (from file or textarea)
        function processInputText(text) {
            // Clear current selection
            selectedPgsIds = [];
            
            // Parse the text (supports comma-separated or newline-separated)
            const lines = text.split(/[\\n,]+/);
            
            lines.forEach(line => {
                const trimmed = line.trim();
                if (trimmed && allPgsIds.includes(trimmed)) {
                    selectedPgsIds.push(trimmed);
                }
            });
            
            // Remove duplicates
            selectedPgsIds = [...new Set(selectedPgsIds)];
            
            // Update selected list
            updateSelectedPgsList();
        }
        
        // Update the selected PGS IDs list
        function updateSelectedPgsList() {
            selectedPgsList.innerHTML = '';
            
            if (selectedPgsIds.length === 0) {
                const emptyMessage = document.createElement('div');
                emptyMessage.textContent = 'No PGS IDs selected';
                emptyMessage.className = 'text-muted fst-italic';
                selectedPgsList.appendChild(emptyMessage);
            } else {
                // Show a sample of selected IDs (first 10)
                const displayIds = selectedPgsIds.slice(0, 10);
                displayIds.forEach(id => {
                    const div = document.createElement('div');
                    div.textContent = id;
                    selectedPgsList.appendChild(div);
                });
                
                // Show "and N more" if needed
                if (selectedPgsIds.length > 10) {
                    const more = document.createElement('div');
                    more.textContent = `...and ${selectedPgsIds.length - 10} more`;
                    more.className = 'text-muted fst-italic';
                    selectedPgsList.appendChild(more);
                }
            }
            
            // Update count
            selectedCount.textContent = `${selectedPgsIds.length} IDs`;
            
            // Clear textarea
            pgsTextarea.value = '';
            
            // Clear file input
            pgsFileUpload.value = '';
        }
        
        // Handle clear selection button
        clearSelectionBtn.addEventListener('click', function() {
            selectedPgsIds = [];
            updateSelectedPgsList();
        });
        
        // Handle add cohort button
        addCohortBtn.addEventListener('click', function() {
            const cohortName = document.getElementById('cohort-name').value.trim();
            const cohortColor = document.getElementById('cohort-color').value;
            
            if (!cohortName) {
                showToast('Please enter a cohort name', 'warning');
                return;
            }
            
            if (selectedPgsIds.length === 0) {
                showToast('Please select at least one PGS ID', 'warning');
                return;
            }
            
            // Add the cohort
            cohorts[cohortName] = {
                color: cohortColor,
                ids: [...selectedPgsIds]
            };
            
            // Update cohort list
            updateCohortList();
            
            // Update plot
            updatePlotColors();
            
            // Clear the form
            document.getElementById('cohort-name').value = '';
            selectedPgsIds = [];
            updateSelectedPgsList();
            
            // Show success message
            showToast(`Cohort '${cohortName}' with ${selectedPgsIds.length} IDs added successfully`, 'success');
            
            // Switch to the manage tab
            const manageTab = new bootstrap.Tab(document.getElementById('manage-tab'));
            manageTab.show();
        });
        
// Create toast container if it doesn't exist
        if (!document.getElementById('toast-container')) {
            const toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            toastContainer.id = 'toast-container';
            document.body.appendChild(toastContainer);
        }
        
        // Function to show toast notifications
        function showToast(message, type = 'info') {
            const toastContainer = document.getElementById('toast-container');
            
            // Create toast element
            const toastEl = document.createElement('div');
            toastEl.className = `toast align-items-center border-0 bg-${type}`;
            toastEl.setAttribute('role', 'alert');
            toastEl.setAttribute('aria-live', 'assertive');
            toastEl.setAttribute('aria-atomic', 'true');
            
            const toastBody = document.createElement('div');
            toastBody.className = 'd-flex';
            
            const messageDiv = document.createElement('div');
            messageDiv.className = 'toast-body text-white';
            messageDiv.textContent = message;
            
            const closeButton = document.createElement('button');
            closeButton.type = 'button';
            closeButton.className = 'btn-close btn-close-white me-2 m-auto';
            closeButton.setAttribute('data-bs-dismiss', 'toast');
            closeButton.setAttribute('aria-label', 'Close');
            
            toastBody.appendChild(messageDiv);
            toastBody.appendChild(closeButton);
            toastEl.appendChild(toastBody);
            toastContainer.appendChild(toastEl);
            
            // Initialize and show the toast
            const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
            toast.show();
            
            // Remove toast from DOM after it's hidden
            toastEl.addEventListener('hidden.bs.toast', function() {
                toastEl.remove();
            });
        }
        
        // Update the cohort list display
        function updateCohortList() {
            cohortList.innerHTML = '';
            
            const cohortKeys = Object.keys(cohorts);
            
            if (cohortKeys.length === 0) {
                noCohortMessage.style.display = 'block';
            } else {
                noCohortMessage.style.display = 'none';
                
                cohortKeys.forEach(name => {
                    const cohort = cohorts[name];
                    
                    const listItem = document.createElement('div');
                    listItem.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
                    
                    const leftSection = document.createElement('div');
                    leftSection.className = 'd-flex align-items-center';
                    
                    const colorSwatch = document.createElement('span');
                    colorSwatch.style.display = 'inline-block';
                    colorSwatch.style.width = '16px';
                    colorSwatch.style.height = '16px';
                    colorSwatch.style.backgroundColor = cohort.color;
                    colorSwatch.style.marginRight = '10px';
                    colorSwatch.style.borderRadius = '3px';
                    leftSection.appendChild(colorSwatch);
                    
                    const nameLabel = document.createElement('span');
                    nameLabel.textContent = name;
                    leftSection.appendChild(nameLabel);
                    
                    const badgeCount = document.createElement('span');
                    badgeCount.className = 'badge bg-secondary rounded-pill ms-2';
                    badgeCount.textContent = cohort.ids.length;
                    leftSection.appendChild(badgeCount);
                    
                    listItem.appendChild(leftSection);
                    
                    const btnGroup = document.createElement('div');
                    btnGroup.className = 'btn-group btn-group-sm';
                    
                    const removeBtn = document.createElement('button');
                    removeBtn.type = 'button';
                    removeBtn.className = 'btn btn-outline-danger';
                    const removeIcon = document.createElement('i');
                    removeIcon.className = 'fas fa-trash-alt';
                    removeBtn.appendChild(removeIcon);
                    removeBtn.setAttribute('data-bs-toggle', 'tooltip');
                    removeBtn.setAttribute('title', 'Remove cohort');
                    removeBtn.addEventListener('click', function() {
                        delete cohorts[name];
                        updateCohortList();
                        updatePlotColors();
                        showToast(`Cohort '${name}' removed`, 'danger');
                    });
                    
                    btnGroup.appendChild(removeBtn);
                    listItem.appendChild(btnGroup);
                    
                    cohortList.appendChild(listItem);
                });
                
                // Initialize tooltips
                const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
                tooltipTriggerList.map(function (tooltipTriggerEl) {
                    return new bootstrap.Tooltip(tooltipTriggerEl);
                });
            }
        }
        
        // Export cohorts to JSON file
        exportCohortsBtn.addEventListener('click', function() {
            if (Object.keys(cohorts).length === 0) {
                showToast('No cohorts defined to export', 'warning');
                return;
            }
            
            const dataStr = JSON.stringify(cohorts, null, 2);
            const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
            
            const exportFileDefaultName = 'pgs_cohorts.json';
            
            const linkElement = document.createElement('a');
            linkElement.setAttribute('href', dataUri);
            linkElement.setAttribute('download', exportFileDefaultName);
            linkElement.click();
            
            showToast('Cohorts exported successfully', 'success');
        });
        
        // Import cohorts from JSON file
        importCohortsBtn.addEventListener('click', function() {
            if (!importFileInput.files || importFileInput.files.length === 0) {
                showToast('Please select a file to import', 'warning');
                return;
            }
            
            const file = importFileInput.files[0];
            
            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    const importedCohorts = JSON.parse(e.target.result);
                    
                    // Validate imported data
                    let isValid = true;
                    for (const name in importedCohorts) {
                        if (!importedCohorts[name].color || !Array.isArray(importedCohorts[name].ids)) {
                            isValid = false;
                            break;
                        }
                    }
                    
                    if (isValid) {
                        // Merge with existing cohorts (overwrite if same name)
                        const importCount = Object.keys(importedCohorts).length;
                        Object.assign(cohorts, importedCohorts);
                        updateCohortList();
                        updatePlotColors();
                        showToast(`${importCount} cohort(s) imported successfully`, 'success');
                        
                        // Switch to the manage tab
                        const manageTab = new bootstrap.Tab(document.getElementById('manage-tab'));
                        manageTab.show();
                    } else {
                        showToast('Invalid cohort data format', 'danger');
                    }
                } catch (error) {
                    showToast('Could not parse the imported file: ' + error.message, 'danger');
                }
                
                // Clear file input
                importFileInput.value = '';
            };
            reader.readAsText(file);
        });
        
        // Wait for Plotly to be fully loaded
        let checkPlotly = setInterval(function() {
            if (plotlyDiv && plotlyDiv.data && plotlyDiv.data[0]) {
                clearInterval(checkPlotly);
                console.log('Plotly loaded');
            }
        }, 100);
        
        // Update the plot colors based on cohorts
        function updatePlotColors() {
            if (!plotlyDiv || !plotlyDiv.data || !plotlyDiv.data[0]) {
                console.log('Plotly not yet loaded');
                return;
            }
            
            const data = plotlyDiv.data[0];
            
            // Create a mapping of PGS ID to color
            const pgsIdToColor = {};
            Object.keys(cohorts).forEach(name => {
                const cohort = cohorts[name];
                cohort.ids.forEach(id => {
                    pgsIdToColor[id] = cohort.color;
                });
            });
            
            // Create colors array for all points (default to red)
            const colors = [];
            let colorAssigned = false;
            
            // Assign colors based on PGS IDs in the text
            for (let i = 0; i < data.text.length; i++) {
                const text = data.text[i];
                const match = text.match(/PGS ID: (PGS\\d+)/);
                
                if (match && match[1] && pgsIdToColor[match[1]]) {
                    colors.push(pgsIdToColor[match[1]]);
                    colorAssigned = true;
                } else {
                    colors.push('red');
                }
            }
            
            // Update the marker colors
            const update = {
                'marker.color': [colors]
            };
            
            Plotly.restyle(plotlyDiv, update, [0]);
            
            // Remove any existing legend traces except the original data
            if (plotlyDiv.data.length > 1) {
                const indicesToRemove = Array.from(
                    {length: plotlyDiv.data.length - 1}, 
                    (_, i) => i + 1
                );
                Plotly.deleteTraces(plotlyDiv, indicesToRemove);
            }
            
            // Create legend entries for cohorts
            Object.keys(cohorts).forEach(name => {
                Plotly.addTraces(plotlyDiv, {
                    x: [null],
                    y: [null],
                    type: 'scatter',
                    mode: 'markers',
                    name: name,
                    marker: {color: cohorts[name].color, size: 6},
                    showlegend: true
                });
            });
            
            // Hide the original trace from legend
            const legendUpdate = {
                showlegend: false
            };
            Plotly.restyle(plotlyDiv, legendUpdate, [0]);
        }
        
        // Initialize UI
        updateSelectedPgsList();
        updateCohortList();
    });
    """ % (div_id, json.dumps(unique_pgs_ids))
    
    # Add the script to the HTML
    soup.body.append(script)
    
    # Save the modified HTML
    output_path = output_filepath or html_filepath
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    
    print(f"Interactive cohort viewer HTML saved to {output_path}") 
    return output_path

def add_interactive_filter_umap(html_file_path, output_file_path=None):
    """
    Add interactive filtering capability to a saved Plotly HTML file,
    properly extracting IDs from hover text values
    """
    # Create output path if not provided
    if output_file_path is None:
        file_name, file_ext = os.path.splitext(html_file_path)
        output_file_path = f"{file_name}_interactive{file_ext}"
        output_file_path = output_file_path[1:]
    
    # Read the original HTML file
    with open(html_file_path[1:], 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Add CSS for the filter UI
    style_tag = soup.new_tag('style')
    style_tag.string = """
    .filter-controls {
        padding: 15px;
        margin: 10px 0;
        border: 1px solid #ddd;
        border-radius: 5px;
        background-color: #f9f9f9;
        font-family: Arial, sans-serif;
    }
    .filter-row {
        display: flex;
        gap: 10px;
        margin-bottom: 10px;
        align-items: center;
    }
    .filter-input {
        flex-grow: 1;
        padding: 8px;
        border: 1px solid #ccc;
        border-radius: 4px;
    }
    .filter-button {
        padding: 8px 15px;
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    .filter-button:hover {
        background-color: #45a049;
    }
    .reset-button {
        padding: 8px 15px;
        background-color: #f44336;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    .reset-button:hover {
        background-color: #d32f2f;
    }
    #filter-status {
        margin-top: 10px;
        padding: 5px;
        color: #666;
    }
    """
    soup.head.append(style_tag)
    
    # Create filter control elements
    filter_div = soup.new_tag('div')
    filter_div['class'] = 'filter-controls'
    filter_div.append(soup.new_tag('h3'))
    filter_div.h3.string = 'Filter Points by ID'
    
    # File upload row
    file_row = soup.new_tag('div')
    file_row['class'] = 'filter-row'
    
    file_label = soup.new_tag('label')
    file_label['for'] = 'id-file-input'
    file_label.string = 'Upload ID file:'
    file_row.append(file_label)
    
    file_input = soup.new_tag('input')
    file_input['type'] = 'file'
    file_input['id'] = 'id-file-input'
    file_input['class'] = 'filter-input'
    file_input['accept'] = '.txt,.csv'
    file_row.append(file_input)
    
    apply_button = soup.new_tag('button')
    apply_button['id'] = 'apply-filter'
    apply_button['class'] = 'filter-button'
    apply_button.string = 'Apply Filter'
    file_row.append(apply_button)
    
    reset_button = soup.new_tag('button')
    reset_button['id'] = 'reset-filter'
    reset_button['class'] = 'reset-button'
    reset_button.string = 'Reset'
    file_row.append(reset_button)
    
    filter_div.append(file_row)
    
    # Manual input row
    manual_row = soup.new_tag('div')
    manual_row['class'] = 'filter-row'
    
    manual_label = soup.new_tag('label')
    manual_label['for'] = 'manual-ids'
    manual_label.string = 'Or enter IDs manually:'
    manual_row.append(manual_label)
    
    manual_input = soup.new_tag('input')
    manual_input['type'] = 'text'
    manual_input['id'] = 'manual-ids'
    manual_input['class'] = 'filter-input'
    manual_input['placeholder'] = 'Comma-separated IDs'
    manual_row.append(manual_input)
    
    manual_button = soup.new_tag('button')
    manual_button['id'] = 'apply-manual-filter'
    manual_button['class'] = 'filter-button'
    manual_button.string = 'Apply'
    manual_row.append(manual_button)
    
    filter_div.append(manual_row)
    
    # Status display
    status_div = soup.new_tag('div')
    status_div['id'] = 'filter-status'
    filter_div.append(status_div)
    
    # Find the plotly div and insert our filter controls before it
    plotly_div = soup.select_one('div.plotly-graph-div')
    if plotly_div:
        plotly_div.insert_before(filter_div)
    
    # Add the JavaScript for filtering functionality
    script_tag = soup.new_tag('script')
    script_tag.string = r"""
// JavaScript for interactive filtering with hover text ID extraction
document.addEventListener('DOMContentLoaded', function() {
    console.log('Hover text ID filter script loaded');
    
    // Store original trace data for reset functionality
    let originalTraceData = [];
    let plotDiv = document.querySelector('.plotly-graph-div');
    
    if (!plotDiv) {
        console.error('Could not find Plotly graph element');
        return;
    }
    
    console.log('Found plot div:', plotDiv.id);
    
    // Wait for Plotly to be fully initialized
    const checkPlotlyInterval = setInterval(() => {
        if (window.Plotly && plotDiv.data) {
            clearInterval(checkPlotlyInterval);
            console.log('Plotly initialized with data');
            
            // Store only the necessary data from each trace
            try {
                plotDiv.data.forEach(trace => {
                    // Create a safe copy without circular references
                    let safeCopy = {
                        x: trace.x ? trace.x.slice() : [],
                        y: trace.y ? trace.y.slice() : [],
                        mode: trace.mode,
                        type: trace.type,
                        name: trace.name,
                        text: trace.text ? (Array.isArray(trace.text) ? trace.text.slice() : trace.text) : null,
                        ids: trace.ids ? trace.ids.slice() : null,
                        customdata: trace.customdata ? trace.customdata.slice() : null,
                        hovertext: trace.hovertext ? (Array.isArray(trace.hovertext) ? trace.hovertext.slice() : trace.hovertext) : null,
                        hovertemplate: trace.hovertemplate,
                        marker: trace.marker ? {
                            size: trace.marker.size,
                            color: Array.isArray(trace.marker.color) ? trace.marker.color.slice() : trace.marker.color,
                            opacity: Array.isArray(trace.marker.opacity) ? trace.marker.opacity.slice() : trace.marker.opacity,
                            symbol: trace.marker.symbol,
                            line: trace.marker.line ? {
                                width: trace.marker.line.width,
                                color: trace.marker.line.color
                            } : null
                        } : null
                    };
                    originalTraceData.push(safeCopy);
                });
                console.log('Original trace data stored safely');
                
                // Analyze first few hover texts to detect format (for console debugging)
                analyzeHoverTextFormat();
            } catch (error) {
                console.error('Error storing original data:', error);
            }
            
            // Setup event listeners
            document.getElementById('apply-filter').addEventListener('click', function() {
                const fileInput = document.getElementById('id-file-input');
                if (fileInput.files.length > 0) {
                    processFile(fileInput.files[0]);
                } else {
                    updateStatus('Please select a file to upload', 'error');
                }
            });
            
            document.getElementById('apply-manual-filter').addEventListener('click', function() {
                const manualInput = document.getElementById('manual-ids').value.trim();
                if (manualInput) {
                    const ids = manualInput.split(',').map(id => id.trim()).filter(id => id);
                    applyFilter(ids);
                } else {
                    updateStatus('Please enter IDs to filter', 'error');
                }
            });
            
            document.getElementById('reset-filter').addEventListener('click', resetFilter);
            
            updateStatus('Filter controls ready. Upload a file with sample IDs or enter IDs manually.', 'info');
        }
    }, 200);
    
    // Analyze hover text format (for debugging in console)
    function analyzeHoverTextFormat() {
        if (!plotDiv || !plotDiv.data) {
            console.error('Plot data not available');
            return;
        }
        
        console.log('Analyzing hover text format...');
        
        plotDiv.data.forEach((trace, i) => {
            if (trace.type === 'scatter' || trace.type === 'scattergl') {
                if (!trace.text || trace.text.length === 0) {
                    console.log('No hover text found in trace ' + i);
                    return;
                }
                
                // Get first few hover texts to analyze
                const samples = Array.isArray(trace.text) ? trace.text.slice(0, 3) : [trace.text];
                
                console.log(`Sample hover texts from trace ${i}:`);
                for (let j = 0; j < samples.length; j++) {
                    const hoverText = samples[j];
                    console.log(`  Sample ${j + 1}: "${hoverText}"`);
                    
                    // Check for "Sample: XXX" pattern
                    const sampleMatch = hoverText.match(/Sample:\s*([^<]+)/);
                    if (sampleMatch && sampleMatch[1]) {
                        console.log(`    → Extracted Sample ID: "${sampleMatch[1].trim()}"`);
                    }
                    
                    // Check for "PGS ID: XXX" pattern
                    const pgsMatch = hoverText.match(/PGS ID:\s*([^<]+)/);
                    if (pgsMatch && pgsMatch[1]) {
                        console.log(`    → Extracted PGS ID: "${pgsMatch[1].trim()}"`);
                    }
                }
            }
        });
    }
    
    function extractIdFromHoverText(hoverText) {
        // If empty or invalid, return null
        if (!hoverText || typeof hoverText !== 'string') {
            return null;
        }
        
        // Try to extract Sample ID
        const sampleMatch = hoverText.match(/Sample:\s*([^<]+)/);
        if (sampleMatch && sampleMatch[1]) {
            return sampleMatch[1].trim();
        }
        
        // Try to extract PGS ID
        const pgsMatch = hoverText.match(/PGS ID:\s*([^<]+)/);
        if (pgsMatch && pgsMatch[1]) {
            return pgsMatch[1].trim();
        }
        
        // If no pattern matches, return null
        return null;
    }
    
    function processFile(file) {
        console.log('Processing file:', file.name);
        updateStatus('Reading file...', 'info');
        
        const reader = new FileReader();
        reader.onload = function(e) {
            console.log('File loaded');
            const content = e.target.result;
            let ids = [];
            
            // Simple parsing based on file extension
            if (file.name.endsWith('.csv')) {
                // Assume CSV has one ID per line or is comma-separated
                ids = content.split(/[\\r\\n,]+/).filter(id => id.trim() !== '');
            } else {
                // Assume plain text with one ID per line
                ids = content.split(/[\\r\\n]+/).filter(id => id.trim() !== '');
            }
            
            console.log(`Extracted ${ids.length} IDs from file`);
            console.log('Sample IDs from file:', ids.slice(0, 5));
            
            applyFilter(ids);
        };
        
        reader.onerror = function() {
            console.error('Error reading file');
            updateStatus('Error reading file', 'error');
        };
        
        reader.readAsText(file);
    }
    
    function applyFilter(idsToHighlight) {
        if (!plotDiv || !plotDiv.data) {
            console.error('Plot data not available');
            updateStatus('Error: Plot data not accessible', 'error');
            return;
        }
        
        console.log(`Applying filter with ${idsToHighlight.length} IDs`);
        
        // Create a set for faster lookups
        const idSet = new Set(idsToHighlight.map(id => id.trim()));
        
        // Create modified traces
        let newData = [];
        let totalMatches = 0;
        
        plotDiv.data.forEach((trace, i) => {
            // Create a new trace based on the original
            let newTrace = {};
            Object.assign(newTrace, trace);
            
            if (newTrace.type === 'scatter' || newTrace.type === 'scattergl') {
                console.log(`Processing trace ${i}, with ${newTrace.x.length} points`);
                
                // Create new marker properties
                let newMarker = {};
                if (newTrace.marker) {
                    Object.assign(newMarker, newTrace.marker);
                } else {
                    newMarker = { size: 6, color: '#1f77b4', opacity: 1 };
                }
                
                // Extract IDs from hover text
                let matchCount = 0;
                
                if (newTrace.text && newTrace.text.length > 0) {
                    // Create color and opacity arrays
                    const colors = [];
                    const opacities = [];
                    
                    // Determine original colors and create new colors
                    const originalColors = Array.isArray(newMarker.color) ? 
                        newMarker.color : 
                        Array(newTrace.x.length).fill(newMarker.color || '#1f77b4');
                    
                    const originalOpacities = Array.isArray(newMarker.opacity) ? 
                        newMarker.opacity : 
                        Array(newTrace.x.length).fill(newMarker.opacity || 1);
                    
                    // Process each point's hover text
                    for (let j = 0; j < newTrace.x.length; j++) {
                        const hoverText = Array.isArray(newTrace.text) ? newTrace.text[j] : newTrace.text;
                        const extractedId = extractIdFromHoverText(hoverText);
                        
                        if (extractedId && idSet.has(extractedId)) {
                            // Highlighted point - keep original color and opacity
                            colors.push(originalColors[j]);
                            opacities.push(originalOpacities[j]);
                            matchCount++;
                        } else {
                            // Non-highlighted point - gray color and reduced opacity
                            colors.push('#cccccc');
                            opacities.push(0.3);
                        }
                    }
                    
                    // Update marker properties
                    newMarker.color = colors;
                    newMarker.opacity = opacities;
                    newTrace.marker = newMarker;
                    
                    console.log(`Updated colors for ${matchCount} highlighted points out of ${newTrace.x.length} total points`);
                    totalMatches += matchCount;
                } else {
                    console.log('No text property found for ID extraction in trace ' + i);
                }
            }
            
            newData.push(newTrace);
        });
        
        // Update the plot with new traces
        try {
            Plotly.react(plotDiv, newData, plotDiv.layout);
            updateStatus(`Filter applied: ${totalMatches} points highlighted out of ${idsToHighlight.length} IDs`, 'success');
        } catch (error) {
            console.error('Error updating plot:', error);
            updateStatus('Error updating plot. Check browser console for details.', 'error');
        }
    }
    
    function resetFilter() {
        console.log('Resetting filter');
        
        if (originalTraceData.length > 0) {
            // Restore original data
            try {
                Plotly.react(plotDiv, originalTraceData, plotDiv.layout);
                updateStatus('Filter reset - showing all points with original colors', 'info');
            } catch (error) {
                console.error('Error resetting plot:', error);
                updateStatus('Error resetting plot. Check browser console for details.', 'error');
            }
        } else {
            updateStatus('Error: Original data not available', 'error');
        }
    }
    
    function updateStatus(message, type) {
        const statusElement = document.getElementById('filter-status');
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.style.color = type === 'error' ? '#f44336' : 
                                       type === 'success' ? '#4CAF50' : '#666';
        }
        console.log(`Status: ${message} (${type})`);
    }
});
    """
    soup.body.append(script_tag)
    
    # Write the modified HTML to the output file
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write(str(soup))
    
    print(f"Interactive filter added successfully!")
    print(f"Modified file saved to: {output_file_path}")
    return output_file_path

def add_interactive_filter_pca(html_file_path, output_file_path=None):
    """
    Add interactive filtering capability to a PCA plot HTML file,
    extracting IDs from hover text for either sample or score points
    """
    return None

def add_interactive_filter_svd(html_file_path, output_file_path=None):
    """
    Add interactive filtering capability to a SVD plot HTML file,
    extracting IDs from hover text for either sample or score points
    """
    return None

