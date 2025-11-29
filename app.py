import os
import io
import zipfile
import tempfile
# تم استيراد send_from_directory
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, make_response, send_from_directory
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.errors import FileNotDecryptedError
import fitz  # PyMuPDF
from PIL import Image
import pdfkit
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'a_super_secret_key'

# ... (كل الكود من parse_page_numbers حتى نهاية دوال المعالجة يبقى كما هو بدون تغيير) ...
# --- Helper function for parsing page ranges (used in multiple tools) ---
def parse_page_numbers(page_str, max_pages):
    pages_to_process = set()
    if not page_str:
        return None
    
    parts = page_str.replace(' ', '').split(',')
    for part in parts:
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                if start > end:
                    start, end = end, start
                pages_to_process.update(range(max(1, start), min(max_pages, end) + 1))
            except ValueError:
                raise ValueError("Invalid page range format.")
        else:
            try:
                page_num = int(part)
                if 1 <= page_num <= max_pages:
                    pages_to_process.add(page_num)
            except ValueError:
                raise ValueError("Invalid page number format.")
    return sorted([p - 1 for p in pages_to_process])

# --- Home Page ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Tool Routes ---

@app.route('/merge')
def merge():
    return render_template('merge.html')

@app.route('/split')
def split():
    return render_template('split.html')

@app.route('/extract_images')
def extract_images():
    return render_template('extract_images.html')

@app.route('/extract_pages')
def extract_pages():
    return render_template('extract_pages.html')

@app.route('/word_to_pdf')
def word_to_pdf():
    return render_template('word_to_pdf.html')

@app.route('/pdf_to_word')
def pdf_to_word():
    return render_template('pdf_to_word.html')

@app.route('/pdf_to_images')
def pdf_to_images():
    return render_template('pdf_to_images.html')

@app.route('/image_to_pdf')
def image_to_pdf():
    return render_template('image_to_pdf.html')

@app.route('/html_to_pdf')
def html_to_pdf():
    return render_template('html_to_pdf.html')

@app.route('/compress')
def compress():
    return render_template('compress.html')

@app.route('/protect')
def protect():
    return render_template('protect.html')

@app.route('/unlock')
def unlock():
    return render_template('unlock.html')

@app.route('/rotate')
def rotate():
    return render_template('rotate.html')

@app.route('/add_page_numbers')
def add_page_numbers():
    return render_template('add_page_numbers.html')

@app.route('/add_watermark')
def add_watermark():
    return render_template('add_watermark.html')

@app.route('/delete_pages')
def delete_pages():
    return render_template('delete_pages.html')

@app.route('/organize_pages')
def organize_pages():
    return render_template('organize_pages.html')

@app.route('/repair')
def repair():
    return render_template('repair.html')

@app.route('/pdfa_to_pdf')
def pdfa_to_pdf():
    return render_template('pdfa_to_pdf.html')


# --- Processing Logic (unchanged) ---

@app.route('/merge-process', methods=['POST'])
def merge_process():
    files = request.files.getlist('pdf_files')
    merger = PdfWriter()
    for file in files:
        if file:
            reader = PdfReader(file.stream)
            for page in reader.pages:
                merger.add_page(page)
    output_io = io.BytesIO()
    merger.write(output_io)
    output_io.seek(0)
    merger.close()
    return send_file(output_io, as_attachment=True, download_name='merged.pdf', mimetype='application/pdf')

@app.route('/split-process', methods=['POST'])
def split_process():
    file = request.files['pdf_file']
    if not file: return "No file uploaded", 400
    reader = PdfReader(file.stream)
    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, 'w') as zipf:
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            page_io = io.BytesIO()
            writer.write(page_io)
            page_io.seek(0)
            zipf.writestr(f'page_{i + 1}.pdf', page_io.getvalue())
    zip_io.seek(0)
    return send_file(zip_io, mimetype='application/zip', as_attachment=True, download_name='split_pages.zip')

@app.route('/extract-images-process', methods=['POST'])
def extract_images_process():
    file = request.files['pdf_file']
    if not file: return "No file uploaded", 400
    pdf_document = fitz.open(stream=file.read(), filetype="pdf")
    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, 'w') as zipf:
        image_count = 0
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                image_count += 1
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                zipf.writestr(f"image_{page_num + 1}_{img_index + 1}.{image_ext}", image_bytes)
    zip_io.seek(0)
    if image_count == 0: 
        flash("No images found in the PDF.")
        return redirect(url_for('extract_images'))
    return send_file(zip_io, mimetype='application/zip', as_attachment=True, download_name='extracted_images.zip')

@app.route('/extract-pages-process', methods=['POST'])
def extract_pages_process():
    file = request.files['pdf_file']
    page_numbers_str = request.form['page_numbers']
    if not file: 
        flash("No file uploaded")
        return redirect(url_for('extract_pages'))
    
    try:
        reader_for_count = PdfReader(file.stream)
        max_pages = len(reader_for_count.pages)
        file.stream.seek(0)
        
        page_indices = parse_page_numbers(page_numbers_str, max_pages)
        
        reader = PdfReader(file.stream)
        writer = PdfWriter()
        for i in page_indices:
            writer.add_page(reader.pages[i])
            
        if not writer.pages:
            flash("Selected page numbers are out of range or invalid.")
            return redirect(url_for('extract_pages'))
            
        output_io = io.BytesIO()
        writer.write(output_io)
        output_io.seek(0)
        return send_file(output_io, as_attachment=True, download_name='extracted_pages.pdf', mimetype='application/pdf')
    except ValueError as e:
        flash(str(e))
        return redirect(url_for('extract_pages'))

@app.route('/word-to-pdf-process', methods=['POST'])
def word_to_pdf_process():
    flash("This tool is currently unavailable on the live server.")
    return redirect(url_for('word_to_pdf'))

@app.route('/images-to-pdf-process', methods=['POST'])
def images_to_pdf_process():
    uploaded_files = request.files.getlist('image_files')
    
    if not uploaded_files or uploaded_files[0].filename == '':
        flash("Please select at least one image file.")
        return redirect(url_for('image_to_pdf'))

    image_list = []
    first_image = None

    for file in uploaded_files:
        if file and (file.filename.lower().endswith(('.png', '.jpeg', '.jpg'))):
            try:
                image = Image.open(file.stream).convert('RGB')
                if first_image is None:
                    first_image = image
                else:
                    image_list.append(image)
            except Exception as e:
                flash(f"Could not process image: {file.filename}")
                return redirect(url_for('image_to_pdf'))

    if first_image is None:
        flash("No valid image files were uploaded. Please use PNG, JPG, or JPEG.")
        return redirect(url_for('image_to_pdf'))

    pdf_buffer = io.BytesIO()
    first_image.save(pdf_buffer, "PDF" ,resolution=100.0, save_all=True, append_images=image_list)
    pdf_buffer.seek(0)
    
    return send_file(pdf_buffer, as_attachment=True, download_name='converted_images.pdf', mimetype='application/pdf')

@app.route('/pdf-to-images-process', methods=['POST'])
def pdf_to_images_process():
    file = request.files.get('pdf_file')
    if not file:
        flash("Please select a PDF file.")
        return redirect(url_for('pdf_to_images'))

    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("jpeg")
                zipf.writestr(f"page_{page_num + 1}.jpg", img_bytes)
        
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='pdf_to_images.zip')

    except Exception as e:
        flash("An error occurred while converting the PDF to images.")
        return redirect(url_for('pdf_to_images'))

@app.route('/pdf-to-word-process', methods=['POST'])
def pdf_to_word_process():
    file = request.files.get('pdf_file')
    if not file:
        flash("Please select a PDF file.")
        return redirect(url_for('pdf_to_word'))

    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        full_text = ""
        for page in pdf_document:
            full_text += page.get_text("text")
            full_text += "\n\n"
        pdf_document.close()

        text_buffer = io.BytesIO(full_text.encode('utf-8'))
        text_buffer.seek(0)
        
        original_filename = os.path.splitext(file.filename)[0]
        download_name = f"{original_filename}.txt"

        return send_file(text_buffer, as_attachment=True, download_name=download_name, mimetype='text/plain')
    except Exception as e:
        flash("Failed to extract text from PDF. The file might be image-based (scanned).")
        return redirect(url_for('pdf_to_word'))

@app.route('/html-to-pdf-process', methods=['POST'])
def html_to_pdf_process():
    url = request.form.get('url')
    if not url:
        flash("Please enter a URL.")
        return redirect(url_for('html_to_pdf'))

    try:
        pdf_bytes = pdfkit.from_url(url, False)
        pdf_buffer = io.BytesIO(pdf_bytes)
        pdf_buffer.seek(0)

        return send_file(pdf_buffer, as_attachment=True, download_name='website.pdf', mimetype='application/pdf')
    except Exception as e:
        flash("Failed to convert URL to PDF. The tool might be unavailable or the URL is invalid.")
        return redirect(url_for('html_to_pdf'))

@app.route('/compress-process', methods=['POST'])
def compress_process():
    file = request.files.get('pdf_file')
    if not file:
        flash("Please select a PDF file.")
        return redirect(url_for('compress'))
    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer, garbage=4, deflate=True)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='compressed.pdf', mimetype='application/pdf')
    except Exception as e:
        flash("An error occurred while compressing the PDF.")
        return redirect(url_for('compress'))

@app.route('/protect-process', methods=['POST'])
def protect_process():
    file = request.files.get('pdf_file')
    password = request.form.get('password')
    if not file or not password:
        flash("Please provide both a file and a password.")
        return redirect(url_for('protect'))
    try:
        reader = PdfReader(file.stream)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(password)
        
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        writer.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='protected.pdf', mimetype='application/pdf')
    except Exception as e:
        flash("An error occurred while protecting the PDF.")
        return redirect(url_for('protect'))

@app.route('/unlock-process', methods=['POST'])
def unlock_process():
    file = request.files.get('pdf_file')
    password = request.form.get('password')
    if not file or not password:
        flash("Please provide both a file and a password.")
        return redirect(url_for('unlock'))
    try:
        reader = PdfReader(file.stream)
        if reader.is_encrypted:
            if reader.decrypt(password):
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                
                output_buffer = io.BytesIO()
                writer.write(output_buffer)
                writer.close()
                output_buffer.seek(0)
                
                return send_file(output_buffer, as_attachment=True, download_name='unlocked.pdf', mimetype='application/pdf')
            else:
                flash("Incorrect password. Could not decrypt the PDF.")
                return redirect(url_for('unlock'))
        else:
            flash("The provided PDF is not encrypted.")
            return redirect(url_for('unlock'))
    except FileNotDecryptedError:
        flash("Incorrect password. Could not decrypt the PDF.")
        return redirect(url_for('unlock'))
    except Exception as e:
        flash("An error occurred while processing the PDF.")
        return redirect(url_for('unlock'))

@app.route('/rotate-process', methods=['POST'])
def rotate_process():
    file = request.files.get('pdf_file')
    rotation = int(request.form.get('rotation', 90))
    if not file:
        flash("Please select a PDF file.")
        return redirect(url_for('rotate'))
    try:
        reader = PdfReader(file.stream)
        writer = PdfWriter()
        for page in reader.pages:
            page.rotate(rotation)
            writer.add_page(page)
            
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        writer.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='rotated.pdf', mimetype='application/pdf')
    except Exception as e:
        flash("An error occurred while rotating the PDF.")
        return redirect(url_for('rotate'))

@app.route('/add-page-numbers-process', methods=['POST'])
def add_page_numbers_process():
    file = request.files.get('pdf_file')
    position = request.form.get('position', 'bottom-center')
    if not file:
        flash("Please select a PDF file.")
        return redirect(url_for('add_page_numbers'))
    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        
        for i, page in enumerate(pdf_document):
            page_num_text = f"{i + 1} / {len(pdf_document)}"
            page_rect = page.rect
            x = page_rect.width / 2
            y = page_rect.height - 30
            
            if 'top' in position:
                y = 30
            
            align = fitz.TEXT_ALIGN_CENTER
            if 'right' in position:
                x = page_rect.width - 60
                align = fitz.TEXT_ALIGN_RIGHT
            elif 'left' in position:
                x = 60
                align = fitz.TEXT_ALIGN_LEFT

            point = fitz.Point(x, y)
            page.insert_text(point, page_num_text, fontsize=10, fontname="helv", color=(0,0,0), align=align)

        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='numbered.pdf', mimetype='application/pdf')
    except Exception as e:
        flash("An error adding page numbers.")
        return redirect(url_for('add_page_numbers'))

@app.route('/add-watermark-process', methods=['POST'])
def add_watermark_process():
    file = request.files.get('pdf_file')
    watermark_text = request.form.get('watermark_text')
    if not file or not watermark_text:
        flash("Please provide a file and watermark text.")
        return redirect(url_for('add_watermark'))
    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        
        for page in pdf_document:
            point = page.rect.center
            page.insert_text(point, watermark_text, fontsize=50, fontname="helv", color=(0.5, 0.5, 0.5), 
                              rotate=45, overlay=True, align=fitz.TEXT_ALIGN_CENTER, opacity=0.5)

        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='watermarked.pdf', mimetype='application/pdf')
    except Exception as e:
        flash("An error occurred while adding the watermark.")
        return redirect(url_for('add_watermark'))

@app.route('/delete-pages-process', methods=['POST'])
def delete_pages_process():
    file = request.files.get('pdf_file')
    page_numbers_str = request.form.get('page_numbers')
    if not file or not page_numbers_str:
        flash("Please provide a file and page numbers to delete.")
        return redirect(url_for('delete_pages'))
    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        max_pages = len(pdf_document)
        
        pages_to_delete = parse_page_numbers(page_numbers_str, max_pages)
        
        if not pages_to_delete:
            flash("Invalid page numbers provided.")
            return redirect(url_for('delete_pages'))
            
        all_pages = list(range(max_pages))
        pages_to_keep = [p for p in all_pages if p not in pages_to_delete]
        
        pdf_document.select(pages_to_keep)

        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='pages_removed.pdf', mimetype='application/pdf')
    except ValueError as e:
        flash(str(e))
        return redirect(url_for('delete_pages'))
    except Exception as e:
        flash("An error occurred while deleting pages.")
        return redirect(url_for('delete_pages'))

@app.route('/organize-pages-process', methods=['POST'])
def organize_pages_process():
    file = request.files.get('pdf_file')
    page_order_str = request.form.get('page_order')
    if not file or not page_order_str:
        flash("Please provide a file and the new page order.")
        return redirect(url_for('organize_pages'))
    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        max_pages = len(pdf_document)
        
        new_order_indices = parse_page_numbers(page_order_str, max_pages)
        
        if not new_order_indices:
            flash("Invalid page order provided.")
            return redirect(url_for('organize_pages'))
        
        pdf_document.select(new_order_indices)

        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='organized.pdf', mimetype='application/pdf')
    except ValueError as e:
        flash(str(e))
        return redirect(url_for('organize_pages'))
    except Exception as e:
        flash("An error occurred while organizing pages.")
        return redirect(url_for('organize_pages'))

@app.route('/repair-process', methods=['POST'])
def repair_process():
    file = request.files.get('pdf_file')
    if not file:
        flash("Please select a PDF file to repair.")
        return redirect(url_for('repair'))
    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer, garbage=4, deflate=True, linear=True)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='repaired.pdf', mimetype='application/pdf')
    except Exception as e:
        flash("Could not repair the PDF. The file may be too corrupted.")
        return redirect(url_for('repair'))

@app.route('/pdfa-to-pdf-process', methods=['POST'])
def pdfa_to_pdf_process():
    file = request.files.get('pdf_file')
    if not file:
        flash("Please select a PDF/A file.")
        return redirect(url_for('pdfa_to_pdf'))
    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='converted_from_pdfa.pdf', mimetype='application/pdf')
    except Exception as e:
        flash("An error occurred during conversion. Ensure the file is a valid PDF/A.")
        return redirect(url_for('pdfa_to_pdf'))


# --- SEO / Sitemap ---

# تمت إضافة هذا المسار لخدمة ملف robots.txt من المجلد static
@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    pages = []
    lastmod_date = datetime.now().strftime('%Y-%m-%d')
    
    pages.append({'loc': url_for('index', _external=True), 'lastmod': lastmod_date, 'priority': '1.0'})

    tool_routes = [
        'merge', 'split', 'compress', 'protect', 'unlock', 'rotate', 
        'delete_pages', 'add_page_numbers', 'add_watermark', 'organize_pages',
        'extract_pages', 'extract_images', 'image_to_pdf', 'pdf_to_word',
        'word_to_pdf', 'html_to_pdf', 'pdf_to_images', 'repair', 'pdfa_to_pdf'
    ]

    for route in tool_routes:
        if route in app.view_functions:
            pages.append({
                'loc': url_for(route, _external=True),
                'lastmod': lastmod_date,
                'priority': '0.8'
            })

    sitemap_xml = render_template('sitemap_template.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"

    return response


if __name__ == '__main__':
    app.run(debug=True)
