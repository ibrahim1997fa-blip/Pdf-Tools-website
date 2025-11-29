import os
import io
import zipfile
import tempfile
import pythoncom
import comtypes.client
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.errors import FileNotDecryptedError
import fitz  # PyMuPDF
from PIL import Image
import pdfkit

app = Flask(__name__)
app.secret_key = 'a_super_secret_key' # Needed for flashing messages

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

# --- (The existing 18 tools are here, code is unchanged) ---
# --- Merge PDF Tool ---
@app.route('/merge-tool')
def merge_tool():
    return render_template('merge.html')

@app.route('/merge', methods=['POST'])
def merge():
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

# --- Split PDF Tool ---
@app.route('/split-tool')
def split_tool():
    return render_template('split.html')

@app.route('/split', methods=['POST'])
def split():
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

# --- Extract Images Tool ---
@app.route('/extract-tool')
def extract_tool():
    return render_template('extract.html')

@app.route('/extract', methods=['POST'])
def extract():
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
    if image_count == 0: return "No images found in the PDF.", 404
    return send_file(zip_io, mimetype='application/zip', as_attachment=True, download_name='extracted_images.zip')

# --- Extract Specific Pages Tool ---
@app.route('/extract-pages-tool')
def extract_pages_tool():
    return render_template('extract_pages.html')

@app.route('/extract-pages', methods=['POST'])
def extract_pages():
    file = request.files['pdf_file']
    page_numbers_str = request.form['page_numbers']
    if not file: return "No file uploaded", 400
    
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
            return redirect(url_for('extract_pages_tool'))
            
        output_io = io.BytesIO()
        writer.write(output_io)
        output_io.seek(0)
        return send_file(output_io, as_attachment=True, download_name='extracted_pages.pdf', mimetype='application/pdf')
    except ValueError as e:
        flash(str(e))
        return redirect(url_for('extract_pages_tool'))

# --- Word to PDF Converter Tool ---
@app.route('/word-to-pdf-tool')
def word_to_pdf_tool():
    return render_template('word_to_pdf.html')

@app.route('/word-to-pdf', methods=['POST'])
def word_to_pdf():
    file = request.files.get('word_file')
    if not file:
        flash("No file uploaded.")
        return redirect(url_for('word_to_pdf_tool'))

    original_filename = file.filename
    temp_word_path = os.path.join(tempfile.gettempdir(), original_filename)
    file.save(temp_word_path)
    
    temp_pdf_path = os.path.splitext(temp_word_path)[0] + '.pdf'

    try:
        pythoncom.CoInitialize()
        word = comtypes.client.CreateObject('Word.Application')
        word.Visible = False
        doc = word.Documents.Open(temp_word_path)
        doc.SaveAs(temp_pdf_path, FileFormat=17)
        doc.Close()
        word.Quit()

        with open(temp_pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        output_io = io.BytesIO(pdf_bytes)
        output_io.seek(0)

        download_name = os.path.splitext(original_filename)[0] + '.pdf'
        
        return send_file(
            output_io,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error during Word to PDF conversion: {e}")
        flash("An error occurred during conversion. Please ensure Microsoft Word is installed and not busy.")
        return redirect(url_for('word_to_pdf_tool'))
    finally:
        if os.path.exists(temp_word_path):
            os.remove(temp_word_path)
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        pythoncom.CoUninitialize()

# --- Images to PDF Tool ---
@app.route('/images-to-pdf-tool')
def images_to_pdf_tool():
    return render_template('images_to_pdf.html')

@app.route('/images-to-pdf', methods=['POST'])
def images_to_pdf():
    uploaded_files = request.files.getlist('image_files')
    
    if not uploaded_files or uploaded_files[0].filename == '':
        flash("Please select at least one image file.")
        return redirect(url_for('images_to_pdf_tool'))

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
                print(f"Error processing image {file.filename}: {e}")
                flash(f"Could not process image: {file.filename}")
                return redirect(url_for('images_to_pdf_tool'))

    if first_image is None:
        flash("No valid image files were uploaded. Please use PNG, JPG, or JPEG.")
        return redirect(url_for('images_to_pdf_tool'))

    pdf_buffer = io.BytesIO()
    first_image.save(pdf_buffer, "PDF" ,resolution=100.0, save_all=True, append_images=image_list)
    pdf_buffer.seek(0)
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name='converted_images.pdf',
        mimetype='application/pdf'
    )

# --- PowerPoint to PDF Tool ---
@app.route('/pptx-to-pdf-tool')
def pptx_to_pdf_tool():
    return render_template('pptx_to_pdf.html')

@app.route('/pptx-to-pdf', methods=['POST'])
def pptx_to_pdf():
    file = request.files.get('pptx_file')
    if not file:
        flash("No file uploaded.")
        return redirect(url_for('pptx_to_pdf_tool'))

    original_filename = file.filename
    temp_pptx_path = os.path.join(tempfile.gettempdir(), original_filename)
    file.save(temp_pptx_path)
    
    temp_pdf_path = os.path.splitext(temp_pptx_path)[0] + '.pdf'

    try:
        pythoncom.CoInitialize()
        powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
        presentation = powerpoint.Presentations.Open(temp_pptx_path)
        presentation.SaveAs(temp_pdf_path, FileFormat=32)
        presentation.Close()
        powerpoint.Quit()

        with open(temp_pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        output_io = io.BytesIO(pdf_bytes)
        output_io.seek(0)

        download_name = os.path.splitext(original_filename)[0] + '.pdf'
        
        return send_file(
            output_io,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error during PowerPoint to PDF conversion: {e}")
        flash("An error occurred during conversion. Please ensure Microsoft PowerPoint is installed and not busy.")
        return redirect(url_for('pptx_to_pdf_tool'))
    finally:
        if os.path.exists(temp_pptx_path):
            os.remove(temp_pptx_path)
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        pythoncom.CoUninitialize()

# --- PDF to Images Tool ---
@app.route('/pdf-to-images-tool')
def pdf_to_images_tool():
    return render_template('pdf_to_images.html')

@app.route('/pdf-to-images', methods=['POST'])
def pdf_to_images():
    file = request.files.get('pdf_file')
    if not file:
        flash("Please select a PDF file.")
        return redirect(url_for('pdf_to_images_tool'))

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
        print(f"Error during PDF to Images conversion: {e}")
        flash("An error occurred while converting the PDF to images.")
        return redirect(url_for('pdf_to_images_tool'))

# --- PDF to Word (as Text) Tool ---
@app.route('/pdf-to-word-tool')
def pdf_to_word_tool():
    return render_template('pdf_to_word.html')

@app.route('/pdf-to-word', methods=['POST'])
def pdf_to_word():
    file = request.files.get('pdf_file')
    if not file:
        flash("Please select a PDF file.")
        return redirect(url_for('pdf_to_word_tool'))

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

        return send_file(
            text_buffer,
            as_attachment=True,
            download_name=download_name,
            mimetype='text/plain'
        )
    except Exception as e:
        print(f"Error during PDF to Text conversion: {e}")
        flash("Failed to extract text from PDF. The file might be image-based (scanned).")
        return redirect(url_for('pdf_to_word_tool'))

# --- HTML to PDF Tool ---
@app.route('/html-to-pdf-tool')
def html_to_pdf_tool():
    return render_template('html_to_pdf.html')

@app.route('/html-to-pdf', methods=['POST'])
def html_to_pdf():
    url = request.form.get('url')
    if not url:
        flash("Please enter a URL.")
        return redirect(url_for('html_to_pdf_tool'))

    try:
        path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        pdf_bytes = pdfkit.from_url(url, False, configuration=config)
        pdf_buffer = io.BytesIO(pdf_bytes)
        pdf_buffer.seek(0)

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name='website.pdf',
            mimetype='application/pdf'
        )
    except FileNotFoundError:
        print("wkhtmltopdf not found at the specified path.")
        flash("Configuration error: Could not find the PDF conversion utility.")
        return redirect(url_for('html_to_pdf_tool'))
    except Exception as e:
        print(f"Error during HTML to PDF conversion: {e}")
        flash("Failed to convert URL to PDF. The URL may be invalid or the website might be blocking requests.")
        return redirect(url_for('html_to_pdf_tool'))

# --- Compress PDF Tool ---
@app.route('/compress-tool')
def compress_tool():
    return render_template('compress.html')

@app.route('/compress', methods=['POST'])
def compress():
    file = request.files.get('pdf_file')
    if not file:
        flash("Please select a PDF file.")
        return redirect(url_for('compress_tool'))
    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer, garbage=4, deflate=True)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(
            output_buffer,
            as_attachment=True,
            download_name='compressed.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error during PDF compression: {e}")
        flash("An error occurred while compressing the PDF.")
        return redirect(url_for('compress_tool'))

# --- Protect PDF Tool ---
@app.route('/protect-tool')
def protect_tool():
    return render_template('protect.html')

@app.route('/protect', methods=['POST'])
def protect():
    file = request.files.get('pdf_file')
    password = request.form.get('password')
    if not file or not password:
        flash("Please provide both a file and a password.")
        return redirect(url_for('protect_tool'))
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
        
        return send_file(
            output_buffer,
            as_attachment=True,
            download_name='protected.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error during PDF protection: {e}")
        flash("An error occurred while protecting the PDF.")
        return redirect(url_for('protect_tool'))

# --- Unlock PDF Tool ---
@app.route('/unlock-tool')
def unlock_tool():
    return render_template('unlock.html')

@app.route('/unlock', methods=['POST'])
def unlock():
    file = request.files.get('pdf_file')
    password = request.form.get('password')
    if not file or not password:
        flash("Please provide both a file and a password.")
        return redirect(url_for('unlock_tool'))
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
                
                return send_file(
                    output_buffer,
                    as_attachment=True,
                    download_name='unlocked.pdf',
                    mimetype='application/pdf'
                )
            else:
                flash("Incorrect password. Could not decrypt the PDF.")
                return redirect(url_for('unlock_tool'))
        else:
            flash("The provided PDF is not encrypted.")
            return redirect(url_for('unlock_tool'))
    except FileNotDecryptedError:
        flash("Incorrect password. Could not decrypt the PDF.")
        return redirect(url_for('unlock_tool'))
    except Exception as e:
        print(f"Error during PDF unlocking: {e}")
        flash("An error occurred while processing the PDF.")
        return redirect(url_for('unlock_tool'))

# --- Rotate PDF Tool ---
@app.route('/rotate-tool')
def rotate_tool():
    return render_template('rotate.html')

@app.route('/rotate', methods=['POST'])
def rotate():
    file = request.files.get('pdf_file')
    rotation = int(request.form.get('rotation', 90))
    if not file:
        flash("Please select a PDF file.")
        return redirect(url_for('rotate_tool'))
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
        
        return send_file(
            output_buffer,
            as_attachment=True,
            download_name='rotated.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error during PDF rotation: {e}")
        flash("An error occurred while rotating the PDF.")
        return redirect(url_for('rotate_tool'))

# --- Add Page Numbers Tool ---
@app.route('/add-page-numbers-tool')
def add_page_numbers_tool():
    return render_template('add_page_numbers.html')

@app.route('/add-page-numbers', methods=['POST'])
def add_page_numbers():
    file = request.files.get('pdf_file')
    position = request.form.get('position', 'bottom-center')
    if not file:
        flash("Please select a PDF file.")
        return redirect(url_for('add_page_numbers_tool'))
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
        print(f"Error adding page numbers: {e}")
        flash("An error occurred while adding page numbers.")
        return redirect(url_for('add_page_numbers_tool'))

# --- Add Watermark Tool ---
@app.route('/add-watermark-tool')
def add_watermark_tool():
    return render_template('add_watermark.html')

@app.route('/add-watermark', methods=['POST'])
def add_watermark():
    file = request.files.get('pdf_file')
    watermark_text = request.form.get('watermark_text')
    if not file or not watermark_text:
        flash("Please provide a file and watermark text.")
        return redirect(url_for('add_watermark_tool'))
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
        print(f"Error adding watermark: {e}")
        flash("An error occurred while adding the watermark.")
        return redirect(url_for('add_watermark_tool'))

# --- Delete Pages Tool ---
@app.route('/delete-pages-tool')
def delete_pages_tool():
    return render_template('delete_pages.html')

@app.route('/delete-pages', methods=['POST'])
def delete_pages():
    file = request.files.get('pdf_file')
    page_numbers_str = request.form.get('page_numbers')
    if not file or not page_numbers_str:
        flash("Please provide a file and page numbers to delete.")
        return redirect(url_for('delete_pages_tool'))
    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        max_pages = len(pdf_document)
        
        pages_to_delete = parse_page_numbers(page_numbers_str, max_pages)
        
        if not pages_to_delete:
            flash("Invalid page numbers provided.")
            return redirect(url_for('delete_pages_tool'))
            
        for page_index in reversed(pages_to_delete):
            pdf_document.delete_page(page_index)

        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='deleted_pages.pdf', mimetype='application/pdf')
    except ValueError as e:
        flash(str(e))
        return redirect(url_for('delete_pages_tool'))
    except Exception as e:
        print(f"Error deleting pages: {e}")
        flash("An error occurred while deleting pages.")
        return redirect(url_for('delete_pages_tool'))

# --- Organize Pages Tool ---
@app.route('/organize-pages-tool')
def organize_pages_tool():
    return render_template('organize_pages.html')

@app.route('/organize-pages', methods=['POST'])
def organize_pages():
    file = request.files.get('pdf_file')
    page_order_str = request.form.get('page_order')
    if not file or not page_order_str:
        flash("Please provide a file and the new page order.")
        return redirect(url_for('organize_pages_tool'))
    try:
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        max_pages = len(pdf_document)
        
        new_order_indices = parse_page_numbers(page_order_str, max_pages)
        
        if not new_order_indices:
            flash("Invalid page order provided.")
            return redirect(url_for('organize_pages_tool'))
        
        pdf_document.select(new_order_indices)

        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(output_buffer, as_attachment=True, download_name='organized.pdf', mimetype='application/pdf')
    except ValueError as e:
        flash(str(e))
        return redirect(url_for('organize_pages_tool'))
    except Exception as e:
        print(f"Error organizing pages: {e}")
        flash("An error occurred while organizing pages.")
        return redirect(url_for('organize_pages_tool'))

# --- [FINAL BATCH] Repair PDF Tool ---
@app.route('/repair-tool')
def repair_tool():
    return render_template('repair.html')

@app.route('/repair', methods=['POST'])
def repair():
    file = request.files.get('pdf_file')
    if not file:
        flash("Please select a PDF file to repair.")
        return redirect(url_for('repair_tool'))
    try:
        # PyMuPDF's 'save' with garbage collection is a good way to repair/rebuild a PDF
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        output_buffer = io.BytesIO()
        # garbage=4 is a deep clean, deflate compresses, and linear optimizes for web
        pdf_document.save(output_buffer, garbage=4, deflate=True, linear=True)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(
            output_buffer,
            as_attachment=True,
            download_name='repaired.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error repairing PDF: {e}")
        flash("Could not repair the PDF. The file may be too corrupted.")
        return redirect(url_for('repair_tool'))

# --- [FINAL BATCH] PDF/A to PDF Tool ---
@app.route('/pdfa-to-pdf-tool')
def pdfa_to_pdf_tool():
    return render_template('pdfa_to_pdf.html')

@app.route('/pdfa-to-pdf', methods=['POST'])
def pdfa_to_pdf():
    file = request.files.get('pdf_file')
    if not file:
        flash("Please select a PDF/A file.")
        return redirect(url_for('pdfa_to_pdf_tool'))
    try:
        # Simply opening and saving the file with PyMuPDF often removes PDF/A compliance
        pdf_document = fitz.open(stream=file.read(), filetype="pdf")
        output_buffer = io.BytesIO()
        # Saving without any special flags converts it to a standard PDF
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)
        
        return send_file(
            output_buffer,
            as_attachment=True,
            download_name='converted_from_pdfa.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error converting PDF/A: {e}")
        flash("An error occurred during conversion. Ensure the file is a valid PDF/A.")
        return redirect(url_for('pdfa_to_pdf_tool'))


if __name__ == '__main__':
    app.run(debug=True)
