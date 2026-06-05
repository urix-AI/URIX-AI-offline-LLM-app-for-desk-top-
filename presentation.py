# urix/modules/presentation.py
import os
import re
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTextEdit,
                             QPushButton, QGroupBox, QSpinBox, QFileDialog, QMessageBox,
                             QFormLayout, QComboBox, QProgressBar)
from PyQt5.QtCore import QThread, pyqtSignal
from urix.utils.logger import get_logger

logger = get_logger(__name__)



class PresentationWorker(QThread):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str) # This signal will now receive more detailed messages

    def __init__(self, engine, topic, num_slides, file_path, template_path, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.topic = topic
        self.num_slides = num_slides
        self.file_path = file_path
        self.template_path = template_path

    def run(self):
        try:
            # The 'generate_presentation_data' method now accepts a callback
            # We pass this thread's 'progress.emit' signal directly to the engine
            presentation_data = self.engine.generate_presentation_data(
                self.topic, 
                self.num_slides, 
                progress_callback=self.progress.emit # This creates the link
            )
            
            if not presentation_data:
                # The engine now handles its own errors and logging, so we can use a simpler error message.
                self.error.emit("The AI failed to generate a complete presentation plan. Please try again.")
                return

            self.progress.emit("Finalizing: Building the PowerPoint file...")
            result = self.engine.create_presentation(self.file_path, presentation_data, self.template_path)
            
            self.finished.emit(result, self.file_path)
        except Exception as e:
            logger.error(f"Critical error in PresentationWorker: {e}", exc_info=True)
            self.error.emit(f"An unexpected error occurred: {e}")


class PresentationWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.templates_path = os.path.join(self.engine.config.get("base_dir", "."), "urix", "gui", "assets", "PPT Templates")
        self._setup_ui()
        self._populate_templates_dropdown()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        control_group = QGroupBox("Create an Intelligent Presentation")
        form_layout = QFormLayout()

        self.topic_input_area = QTextEdit()
        self.topic_input_area.setPlaceholderText("e.g., 'The Impact of Quantum Computing on Cybersecurity'")
        self.topic_input_area.setFixedHeight(60)
        form_layout.addRow("Presentation Topic:", self.topic_input_area)

        self.num_slides_spinbox = QSpinBox()
        self.num_slides_spinbox.setRange(3, 15)
        self.num_slides_spinbox.setValue(5)
        form_layout.addRow("Number of Content Slides:", self.num_slides_spinbox)
        
        self.template_selector = QComboBox()
        form_layout.addRow("Template:", self.template_selector)

        self.generate_button = QPushButton("✨ Generate Top-Notch PPT")
        self.generate_button.setFixedHeight(40)
        self.generate_button.clicked.connect(self._handle_generate_presentation)
        
        form_layout.addRow(self.generate_button)
        control_group.setLayout(form_layout)
        main_layout.addWidget(control_group)

        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        self.status_label = QLabel("Ready to generate a new presentation.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        main_layout.addStretch()
        self.setLayout(main_layout)

    def _handle_generate_presentation(self):
        topic = self.topic_input_area.toPlainText().strip()
        num_slides = self.num_slides_spinbox.value()
        
        if not topic:
            QMessageBox.warning(self, "Missing Topic", "Please enter a topic.")
            return

        default_filename = f"{topic[:50].replace(' ', '_')}.pptx"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Presentation", default_filename, "PowerPoint Files (*.pptx)")
        
        if not save_path:
            return

        selected_template_name = self.template_selector.currentText()
        template_path = None
        if selected_template_name != "Default (Blank Presentation)":
            template_path = os.path.join(self.templates_path, selected_template_name)

        self.set_ui_busy(True)
        self.worker = PresentationWorker(self.engine, topic, num_slides, save_path, template_path)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._update_progress)
        self.worker.start()
    
    def _update_progress(self, message):
        """This function is now smarter and dynamically updates the progress bar."""
        self.status_label.setText(message)
        
        # Check for specific keywords in the message to set progress
        if "Generating presentation structure" in message:
            self.progress_bar.setValue(10)
        elif "Generating content for slide" in message:
            # Extracts numbers like "1" and "5" from "slide 1/5"
            match = re.search(r"slide (\d+)/(\d+)", message)
            if match:
                current_slide, total_slides = int(match.group(1)), int(match.group(2))
                # Calculate progress from 15% to 85% based on slide number
                progress = 15 + int((current_slide / total_slides) * 70)
                self.progress_bar.setValue(progress)
        elif "Finalizing" in message:
            self.progress_bar.setValue(90)

    def _on_finished(self, result_message, file_path):
        self.set_ui_busy(False)
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "Success", result_message)
        self.status_label.setText("Presentation generated successfully. Ready for next task.")

    def _on_error(self, error_message):
        self.set_ui_busy(False)
        QMessageBox.critical(self, "Error", error_message)
        self.status_label.setText("An error occurred. Please try again.")

    def set_ui_busy(self, is_busy):
        self.generate_button.setEnabled(not is_busy)
        self.topic_input_area.setEnabled(not is_busy)
        self.num_slides_spinbox.setEnabled(not is_busy)
        self.progress_bar.setVisible(is_busy)
        if not is_busy:
            self.progress_bar.setValue(0)

    def _populate_templates_dropdown(self):
        self.template_selector.addItem("Default (Blank Presentation)")
        if not os.path.isdir(self.templates_path):
            logger.warning(f"Templates directory not found at: {self.templates_path}")
            return
        try:
            templates = [f for f in os.listdir(self.templates_path) if f.lower().endswith('.pptx')]
            if templates:
                self.template_selector.addItems(sorted(templates))
        except Exception as e:
            logger.error(f"Failed to load presentation templates: {e}")

