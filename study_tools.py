# urix/modules/study_tools.py
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                             QPushButton, QGroupBox, QSpinBox, QFrame, QScrollArea, QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from urix.utils.logger import get_logger

logger = get_logger(__name__)

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

            logger.debug(f"StudyToolsWorker sending prompt to LLM: {self.prompt[:100]}...")
            
            history = [{'role': 'user', 'content': self.prompt}]
            # --- CORRECTED: Using the correct engine method name ---
            output = self.engine.generate_chat_response(
                history,
                max_tokens=768,
            )
            
            result_text = output['choices'][0]['text'].strip()
            self.result_ready.emit(result_text)
            logger.info("LLM task completed for study tools.")
        except Exception as e:
            logger.error(f"Error in LLMWorker for study tools: {e}", exc_info=True)
            self.error_occurred.emit(str(e))


class StudyToolsWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.flashcards = []
        self.current_flashcard_index = -1
        self.showing_front = True
        self._setup_ui()
        logger.info("StudyToolsWidget initialized.")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        flashcard_gen_group = QGroupBox("Generate Flashcards from Text")
        flashcard_gen_layout = QVBoxLayout()
        self.flashcard_input_text = QTextEdit()
        self.flashcard_input_text.setPlaceholderText("Paste text here to generate flashcards (e.g., notes, definitions)...")
        self.flashcard_input_text.setMinimumHeight(80)
        self.flashcard_input_text.setStyleSheet("border-radius: 8px; padding: 15px; background-color: #3c3c3c; color: #e0e0e0;")
        flashcard_gen_layout.addWidget(self.flashcard_input_text)

        self.generate_flashcards_button = QPushButton("Generate Flashcards")
        self.generate_flashcards_button.setStyleSheet("""...""") # Styles unchanged
        self.generate_flashcards_button.clicked.connect(self._handle_generate_flashcards)
        flashcard_gen_layout.addWidget(self.generate_flashcards_button)
        flashcard_gen_group.setLayout(flashcard_gen_layout)
        main_layout.addWidget(flashcard_gen_group)

        question_gen_group = QGroupBox("Generate Questions from Text")
        question_gen_layout = QVBoxLayout()
        self.question_input_text = QTextEdit()
        self.question_input_text.setPlaceholderText("Paste text here to generate questions...")
        self.question_input_text.setMinimumHeight(80)
        self.question_input_text.setStyleSheet("border-radius: 8px; padding: 5px; background-color: #3c3c3c; color: #e0e0e0;")
        question_gen_layout.addWidget(self.question_input_text)

        self.generate_questions_button = QPushButton("Generate Questions")
        self.generate_questions_button.setStyleSheet("""...""") # Styles unchanged
        self.generate_questions_button.clicked.connect(self._handle_generate_questions)
        question_gen_layout.addWidget(self.generate_questions_button)

        self.generated_questions_display = QTextEdit()
        self.generated_questions_display.setReadOnly(True)
        self.generated_questions_display.setPlaceholderText("Generated questions will appear here.")
        self.generated_questions_display.setMinimumHeight(100)
        self.generated_questions_display.setStyleSheet("background-color: #2c2c2c; color: #e0e0e0; border-radius: 8px; padding: 10px;")
        question_gen_layout.addWidget(self.generated_questions_display)

        question_gen_group.setLayout(question_gen_layout)
        main_layout.addWidget(question_gen_group)

        flashcard_display_group = QGroupBox("Flashcard Deck")
        flashcard_display_layout = QVBoxLayout()

        self.flashcard_deck_status_label = QLabel("Deck: 0 cards.")
        self.flashcard_deck_status_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        flashcard_display_layout.addWidget(self.flashcard_deck_status_label)

        self.flashcard_display_area = QTextEdit()
        self.flashcard_display_area.setReadOnly(True)
        self.flashcard_display_area.setPlaceholderText("Flashcards will appear here.")
        self.flashcard_display_area.setMinimumHeight(150)
        self.flashcard_display_area.setStyleSheet("background-color: #2c2c2c; color: #e0e0e0; border-radius: 8px; padding: 10px;")
        flashcard_display_layout.addWidget(self.flashcard_display_area)

        nav_buttons_layout = QHBoxLayout()
        self.prev_flashcard_button = QPushButton("Previous")
        self.prev_flashcard_button.clicked.connect(self._handle_prev_flashcard)
        self.prev_flashcard_button.setEnabled(False)
        nav_buttons_layout.addWidget(self.prev_flashcard_button)

        self.flip_flashcard_button = QPushButton("Show Answer")
        self.flip_flashcard_button.clicked.connect(self._handle_flip_flashcard)
        self.flip_flashcard_button.setEnabled(False)
        nav_buttons_layout.addWidget(self.flip_flashcard_button)

        self.next_flashcard_button = QPushButton("Next")
        self.next_flashcard_button.clicked.connect(self._handle_next_flashcard)
        self.next_flashcard_button.setEnabled(False)
        nav_buttons_layout.addWidget(self.next_flashcard_button)

        flashcard_display_layout.addLayout(nav_buttons_layout)
        flashcard_display_group.setLayout(flashcard_display_layout)
        main_layout.addWidget(flashcard_display_group)

        main_layout.addStretch()
        self.setLayout(main_layout)

    def _handle_generate_flashcards(self):
        text_input = self.flashcard_input_text.toPlainText().strip()
        if not text_input:
            self.flashcard_display_area.setText("Please enter text to generate flashcards.")
            return

        prompt = (f"Generate a list of 5-10 flashcards (question and answer pairs) from the following text. "
                  f"Format each flashcard as 'Q: [Question]\\nA: [Answer]'. Separate each flashcard with a newline.\n\n"
                  f"Text: {text_input}")

        self.generate_flashcards_button.setEnabled(False)
        self.flashcard_display_area.setText("Generating flashcards... This may take a moment.")
        self._set_nav_buttons_enabled(False)

        self.llm_worker = LlmWorker(self.engine, prompt)
        self.llm_worker.result_ready.connect(self._on_flashcards_ready)
        self.llm_worker.error_occurred.connect(self._on_flashcards_error)
        self.llm_worker.finished.connect(self._on_flashcards_finished)
        self.llm_worker.start()
        logger.info("Started AI flashcard generation.")

    def _on_flashcards_ready(self, result_text: str):
        self.flashcards = []
        pairs = result_text.split('\n\n')
        for pair in pairs:
            if 'Q:' in pair and 'A:' in pair:
                q_match = pair.find('Q:')
                a_match = pair.find('A:')
                if q_match != -1 and a_match != -1:
                    question = pair[q_match + 2 : a_match].strip()
                    answer = pair[a_match + 2 :].strip()
                    if question and answer:
                        self.flashcards.append({"front": question, "back": answer})
        
        if self.flashcards:
            self.current_flashcard_index = 0
            self.showing_front = True
            self._update_flashcard_display()
            self._set_nav_buttons_enabled(True)
            QMessageBox.information(self, "Flashcards Generated", f"Successfully generated {len(self.flashcards)} flashcards!")
        else:
            self.flashcard_display_area.setText("Could not generate flashcards. Please try different text.")
            QMessageBox.warning(self, "No Flashcards", "AI could not generate flashcards from the provided text.")
        logger.info(f"Generated {len(self.flashcards)} flashcards.")

    def _on_flashcards_error(self, error_message: str):
        self.flashcard_display_area.setText(f"Error generating flashcards: {error_message}")
        QMessageBox.critical(self, "Flashcard Error", f"Could not generate flashcards: {error_message}")
        logger.error(f"Flashcard generation error: {error_message}")
        self._set_nav_buttons_enabled(False)

    def _on_flashcards_finished(self):
        self.generate_flashcards_button.setEnabled(True)
        self.llm_worker = None
        logger.info("Flashcard generation worker finished.")

    def _update_flashcard_display(self):
        if not self.flashcards:
            self.flashcard_display_area.setText("No flashcards available.")
            self._set_nav_buttons_enabled(False)
            self.flashcard_deck_status_label.setText("Deck: 0 cards.")
            return

        if self.current_flashcard_index < 0:
            self.current_flashcard_index = 0
        elif self.current_flashcard_index >= len(self.flashcards):
            self.current_flashcard_index = len(self.flashcards) - 1

        card = self.flashcards[self.current_flashcard_index]
        if self.showing_front:
            self.flashcard_display_area.setText(f"<b>Front ({self.current_flashcard_index + 1}/{len(self.flashcards)}):</b><br>{card['front']}")
            self.flip_flashcard_button.setText("Show Answer")
        else:
            self.flashcard_display_area.setText(f"<b>Back ({self.current_flashcard_index + 1}/{len(self.flashcards)}):</b><br>{card['back']}")
            self.flip_flashcard_button.setText("Show Question")
        self.flashcard_deck_status_label.setText(f"Deck: {len(self.flashcards)} cards. Current: {self.current_flashcard_index + 1}")
        self._set_nav_buttons_enabled(True)

    def _handle_flip_flashcard(self):
        if not self.flashcards: return
        self.showing_front = not self.showing_front
        self._update_flashcard_display()

    def _handle_next_flashcard(self):
        if not self.flashcards: return
        self.current_flashcard_index = (self.current_flashcard_index + 1) % len(self.flashcards)
        self.showing_front = True
        self._update_flashcard_display()

    def _handle_prev_flashcard(self):
        if not self.flashcards: return
        if len(self.flashcards) > 0:
            self.current_flashcard_index = (self.current_flashcard_index - 1 + len(self.flashcards)) % len(self.flashcards)
            self.showing_front = True
            self._update_flashcard_display()

    def _set_nav_buttons_enabled(self, enabled: bool):
        self.flip_flashcard_button.setEnabled(enabled)
        self.next_flashcard_button.setEnabled(enabled)
        self.prev_flashcard_button.setEnabled(enabled)

    def _handle_generate_questions(self):
        text_input = self.question_input_text.toPlainText().strip()
        if not text_input:
            self.generated_questions_display.setText("Please enter text to generate questions.")
            return

        prompt = (f"Generate 5-10 insightful questions from the following text. "
                  f"List each question with a number. Example:\n1. What is...?\n2. How does...?\n\n"
                  f"Text: {text_input}")

        self.generate_questions_button.setEnabled(False)
        self.generated_questions_display.setText("Generating questions... This may take a moment.")

        self.llm_worker_questions = LlmWorker(self.engine, prompt)
        self.llm_worker_questions.result_ready.connect(self._on_questions_ready)
        self.llm_worker_questions.error_occurred.connect(self._on_questions_error)
        self.llm_worker_questions.finished.connect(self._on_questions_finished)
        self.llm_worker_questions.start()
        logger.info("Started AI question generation.")

    def _on_questions_ready(self, result_text: str):
        if result_text:
            self.generated_questions_display.setText(result_text)
            QMessageBox.information(self, "Questions Generated", "AI successfully generated questions!")
        else:
            self.generated_questions_display.setText("Could not generate questions. Please try different text.")
            QMessageBox.warning(self, "No Questions", "AI could not generate questions from the provided text.")
        logger.info("Questions received from AI.")

    def _on_questions_error(self, error_message: str):
        self.generated_questions_display.setText(f"Error generating questions: {error_message}")
        QMessageBox.critical(self, "Question Error", f"Could not generate questions: {error_message}")
        logger.error(f"Question generation error: {error_message}")

    def _on_questions_finished(self):
        self.generate_questions_button.setEnabled(True)
        self.llm_worker_questions = None
        logger.info("Question generation worker finished.")