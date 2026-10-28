"""
LocalPilot — Autonomous Browser Agent Service
Module 5: Semantic Web Automation Loop via Playwright + Ollama (Qwen)

Qwen acts as the autonomous driver:
  1. Inspects the interactive DOM state (clickable elements, inputs with unique indexed tags [e0, e1, ...])
  2. Generates structured JSON browser actions:
     - {"action": "navigate", "url": "https://..."}
     - {"action": "click", "element_id": "e3"}
     - {"action": "type", "element_id": "e2", "text": "...", "press_enter": true}
     - {"action": "finish", "answer": "..."}
  3. Playwright executes the action live in the visible browser (headless=False)
  4. Loop repeats until the task is complete or max steps reached
"""

import json
import logging
import re
from typing import Tuple, Optional, Dict, Any, List, Callable
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
import ollama

logger = logging.getLogger("LocalPilot.BrowserAgent")

OLLAMA_MODEL = "qwen2.5:3b"
MAX_AGENT_STEPS = 10

_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None
_playwright = None

# Global control flags for Human-in-the-Loop guidance
_is_paused: bool = False
_should_go_back: bool = False
_should_stop: bool = False


def pause_agent() -> bool:
    """Toggles pause/resume state."""
    global _is_paused
    _is_paused = not _is_paused
    logger.info(f"Agent pause state set to: {_is_paused}")
    return _is_paused


def is_paused() -> bool:
    return _is_paused


def infer_initial_url(task_description: str) -> str:
    """
    Uses Qwen to infer the best starting URL from the user's natural language task prompt,
    falling back to regex extraction or Google search.
    """
    # 1. Check if the user explicitly provided an explicit URL or domain in the prompt
    explicit_match = re.search(r"(https?://\S+|[\w-]+\.(?:com|org|io|net|edu|gov)(?:/\S*)?)", task_description, re.IGNORECASE)
    if explicit_match:
        url = explicit_match.group(1).rstrip(",.!?")
        if not url.startswith("http"):
            url = "https://" + url
        logger.info(f"Explicit URL found in task: {url}")
        return url

    # 2. Ask Qwen to infer the target starting web address
    prompt = (
        "Given the user's task prompt, output the single best starting website URL (e.g., https://github.com, https://amazon.com, https://google.com).\n"
        "Output ONLY the raw URL starting with https:// and nothing else.\n\n"
        f"Task: {task_description}\n"
        "URL:"
    )
    try:
        res = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0, "num_predict": 32}
        )
        url_cand = res["message"]["content"].strip()
        url_match = re.search(r"https?://[^\s\"']+", url_cand)
        if url_match:
            inferred = url_match.group(0).rstrip(",.!?")
            logger.info(f"Qwen inferred initial starting URL: {inferred}")
            return inferred
    except Exception as e:
        logger.warning(f"Failed to infer URL with Qwen: {e}")

    # 3. Universal fallback: start at Google Search for the task
    encoded = task_description.replace(" ", "+")
    return f"https://www.google.com/search?q={encoded}"


def trigger_go_back() -> None:
    """Instructs the agent loop to navigate one step back."""
    global _should_go_back
    _should_go_back = True
    logger.info("Human triggered go back command.")


def stop_agent() -> None:
    """Stops the active agent loop."""
    global _should_stop
    _should_stop = True
    logger.info("Human triggered stop command.")


def _ensure_browser() -> Page:
    """Launches or reuses a visible Chromium browser and returns the active page."""
    global _browser, _context, _page, _playwright

    if _page and not _page.is_closed():
        return _page

    close_browser()

    logger.info("Launching visible Chromium browser (headless=False)...")
    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(
        headless=False,
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
    )
    _context = _browser.new_context(
        no_viewport=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    _page = _context.new_page()
    return _page


def close_browser() -> None:
    """Closes the browser and cleans up Playwright resources."""
    global _browser, _context, _page, _playwright

    try:
        if _page and not _page.is_closed():
            _page.close()
    except Exception:
        pass
    try:
        if _context:
            _context.close()
    except Exception:
        pass
    try:
        if _browser:
            _browser.close()
    except Exception:
        pass
    try:
        if _playwright:
            _playwright.stop()
    except Exception:
        pass

    _page = None
    _context = None
    _browser = None
    _playwright = None
    logger.info("Browser closed and Playwright resources cleaned up.")


def is_browser_open() -> bool:
    """Checks whether a browser window is currently open."""
    return _page is not None and not _page.is_closed()


def _get_interactive_elements_and_snapshot(page: Page) -> Tuple[List[Dict[str, Any]], str]:
    """
    Scans the current DOM for interactive elements (inputs, buttons, links, search triggers),
    tags them with data-localpilot-id, and extracts a simplified textual representation for Qwen.
    """
    js_extract = """
    () => {
        // Clear previous markers
        document.querySelectorAll('[data-localpilot-id]').forEach(el => el.removeAttribute('data-localpilot-id'));

        const interactiveSelectors = 'input, button, a, [role="button"], [role="searchbox"], textarea, select, [contenteditable="true"]';
        const elements = Array.from(document.querySelectorAll(interactiveSelectors));

        const visibleItems = [];
        let index = 0;

        for (const el of elements) {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            const isVisible = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
            if (!isVisible) continue;

            const id = 'e' + index;
            el.setAttribute('data-localpilot-id', id);

            let label = el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || el.getAttribute('name') || el.value || '';
            label = label.replace(/\\s+/g, ' ').trim().slice(0, 100);

            const tagName = el.tagName.toLowerCase();
            const type = el.getAttribute('type') || '';

            visibleItems.push({
                id: id,
                tag: tagName,
                type: type,
                label: label,
                href: el.getAttribute('href') || ''
            });

            index++;
            if (index >= 60) break; // Keep representation focused for 3B context
        }

        return visibleItems;
    }
    """
    try:
        elements = page.evaluate(js_extract)
    except Exception as e:
        logger.warning(f"Error evaluating interactive elements: {e}")
        elements = []

    # Get clean text overview from main content area (or body) for semantic context
    try:
        if page.locator("main").count() > 0 and page.locator("main").first.is_visible(timeout=1000):
            raw_text = page.inner_text("main", timeout=2000)
        elif page.locator("article").count() > 0 and page.locator("article").first.is_visible(timeout=1000):
            raw_text = page.inner_text("article", timeout=2000)
        else:
            raw_text = page.inner_text("body", timeout=2000)

        raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)
        raw_text = re.sub(r"[ \t]{2,}", " ", raw_text).strip()
        body_snippet = raw_text[:3000]
    except Exception:
        body_snippet = ""

    return elements, body_snippet


def _decide_next_action(
    task: str,
    current_url: str,
    elements: List[Dict[str, Any]],
    page_snippet: str,
    history: List[str]
) -> Dict[str, Any]:
    """Asks Qwen to decide the next action based on current state and goal."""

    elem_lines = []
    for item in elements:
        label_part = f'"{item["label"]}"' if item["label"] else "(no text)"
        type_part = f'[{item["type"]}]' if item["type"] else ""
        elem_lines.append(f'[{item["id"]}] <{item["tag"]}{type_part}> {label_part}')

    elements_text = "\n".join(elem_lines[:25])
    history_text = "\n".join(history[-3:]) if history else "(None)"

    system_prompt = (
        "You are an autonomous web browser agent. Complete the user task by outputting EXACTLY ONE JSON action.\n\n"
        "ACTIONS:\n"
        '1. {"action": "navigate", "url": "https://..."}\n'
        '2. {"action": "click", "element_id": "e0"}\n'
        '3. {"action": "type", "element_id": "e1", "text": "...", "press_enter": true}  (ONLY use for <input> or <textarea> elements!)\n'
        '4. {"action": "finish", "answer": "..."}\n\n'
        "RULES:\n"
        "- If the answer to the TASK is visible in the SNIPPET or in the element labels, immediately return action 'finish' with the answer.\n"
        "- NEVER use 'type' on links <a> or buttons <button>; use 'click' instead.\n"
        "- Output ONLY raw JSON. No markdown fences."
    )

    user_prompt = (
        f"TASK: {task}\n"
        f"URL: {current_url}\n"
        f"PREVIOUS: {history_text}\n"
        f"ELEMENTS:\n{elements_text}\n"
        f"SNIPPET: {page_snippet[:1200]}\n"
        "JSON action:"
    )

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            options={
                "temperature": 0.1,
                "num_predict": 128
            }
        )
        content = response["message"]["content"].strip()

        # Parse JSON from model output (handling possible markdown fences)
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            action = json.loads(json_match.group(0))
            return action
        else:
            return {"action": "error", "raw": content}

    except Exception as e:
        logger.error(f"Error querying Qwen action: {e}")
        return {"action": "error", "error": str(e)}


def browse_and_answer(
    task_description: str,
    on_step: Optional[Callable[[int, int, str, str], None]] = None
) -> Tuple[bool, str, str]:
    """
    Executes the autonomous Playwright + Qwen navigation loop.
    Calls on_step(current_step, max_steps, action_summary, current_url) at each phase.
    Returns: (success: bool, answer_or_error: str, final_url: str)
    """
    try:
        page = _ensure_browser()
        history: List[str] = []

        if on_step:
            on_step(0, MAX_AGENT_STEPS, "Initializing browser window...", page.url)

        # If starting on blank page, infer initial target URL from the user's prompt using Qwen
        current_url = page.url
        if current_url == "about:blank" or not current_url.startswith("http"):
            if on_step:
                on_step(0, MAX_AGENT_STEPS, "Inferring target website from task...", "about:blank")
            initial_target = infer_initial_url(task_description)
            logger.info(f"[Step 0] Inferred starting navigation: {initial_target}")
            print(f"\n[BrowserAgent] Target inferred -> Navigating to {initial_target}...", flush=True)
            if on_step:
                on_step(0, MAX_AGENT_STEPS, f"Navigating to {initial_target}...", initial_target)
            page.goto(initial_target, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)
            history.append(f"Navigated to {initial_target}")

        global _is_paused, _should_go_back, _should_stop
        _is_paused = False
        _should_go_back = False
        _should_stop = False

        for step in range(1, MAX_AGENT_STEPS + 1):
            if _should_stop:
                return False, "Agent stopped by user via Telegram.", page.url

            # Human-in-the-loop: Pause loop handling
            while _is_paused:
                if on_step:
                    on_step(step, MAX_AGENT_STEPS, "⏸️ Agent PAUSED by human operator.", page.url)
                page.wait_for_timeout(1000)
                if _should_stop:
                    return False, "Agent stopped while paused.", page.url

            # Human-in-the-loop: Go Back handling
            if _should_go_back:
                _should_go_back = False
                logger.info("Executing human requested Go Back...")
                if on_step:
                    on_step(step, MAX_AGENT_STEPS, "⬅️ Navigating back as requested by human operator...", page.url)
                page.go_back(wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                history.append(f"Step {step}: Human pressed Go Back. Returned to {page.url}")

            current_url = page.url
            logger.info(f"--- [Step {step}/{MAX_AGENT_STEPS}] URL: {current_url} ---")
            print(f"\n[BrowserAgent] Step {step}/{MAX_AGENT_STEPS}: Inspecting DOM at {current_url}", flush=True)

            elements, page_snippet = _get_interactive_elements_and_snapshot(page)
            print(f"[BrowserAgent] Identified {len(elements)} interactive elements. Asking Qwen...", flush=True)
            if on_step:
                on_step(step, MAX_AGENT_STEPS, f"Qwen analyzing page elements ({len(elements)} found)...", current_url)

            # Query Qwen for the next action
            decision = _decide_next_action(
                task=task_description,
                current_url=current_url,
                elements=elements,
                page_snippet=page_snippet,
                history=history
            )

            action_type = decision.get("action")
            logger.info(f"[Step {step} Decision] {decision}")
            print(f"[BrowserAgent] Qwen Action -> {decision}", flush=True)

            if action_type == "finish":
                answer = decision.get("answer", "Task completed.")
                if on_step:
                    on_step(step, MAX_AGENT_STEPS, "Goal completed! Compiling response...", current_url)
                return True, answer, current_url

            elif action_type == "navigate":
                target_url = decision.get("url")
                if target_url:
                    if on_step:
                        on_step(step, MAX_AGENT_STEPS, f"Navigating to: {target_url}", current_url)
                    try:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(2000)
                        history.append(f"Step {step}: Navigated to {target_url}")
                    except Exception as nav_err:
                        logger.warning(f"Navigation failed ({nav_err})")
                        history.append(f"Step {step}: Navigation failed to {target_url}: {nav_err}")

            elif action_type == "click":
                element_id = decision.get("element_id")
                # Find label for human readability in logs
                elem_label = next((e["label"] for e in elements if e["id"] == element_id), element_id)
                if on_step:
                    on_step(step, MAX_AGENT_STEPS, f"Clicking: \"{elem_label}\"", current_url)
                selector = f'[data-localpilot-id="{element_id}"]'
                try:
                    loc = page.locator(selector).first
                    if loc.is_visible(timeout=2500):
                        try:
                            # Attempt standard click, fallback to force click if pointer events are intercepted by a menu
                            loc.click(timeout=5000)
                        except Exception as click_err:
                            logger.warning(f"Normal click failed ({click_err}), attempting force click...")
                            try:
                                loc.click(force=True, timeout=4000)
                            except Exception:
                                # Direct DOM click dispatch as ultimate fallback
                                loc.dispatch_event("click")
                        page.wait_for_timeout(2000)
                        history.append(f"Step {step}: Clicked {element_id} ({elem_label})")
                    else:
                        history.append(f"Step {step}: Element {element_id} was not clickable, refreshing DOM")
                except Exception as click_err:
                    logger.warning(f"Click failed on {element_id}: {click_err}")
                    history.append(f"Step {step}: Click failed on {element_id}: {click_err}")

            elif action_type == "type":
                element_id = decision.get("element_id")
                text = decision.get("text", "")
                press_enter = decision.get("press_enter", True)
                if on_step:
                    on_step(step, MAX_AGENT_STEPS, f"Typing: \"{text}\"", current_url)
                selector = f'[data-localpilot-id="{element_id}"]'
                try:
                    loc = page.locator(selector).first
                    if loc.is_visible(timeout=3000):
                        tag_name = loc.evaluate("el => el.tagName.toLowerCase()")
                        is_editable = loc.evaluate(
                            "el => el.isContentEditable || ['input', 'textarea', 'select'].includes(el.tagName.toLowerCase())"
                        )
                        if is_editable:
                            loc.fill(text)
                            page.wait_for_timeout(500)
                            if press_enter:
                                loc.press("Enter")
                            page.wait_for_timeout(2500)
                            history.append(f"Step {step}: Typed '{text}' into {element_id} (<{tag_name}>)")
                        else:
                            # Model tried to type into an anchor link or button -> click it instead!
                            logger.warning(f"Element {element_id} (<{tag_name}>) is not an editable field. Redirecting action to click.")
                            try:
                                loc.click(timeout=4000)
                            except Exception:
                                loc.dispatch_event("click")
                            page.wait_for_timeout(2000)
                            history.append(f"Step {step}: Element {element_id} was not editable (<{tag_name}>); clicked it instead")
                    else:
                        history.append(f"Step {step}: Input element {element_id} was not found")
                except Exception as type_err:
                    logger.warning(f"Type action failed on {element_id}: {type_err}")
                    history.append(f"Step {step}: Typing failed on {element_id}: {type_err}")

            else:
                logger.warning(f"Unrecognized or fallback decision: {decision}")
                history.append(f"Step {step}: Could not parse valid action")

        # Fallback if loop ends without explicit finish action
        if on_step:
            on_step(MAX_AGENT_STEPS, MAX_AGENT_STEPS, "Synthesizing final findings from page...", page.url)
        print("[BrowserAgent] Max steps reached. Extracting best answer from final page...", flush=True)
        _, final_body = _get_interactive_elements_and_snapshot(page)
        fallback_prompt = (
            f"Based on the current page content from {page.url}, please answer the user's question:\n"
            f"Task: {task_description}\n\nPage text:\n{final_body[:3000]}"
        )
        res = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": fallback_prompt}])
        return True, res["message"]["content"].strip(), page.url

    except Exception as e:
        logger.error(f"Agent loop error: {e}")
        print(f"[BrowserAgent] Error: {e}", flush=True)
        url = _page.url if _page and not _page.is_closed() else "N/A"
        return False, f"Agent loop failed: {str(e)}", url
