A Python-based GUI tool with capabilities for language detection, text processing, and image generation, using GPT4o-mini and Replicate Flux API.

You’ll need valid Replicate token and OpenAI API key.

Download the files. 
On the config.json file replace with your Open ai API key.
On the main.py file , replace your Replicate token here: 
os.environ["REPLICATE_API_TOKEN"] = "REPLICATE API"  # Replace with your actual Replicate API key)

Navegate to the folder
Install dependencies using pip
pip install -r requirements.txt
Run the application: python main.py

Functionality Overview

	•	Text Processing: Detects language and processes text with OpenAI API integration.
	•	Image Generation: Generates images based on text prompts with adjustable parameters such as aspect ratio and safety filters, leveraging the Replicate API.
	•	Clipboard Integration: Allows easy copying and pasting of content.

USE:
Select text, copy it and then on the menu bar icon select one of the options: 
Proofread
Rewrite
Make Friendly
Make Professional
Make Concise
Summarize
Extract Key Points
Convert to Table
Convert to List

A new UI window will show with the reply from GPT4o-mini. 
It is possible to engage in Q&A about the selected text.

Generate image option will create an image with FLux dev or Pro and display it on the UI, with an option to downloaded the image. 



Distributed under the MIT License. See LICENSE for details.
