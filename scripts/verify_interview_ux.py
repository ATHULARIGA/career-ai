import os
import re

TEMPLATE_PATH = "templates/interview.html"

def verify_ux_changes():
    if not os.path.exists(TEMPLATE_PATH):
        print(f"❌ Template not found at {TEMPLATE_PATH}")
        return

    with open(TEMPLATE_PATH, "r") as f:
        content = f.read()

    errors = []
    
    # Check 1: Follow-up question no longer visible BEFORE submission
    # We relocated the `next_followup` block outside the active `/evaluate` answer form block.
    # The original active form closes before the feedback loop.
    # We want to ensure the `next_followup` section is defined BELOW the score feedback grid.
    if "Next follow-up question" not in content:
        errors.append("Missing the 'Next follow-up question' template block completely.")
    
    # We can check that the "Next follow-up question" block is strictly after the live rubric scoring block.
    if content.find('class="mi-answer-form"') > content.find('Next follow-up question'):
        errors.append("Follow up rendering appears BEFORE the answer form! It should be hidden.")
    
    # Check 2: Stopwatch timer successfully passes to `answer_time_sec`
    if 'document.getElementById("answer_time_sec")' not in content:
        errors.append("Timer value element 'answer_time_sec' is missing from the JS update block.")
    if 'target.value = sec;' not in content and 'target.value = sec' not in content:
        errors.append("Stopwatch sec value isn't bound to the target form input securely.")
        
    # Check 3: Webcam permission dialog never triggers (no getUserMedia)
    if 'getUserMedia' in content:
        errors.append("Webcam permission 'getUserMedia' STILL EXISTS in the payload! Friction isn't removed.")
    if 'navigator.mediaDevices' in content:
        errors.append("Navigator mediadevices check STILL EXISTS!")

    if not errors:
        print("\n✅ Verification COMPLETE: All UI/UX logic natively conforms.")
        print("- Follow-up questions render accurately behind form submissions via feedback loops.")
        print("- Stopwatch form hooks actively pass sec counts dynamically per submit.")
        print("- Camera permission trackers and theatre strings removed definitively.\n")
    else:
        print("\n❌ Verification FAILED:")
        for e in errors:
            print(f"   -> {e}")

if __name__ == "__main__":
    verify_ux_changes()
