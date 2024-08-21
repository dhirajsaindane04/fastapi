from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import fitz  # PyMuPDF
import io
import os
import google.generativeai as genai
import json
import logging

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_gemini_response(input_text, image_parts):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt =  """
        Analyze the 'Invoice' PDF in @docs. Extract all data and format it into the following JSON structure. Ensure each field is accurately filled with data from the PDF, and if any data is missing, use null for that field. Ensure that each field is present in the output JSON, even if the value is null. For financial fields, use numeric values (integers or floats) and ensure proper formatting.

    {
        "buyer_address": null,
        "buyer_city": null,
        "buyer_country": null,
        "buyer_name": null,
        "buyer_postal_code": null,
        "currency": null,
        "due_date": null,
        "einvoiceTypeCode": null,
        "invoice_date": null,
        "invoice_no": null,
        "items": [
            {
                "Amt": 0.0,
                "Description": null,
                "Disc": 0.0,
                "Net Amt": 0.0,
                "No.": 0,
                "Qty": 0.0,
                "Tax": 0.0,
                "U/Price": 0.0
            }
        ],
        "payment_term": null,
        "reference_no": null,
        "supplier_service_tax_id": null,
        "subtotal": 0.0,
        "supplier_address": null,
        "supplier_city": null,
        "supplier_contact": null,
        "supplier_country": null,
        "supplier_email": null,
        "supplier_name": null,
        "supplier_postal_code": null,
        "supplier_reg_no": null,
        "supplier_website": null,
        "total": 0.0,
        "refund": 0.0,
        "service_tax": 0.0,
        "apply_amount": 0.0,
        "bank_transfer": 0.0,
        "discount":0.0
    } make sure supplier_service_tax_id,supplier_postal_code,supplier_country,currency extracted properly
    """
    response = model.generate_content([input_text, image_parts[0], prompt])
    
    response_text = response.text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:-3].strip()

    response_text = ' '.join(response_text.split())

    try:
        response_json = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error: {e}")
        response_json = {'error': 'Invalid JSON response from the model'}
    
    return response_json

async def input_image_setup(uploaded_file: UploadFile):
    if uploaded_file:
        bytes_data = await uploaded_file.read()

        if uploaded_file.content_type == "application/pdf":
            pdf_document = fitz.open(stream=bytes_data, filetype="pdf")
            image_parts = []
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                image_parts.append({
                    "mime_type": "image/png",
                    "data": img_data
                })
            return image_parts
        else:
            return [
                {
                    "mime_type": uploaded_file.content_type,
                    "data": bytes_data
                }
            ]
    else:
        raise FileNotFoundError("No file uploaded")

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="No file part")
    
    if file.filename == '':
        raise HTTPException(status_code=400, detail="No selected file")

    try:
        image_data = await input_image_setup(file)
        response = get_gemini_response("Extract invoice data", image_data)
        return JSONResponse(content=response)
    except FileNotFoundError as e:
        logger.error(f"File Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
