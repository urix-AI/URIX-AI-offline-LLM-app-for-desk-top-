# # urix/utils/file_reader.py

# import os
# import logging
# from typing import Optional


# import PyPDF2
# import docx
# import openpyxl
# import pptx
# from PIL import Image
# import pytesseract

# # --- THIS IS THE MISSING LINE ---
# from urix.utils.logger import get_logger

# logger = get_logger(__name__)

# # --- CONFIGURATION ---
# # Max file size in bytes (10 MB)
# MAX_FILE_SIZE = 10 * 1024 * 1024 

# def extract_text_from_file(file_path: str, config: dict) -> Optional[str]:
#     """
#     Extracts text content from various file types, checking size limits.
    
#     Args:
#         file_path: The full path to the file.
#         config: The application's config dictionary to get tesseract_cmd_path.

#     Returns:
#         A string containing the extracted text, or an error message string.
#     """
#     try:
#         # 1. Check file size
#         if os.path.getsize(file_path) > MAX_FILE_SIZE:
#             logger.warning(f"File exceeds 10MB limit: {file_path}")
#             return "Error: File is larger than the 10 MB limit."

#         # 2. Get file extension to determine the parsing method
#         _, extension = os.path.splitext(file_path)
#         ext = extension.lower()
        
#         text_content = ""
        
#         # 3. Use the correct library based on the file extension
#         if ext in ['.txt', '.py', '.js', '.html', '.css', '.json', '.md']:
#             with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
#                 text_content = f.read()
        
#         elif ext == '.pdf':
#             with open(file_path, 'rb') as f:
#                 reader = PyPDF2.PdfReader(f)
#                 for page in reader.pages:
#                     text_content += page.extract_text() or ""
        
#         elif ext == '.docx':
#             doc = docx.Document(file_path)
#             for para in doc.paragraphs:
#                 text_content += para.text + "\n"
        
#         elif ext == '.xlsx':
#             workbook = openpyxl.load_workbook(file_path)
#             for sheet_name in workbook.sheetnames:
#                 sheet = workbook[sheet_name]
#                 text_content += f"--- Sheet: {sheet_name} ---\n"
#                 for row in sheet.iter_rows(values_only=True):
#                     # Convert each cell to string and filter out None values
#                     row_text = [str(cell) if cell is not None else "" for cell in row]
#                     text_content += ", ".join(row_text) + "\n"
        
#         elif ext == '.pptx':
#             prs = pptx.Presentation(file_path)
#             for slide in prs.slides:
#                 for shape in slide.shapes:
#                     if hasattr(shape, "text"):
#                         text_content += shape.text + "\n"

#         elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
#             tesseract_path = config.get('tesseract_cmd_path')
#             if not tesseract_path or not os.path.exists(tesseract_path):
#                 logger.error("Tesseract command path is not configured or invalid.")
#                 return "Error: Tesseract OCR is not configured. Please set the path in config.yaml."
            
#             pytesseract.pytesseract.tesseract_cmd = tesseract_path
#             text_content = pytesseract.image_to_string(Image.open(file_path))

#         else:
#             logger.warning(f"Unsupported file type: {ext}")
#             return f"Error: Unsupported file type '{ext}'."

#         logger.info(f"Successfully extracted text from {os.path.basename(file_path)}")
#         return text_content.strip()

#     except Exception as e:
#         logger.error(f"Failed to read or process file {file_path}: {e}", exc_info=True)
#         return f"Error: Could not read or process the file. It may be corrupted or in an unexpected format."