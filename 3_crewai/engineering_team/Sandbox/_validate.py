# _validate.py

import app

try:
    # Validate Gradio UI construction
    interface = app.build_ui()
    print("Validation succeeded: Gradio UI constructed without errors.")
except Exception as e:
    print(f"Validation failed: {e}")