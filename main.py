import os
import io
import numpy as np
from PIL import Image
import cv2
from google.cloud import vision
from pdf2image import convert_from_path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set the environment variable for Google Vision API credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'' #add the path of the json credential file which is downloaded 

def detect_text_from_image(image_data):
    """
    Detects text in an image file using Google Vision API and returns it.
    
    Args:
        image_data (bytes): The image data in bytes format.
        
    Returns:
        str: The detected text.
    """
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_data)

    # Perform text detection
    response = client.text_detection(image=image)
    texts = response.text_annotations

    # Extract and return the detected text (first annotation contains full text)
    if texts:
        return texts[0].description
    else:
        return ""

def preprocess_image(image):
    """
    Preprocesses the image to enhance OCR accuracy by converting it to grayscale.
    
    Args:
        image (PIL.Image.Image): The image to preprocess.
        
    Returns:
        PIL.Image.Image: The preprocessed image.
    """
    # Convert PIL image to OpenCV format
    image_np = np.array(image)
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    
    # Convert back to PIL image
    return Image.fromarray(gray)

def process_page(page, page_number):
    """
    Processes a single page of PDF: converts to image, preprocesses, performs OCR, and returns the extracted text.
    
    Args:
        page (PIL.Image.Image): The PDF page as a PIL image.
        page_number (int): The page number.
        
    Returns:
        tuple: A tuple containing the page number and extracted text.
    """
    # Convert page to a BytesIO object
    buffer = io.BytesIO()
    page = preprocess_image(page)
    page.save(buffer, format="PNG")
    image_data = buffer.getvalue()

    # Perform OCR on the image data
    extracted_text = detect_text_from_image(image_data)
    
    return (page_number, extracted_text)

def process_pdf(pdf_path, output_folder):
    """
    Processes each page in a PDF file and performs OCR.
    
    Args:
        pdf_path (str): The path to the PDF file.
        output_folder (str): The folder where the output text file will be saved.
    """
    # Convert PDF to images
    pages = convert_from_path(pdf_path)

    # Define the output text file path
    output_text_file = os.path.join(output_folder, f"{os.path.basename(pdf_path)}.txt")
    
    with open(output_text_file, 'w', encoding='utf-8') as text_file:
        # Use ThreadPoolExecutor to process pages in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_page, page, page_number)
                       for page_number, page in enumerate(pages, start=1)]
            results = sorted([future.result() for future in as_completed(futures)], key=lambda x: x[0])
        
        # Write results to file in the correct order
        for page_number, text in results:
            text_file.write(f"\n--- Page {page_number} ---\n")
            text_file.write(text)
            text_file.write("\n\n")

def process_all_pdfs(input_folder, output_folder):
    """
    Processes all PDFs in the input folder and stores the results in the output folder.
    
    Args:
        input_folder (str): The folder containing PDF files.
        output_folder (str): The folder where the output text files will be saved.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for file_name in os.listdir(input_folder):
        if file_name.endswith(".pdf"):
            pdf_path = os.path.join(input_folder, file_name)
            print(f"Processing {pdf_path}...")
            process_pdf(pdf_path, output_folder)

if __name__ == "__main__":
    input_folder = r"" #add the path of the folder that contains the pdf 
    output_folder = r"" #add the path of the output folder 
    process_all_pdfs(input_folder, output_folder)
    print("Text extraction completed!")
