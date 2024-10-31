import sys
import os
import pyperclip
import subprocess
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from io import BytesIO
from openai import OpenAI
import json
import logging
from langdetect import detect
import markdown
import requests

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Set Replicate API token before importing replicate
os.environ["REPLICATE_API_TOKEN"] = "REPLICATE API"  # Replace with your actual Replicate API key
import replicate

class ImageDownloadThread(QThread):
    finished = Signal(bytes)
    error = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()
            self.finished.emit(response.content)
        except Exception as e:
            self.error.emit(str(e))

class ImageGenerationThread(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, model, prompt, aspect_ratio, disable_safety):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.aspect_ratio = aspect_ratio
        self.disable_safety = disable_safety

    def run(self):
        try:
            output = replicate.run(
                self.model,
                input={
                    "prompt": self.prompt,
                    "aspect_ratio": self.aspect_ratio,
                    "disable_safety_checker": self.disable_safety
                }
            )
            # Convert output to list of strings if it's not already
            if isinstance(output, list):
                output = [str(url) for url in output]
            else:
                output = [str(output)]
            self.finished.emit(output)
        except Exception as e:
            self.error.emit(str(e))

class ImageGeneratorDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.last_prompt = ""

    def initUI(self):
        self.setWindowTitle('Image Generation Interface')
        layout = QtWidgets.QVBoxLayout()

        # Model selection
        model_label = QtWidgets.QLabel('Select model:')
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.addItems(['black-forest-labs/flux-dev', 'black-forest-labs/flux-pro'])
        layout.addWidget(model_label)
        layout.addWidget(self.model_combo)

        # Prompt input
        prompt_label = QtWidgets.QLabel('Enter your prompt:')
        self.prompt_input = QtWidgets.QLineEdit()
        layout.addWidget(prompt_label)
        layout.addWidget(self.prompt_input)

        # Aspect ratio input
        aspect_label = QtWidgets.QLabel('Enter aspect ratio (e.g., 16:9):')
        self.aspect_input = QtWidgets.QLineEdit()
        self.aspect_input.setText('16:9')
        layout.addWidget(aspect_label)
        layout.addWidget(self.aspect_input)

        # Safety checker checkbox
        self.safety_checker = QtWidgets.QCheckBox('Disable Safety Checker')
        layout.addWidget(self.safety_checker)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.generate_button = QtWidgets.QPushButton('Generate Image')
        self.last_prompt_button = QtWidgets.QPushButton('Use Last Prompt')
        button_layout.addWidget(self.generate_button)
        button_layout.addWidget(self.last_prompt_button)
        layout.addLayout(button_layout)

        # Status label
        self.status_label = QtWidgets.QLabel('')
        layout.addWidget(self.status_label)

        # Image preview
        self.preview_label = QtWidgets.QLabel('Image Preview:')
        layout.addWidget(self.preview_label)
        
        self.image_label = QtWidgets.QLabel()
        self.image_label.setMinimumSize(400, 400)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("QLabel { background-color: #f0f0f0; border: 1px solid #cccccc; }")
        layout.addWidget(self.image_label)

        # Output URL
        self.output_label = QtWidgets.QLabel('Output URL:')
        self.output_url = QtWidgets.QLineEdit()
        self.output_url.setReadOnly(True)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output_url)

        # Download button
        self.download_button = QtWidgets.QPushButton('Download Last Created Image')
        layout.addWidget(self.download_button)

        # Close button
        self.close_button = QtWidgets.QPushButton('Close Window')
        layout.addWidget(self.close_button)

        self.setLayout(layout)

        # Connect buttons to functions
        self.generate_button.clicked.connect(self.generate_image)
        self.last_prompt_button.clicked.connect(self.use_last_prompt)
        self.download_button.clicked.connect(self.download_image)
        self.close_button.clicked.connect(self.accept)

        # Set a reasonable minimum size for the dialog
        self.setMinimumSize(600, 800)

    def generate_image(self):
        prompt = self.prompt_input.text()
        aspect_ratio = self.aspect_input.text()
        disable_safety = self.safety_checker.isChecked()
        model = self.model_combo.currentText()
        
        self.status_label.setText("Generating...")
        self.generate_button.setEnabled(False)
        self.image_label.clear()
        self.image_label.setText("Generating image...")
        
        self.thread = ImageGenerationThread(model, prompt, aspect_ratio, disable_safety)
        self.thread.finished.connect(self.on_generation_finished)
        self.thread.error.connect(self.on_generation_error)
        self.thread.start()

    def on_generation_finished(self, output):
        if isinstance(output, list) and output:
            url = str(output[0])  # Ensure it's a string
            self.output_url.setText(url)
            self.status_label.setText(f"Generated {len(output)} images. Displaying the first one.")
            print(f"Generated image URL: {url}")  # Debug print
            
            # Download and display the image
            self.download_thread = ImageDownloadThread(url)
            self.download_thread.finished.connect(self.display_image)
            self.download_thread.error.connect(lambda e: self.status_label.setText(f"Error loading preview: {e}"))
            self.download_thread.start()
        else:
            self.status_label.setText("No images were generated.")
        
        self.last_prompt = self.prompt_input.text()
        self.generate_button.setEnabled(True)

    def display_image(self, image_data):
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        
        # Scale the image to fit the label while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        self.image_label.setPixmap(scaled_pixmap)
        self.status_label.setText("Image generated and displayed successfully.")

    def on_generation_error(self, error_msg):
        self.status_label.setText(f"Error generating image: {error_msg}")
        self.generate_button.setEnabled(True)
        self.image_label.clear()
        self.image_label.setText("Error generating image")

    def use_last_prompt(self):
        if self.last_prompt:
            self.prompt_input.setText(self.last_prompt)
        else:
            self.status_label.setText("No previous prompt available.")

    def download_image(self):
        url = self.output_url.text()
        if not url:
            self.status_label.setText("No image URL available. Generate an image first.")
            return

        try:
            response = requests.get(url)
            response.raise_for_status()
            
            file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Image", "", "Images (*.png *.jpg *.jpeg)")
            if file_name:
                with open(file_name, 'wb') as file:
                    file.write(response.content)
                self.status_label.setText(f"Image downloaded successfully: {file_name}")
            else:
                self.status_label.setText("Download cancelled.")
        except requests.RequestException as e:
            self.status_label.setText(f"Error downloading image: {str(e)}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.image_label.pixmap():
            # Rescale the image when the window is resized
            scaled_pixmap = self.image_label.pixmap().scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)

class MenuBarApp(QtWidgets.QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)
        self.create_menu_bar()
        self.load_api_key()
        self.current_dialog = None

    def create_menu_bar(self):
        self.tray = QtWidgets.QSystemTrayIcon(self)
        icon = self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
        self.tray.setIcon(icon)
        self.tray.setVisible(True)

        self.menu = QtWidgets.QMenu()
        
        self.menu.addAction("Proofread", self.on_proofread)
        self.menu.addAction("Rewrite", self.on_rewrite)
        self.menu.addAction("Make Friendly", self.on_friendly)
        self.menu.addAction("Make Professional", self.on_professional)
        self.menu.addAction("Make Concise", self.on_concise)
        self.menu.addAction("Summarize", self.on_summary)
        self.menu.addAction("Extract Key Points", self.on_keypoints)
        self.menu.addAction("Convert to Table", self.on_table)
        self.menu.addAction("Convert to List", self.on_list)
        
        self.menu.addSeparator()
        self.menu.addAction("Generate Image", self.on_generate_image)
        
        self.menu.addSeparator()
        self.menu.addAction("Exit", self.quit)

        self.tray.activated.connect(self.show_menu)

    def show_menu(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            self.menu.popup(QtGui.QCursor.pos())

    def on_generate_image(self):
        if self.current_dialog:
            self.current_dialog.close()
        dialog = ImageGeneratorDialog()
        self.current_dialog = dialog
        dialog.exec()

    def on_proofread(self):
        self.process_option('Proofread', self.get_selected_text())

    def on_rewrite(self):
        self.process_option('Rewrite', self.get_selected_text())

    def on_friendly(self):
        self.process_option('Friendly', self.get_selected_text())

    def on_professional(self):
        self.process_option('Professional', self.get_selected_text())

    def on_concise(self):
        self.process_option('Concise', self.get_selected_text())

    def on_summary(self):
        self.process_option('Summary', self.get_selected_text())

    def on_keypoints(self):
        self.process_option('Key Points', self.get_selected_text())

    def on_table(self):
        self.process_option('Table', self.get_selected_text())

    def on_list(self):
        self.process_option('List', self.get_selected_text())

    def get_selected_text(self):
        try:
            return pyperclip.paste()
        except Exception as e:
            print(f"Error accessing clipboard: {e}")
            return ""

    def load_api_key(self):
        config_file = 'config.json'
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.api_key = config.get('api_key')
        except FileNotFoundError:
            self.api_key = None

        if not self.api_key:
            self.api_key, ok = QtWidgets.QInputDialog.getText(None, "OpenAI API Key", "Enter your OpenAI API Key:")
            if ok and self.api_key:
                self.save_api_key(self.api_key)
            else:
                print("No API key provided. AI processing will not work.")

    def save_api_key(self, api_key):
        config_file = 'config.json'
        config = {'api_key': api_key}
        with open(config_file, 'w') as f:
            json.dump(config, f)

    def process_option(self, option, input_text):
        if not input_text:
            self.show_error_message("No Text Selected", "Please select some text before choosing an option.")
            return

        if not self.api_key:
            self.show_error_message("API Key Missing", "Please provide an OpenAI API key to use this feature.")
            return

        print(f"Processing '{option}' for text:")
        print(input_text)

        try:
            processed_text = self.call_openai_api(option, input_text)
            
            input_lang = detect_language(input_text)
            output_lang = detect_language(processed_text)
            
            if input_lang != output_lang:
                logging.warning(f"Language mismatch detected. Input: {input_lang}, Output: {output_lang}")
                self.show_error_message("Language Mismatch", f"The API response is in a different language. Input: {input_lang}, Output: {output_lang}")
            
            pyperclip.copy(processed_text)
            self.show_result_dialog(option, input_text, processed_text)
        except Exception as e:
            self.show_error_message("Error", f"An error occurred while processing the text: {str(e)}")

    def call_openai_api(self, option, input_text):
        client = OpenAI(api_key=self.api_key)
        
        base_instruction = """
        Process the following text according to the given instructions. 
        IMPORTANT: 
        1. Always respond in the EXACT SAME LANGUAGE as the input text.
        2. If the input is in Portuguese, use European Portuguese (from Portugal), not Brazilian Portuguese.
        3. DO NOT translate the text to any other language.
        4. Maintain the original language, dialect, and style of the input text in your response.
        """
        
        prompts = {
            'Proofread': f"{base_instruction} Proofread the text, focusing on grammar, spelling, punctuation, style, and clarity. Return a corrected version.",
            'Rewrite': f"{base_instruction} Rewrite the text, focusing on clarity, style, and coherence. Maintain the original meaning and tone.",
            'Friendly': f"{base_instruction} Rewrite the text to make it friendlier. Focus on a warm, approachable, and conversational tone.",
            'Professional': f"{base_instruction} Rewrite the text to make it more professional. Use formal, respectful language and improve clarity and structure.",
            'Concise': f"{base_instruction} Rewrite the text to make it more concise. Focus on clarity and brevity while maintaining the original meaning.",
            'Summary': f"{base_instruction} Summarize the text, focusing on key points and main ideas. Ensure the summary is clear and concise.",
            'Key Points': f"{base_instruction} Extract the key points from the text. Present them in a bulleted or numbered list.",
            'Table': f"""{base_instruction} Create a table from the text. Organize the information in a clear, tabular format.
            Use markdown-style table formatting. Follow these guidelines:
            1. Use '|' to separate columns.
            2. Use a row of '---' or ':---:' (for center alignment) or '---:' (for right alignment) to separate the header from the body.
            3. Ensure proper alignment of the content for readability.
            4. If the table is wide, consider using only essential columns to fit the data.
            Example format:
            | Header1 | Header2 | Header3 |
            |---------|:-------:|--------:|
            | Left    | Center  |   Right |
            | Data    | Data    |    Data |
            """,
            'List': f"{base_instruction} Transform the text into a list. Break down the information into clear, concise points. Present the list in either bulleted or numbered form."
        }

        full_prompt = f"{prompts[option]}\n\nInput text language: {detect_language(input_text)}\n\n{input_text}"
        
        logging.debug(f"Sending to API - Option: {option}")
        logging.debug(f"Full prompt: {full_prompt}")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that processes text according to specific instructions. You MUST ALWAYS respond in the EXACT SAME LANGUAGE as the input text. Never translate or change the language."},
                {"role": "user", "content": full_prompt}
            ]
        )

        result = response.choices[0].message.content.strip()
        logging.debug(f"Received from API: {result}")
        
        return result

    def handle_qa(self, input_text, processed_text, question):
        if not question.strip():
            return "Please enter a question."

        try:
            client = OpenAI(api_key=self.api_key)
            
            # Create a summary of changes instead of sending full texts
            changes_summary = f"Changes made: The text was transformed from the original version to a processed version. Length changed from {len(input_text)} to {len(processed_text)} characters."
            
            prompt = f"""
            Context: {changes_summary}
            
            Text to analyze: {processed_text}
            
            Question: {question}

            Please provide a detailed answer about the text, focusing specifically on addressing the question asked.
            Respond in the same language as the text.
            """

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant analyzing text and answering questions about it."},
                    {"role": "user", "content": prompt}
                ]
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"Error in handle_qa: {str(e)}")
            return f"Error processing question: {str(e)}"

    def show_qa_dialog(self, input_text, processed_text):
        if self.current_dialog:
            self.current_dialog.close()
        
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle("Ask Questions")
        layout = QtWidgets.QVBoxLayout()

        # Original response display
        response_label = QtWidgets.QLabel("Original Response:")
        layout.addWidget(response_label)
        
        response_display = QtWidgets.QTextEdit()
        response_display.setReadOnly(True)
        response_display.setPlainText(processed_text)
        response_display.setMinimumHeight(200)
        layout.addWidget(response_display)

        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(separator)

        # Question input
        question_label = QtWidgets.QLabel("Enter your question about the text:")
        layout.addWidget(question_label)
        
        question_input = QtWidgets.QTextEdit()
        question_input.setMaximumHeight(100)
        layout.addWidget(question_input)

        # Answer display
        answer_label = QtWidgets.QLabel("Answer:")
        layout.addWidget(answer_label)
        
        answer_display = QtWidgets.QTextEdit()
        answer_display.setReadOnly(True)
        layout.addWidget(answer_display)

        # Ask button
        ask_button = QtWidgets.QPushButton("Ask")
        def on_ask():
            question = question_input.toPlainText()
            answer = self.handle_qa(input_text, processed_text, question)
            answer_display.setPlainText(answer)
        ask_button.clicked.connect(on_ask)
        layout.addWidget(ask_button)

        # Close button
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.setLayout(layout)
        dialog.resize(800, 800)  # Increased height to accommodate the original response
        
        self.current_dialog = dialog
        dialog.exec()

    def show_result_dialog(self, option, input_text, processed_text):
        if self.current_dialog:
            self.current_dialog.close()
            
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle("Processed Text")
        layout = QtWidgets.QVBoxLayout()
        
        text_edit = QtWidgets.QTextEdit()
        text_edit.setReadOnly(True)
        
        if option == 'Table':
            # Convert markdown to HTML for better table display
            html_content = markdown.markdown(processed_text, extensions=['tables'])
            text_edit.setHtml(f"<h3>Option: {option}</h3>"
                              f"{html_content}"
                              "<p>The processed text has been copied to your clipboard.</p>")
        else:
            # For non-table options, use plain text as before
            text_edit.setPlainText(f"Option: {option}\n\n"
                                   f"{processed_text}\n\n"
                                   "The processed text has been copied to your clipboard.")
        
        layout.addWidget(text_edit)
        
        button_layout = QtWidgets.QHBoxLayout()
        
        qa_button = QtWidgets.QPushButton("Ask Questions")
        qa_button.clicked.connect(lambda: self.show_qa_dialog(input_text, processed_text))
        button_layout.addWidget(qa_button)
        
        ok_button = QtWidgets.QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        button_layout.addWidget(ok_button)
        
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.resize(800, 600)
        
        self.current_dialog = dialog
        dialog.exec()

    def show_error_message(self, title, message):
        QtWidgets.QMessageBox.critical(None, title, message)

def detect_language(text):
    try:
        lang = detect(text)
        if lang == 'pt':
            return "Portuguese (European)"  # Assuming European Portuguese by default
        elif lang == 'en':
            return "English"
        else:
            return f"Other ({lang})"
    except:
        return "Unknown"

if __name__ == "__main__":
    app = MenuBarApp(sys.argv)
    sys.exit(app.exec())
