import os
import re
from bs4 import BeautifulSoup

def add_interactive_filter(html_file_path, output_file_path=None):
    """
    Add interactive filtering capability to a saved Plotly HTML file,
    properly extracting IDs from hover text values
    """
    # Create output path if not provided
    if output_file_path is None:
        file_name, file_ext = os.path.splitext(html_file_path)
        output_file_path = f"{file_name}_interactive{file_ext}"
    
    # Read the original HTML file
    with open(html_file_path, 'r', encoding='utf-8') as file:
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
    script_tag.string = """
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

# Usage example
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        html_file_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else None
        add_interactive_filter(html_file_path, output_path)
    else:
        print("Usage: python script.py <path_to_plotly_html> [output_path]")
        print("Example: python script.py /Users/nsabry/PGSExplorer/temp_copy/temp/umap_EUR_Z_norm2_47840d20d7b2a979098455ac020e3c8e_20250403_092422.html")