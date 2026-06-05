# urix/modules/email_handler.py


import logging
import smtplib
import imaplib
import email # Standard library email module
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import os
import re
from pathlib import Path
import datetime
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                             QPushButton, QListWidget, QListWidgetItem, QSplitter,
                             QGroupBox, QFormLayout, QLineEdit, QMessageBox,
                             QInputDialog)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from urix.utils.logger import get_logger

logger = get_logger(__name__)

# --- CORRECTED: A generic worker for synchronous, long-running tasks ---
class Worker(QThread):
    """
    A generic worker thread for running synchronous functions
    without freezing the GUI.
    """
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, function, *args, parent=None, **kwargs):
        super().__init__(parent)
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.function(*self.args, **self.kwargs)
            self.result_ready.emit(result)
        except Exception as e:
            logger.error(f"Error in Worker thread: {e}", exc_info=True)
            self.error_occurred.emit(str(e))


class EmailHandlerBackend:
    """
    Backend for email operations. This now correctly interfaces
    with the UrixEngine for AI tasks.
    """
    def __init__(self, engine):
        self.engine = engine
        self.logger = get_logger(f"{__name__}.EmailHandlerBackend")
        self.mock_emails_dir = Path("urix_mock_emails")
        self.mock_emails_dir.mkdir(exist_ok=True)
        self._generate_mock_emails()
        self.logger.info("EmailHandlerBackend initialized.")

    def _generate_mock_emails(self):
        # Generate some mock email files for demonstration
        if not any(self.mock_emails_dir.iterdir()):
            self.logger.info("Generating initial mock emails.")
            emails_to_create = {
                "mock_email_1.txt": "Subject: Project Update\nFrom: team_lead@example.com\n\nHi team, please provide your updates for the project by EOD.",
                "mock_email_2.txt": "Subject: Weekly Report\nFrom: analyst@example.com\n\nPlease find the attached weekly performance report.",
                "mock_email_3.txt": "Subject: Lunch Invitation\nFrom: colleague@example.com\n\nAre you free for lunch tomorrow to discuss the new feature?",
                "mock_email_search_report.txt": "Subject: Q3 Financial Report\nFrom: finance@example.com\n\nHere is the Q3 financial report. Please review it.",
                "mock_email_search_meeting.txt": "Subject: Team Meeting Agenda\nFrom: manager@example.com\n\nAgenda for tomorrow's team meeting.",
            }
            for filename, content in emails_to_create.items():
                with open(self.mock_emails_dir / filename, "w") as f:
                    f.write(content)

    def send_email(self, recipient: str, subject: str, body: str) -> bool:
        self.logger.info(f"MOCK: Pretending to send email to {recipient} with subject '{subject}'")
        # In a real app, this would contain smtplib logic
        return True

    # --- THIS IS THE CORRECTED AI DRAFTING METHOD ---
    def draft_email_with_ai(self, prompt: str, context: Optional[str] = None) -> Dict[str, str]:
        """
        Calls the UrixEngine with the correct prompt format to draft an email.
        This is now a synchronous function.
        """
        self.logger.info(f"AI drafting email for prompt: {prompt}")

        # Create a detailed prompt for the LLM
        full_prompt = (
            f"You are an email writing assistant. Based on the user's request, "
            f"draft a professional email. The user's request is: '{prompt}'.\n\n"
            f"Your response MUST include a 'Subject:' line and then the body of the email. "
            f"Do not add any other text before the 'Subject:' line."
        )
        if context:
            full_prompt += f"\nAdditional context to consider: {context}"

        # Format the prompt for the engine's chat history
        history = [{'role': 'user', 'content': full_prompt}]

        # Call the correct engine method
        response_dict = self.engine.generate_chat_response(history, max_tokens=512)
        draft_text = response_dict.get("choices", [{}])[0].get("text", "Could not draft email.")

        # Parse the AI response to separate subject and body
        subject = "AI Drafted Subject"
        body = draft_text

        subject_match = re.search(r"Subject:\s*(.*)", draft_text, re.IGNORECASE)
        if subject_match:
            subject = subject_match.group(1).strip()
            # Remove the subject line and any leading/trailing whitespace from the body
            body = re.sub(r"Subject:\s*.*?\n", "", draft_text, count=1, flags=re.IGNORECASE).strip()

        self.logger.info("AI drafting complete.")
        return {"subject": subject, "body": body}


    def read_emails(self, folder: str = "inbox", count: int = 10) -> List[Dict[str, str]]:
        self.logger.info(f"MOCK: Reading {count} emails from {folder}")
        emails = []
        mock_files = list(self.mock_emails_dir.glob("*.txt"))
        mock_files.sort(key=os.path.getmtime, reverse=True) # Newest first

        for i, file_path in enumerate(mock_files[:count]):
            try:
                with open(file_path, "r", encoding='utf-8') as f:
                    content = f.read()
                    msg = email.message_from_string(content)
                    subject, _ = decode_header(msg["Subject"])[0]
                    sender, _ = decode_header(msg["From"])[0]

                    emails.append({
                        "id": str(i),
                        "subject": str(subject),
                        "sender": str(sender),
                        "date": msg.get("Date", datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S")),
                        "body": msg.get_payload()
                    })
            except Exception as e:
                self.logger.error(f"Error reading mock email file {file_path}: {e}")
        return emails


class EmailWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.backend = EmailHandlerBackend(engine)
        self.worker_thread = None
        self._setup_ui()
        self._refresh_emails()
        logger.info("EmailWidget initialized.")

    def _setup_ui(self):
        # (Your UI setup code is good, no changes needed here)
        main_layout = QHBoxLayout(self)
        left_pane = QVBoxLayout()
        email_list_group = QGroupBox("Inbox")
        email_list_layout = QVBoxLayout()
        self.email_list_widget = QListWidget()
        self.email_list_widget.itemClicked.connect(self._display_email_details)
        email_list_layout.addWidget(self.email_list_widget)
        refresh_button = QPushButton("Refresh Emails")
        refresh_button.clicked.connect(self._refresh_emails)
        email_list_layout.addWidget(refresh_button)
        email_list_group.setLayout(email_list_layout)
        left_pane.addWidget(email_list_group)
        right_pane = QVBoxLayout()
        details_group = QGroupBox("Email Details")
        details_layout = QFormLayout()
        self.detail_subject = QLabel("<b>Subject:</b> ")
        self.detail_sender = QLabel("<b>From:</b> ")
        self.detail_date = QLabel("<b>Date:</b> ")
        self.detail_body = QTextEdit()
        self.detail_body.setReadOnly(True)
        details_layout.addRow(self.detail_subject)
        details_layout.addRow(self.detail_sender)
        details_layout.addRow(self.detail_date)
        details_layout.addRow(self.detail_body)
        details_group.setLayout(details_layout)
        right_pane.addWidget(details_group)
        compose_group = QGroupBox("Compose Email")
        compose_layout = QFormLayout()
        self.compose_recipient = QLineEdit()
        self.compose_subject = QLineEdit()
        self.compose_body = QTextEdit()
        compose_layout.addRow("To:", self.compose_recipient)
        compose_layout.addRow("Subject:", self.compose_subject)
        compose_layout.addRow("Body:", self.compose_body)
        compose_buttons_layout = QHBoxLayout()
        self.draft_button = QPushButton("Draft with AI")
        self.draft_button.clicked.connect(self._handle_draft_email)
        compose_buttons_layout.addWidget(self.draft_button)
        self.send_button = QPushButton("Send Email")
        self.send_button.clicked.connect(self._handle_send_email)
        compose_buttons_layout.addWidget(self.send_button)
        compose_layout.addRow(compose_buttons_layout)
        compose_group.setLayout(compose_layout)
        right_pane.addWidget(compose_group)
        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_widget.setLayout(left_pane)
        right_widget = QWidget()
        right_widget.setLayout(right_pane)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 500])
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def _refresh_emails(self):
        logger.info("Refreshing emails...")
        self.email_list_widget.clear()
        emails = self.backend.read_emails()
        for email_item in emails:
            item = QListWidgetItem(f"{email_item['sender']} - {email_item['subject']}")
            item.setData(Qt.UserRole, email_item)
            self.email_list_widget.addItem(item)

    def _display_email_details(self, item: QListWidgetItem):
        email_data = item.data(Qt.UserRole)
        self.detail_subject.setText(f"<b>Subject:</b> {email_data['subject']}")
        self.detail_sender.setText(f"<b>From:</b> {email_data['sender']}")
        self.detail_date.setText(f"<b>Date:</b> {email_data['date']}")
        self.detail_body.setText(email_data['body'])

    def _handle_send_email(self):
        # This part is for sending, not drafting. Your logic here is fine.
        # For simplicity, we'll just show a message.
        QMessageBox.information(self, "Send Email", "This is a mock-up. Email sending is not implemented.")

    # --- THIS NOW USES THE NEW `Worker` THREAD ---
    def _handle_draft_email(self):
        prompt, ok = QInputDialog.getText(self, "Draft Email with AI", "Enter prompt for the email:")
        if ok and prompt:
            self.draft_button.setEnabled(False)
            self.send_button.setEnabled(False)
            self.window().statusBar().showMessage("Drafting email with AI...")

            # Use the generic Worker for the synchronous backend call
            self.worker_thread = Worker(self.backend.draft_email_with_ai, prompt)
            self.worker_thread.result_ready.connect(self._on_email_drafted)
            self.worker_thread.error_occurred.connect(self._on_operation_error)
            self.worker_thread.finished.connect(self._on_operation_finished)
            self.worker_thread.start()

    def _on_email_drafted(self, draft_content: Dict[str, str]):
        if draft_content and draft_content.get("subject") and draft_content.get("body"):
            self.compose_subject.setText(draft_content["subject"])
            self.compose_body.setText(draft_content["body"])
            self.window().statusBar().showMessage("AI draft complete.", 4000)
        else:
            QMessageBox.warning(self, "Drafting Failed", "AI could not draft the email. Please try a different prompt.")

    def _on_operation_error(self, error_message: str):
        QMessageBox.critical(self, "Operation Error", f"An error occurred: {error_message}")

    def _on_operation_finished(self):
        self.draft_button.setEnabled(True)
        self.send_button.setEnabled(True)
        self.window().statusBar().showMessage("Ready", 4000)
        self.worker_thread = None