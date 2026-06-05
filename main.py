# main.py

import os
import sys
import argparse
import logging
import yaml
from typing import Dict, Any

# --- PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))



print("--- PYTHON ENVIRONMENT CHECK ---")
print(f"Running from: {sys.executable}")
if ".venv" not in sys.executable:
    print("\n!!! WARNING !!!")
    print("You are NOT running Python from your virtual environment.")
    print("This is likely the cause of the 'not found' error.")
    print("Please configure your code editor to use the Python interpreter from:")
    print(os.path.abspath(os.path.join(".venv", "Scripts", "python.exe")))
print("----------------------------\n")

# --- Pydub and FFmpeg Configuration ---
try:
    from pydub import AudioSegment
    ffmpeg_executable = os.path.join(BASE_DIR, "models", "ffmpeg", "bin", "ffmpeg.exe")
    ffprobe_executable = os.path.join(BASE_DIR, "models", "ffmpeg", "bin", "ffprobe.exe")
    
    if os.path.exists(ffmpeg_executable):
        AudioSegment.converter = ffmpeg_executable
    if os.path.exists(ffprobe_executable):
        AudioSegment.ffprobe = ffprobe_executable
except ImportError:
    print("Warning: pydub library not found. Audio file conversion might not work.")
    AudioSegment = None

# --- URIX Imports ---
from urix.core.engine import UrixEngine
from urix.gui.main_window import MainWindow
from urix.utils.logger import setup_logger

logger = logging.getLogger("urix_main_bootstrap")

def parse_arguments():
    parser = argparse.ArgumentParser(description="URIX - Local AI Assistant")
    default_config_path = os.path.join(BASE_DIR, "config", "config.yaml")
    parser.add_argument("--config", "-c", type=str, default=default_config_path, help="Path to configuration file")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO", help="Set logging level")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no GUI)")
    return parser.parse_args()

def load_config(config_path: str) -> Dict[str, Any]:
    # --- START OF CHANGE: Update default config for llama-cpp-python ---
    config = {
        "app_name": "URIX",
        "version": "0.1.0",
        "base_dir": BASE_DIR,
        "models": { 
            "model_path": "path/to/your/model.gguf", # Placeholder path
            "n_gpu_layers": -1,
            "n_ctx": 4096
        },
        "gui": {"theme": "dark"},
    }
    # --- END OF CHANGE ---
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                base_config = yaml.safe_load(f)
                if isinstance(base_config, dict):
                    # This allows deep merging of nested dictionaries like 'models'
                    def update_dict(d, u):
                        for k, v in u.items():
                            if isinstance(v, dict):
                                d[k] = update_dict(d.get(k, {}), v)
                            else:
                                d[k] = v
                        return d
                    config = update_dict(config, base_config)
        except Exception as e:
            logger.error(f"Error loading config {config_path}: {e}")
    else:
        logger.warning(f"Config file not found at {config_path}. Using default settings. Please create a config file.")
    return config


def run_headless(engine: UrixEngine):
    print(f"\nURIX AI Assistant - Command Line Interface (Model: {engine.model_name})\nType 'exit' or 'quit' to exit\n")
    
    conversation_history = []
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ("exit", "quit"): break

            # --- START OF CHANGE: Updated headless mode logic for new response format ---
            history = [{'role': 'user', 'content': user_input}]
            response_dict = engine.generate_chat_response(history)
            
            ai_response = response_dict.get("choices", [{}])[0].get("text", "Error: No response from AI.")
            
            # Update conversation history for context
            conversation_history.append({'role': 'user', 'content': user_input})
            conversation_history.append({'role': 'assistant', 'content': ai_response})
            print(f"URIX: {ai_response}")
            # --- END OF CHANGE ---
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in headless mode: {e}", exc_info=True)
            print("An error occurred.")
    print("Goodbye!")

def run_gui(engine: UrixEngine, config: Dict[str, Any]):
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QFont
    try:
        app = QApplication(sys.argv)
        default_font = QFont()
        default_font.setPointSize(12) 
        app.setFont(default_font)
        main_window = MainWindow(engine, config)
        main_window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred in run_gui: {e}", exc_info=True)
        # Fallback to headless mode if GUI fails
        print("\n--- GUI FAILED TO START ---")
        print(f"Error: {e}")
        print("Starting in headless (command-line) mode.\n")
        run_headless(engine)


def main():
    args = parse_arguments()
    setup_logger(level=getattr(logging, args.log_level.upper(), logging.INFO))
    logger.info("--- Starting URIX ---")
    config = load_config(args.config)
    try:
        engine = UrixEngine(config)
        logger.info("URIX Engine initialized by main function.")
    except Exception as e:
        logger.critical(f"Failed to initialize URIX Engine in main: {e}", exc_info=True)
        # Provide a more user-friendly error if model is not found
        if "Model path not found" in str(e):
            print("\nFATAL ERROR: AI Model not found.")
            print("Please create or edit your 'config/config.yaml' file and set the correct 'model_path'.")
            print("Example: model_path: 'C:/AI/models/my_model.gguf'")
        return 1
        
    if args.headless:
        run_headless(engine)
    else:
        run_gui(engine, config)
        
    logger.info("--- URIX Shutting Down ---")
    return 0

if __name__ == "__main__":
    sys.exit(main())