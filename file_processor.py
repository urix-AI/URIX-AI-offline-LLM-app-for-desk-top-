# urix/modules/file_processor.py
import os
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                             QPushButton, QFileDialog, QGroupBox, QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
    logging.warning("PyPDF2 library not found. PDF processing will not be available. Run: pip install PyPDF2")

from urix.utils.logger import get_logger

logger = get_logger(__name__)

class FileReadWorker(QThread):
    result_ready = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str, str)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        try:
            _, extension = os.path.splitext(self.file_path.lower())
            content = ""
            if extension in ['.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.md']:
                with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            elif extension == '.pdf':
                if PyPDF2:
                    with open(self.file_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        content = "".join(page.extract_text() or '' for page in reader.pages)
                else:
                    self.error_occurred.emit(self.file_path, "PyPDF2 not installed. Cannot read PDF files.")
                    return
            else:
                self.error_occurred.emit(self.file_path, f"Unsupported file type: {extension}")
                return
            self.result_ready.emit(self.file_path, content)
        except Exception as e:
            self.error_occurred.emit(self.file_path, f"An unexpected error occurred: {e}")

class LlmWorker(QThread):
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, engine, prompt, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.prompt = prompt

    def run(self):
        try:
            if not self.engine:
                self.error_occurred.emit("LLM engine is not available.")
                return

            logger.debug(f"FileProcessorWorker sending prompt to LLM: {self.prompt[:100]}...")
            
            history = [{'role': 'user', 'content': self.prompt}]
            # --- CORRECTED: Using the correct engine method name ---
            output = self.engine.generate_chat_response(history)
            
            result_text = output['choices'][0]['text'].strip()
            self.result_ready.emit(result_text)
            logger.info("LLM summarization completed.")
        except Exception as e:
            logger.error(f"Error in LLMWorker for file processing: {e}", exc_info=True)
            self.error_occurred.emit(str(e))


class FileProcessorWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.current_file_path = None
        self.extracted_text_content = ""
        self._setup_ui()
        logger.info("FileProcessorWidget initialized.")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        file_selection_group = QGroupBox("File Content")
        file_selection_layout = QVBoxLayout()

        self.status_label = QLabel("No file selected.")
        self.status_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        file_selection_layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        self.upload_button = QPushButton("Select File")
        self.upload_button.clicked.connect(self._handle_file_selection)
        button_layout.addWidget(self.upload_button)

        self.summarize_button = QPushButton("Summarize Content with AI")
        self.summarize_button.clicked.connect(self._handle_summarize_content)
        self.summarize_button.setEnabled(False)
        button_layout.addWidget(self.summarize_button)
        file_selection_layout.addLayout(button_layout)

        self.file_content_display = QTextEdit()
        self.file_content_display.setReadOnly(True)
        self.file_content_display.setPlaceholderText("File content will appear here...")
        self.file_content_display.setStyleSheet("background-color: #2c2c2c; color: #e0e0e0; border-radius: 8px; padding: 10px;")
        file_selection_layout.addWidget(self.file_content_display)

        file_selection_group.setLayout(file_selection_layout)
        main_layout.addWidget(file_selection_group, stretch=1)

        summary_group = QGroupBox("AI Summary")
        summary_layout = QVBoxLayout()
        
        self.summary_display_area = QTextEdit()
        self.summary_display_area.setReadOnly(True)
        self.summary_display_area.setPlaceholderText("AI-generated summary will appear here...")
        self.summary_display_area.setStyleSheet("background-color: #2c2c2c; color: #e0e0e0; border-radius: 8px; padding: 10px;")
        summary_layout.addWidget(self.summary_display_area)
        
        summary_group.setLayout(summary_layout)
        main_layout.addWidget(summary_group, stretch=1)

        self.setLayout(main_layout)

    def _handle_file_selection(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "All Files (*)")
        if file_path:
            self.current_file_path = file_path
            self.status_label.setText(f"Loading: {os.path.basename(file_path)}...")
            self.file_content_display.clear()
            self.summary_display_area.clear()
            self.summarize_button.setEnabled(False)
            
            self.file_read_worker = FileReadWorker(file_path)
            self.file_read_worker.result_ready.connect(self._on_file_read_ready)
            self.file_read_worker.error_occurred.connect(self._on_file_read_error)
            self.file_read_worker.start()

    def _on_file_read_ready(self, original_file_path: str, extracted_text: str):
        self.extracted_text_content = extracted_text
        self.file_content_display.setText(extracted_text)
        self.status_label.setText(f"Loaded: {os.path.basename(original_file_path)}")
        self.summarize_button.setEnabled(True)

    def _on_file_read_error(self, original_file_path: str, error_message: str):
        self.status_label.setText(f"Error loading {os.path.basename(original_file_path)}")
        self.file_content_display.setText(f"Could not load file: {error_message}")
        self.summarize_button.setEnabled(False)

    def _handle_summarize_content(self):
        if not self.extracted_text_content:
            QMessageBox.warning(self, "No Content", "Please load a file first.")
            return
        
        text_to_summarize = self.extracted_text_content[:4000]
        prompt = f"Please provide a concise summary of the following text:\n\n---\n{text_to_summarize}\n---\n\nSummary:"

        self.summarize_button.setEnabled(False)
        self.upload_button.setEnabled(False)
        self.status_label.setText("Summarizing content with AI...")
        self.summary_display_area.setText("Generating summary...")

        self.llm_worker = LlmWorker(self.engine, prompt)
        self.llm_worker.result_ready.connect(self._on_summary_ready)
        self.llm_worker.error_occurred.connect(self._on_summary_error)
        self.llm_worker.finished.connect(self._on_summary_finished)
        self.llm_worker.start()

    def _on_summary_ready(self, summary_text: str):
        self.summary_display_area.setText(summary_text)
        filename = os.path.basename(self.current_file_path) if self.current_file_path else "text"
        self.status_label.setText(f"Summary generated for {filename}.")
        logger.info(f"Summary received: {summary_text[:100]}...")

    def _on_summary_error(self, error_message: str):
        self.summary_display_area.setText(f"Could not summarize text: {error_message}")
        QMessageBox.critical(self, "Summarization Error", f"Could not summarize text: {error_message}")
        self.status_label.setText("Summarization failed.")
        logger.error(f"Summarization error: {error_message}")

    def _on_summary_finished(self):
        self.summarize_button.setEnabled(True)
        self.upload_button.setEnabled(True)