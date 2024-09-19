# PDF Text Extraction with Google Vision API

## Overview

This project provides a solution for extracting text from PDF files using the Google Vision API. The code converts each page of a PDF into an image, preprocesses the image to enhance OCR accuracy, and then uses the Google Vision API to detect and extract text. The extracted text is saved to a text file for each PDF.

## Features

- **PDF to Image Conversion:** Converts PDF pages to images using the `pdf2image` library.
- **Text Detection:** Utilizes the Google Vision API to perform OCR and detect text in the images.
- **Image Preprocessing:** Enhances OCR accuracy by converting images to grayscale.
- **Parallel Processing:** Uses `ThreadPoolExecutor` to process pages concurrently, improving performance.
- **Output Formatting:** Saves the extracted text in a structured format, with each page's content clearly separated.

## Advantages

- **High Accuracy:** Utilizes Google Vision API, which is known for its advanced machine learning models and high-quality text extraction.
- **Efficient Processing:** Concurrent processing of PDF pages speeds up the extraction process, especially for large PDFs.
- **Customizable:** Easily adaptable to different PDFs and output requirements.
- **Enhanced OCR:** Includes preprocessing steps like grayscale conversion to improve OCR results.

## Requirements

- Python 3.x
- Required Python packages:
  - `google-cloud-vision`
  - `pdf2image`
  - `Pillow`
  - `numpy`
  - `opencv-python`
  - `concurrent.futures`

## Setup

1. **Install Dependencies:**

   Install the required Python packages using pip:

   ```bash
   pip install google-cloud-vision pdf2image Pillow numpy opencv-python
2. **Google Vision API Credentials:**
- Ensure you have a Google Cloud project with the Vision API enabled.
- Download your credentials JSON file.
- Set the path to your credentials JSON file in the environment variable GOOGLE_APPLICATION_CREDENTIALS:

  ```bash
  export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"

3. **Usage:**
   Place your PDF files in the pdfs folder.
   Run the script:

   ```bash
   python script_name.py
## Code Explanation
- detect_text_from_image(image_data): Detects text from an image using the Google Vision API.
- preprocess_image(image): Converts the image to grayscale to improve OCR accuracy.
- process_page(page, page_number): Converts a PDF page to an image, preprocesses it, performs OCR, and returns the extracted text.
- process_pdf(pdf_path, output_folder): Processes each page of a PDF and writes the extracted text to a file.
- process_all_pdfs(input_folder, output_folder): Iterates over all PDFs in the input folder and processes each one.



