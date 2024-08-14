import os
import time
import logging
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from PIL import Image
import fitz  # PyMuPDF
from groq import Groq

# Initialize embedding models
text_model = SentenceTransformer('all-MiniLM-L6-v2')
image_model = SentenceTransformer('clip-ViT-B-32')

# Initialize Groq client
groq_client = Groq(api_key="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")

# Initialize Faiss indexes
text_dimension = 384
image_dimension = 512
text_index = faiss.IndexFlatL2(text_dimension)
image_index = faiss.IndexFlatL2(image_dimension)

text_id_to_content = {}
image_id_to_content = {}

# Set up logging
logging.basicConfig(filename='groq_errors.log', level=logging.ERROR)

def extract_images_from_page(page, image_dir, page_num):
    image_paths = []

    for img_index, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        base_image = page.get_pixmap(xref)  # Get the Pixmap from the xref

        # Generate a unique filename for each image
        image_filename = f"page{page_num+1}_img{img_index+1}.png"
        image_path = os.path.join(image_dir, image_filename)

        # Save the image
        base_image.save(image_path)

        image_paths.append(image_path)

    return image_paths



def parse_pdf(pdf_path):
    text_content = ""
    image_list = []

    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    image_dir = f"{pdf_name}_images"
    os.makedirs(image_dir, exist_ok=True)

    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Extract text
        text_content += page.get_text() + "\n"

        # Extract images
        image_list.extend(extract_images_from_page(page, image_dir, page_num))

    doc.close()
    return text_content, image_list

def chunk_text(text, chunk_size=200, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def process_text(text_content):
    chunks = chunk_text(text_content)
    embeddings = text_model.encode(chunks)

    for i, emb in enumerate(embeddings):
        text_index.add(np.array([emb]))
        text_id_to_content[text_index.ntotal - 1] = {"content": chunks[i]}

def process_images(image_list):
    for i, img_path in enumerate(image_list):
        with Image.open(img_path) as img:
            emb = image_model.encode(img)
        image_index.add(np.array([emb]))
        image_id_to_content[image_index.ntotal - 1] = {"image_id": i, "image_path": img_path}

def process_query(query, k=5):
    text_query_emb = text_model.encode([query])

    D_text, I_text = text_index.search(text_query_emb, k)
    relevant_text = [text_id_to_content[idx]["content"] for idx in I_text[0]]

    image_query_emb = image_model.encode([query])

    D_image, I_image = image_index.search(image_query_emb, k)
    relevant_images = [image_id_to_content.get(idx, {}).get("image_path", "Image not found") for idx in I_image[0]]

    return relevant_text, relevant_images

def generate_response_with_retry(query, relevant_text, relevant_images, retries=3, delay=5):
    context = "\n".join(relevant_text)
    prompt = f"""Context: {context}

    Query: {query}

    Relevant image paths: {relevant_images}

    Please provide a response to the query based on the given context and mention any relevant images by their paths.
    """

    for attempt in range(retries):
        try:
            response = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                    {"role": "user", "content": prompt}
                ],
                model="llama3-70b-8192",  # Adjust this to the appropriate Groq model name
                max_tokens=1000
            )
            return response.choices[0].message.content
        except groq.InternalServerError as e:
            if attempt < retries - 1:
                print(f"Error occurred: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"Failed after {retries} attempts. Error: {e}")
                logging.error(f"InternalServerError occurred: {e}")
                raise

def multi_modal_rag(pdf_path, query):
    try:
        text_content, image_list = parse_pdf(pdf_path)
        process_text(text_content)
        process_images(image_list)

        relevant_text, relevant_images = process_query(query)
        response = generate_response_with_retry(query, relevant_text, relevant_images)
        
        return {
            'response': response,
            'relevant_text': relevant_text,
            'relevant_images': relevant_images
        }
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        logging.error(f"An error occurred: {str(e)}")
        raise
