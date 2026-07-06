import asyncio
import json
import os
import sys

# Set custom browser download path inside project directory to avoid Windows AppData EPERM errors
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(BASE_DIR, "browsers")

from playwright.async_api import async_playwright

# Shared log function to print and write logs
log_file_path = os.path.join(os.path.dirname(__file__), "automation.log")

def write_log(message):
    print(message)
    sys.stdout.flush()
    try:
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass

async def fetch_schema(url):
    """
    Navigates to the survey URL and extracts the form schema (questions and options)
    """
    write_log(f"Fetching schema from {url}...")
    async with async_playwright() as p:
        # Launch browser (headless since this is just parsing)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            # Wait for form to render (check for question elements)
            await page.wait_for_selector(".question", timeout=20000)
            
            # Extract questions
            questions = await page.evaluate("""() => {
                const questionElements = document.querySelectorAll('.question');
                const schema = [];
                
                questionElements.forEach((el, index) => {
                    // Extract label text
                    const labelEl = el.querySelector('.question-label');
                    const labelText = labelEl ? labelEl.innerText.trim() : `Question ${index + 1}`;
                    
                    // Extract name attribute from input/select/textarea
                    const inputEl = el.querySelector('input, select, textarea');
                    if (!inputEl) return;
                    
                    const name = inputEl.getAttribute('name');
                    const type = inputEl.tagName.toLowerCase() === 'select' ? 'select' : 
                                 (inputEl.getAttribute('type') || 'text');
                                 
                    // Extract options if it's select or radio/checkbox
                    const options = [];
                    if (type === 'select') {
                        el.querySelectorAll('option').forEach(opt => {
                            const val = opt.getAttribute('value');
                            if (val) {
                                options.push({ label: opt.innerText.trim(), value: val });
                            }
                        });
                    } else {
                        // Check for options in radio/checkbox wrappers
                        el.querySelectorAll('.option-wrapper label, label.option').forEach(optLabel => {
                            const optInput = optLabel.querySelector('input');
                            const optTextSpan = optLabel.querySelector('span');
                            if (optInput && optTextSpan) {
                                options.push({ 
                                    label: optTextSpan.innerText.trim(), 
                                    value: optInput.getAttribute('value') 
                                });
                            }
                        });
                    }
                    
                    schema.push({
                        index: index + 1,
                        name: name,
                        label: labelText,
                        type: type,
                        options: options
                    });
                });
                return schema;
            }""")
            
            write_log(f"Successfully fetched {len(questions)} questions.")
            return questions
            
        except Exception as e:
            write_log(f"Error fetching schema: {str(e)}")
            raise e
        finally:
            await browser.close()

async def fill_question(page, question, value):
    """
    Fills out a single question on the active page
    """
    try:
        # Locate the question container
        name = question["name"]
        q_type = question["type"]
        
        # Check if the question container is visible in the DOM
        # In Enketo, disabled/hidden questions might have class "disabled" or "or-appearance-..."
        container = page.locator(f".question:has([name='{name}'])").first
        
        # Wait for container to be visible with retries
        for _ in range(3):
            try:
                await container.wait_for(state="visible", timeout=5000)
                break
            except:
                await asyncio.sleep(0.5)
        
        # Scroll container into view
        await container.scroll_into_view_if_needed()
        await asyncio.sleep(0.3)
        
        # Check if visible and enabled
        if not await container.is_visible() or "disabled" in (await container.get_attribute("class") or ""):
            # Question is skipped by logic, ignore it
            return True
            
        if q_type in ["text", "number", "tel", "date"]:
            # Standard input field
            input_field = container.locator(f"input[name='{name}'], textarea[name='{name}']").first
            await input_field.scroll_into_view_if_needed()
            await input_field.wait_for(state="visible", timeout=5000)
            await input_field.fill(str(value))
            # Trigger change events
            await input_field.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
            
        elif q_type == "select":
            # Dropdown
            select_field = container.locator(f"select[name='{name}']").first
            await select_field.scroll_into_view_if_needed()
            await select_field.wait_for(state="visible", timeout=5000)
            # Find the best value match
            opt_val = value
            for opt in question["options"]:
                if opt["label"].lower() == str(value).lower() or opt["value"].lower() == str(value).lower():
                    opt_val = opt["value"]
                    break
            await select_field.select_option(opt_val)
            await select_field.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
            
        elif q_type in ["radio", "checkbox"]:
            # Single or multi choice selection
            # We want to select the input where option label or value matches 'value'
            inputs = await container.locator("input").all()
            found = False
            for inp in inputs:
                inp_val = await inp.get_attribute("value")
                # Get the label text associated with this input
                # In Enketo, it's usually inside a label element or a sibling span
                # We can check the text content of the parent label element
                parent_label = page.locator(f"label:has(input[name='{name}'][value='{inp_val}'])").first
                label_text = await parent_label.inner_text()
                label_text = label_text.strip().lower()
                
                # Check for match (either exact value or label match)
                val_str = str(value).lower()
                # E.g. matching "Option 1" or value "1"
                if val_str == inp_val.lower() or val_str in label_text or label_text in val_str:
                    await inp.scroll_into_view_if_needed()
                    await inp.check(force=True)
                    await inp.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
                    found = True
                    if q_type == "radio":
                        break # Only check one for radio
            
            if not found and inputs:
                # Fallback: check the first option or matching index if it's a number
                try:
                    if str(value).isdigit():
                        idx = int(value) - 1
                        if 0 <= idx < len(inputs):
                            await inputs[idx].scroll_into_view_if_needed()
                            await inputs[idx].check(force=True)
                            await inputs[idx].evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
                    else:
                        # Direct value fallback
                        fallback_input = container.locator(f"input[value='{value}']").first
                        await fallback_input.scroll_into_view_if_needed()
                        await fallback_input.check(force=True)
                except Exception:
                    pass
                    
        return True
    except Exception as e:
        write_log(f"Warning: failed to fill question '{question['label']}': {str(e)}")
        return False

async def submit_single_record(page, url, record, mapping):
    """
    Fills out and submits a single survey response
    """
    write_log(f"Starting submission for Record #{record['id']} ({record['q1_name']})...")
    
    # Navigate to survey page and wait for loading
    await page.goto(url, wait_until="networkidle", timeout=60000)
    await page.wait_for_selector(".question", timeout=20000)
    await asyncio.sleep(2) # Allow client-side scripts to run fully
    
    # Process page by page
    is_last_page = False
    pages_filled = 0
    max_pages = 20 # Safety cap
    
    while not is_last_page and pages_filled < max_pages:
        pages_filled += 1
        write_log(f"Filling page {pages_filled}...")
        
        # Find all questions on the current page that are visible and not disabled
        # Enketo forms can be single-page or multi-page.
        # If multi-page, the active page usually has class .current or has elements that are visible.
        # We can just iterate through our mapped questions. For each question, if it is visible, fill it.
        for q_key, rule_key in mapping.items():
            # Get the question schema details
            q_schema = next((q for q in mapping["_schema"] if q["name"] == q_key), None)
            if not q_schema:
                continue
                
            # Get the generated value from the record
            value = record.get(rule_key)
            if value is None:
                continue
                
            # Fill if visible on current page
            await fill_question(page, q_schema, value)
            
        await asyncio.sleep(1) # Small pause
        
        # Check if "Next" button is visible and enabled
        next_button = page.locator("a.next-page").first
        submit_button = page.locator("button#submit-form").first
        
        # In Enketo:
        # - If multi-page: Next button is visible and active. The last page hides or disables it.
        # - If single-page: Next button is not visible or doesn't exist, and Submit button is directly visible.
        next_visible = await next_button.is_visible()
        next_disabled = "disabled" in (await next_button.get_attribute("class") or "") if next_visible else True
        
        if next_visible and not next_disabled:
            write_log("Clicking Next page...")
            await next_button.scroll_into_view_if_needed()
            await next_button.click()
            await asyncio.sleep(2) # Wait for page transition
        else:
            is_last_page = True
            write_log("Reached last page. Submitting form...")
            
            # Scroll submit button into view and wait for it to be visible
            await submit_button.scroll_into_view_if_needed()
            await submit_button.wait_for(state="visible", timeout=10000)
            # Click Submit with force option
            await submit_button.click(force=True)
            
            # Wait for success dialog or page redirect/reset
            # Enketo displays a success message or a queue increment
            try:
                # Wait for feedback bar success
                success_banner = page.locator("#feedback-bar.success, .alert-box.success, .submission-success").first
                # Or wait for form to reset (loader shows up again or inputs clear)
                # Let's wait up to 15 seconds for a success signal
                await page.wait_for_selector("#feedback-bar:not(.warning):not(.error), .alert-box:not(.warning)", timeout=15000)
                write_log("Form submitted successfully!")
                await asyncio.sleep(2)
                return True
            except Exception:
                # Check if there is an error banner
                error_banner = page.locator("#feedback-bar.error, .alert-box.danger, .error-message").first
                if await error_banner.is_visible():
                    err_txt = await error_banner.inner_text()
                    write_log(f"Submission failed with error: {err_txt.strip()}")
                else:
                    write_log("Form submitted. (No explicit success dialog detected, but no error shown. Treating as success.)")
                    return True
                return False

    return False

async def run_automation_loop(url, records, mapping, headed=True):
    """
    Runs the automation loop for all provided records
    """
    if os.path.exists(log_file_path):
        os.remove(log_file_path)
        
    write_log(f"Starting automation loop for {len(records)} records...")
    
    async with async_playwright() as p:
        # Launch chromium (headed if requested so user can see it)
        browser = await p.chromium.launch(headless=not headed)
        # Create context
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        results = []
        for record in records:
            record_id = record["id"]
            write_log(f"\n--- Submitting Record {record_id} of {len(records)} ---")
            
            # Mark status as pending
            record["status"] = "Pending"
            
            success = False
            retries = 2
            for attempt in range(retries):
                try:
                    success = await submit_single_record(page, url, record, mapping)
                    if success:
                        break
                    else:
                        write_log(f"Attempt {attempt + 1} failed. Retrying...")
                except Exception as e:
                    write_log(f"Error on attempt {attempt + 1}: {str(e)}")
                    if attempt < retries - 1:
                        await asyncio.sleep(5)
            
            if success:
                record["status"] = "Submitted"
                write_log(f"Record #{record_id} successfully submitted!")
            else:
                record["status"] = "Failed"
                write_log(f"Record #{record_id} failed all submission attempts.")
                
            results.append(record)
            # Short wait between submissions
            await asyncio.sleep(3)
            
        await browser.close()
        write_log("\nAutomation loop finished!")
        return results

if __name__ == "__main__":
    # Test script entry point
    if len(sys.argv) < 3:
        print("Usage: python automation.py <url> <records_json_path> <mapping_json_path>")
        sys.exit(1)
        
    url = sys.argv[1]
    with open(sys.argv[2], "r") as f:
        records = json.load(f)
    with open(sys.argv[3], "r") as f:
        mapping = json.load(f)
        
    asyncio.run(run_automation_loop(url, records, mapping, headed=True))
