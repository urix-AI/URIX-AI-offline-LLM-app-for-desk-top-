import sys
import logging
import os
from typing import Dict, Any, Optional

from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QStatusBar, QToolBar, QAction,
    QSizePolicy, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from qt_material import apply_stylesheet

from urix.modules.code_assistant import CodeAssistantWidget
from urix.modules.email_handler import EmailWidget
from urix.modules.presentation import PresentationWidget
from urix.modules.study_tools import StudyToolsWidget
from urix.modules.image_generator import ImageGeneratorWidget
from urix.utils.logger import get_logger
from urix.utils.response import normalize_llm_response, markdown_to_safe_html

logger = get_logger(__name__)

ASSETS_BASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gui", "assets")

class ChatWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, engine, history, file_context: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.history = history
        self.file_context = file_context

    def run(self):
        try:
            result = self.engine.generate_chat_response(self.history, max_tokens=0)
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Error in ChatWorker: {e}", exc_info=True)
            self.error.emit(f"An unexpected error occurred: {e}")


class ModelSwitchWorker(QThread):
    finished = pyqtSignal(bool, str)
    def __init__(self, engine, mode, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.mode = mode
    def run(self):
        success = self.engine.switch_model(self.mode)
        self.finished.emit(success, self.mode)


class ChatWidget(QWidget):
    def __init__(self, engine, config, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.config = config
        self.conversation_history = []
        self.chat_worker: Optional[ChatWorker] = None
        self._setup_ui()
        logger.info("ChatWidget initialized")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        layout.addWidget(self.chat_history)

        input_layout = QHBoxLayout()
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Type your message...")
        self.input_text.setMinimumHeight(40)
        self.input_text.setMaximumHeight(120)
        self.input_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        input_layout.addWidget(self.input_text)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self._handle_send_message)
        input_layout.addWidget(self.send_button)

        layout.addLayout(input_layout)
        self.setLayout(layout)

    def _handle_send_message(self):
        user_message = self.input_text.toPlainText().strip()
        if not user_message:
            return

        # Prevent overlapping workers
        if self.chat_worker and self.chat_worker.isRunning():
            self.chat_worker.quit()
            self.chat_worker.wait()

        self._set_ui_busy(True)

        self.chat_history.append("<div style='color:#6CB4EE; font-weight:bold;'>You:</div>" \
                                 f"<div style='color:#E0E0E0; margin-bottom: 10px;'>{user_message}</div>")
        self.input_text.clear()

        self.conversation_history.append({'role': 'user', 'content': user_message})

        self.chat_worker = ChatWorker(self.engine, self.conversation_history, file_context=None)
        self.chat_worker.finished.connect(self._on_ai_response)
        self.chat_worker.error.connect(self._on_ai_error)
        self.chat_worker.start()

    def _on_ai_response(self, ai_response_dict: dict):
        ai_text = normalize_llm_response(ai_response_dict) or ai_response_dict.get("choices", [{}])[0].get("text", "No response from AI.")
        html_response = markdown_to_safe_html(ai_text)

        self.conversation_history.append({'role': 'assistant', 'content': ai_text})
        self.chat_history.append("<div style='color:#77DD77; font-weight:bold;'>AI:</div>" + html_response)

        self._finalize_message()

    def _on_ai_error(self, error_message: str):
        self.chat_history.append(f"<p style='color:red;'><b>Error:</b> {error_message}</p>")
        logger.error("Error in ChatWidget", exc_info=True)
        self._finalize_message()

    def _set_ui_busy(self, busy: bool, message: str = "Thinking..."):
        self.send_button.setEnabled(not busy)
        self.input_text.setEnabled(not busy)
        if busy:
            self.window().statusBar().showMessage(message)
        else:
            self.window().statusBar().showMessage("Ready", 3000)


    def _finalize_message(self):
        self._set_ui_busy(False)
        self.chat_history.verticalScrollBar().setValue(self.chat_history.verticalScrollBar().maximum())
        self.chat_worker = None


class MainWindow(QMainWindow):
    def __init__(self, engine, config: Dict[str, Any]):
        super().__init__()
        self.engine = engine
        self.config = config
        self.model_worker: Optional[ModelSwitchWorker] = None
        self._setup_ui()
        logger.info("MainWindow initialized with stunning GUI.")

    def _setup_ui(self):
        self.setWindowTitle(self.config.get("app_name", "URIX AI Lite"))
        self.setGeometry(100, 100, 1200, 800)
        logo_path = os.path.join(ASSETS_BASE_PATH, "urix_logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()

        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.chat_widget = ChatWidget(self.engine, self.config)
        self.tab_widget.addTab(self.chat_widget, "Chat Assistant")
        self.code_assistant_widget = CodeAssistantWidget(self.engine)
        self.tab_widget.addTab(self.code_assistant_widget, "Code Assistant")
        self.email_widget = EmailWidget(self.engine)
        self.tab_widget.addTab(self.email_widget, "Email Handler")
        self.presentation_widget = PresentationWidget(self.engine)
        self.tab_widget.addTab(self.presentation_widget, "Presentation Maker")
        self.image_generator_widget = ImageGeneratorWidget(self.engine)
        self.tab_widget.addTab(self.image_generator_widget, "Image Generator")
        self.study_tools_widget = StudyToolsWidget(self.engine)
        self.tab_widget.addTab(self.study_tools_widget, "Study Tools")

        self._apply_theme(self.config.get("gui", {}).get("default_theme", "dark_blue.xml"))

        if self.engine.current_mode:
            initial_mode = self.engine.current_mode
            self.statusBar().showMessage(f"LLM Mode: {initial_mode.capitalize()} | Ready")

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        settings_menu = menu_bar.addMenu("Settings")

        theme_menu = settings_menu.addMenu("Theme")
        themes = [
            "dark_blue.xml", "light_blue.xml", "dark_amber.xml",
            "light_amber.xml", "dark_teal.xml", "light_teal.xml",
        ]
        for theme_name in themes:
            action = QAction(theme_name.replace(".xml", "").replace("_", " ").title(), self)
            action.triggered.connect(lambda checked, t=theme_name: self._apply_theme(t))
            theme_menu.addAction(action)

        self.llm_mode_menu = settings_menu.addMenu("LLM Mode")
        llm_modes = self.config.get("models", {}).get("modes", {}).keys()
        for mode in llm_modes:
            action = QAction(mode.capitalize(), self)
            action.triggered.connect(lambda checked, m=mode: self._set_llm_mode(m))
            self.llm_mode_menu.addAction(action)

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_tool_bar(self):
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        refresh_icon_path = os.path.join(ASSETS_BASE_PATH, "refresh.png")
        refresh_action = QAction(QIcon(refresh_icon_path), "Refresh", self) if os.path.exists(refresh_icon_path) else QAction("Refresh", self)
        toolbar.addAction(refresh_action)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

    def _create_status_bar(self):
        self.statusBar().showMessage("Ready")

    def _apply_theme(self, selected_theme: str):
        try:
            from PyQt5.QtWidgets import QApplication
            apply_custom_styles(QApplication.instance(), selected_theme)
            # Force refresh
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
            self.statusBar().showMessage(
                f"Theme: {selected_theme.replace('.xml', '').replace('_', ' ').title()}"
            )
            logger.info(f"Applied qt-material theme: {selected_theme}")
        except Exception as e:
            logger.error(f"Failed to apply theme {selected_theme}: {e}", exc_info=True)
            self.statusBar().showMessage(f"Failed to apply theme: {selected_theme}")

    def _set_llm_mode(self, selected_mode: str):
        if self.engine.current_mode == selected_mode:
            self.statusBar().showMessage(f"LLM Mode '{selected_mode.capitalize()}' is already active.")
            return
        self.statusBar().showMessage(f"Switching to LLM Mode: {selected_mode.capitalize()}... Please wait.")
        self.menuBar().setEnabled(False)
        self.model_worker = ModelSwitchWorker(self.engine, selected_mode)
        self.model_worker.finished.connect(self._on_model_switched)
        self.model_worker.start()

    def _on_model_switched(self, success: bool, mode: str):
        self.menuBar().setEnabled(True)
        if success:
            self.statusBar().showMessage(f"LLM Mode set to {mode.capitalize()} | Ready")
            QMessageBox.information(self, "Mode Changed", f"Successfully switched to {mode.capitalize()} mode.")
        else:
            failed_mode = self.engine.current_mode or "None"
            self.statusBar().showMessage(f"Failed to switch mode. Current mode: {failed_mode.capitalize()}")
            QMessageBox.critical(self, "Mode Change Failed", f"Could not switch to {mode.capitalize()} mode. Please check logs and config.")
        self.model_worker = None

    def _show_about(self):
        QMessageBox.about(
            self,
            "About URIX AI",
            f"URIX AI v{self.config.get('version', '0.1.0')}\n\n"
            "A custom-built, offline AI assistant.\n\n"
            "Engineered and Developed by: Mr. Bhuvnesh Kumar",
        )

    def closeEvent(self, event):
        logger.info("MainWindow closing, shutting down engine...")
        if hasattr(self.engine, 'shutdown'):
            self.engine.shutdown()
        event.accept()


def apply_custom_styles(app, theme_name: str):
    try:
        apply_stylesheet(app, theme=theme_name, extra={
            'density_scale': '-2',
            'font_size': '14px',
            'primaryTextColor': '#E0E0E0' if 'dark' in theme_name else '#000000',
            'secondaryTextColor': '#B0B0B0' if 'dark' in theme_name else '#555555',
            'primaryBackgroundColor': '#212121' if 'dark' in theme_name else '#FFFFFF',
            'secondaryBackgroundColor': '#424242' if 'dark' in theme_name else '#E0E0E0',
            'border': '1px solid #555555' if 'dark' in theme_name else '1px solid #BBBBBB',
            'border_radius': '8px',
            'font': 'Inter',
            'icon_size': '24px',
            'icon_path': ASSETS_BASE_PATH,
        })
        logger.info(f"Applied theme: {theme_name}")
    except Exception as e:
        logger.error(f"Error applying stylesheet: {e}", exc_info=True)
