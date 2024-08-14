from flask import Flask, render_template, request, send_file
import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter
from reportlab.lib import utils
from reportlab.pdfgen import canvas
from io import BytesIO
from urllib.parse import urljoin

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    url = request.form['url']
    
    # Fetch the webpage content
    response = requests.get(url)
    webpage = response.text
    
    # Parse the HTML content
    soup = BeautifulSoup(webpage, 'html.parser')
    
    # Extract all text
    text = soup.get_text()

    # Create PDF
    pdf_file_path = "webpage_content.pdf"
    c = canvas.Canvas(pdf_file_path, pagesize=letter)
    
    # Set font and size
    c.setFont("Helvetica", 12)
    
    # Add text to PDF, handling long text and pages
    text_object = c.beginText(40, 750)
    text_object.setTextOrigin(40, 750)
    text_object.setLeading(14)  # Line spacing

    # Split text into lines and add to the PDF
    lines = text.splitlines()
    for line in lines:
        text_object.textLine(line)
        if text_object.getY() < 50:  # Create a new page if there's not enough space
            c.drawText(text_object)
            c.showPage()
            text_object = c.beginText(40, 750)
            text_object.setFont("Helvetica", 12)
            text_object.setLeading(14)
    
    c.drawText(text_object)
    
    # Process images
    image_tags = soup.find_all('img')
    y_position = 700  # Start position for images
    for img_tag in image_tags:
        img_url = img_tag.get('src')
        
        # Handle relative URLs
        if not img_url.startswith(('http://', 'https://')):
            img_url = urljoin(url, img_url)
        
        try:
            # Fetch the image data
            img_data = requests.get(img_url).content
            image = utils.ImageReader(BytesIO(img_data))
            img_width, img_height = image.getSize()
            aspect_ratio = img_width / img_height
            max_width, max_height = 500, 400
            if img_width > max_width:
                img_width = max_width
                img_height = img_width / aspect_ratio
            if img_height > max_height:
                img_height = max_height
                img_width = img_height * aspect_ratio
            
            # Add image to PDF
            c.drawImage(image, 40, y_position, width=img_width, height=img_height)
            y_position -= (img_height + 20)  # Update y_position for next image
            
            # Start a new page if y_position is too low
            if y_position < 100:
                c.showPage()
                y_position = 700
        
        except Exception as e:
            print(f"Failed to process image from {img_url}: {e}")

    # Add links to audio files (cannot embed audio directly into PDFs)
    audio_tags = soup.find_all('audio')
    for audio_tag in audio_tags:
        audio_src = audio_tag.get('src')
        if audio_src:
            c.showPage()
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, 750, "Audio File")
            c.setFont("Helvetica", 12)
            c.drawString(40, 730, f"Audio available at: {audio_src}")
    
    # Save PDF
    c.save()

    # Return the PDF file
    return send_file(pdf_file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True,port=5656)
