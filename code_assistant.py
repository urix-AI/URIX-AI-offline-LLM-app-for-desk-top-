# urix/modules/code_assistant.py
import logging
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton
from PyQt5.QtCore import pyqtSignal, Qt
from urix.utils.logger import get_logger

logger = get_logger(__name__)

class CodeAssistantWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._setup_ui()
        logger.info("CodeAssistantWidget initialized")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Enter your code or query here (e.g., 'fix this python code', 'write a function to sort a list')...")
        self.input_text.setStyleSheet("border-radius: 8px; padding: 5px; background-color: #3c3c3c; color: #e0e0e0;")
        layout.addWidget(self.input_text)

        self.submit_button = QPushButton("Process Code")
        self.submit_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border-radius: 8px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        self.submit_button.clicked.connect(self.process_code)
        layout.addWidget(self.submit_button)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("Output will appear here...")
        self.output_text.setStyleSheet("background-color: #2c2c2c; color: #e0e0e0; border-radius: 8px; padding: 10px;")
        layout.addWidget(self.output_text)

    def process_code(self):
        try:
            user_input = self.input_text.toPlainText()
            if not user_input:
                self.output_text.setText("Error: Input is empty.")
                return

            # --- CORRECTED: Using the correct engine method name ---
            history = [{'role': 'user', 'content': user_input}]
            response_dict = self.engine.generate_chat_response(history)
            
            response = response_dict.get("choices", [{}])[0].get("text", "No response from AI.")
            self.output_text.setText(response)
            logger.info("Code processed successfully")
        except Exception as e:
            self.output_text.setText(f"An error occurred: {e}")
            logger.error(f"Error processing code: {e}", exc_info=True)