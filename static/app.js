// State variables
let currentTab = 'dashboard-tab';
let surveySchema = [];
let mappingConfig = {};
let generatedRecords = [];
let selectedRecord = null;
let logInterval = null;
let statusInterval = null;

// DOM Elements
const navButtons = document.querySelectorAll('.nav-btn');
const tabContents = document.querySelectorAll('.tab-content');
const surveyUrlInput = document.getElementById('survey-url-input');
const fetchSchemaBtn = document.getElementById('fetch-schema-btn');
const schemaLoading = document.getElementById('schema-loading');
const schemaEmpty = document.getElementById('schema-empty');
const schemaTableWrapper = document.getElementById('schema-table-wrapper');
const mappingTbody = document.getElementById('mapping-tbody');
const saveMappingBtn = document.getElementById('save-mapping-btn');

// Generator elements
const generateCountInput = document.getElementById('generate-count-input');
const generateDataBtn = document.getElementById('generate-data-btn');
const clearQueueBtn = document.getElementById('clear-queue-btn');
const queueTbody = document.getElementById('queue-tbody');

// Automation elements
const submitFirst5Btn = document.getElementById('submit-first5-btn');
const submitAllBtn = document.getElementById('submit-all-btn');
const headedModeCheckbox = document.getElementById('headed-mode-checkbox');
const consoleOutput = document.getElementById('console-output');
const clearLogsBtn = document.getElementById('clear-logs-btn');

// Modal elements
const editRecordModal = document.getElementById('edit-record-modal');
const modalRecordId = document.getElementById('modal-record-id');
const modalBodyFields = document.getElementById('modal-body-fields');
const closeModalBtn = document.getElementById('close-modal');
const cancelEditBtn = document.getElementById('cancel-edit-btn');
const saveEditBtn = document.getElementById('save-edit-btn');

// Stat cards
const statTotalRecords = document.getElementById('stat-total-records');
const statSubmittedRecords = document.getElementById('stat-submitted-records');
const statReadyRecords = document.getElementById('stat-ready-records');
const statFailedRecords = document.getElementById('stat-failed-records');
const connectionStatus = document.getElementById('connection-status');

// 79 Rules list for mapping dropdown
const GENERATOR_RULES = [
    { key: "q1_name", label: "Rule 1: Ghanaian Names (Ga/Fante)" },
    { key: "q2_phone", label: "Rule 2: Ghanaian Phone Numbers" },
    { key: "q3_gender", label: "Rule 3: Gender (All Male)" },
    { key: "q4_age", label: "Rule 4: Age Range (25-49)" },
    { key: "q5_ans", label: "Rule 5: Random Option Selection" },
    { key: "q6_ans", label: "Rule 6: Dominated by first 3 options" },
    { key: "q7_ans", label: "Rule 7: Weight ranking 3,1,4,2" },
    { key: "q8_ans", label: "Rule 8: Options 1/2 (80% 1)" },
    { key: "q9_location", label: "Rule 9: Jamestown & surrounding towns" },
    { key: "q10_ans", label: "Rule 10: Options 1/2 (mostly 1)" },
    { key: "q11_ans", label: "Rule 11: Weight ranking 1,3,4,2" },
    { key: "q12_ans", label: "Rule 12: Mostly Options 2 and 3" },
    { key: "q13_num", label: "Rule 13: Numeric Range 2 to 7" },
    { key: "q14_ans", label: "Rule 14: Option 1" },
    { key: "q15_ans", label: "Rule 15: Random Option Selection" },
    { key: "q16_occupation", label: "Rule 16: Trade/Casual/Process" },
    { key: "q17_experience", label: "Rule 17: Years of experience (correlated)" },
    { key: "q18_role", label: "Rule 18: Crew members / both" },
    { key: "q19_activity", label: "Rule 19: Role tasks (correlated)" },
    { key: "q20_ans", label: "Rule 20: Options 1 or 2" },
    { key: "q21_ans", label: "Rule 21: Mostly Yes (80%)" },
    { key: "q22_group", label: "Rule 22: Fisher association/coop" },
    { key: "q23_status", label: "Rule 23: Relate to age & experience" },
    { key: "q24_issue", label: "Rule 24: Fuel/Gear/Pollution" },
    { key: "q25_ans", label: "Rule 25: 90% Yes" },
    { key: "q26_cost", label: "Rule 26: Cost Range 300 - 1200" },
    { key: "q27_intensity", label: "Rule 27: Range Low - Very High" },
    { key: "q28_ans", label: "Rule 28: 70% Yes" },
    { key: "q29_freq", label: "Rule 29: Often and occasionally" },
    { key: "q30_ans", label: "Rule 30: 55% Yes" },
    { key: "q31_level", label: "Rule 31: Moderate and high" },
    { key: "q32_ans", label: "Rule 32: 60% No" },
    { key: "q33_practice", label: "Rule 33: Light fishing / Pair trawling" },
    { key: "q34_ans", label: "Rule 34: All Yes" },
    { key: "q35_cause", label: "Rule 35: Pollution / Wear and tear" },
    { key: "q36_amount", label: "Rule 36: Amount Range 200 - 600" },
    { key: "q37_ans", label: "Rule 37: 65% Yes" },
    { key: "q38_impact", label: "Rule 38: Moderate and high" },
    { key: "q39_ans", label: "Rule 39: 90% Yes" },
    { key: "q40_ans", label: "Rule 40: 85% No" },
    { key: "q41_ans", label: "Rule 41: 67% Yes" },
    { key: "q42_freq", label: "Rule 42: Range Often - Rarely" },
    { key: "q43_ans", label: "Rule 43: 55% Yes" },
    { key: "q44_ans", label: "Rule 44: 60% Yes" },
    { key: "q45_range", label: "Rule 45: Range Moderate to High" },
    { key: "q46_ans", label: "Rule 46: 75% Yes" },
    { key: "q47_ans", label: "Rule 47: Random (least 5 and 2)" },
    { key: "q48_priority", label: "Rule 48: Frequency ranking matches" },
    { key: "q49_challenges", label: "Rule 49: Challenges text (Illiterate Eng)" },
    { key: "q50_catch", label: "Rule 50: Range 125 - 350" },
    { key: "q51_price", label: "Rule 51: Range 45 - 80" },
    { key: "q52_income", label: "Rule 52: Income 3000-7000 (correlated)" },
    { key: "q53_stability", label: "Rule 53: Range Very unstable - stable" },
    { key: "q54_freq", label: "Rule 54: Range Often - sometimes" },
    { key: "q55_ans", label: "Rule 55: 75% Yes" },
    { key: "q56_ans", label: "Rule 56: 80% Yes" },
    { key: "q57_season", label: "Rule 57: Mostly peak (60%)" },
    { key: "q58_season", label: "Rule 58: Mostly lean (60%)" },
    { key: "q59_ans", label: "Rule 59: 90% No" },
    { key: "q60_ans", label: "Rule 60: 85% No" },
    { key: "q61_ans", label: "Rule 61: 56% No" },
    { key: "q62_ans", label: "Rule 62: 77% Yes" },
    { key: "q63_ans", label: "Rule 63: 90% Yes" },
    { key: "q64_ans", label: "Rule 64: Random Option Selection" },
    { key: "q65_strength", label: "Rule 65: Range Weak to Strong" },
    { key: "q66_rating", label: "Rule 66: Range Very good to Poor" },
    { key: "q67_recommendations", label: "Rule 67: Recommendations text (Illiterate Eng)" },
    { key: "q68_ans", label: "Rule 68: 57% Yes" },
    { key: "q69_ans", label: "Rule 69: 64% No" },
    { key: "q70_ans", label: "Rule 70: 51% No" },
    { key: "q71_ans", label: "Rule 71: Weighted options 1,4,3,2" },
    { key: "q72_ans", label: "Rule 72: Weighted options 3,1,4,5,6,2" },
    { key: "q73_ans", label: "Rule 73: 71% Yes" },
    { key: "q74_ans", label: "Rule 74: 85% Yes" },
    { key: "q75_ans", label: "Rule 75: 72% No" },
    { key: "q76_ans", label: "Rule 76: All Yes" },
    { key: "q77_ans", label: "Rule 77: 85% Yes" },
    { key: "q78_ans", label: "Rule 78: Mostly yes for older ages" },
    { key: "q79_ans", label: "Rule 79: Match response to Q67" }
];

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    setupTabNavigation();
    setupEventListeners();
    fetchStatus();
    loadSubmissions();
    
    // Start status polling
    statusInterval = setInterval(fetchStatus, 3000);
});

// Setup sidebar tab navigation
function setupTabNavigation() {
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            navButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(targetTab).classList.add('active');
            
            currentTab = targetTab;
            
            if (currentTab === 'generator-tab') {
                loadSubmissions();
            }
        });
    });
}

function setupEventListeners() {
    fetchSchemaBtn.addEventListener('click', fetchSurveySchema);
    saveMappingBtn.addEventListener('click', saveMapping);
    generateDataBtn.addEventListener('click', generateDataset);
    clearQueueBtn.addEventListener('click', clearQueue);
    submitFirst5Btn.addEventListener('click', () => runAutomation(true)); // Test first 5
    submitAllBtn.addEventListener('click', () => runAutomation(false)); // Run all
    clearLogsBtn.addEventListener('click', () => { consoleOutput.innerText = ''; });
    
    // Modal close events
    closeModalBtn.addEventListener('click', hideModal);
    cancelEditBtn.addEventListener('click', hideModal);
    saveEditBtn.addEventListener('click', saveEditedRecord);
}

// Fetch general server status
async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        statTotalRecords.innerText = data.records_count;
        connectionStatus.innerHTML = '<span class="status-dot green"></span> Connected';
        
        if (data.automation_running) {
            submitFirst5Btn.disabled = true;
            submitAllBtn.disabled = true;
            generateDataBtn.disabled = true;
            clearQueueBtn.disabled = true;
            
            if (!logInterval) {
                logInterval = setInterval(fetchLogs, 1000);
            }
        } else {
            if (logInterval) {
                clearInterval(logInterval);
                logInterval = null;
                fetchLogs(); // one last fetch
                loadSubmissions(); // reload statuses
            }
            
            // Enable buttons if we have records
            const hasRecords = data.records_count > 0;
            submitFirst5Btn.disabled = !hasRecords;
            submitAllBtn.disabled = !hasRecords;
            generateDataBtn.disabled = false;
            clearQueueBtn.disabled = !hasRecords;
        }
    } catch (err) {
        console.error(err);
        connectionStatus.innerHTML = '<span class="status-dot orange"></span> Connection Error';
    }
}

// Fetch logs from background worker
async function fetchLogs() {
    try {
        const res = await fetch('/api/submit/logs');
        const data = await res.json();
        if (data.logs) {
            consoleOutput.innerText = data.logs;
            // Scroll to bottom
            const wrapper = consoleOutput.parentElement;
            wrapper.scrollTop = wrapper.scrollHeight;
        }
    } catch (err) {
        console.error(err);
    }
}

// Fetch KoboToolbox HTML Schema via Playwright
async function fetchSurveySchema() {
    const url = surveyUrlInput.value.trim();
    if (!url) {
        alert("Please enter a valid survey link.");
        return;
    }
    
    fetchSchemaBtn.disabled = true;
    schemaLoading.style.display = 'block';
    schemaEmpty.style.display = 'none';
    schemaTableWrapper.style.display = 'none';
    
    try {
        const res = await fetch('/api/schema/fetch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await res.json();
        
        if (data.success) {
            surveySchema = data.schema;
            mappingConfig = data.mapping;
            renderMappingTable();
            schemaTableWrapper.style.display = 'block';
        } else {
            alert("Failed to fetch schema: " + data.detail);
            schemaEmpty.style.display = 'block';
        }
    } catch (err) {
        console.error(err);
        alert("Error connecting to backend server.");
        schemaEmpty.style.display = 'block';
    } finally {
        fetchSchemaBtn.disabled = false;
        schemaLoading.style.display = 'none';
    }
}

// Render mapping table rows
function renderMappingTable() {
    mappingTbody.innerHTML = '';
    
    surveySchema.forEach(q => {
        const tr = document.createElement('tr');
        
        // Col 1: Index
        const tdIdx = document.createElement('td');
        tdIdx.innerText = q.index;
        tr.appendChild(tdIdx);
        
        // Col 2: Label
        const tdLabel = document.createElement('td');
        tdLabel.innerText = q.label;
        tdLabel.style.fontWeight = '500';
        tr.appendChild(tdLabel);
        
        // Col 3: Type
        const tdType = document.createElement('td');
        tdType.innerHTML = `<span class="badge badge-ready">${q.type}</span>`;
        tr.appendChild(tdType);
        
        // Col 4: Name
        const tdName = document.createElement('td');
        tdName.innerText = q.name;
        tdName.style.fontFamily = 'monospace';
        tdName.style.color = 'var(--text-secondary)';
        tr.appendChild(tdName);
        
        // Col 5: Dropdown mapping selector
        const tdMap = document.createElement('td');
        const select = document.createElement('select');
        select.className = 'mapping-select';
        select.setAttribute('data-qname', q.name);
        
        // Populate rule options
        GENERATOR_RULES.forEach(rule => {
            const opt = document.createElement('option');
            opt.value = rule.key;
            opt.innerText = rule.label;
            
            // Check if mapped
            if (mappingConfig[q.name] === rule.key) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });
        
        tdMap.appendChild(select);
        tr.appendChild(tdMap);
        
        mappingTbody.appendChild(tr);
    });
}

// Save Mapping Configuration
async function saveMapping() {
    const selects = document.querySelectorAll('.mapping-select');
    selects.forEach(select => {
        const qname = select.getAttribute('data-qname');
        mappingConfig[qname] = select.value;
    });
    
    try {
        const res = await fetch('/api/data/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mapping: mappingConfig, count: 0 }) // count 0 just updates configuration without generating new dataset
        });
        const data = await res.json();
        if (data.success) {
            alert("Mapping configuration saved successfully.");
        } else {
            alert("Failed to save mapping: " + data.detail);
        }
    } catch (err) {
        console.error(err);
        alert("Error saving mapping.");
    }
}

// Generate new synthetic responses dataset
async function generateDataset() {
    // Compile latest mapping config first
    const selects = document.querySelectorAll('.mapping-select');
    selects.forEach(select => {
        const qname = select.getAttribute('data-qname');
        mappingConfig[qname] = select.value;
    });

    const count = parseInt(generateCountInput.value) || 95;
    generateDataBtn.disabled = true;
    
    try {
        const res = await fetch('/api/data/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mapping: mappingConfig, count: count })
        });
        const data = await res.json();
        
        if (data.success) {
            generatedRecords = data.records;
            renderQueueTable();
            fetchStatus();
            alert(`Successfully generated ${data.count} records according to your rules.`);
        } else {
            alert("Failed to generate data: " + data.detail);
        }
    } catch (err) {
        console.error(err);
        alert("Error generating data.");
    } finally {
        generateDataBtn.disabled = false;
    }
}

// Fetch submissions from server and render queue
async function loadSubmissions() {
    try {
        const res = await fetch('/api/submissions');
        const data = await res.json();
        generatedRecords = data;
        renderQueueTable();
        
        // Count statuses
        let submitted = 0;
        let ready = 0;
        let failed = 0;
        
        data.forEach(r => {
            if (r.status === 'Submitted') submitted++;
            else if (r.status === 'Failed') failed++;
            else ready++;
        });
        
        statSubmittedRecords.innerText = submitted;
        statReadyRecords.innerText = ready;
        statFailedRecords.innerText = failed;
    } catch (err) {
        console.error(err);
    }
}

// Render submissions queue table
function renderQueueTable() {
    queueTbody.innerHTML = '';
    
    if (generatedRecords.length === 0) {
        queueTbody.innerHTML = `<tr><td colspan="9" class="text-center">No records generated. Click "Generate Dataset" to start.</td></tr>`;
        return;
    }
    
    generatedRecords.forEach(r => {
        const tr = document.createElement('tr');
        
        tr.innerHTML = `
            <td>${r.id}</td>
            <td><strong>${r.q1_name}</strong></td>
            <td>${r.q2_phone}</td>
            <td>${r.q4_age}</td>
            <td>${r.q17_experience} yrs</td>
            <td>GHS ${r.q52_income}</td>
            <td>${r.q9_location}</td>
            <td><span class="badge badge-${r.status.toLowerCase()}">${r.status}</span></td>
            <td>
                <button class="btn btn-secondary btn-edit" style="padding: 5px 10px; font-size: 12px;" onclick="editRecord(${r.id})">
                    <i class="fa-solid fa-pen-to-square"></i> Edit
                </button>
            </td>
        `;
        
        queueTbody.appendChild(tr);
    });
}

// Clear submissions queue
async function clearQueue() {
    if (!confirm("Are you sure you want to clear all submissions in the queue?")) return;
    
    try {
        const res = await fetch('/api/submissions/clear', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            loadSubmissions();
            fetchStatus();
        }
    } catch (err) {
        console.error(err);
    }
}

// Edit a submission record
window.editRecord = function(id) {
    selectedRecord = generatedRecords.find(r => r.id === id);
    if (!selectedRecord) return;
    
    modalRecordId.innerText = selectedRecord.id;
    modalBodyFields.innerHTML = '';
    
    // Render fields (show main survey fields)
    const editableFields = [
        { key: "q1_name", label: "Full Name (Q1)", type: "text" },
        { key: "q2_phone", label: "Phone Number (Q2)", type: "text" },
        { key: "q3_gender", label: "Gender (Q3)", type: "select", options: ["Male", "Female"] },
        { key: "q4_age", label: "Age (Q4)", type: "number" },
        { key: "q9_location", label: "Location (Q9)", type: "text" },
        { key: "q13_num", label: "Household size (Q13)", type: "number" },
        { key: "q16_occupation", label: "Primary occupation (Q16)", type: "text" },
        { key: "q17_experience", label: "Fishing Experience (Q17)", type: "number" },
        { key: "q18_role", label: "Role in fishery (Q18)", type: "text" },
        { key: "q26_cost", label: "Cost (Q26)", type: "number" },
        { key: "q36_amount", label: "Amount (Q36)", type: "number" },
        { key: "q49_challenges", label: "Challenges Open Text (Q49)", type: "textarea" },
        { key: "q52_income", label: "Income (Q52)", type: "number" },
        { key: "q67_recommendations", label: "Recommendations Open Text (Q67)", type: "textarea" }
    ];
    
    editableFields.forEach(f => {
        const div = document.createElement('div');
        div.className = f.type === 'textarea' ? 'form-group form-group-full' : 'form-group';
        
        const label = document.createElement('label');
        label.innerText = f.label;
        div.appendChild(label);
        
        const val = selectedRecord[f.key] !== undefined ? selectedRecord[f.key] : '';
        
        if (f.type === 'textarea') {
            const el = document.createElement('textarea');
            el.className = 'edit-field';
            el.setAttribute('data-key', f.key);
            el.value = val;
            div.appendChild(el);
        } else if (f.type === 'select') {
            const el = document.createElement('select');
            el.className = 'edit-field';
            el.setAttribute('data-key', f.key);
            f.options.forEach(opt => {
                const o = document.createElement('option');
                o.value = opt;
                o.innerText = opt;
                if (opt === val) o.selected = true;
                el.appendChild(o);
            });
            div.appendChild(el);
        } else {
            const el = document.createElement('input');
            el.type = f.type;
            el.className = 'edit-field';
            el.setAttribute('data-key', f.key);
            el.value = val;
            div.appendChild(el);
        }
        
        modalBodyFields.appendChild(div);
    });
    
    // Show Modal
    editRecordModal.style.display = 'flex';
};

function hideModal() {
    editRecordModal.style.display = 'none';
    selectedRecord = null;
}

// Save edited record to server
async function saveEditedRecord() {
    if (!selectedRecord) return;
    
    const fields = document.querySelectorAll('.edit-field');
    const updatedData = {};
    
    fields.forEach(el => {
        const key = el.getAttribute('data-key');
        let val = el.value;
        
        // Parse numerical values
        const inputType = el.getAttribute('type');
        if (inputType === 'number') {
            val = parseInt(val) || 0;
        }
        updatedData[key] = val;
    });
    
    // Copy q67 response to q79 as specified by Rule 79
    if (updatedData["q67_recommendations"]) {
        updatedData["q79_ans"] = updatedData["q67_recommendations"];
    }
    
    try {
        const res = await fetch('/api/submissions/edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: selectedRecord.id, data: updatedData })
        });
        const data = await res.json();
        if (data.success) {
            hideModal();
            loadSubmissions();
        } else {
            alert("Failed to save: " + data.detail);
        }
    } catch (err) {
        console.error(err);
        alert("Error saving record.");
    }
}

// Run Playwright Browser Automation
async function runAutomation(testFirst5Only) {
    const url = surveyUrlInput.value.trim();
    if (!url) {
        alert("Please enter a valid survey link.");
        return;
    }
    
    let idsToSubmit = [];
    if (testFirst5Only) {
        // Take the first 5 records
        idsToSubmit = generatedRecords.slice(0, 5).map(r => r.id);
        if (idsToSubmit.length === 0) {
            alert("No records in queue. Generate dataset first.");
            return;
        }
    } else {
        // Take all records that are not already submitted successfully
        idsToSubmit = generatedRecords.filter(r => r.status !== 'Submitted').map(r => r.id);
        if (idsToSubmit.length === 0) {
            alert("All records in queue are already marked as Submitted.");
            return;
        }
    }
    
    const headed = headedModeCheckbox.checked;
    
    // Switch to logs tab
    navButtons.forEach(b => b.classList.remove('active'));
    tabContents.forEach(c => c.classList.remove('active'));
    document.querySelector('[data-tab="logs-tab"]').classList.add('active');
    document.getElementById('logs-tab').classList.add('active');
    currentTab = 'logs-tab';
    
    consoleOutput.innerText = "Launching automation process...\n";
    
    try {
        const res = await fetch('/api/submit/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                ids: idsToSubmit,
                headed: headed
            })
        });
        const data = await res.json();
        if (data.success) {
            // Automation started successfully, fetchStatus will handle triggering periodic log downloads
            fetchStatus();
        } else {
            alert("Failed to start automation: " + data.detail);
        }
    } catch (err) {
        console.error(err);
        alert("Error starting automation.");
    }
}
