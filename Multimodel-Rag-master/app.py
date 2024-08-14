from flask import Flask, request, render_template, redirect, url_for
from utils import multi_modal_rag
import os

app = Flask(__name__)

# Configure upload folder
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query = request.form['query']
        pdf_file = request.files['pdf_file']

        if pdf_file and query:
            # Save the uploaded PDF
            pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_file.filename)
            pdf_file.save(pdf_path)

            # Process the query and PDF
            result_data = multi_modal_rag(pdf_path, query)

            # Pass the response and other details to the results page
            return redirect(url_for('results', response=result_data['response'], 
                                    relevant_text=result_data['relevant_text'], 
                                    relevant_images=result_data['relevant_images']))

    return render_template('index.html')

@app.route('/results')
def results():
    # Retrieve results to display
    response = request.args.get('response')
    relevant_text = request.args.getlist('relevant_text')
    relevant_images = request.args.getlist('relevant_images')
    print(response)

    return render_template('results.html', response=response, 
                           relevant_text=relevant_text, 
                           relevant_images=relevant_images)

if __name__ == '__main__':
    app.run(debug=True)
