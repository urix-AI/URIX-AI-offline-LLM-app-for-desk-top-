# urix/modules/image_generator.py

import os
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                             QPushButton, QGroupBox, QMessageBox, QComboBox,
                             QSpinBox, QDoubleSpinBox, QFileDialog, QApplication, QDialog)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap, QImage
from urix.utils.logger import get_logger

# Import image generation libraries
try:
    import torch
    from diffusers import StableDiffusionPipeline, StableDiffusion3Pipeline
except ImportError:
    torch = None
    StableDiffusionPipeline = None
    StableDiffusion3Pipeline = None
    logging.warning("torch or diffusers not found. Image generation will be disabled.")

logger = get_logger(__name__)

# ImageViewer class remains the same...
class ImageViewer(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Full-Size Image Viewer")
        layout = QVBoxLayout(self)
        label = QLabel()
        label.setPixmap(pixmap)
        layout.addWidget(label)
        self.setWindowFlags(self.windowFlags() | Qt.Window)

class ImageGenerationWorker(QThread):
    finished = pyqtSignal(QImage)
    error = pyqtSignal(str)

    def __init__(self, model_path, prompt, negative_prompt, steps, guidance_scale, parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.steps = steps
        self.guidance_scale = guidance_scale

    def run(self):
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {device} for image generation.")

            pipeline = None
            model_filename = os.path.basename(self.model_path).lower()

            # --- THIS IS THE KEY CHANGE ---
            # Paste your new Hugging Face token here
            hf_token = "your-token-key" 

            if "sd3" in model_filename or "stable-diffusion-3" in model_filename:
                logger.info("Stable Diffusion 3 model detected. Using SD3 Pipeline.")
                pipeline = StableDiffusion3Pipeline.from_single_file(
                    self.model_path,
                    torch_dtype=torch.float16,
                    use_safetensors=True,
                    token=hf_token  # Authenticate directly here
                )
                pipeline.enable_model_cpu_offload()
            else:
                logger.info("Stable Diffusion 1.5 model detected. Using standard Pipeline.")
                pipeline = StableDiffusionPipeline.from_single_file(
                    self.model_path,
                    torch_dtype=torch.float16,
                    use_safetensors=True,
                    token=hf_token # Also add token here for consistency
                )
                pipeline.to(device)

            if isinstance(pipeline, StableDiffusion3Pipeline):
                 image = pipeline(
                    prompt=self.prompt,
                    negative_prompt=self.negative_prompt,
                    num_inference_steps=self.steps,
                    guidance_scale=self.guidance_scale,
                ).images[0]
            else:
                image = pipeline(
                    prompt=self.prompt,
                    negative_prompt=self.negative_prompt,
                    num_inference_steps=self.steps,
                    guidance_scale=self.guidance_scale
                ).images[0]

            q_image = QImage(image.tobytes("raw", "RGB"), image.width, image.height, QImage.Format_RGB888)
            self.finished.emit(q_image)

        except Exception as e:
            logger.error(f"Error during image generation: {e}", exc_info=True)
            self.error.emit(str(e))



class ImageGeneratorWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.worker = None
        self.generated_pixmap = None
        self.models_dir = r"C:\urix_pro\models\IMAGE_MODELS"
        self._setup_ui()
        self._populate_models_dropdown()
        logger.info("ImageGeneratorWidget initialized with advanced controls.")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        control_group = QGroupBox("Image Generation Controls")
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Prompt (What you want to see):"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("e.g., A stunning portrait of a warrior, cinematic lighting, 8k, masterpiece, by Artgerm")
        form_layout.addWidget(self.prompt_input)
        form_layout.addWidget(QLabel("Negative Prompt (What to avoid):"))
        self.negative_prompt_input = QTextEdit()
        self.negative_prompt_input.setPlaceholderText("e.g., ugly, blurry, bad anatomy, deformed, watermark, text")
        self.negative_prompt_input.setFixedHeight(60)
        form_layout.addWidget(self.negative_prompt_input)
        form_layout.addWidget(QLabel("Select Model:"))
        self.model_selector = QComboBox()
        form_layout.addWidget(self.model_selector)
        param_layout = QHBoxLayout()
        steps_layout = QVBoxLayout()
        steps_layout.addWidget(QLabel("Inference Steps:"))
        self.steps_spinbox = QSpinBox()
        self.steps_spinbox.setRange(10, 100)
        self.steps_spinbox.setValue(28)
        steps_layout.addWidget(self.steps_spinbox)
        param_layout.addLayout(steps_layout)
        cfg_layout = QVBoxLayout()
        cfg_layout.addWidget(QLabel("Guidance Scale (CFG):"))
        self.cfg_spinbox = QDoubleSpinBox()
        self.cfg_spinbox.setRange(1.0, 20.0)
        self.cfg_spinbox.setValue(7.0)
        self.cfg_spinbox.setSingleStep(0.5)
        cfg_layout.addWidget(self.cfg_spinbox)
        param_layout.addLayout(cfg_layout)
        form_layout.addLayout(param_layout)
        self.generate_button = QPushButton("Generate Image")
        self.generate_button.clicked.connect(self._handle_generate_image)
        form_layout.addWidget(self.generate_button)
        control_group.setLayout(form_layout)
        main_layout.addWidget(control_group)
        display_group = QGroupBox("Generated Image")
        display_layout = QVBoxLayout()
        self.image_display_label = QLabel("Your generated image will appear here. Click on the image to view full size.")
        self.image_display_label.setAlignment(Qt.AlignCenter)
        self.image_display_label.setMinimumSize(512, 512)
        self.image_display_label.mousePressEvent = self._open_image_viewer
        display_layout.addWidget(self.image_display_label)
        self.taskbar_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Image")
        self.save_button.clicked.connect(self._save_image)
        self.save_button.setEnabled(False)
        self.taskbar_layout.addWidget(self.save_button)
        self.copy_button = QPushButton("Copy Image")
        self.copy_button.clicked.connect(self._copy_image)
        self.copy_button.setEnabled(False)
        self.taskbar_layout.addWidget(self.copy_button)
        display_layout.addLayout(self.taskbar_layout)
        display_group.setLayout(display_layout)
        main_layout.addWidget(display_group, stretch=1)

    def _populate_models_dropdown(self):
        self.model_selector.clear()
        if not os.path.isdir(self.models_dir):
            QMessageBox.critical(self, "Directory Not Found", f"The model directory does not exist:\n{self.models_dir}")
            return
        models = [f for f in os.listdir(self.models_dir) if f.lower().endswith('.safetensors')]
        if models:
            self.model_selector.addItems(sorted(models))
        else:
            self.generate_button.setEnabled(False)
            QMessageBox.warning(self, "No Models Found", "No .safetensors models found in the directory.")

    def _handle_generate_image(self):
        prompt = self.prompt_input.toPlainText()
        if not prompt or prompt.isspace():
            QMessageBox.warning(self, "Missing Prompt", "Please enter a prompt.")
            return
        negative_prompt = self.negative_prompt_input.toPlainText().strip()
        steps = self.steps_spinbox.value()
        guidance_scale = self.cfg_spinbox.value()
        model_path = os.path.join(self.models_dir, self.model_selector.currentText())
        self.set_ui_busy(True)
        self.worker = ImageGenerationWorker(model_path, prompt, negative_prompt, steps, guidance_scale)
        self.worker.finished.connect(self._on_generation_finished)
        self.worker.error.connect(self._on_generation_error)
        self.worker.start()

    def _on_generation_finished(self, image: QImage):
        self.generated_pixmap = QPixmap.fromImage(image)
        self.image_display_label.setPixmap(self.generated_pixmap.scaled(self.image_display_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.set_ui_busy(False)
        self.save_button.setEnabled(True)
        self.copy_button.setEnabled(True)

    def _on_generation_error(self, error_message: str):
        self.set_ui_busy(False)
        QMessageBox.critical(self, "Generation Error", error_message)

    def set_ui_busy(self, is_busy: bool):
        self.generate_button.setEnabled(not is_busy)
        self.prompt_input.setEnabled(not is_busy)
        self.negative_prompt_input.setEnabled(not is_busy)
        self.model_selector.setEnabled(not is_busy)
        self.steps_spinbox.setEnabled(not is_busy)
        self.cfg_spinbox.setEnabled(not is_busy)
        if is_busy:
            self.image_display_label.setText("Generating image... Please wait.")
            self.save_button.setEnabled(False)
            self.copy_button.setEnabled(False)
            self.generated_pixmap = None

    def _save_image(self):
        if not self.generated_pixmap: return
        filePath, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "PNG Image (*.png);;JPEG Image (*.jpg)")
        if filePath: self.generated_pixmap.save(filePath)

    def _copy_image(self):
        if not self.generated_pixmap: return
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(self.generated_pixmap)
        QMessageBox.information(self, "Copied", "Image has been copied to the clipboard.")

    def _open_image_viewer(self, event):
        if self.generated_pixmap:
            self.viewer = ImageViewer(self.generated_pixmap, self)
            self.viewer.show()