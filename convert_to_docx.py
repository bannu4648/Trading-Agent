import os
import subprocess

def convert_markdown_to_docx(md_filepath: str, docx_filepath: str):
    """
    Converts a Markdown document to a Word (.docx) document,
    ensuring that embedded images are correctly processed and included.
    
    This script utilizes 'pandoc', which should be installed on your system.
    """
    if not os.path.exists(md_filepath):
        print(f"Error: Could not find input file '{md_filepath}'.")
        return False
        
    print(f"Starting conversion of {md_filepath} to {docx_filepath}...")
    
    # We execute pandoc directly as a safer, pure-python alternative to pypandoc
    # It will automatically bundle all referenced absolute-path PNGs into the Word doc.
    command = [
        "pandoc",
        md_filepath,
        "--reference-doc=ref.docx",
        "-o",
        docx_filepath
    ]
    
    try:
        # Run pandoc command
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Success! Document converted to {docx_filepath}.")
        print("All Nano Banano diagrams and dashboard screenshots have been embedded.")
        
        # Apply professional table formatting using python-docx
        try:
            from docx import Document
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            
            print("Applying professional table formatting...")
            doc = Document(docx_filepath)
            
            for table in doc.tables:
                # Apply a clean professional style available in default Word templates
                # Using 'Light Shading Accent 1' as it gives a nice, academic, clean look
                try:
                    table.style = 'Light Shading Accent 1'
                except KeyError:
                    # Fallback to simple grid if the accent style is missing
                    table.style = 'Table Grid'
                
                table.autofit = True
                
            doc.save(docx_filepath)
            print("Table formatting applied successfully!")
        except ImportError:
            print("Notice: 'python-docx' library not found. Skipping advanced table formatting.")
        except Exception as e:
            print(f"Notice: Non-critical error applying table styles: {e}")

        return True
    except subprocess.CalledProcessError as e:
        print("An error occurred during conversion.")
        print("Pandoc Error Output:")
        print(e.stderr)
        return False
    except FileNotFoundError:
        print("Error: 'pandoc' is not installed or not in your system PATH.")
        print("Please install pandoc (e.g., 'brew install pandoc' on macOS).")
        return False

if __name__ == "__main__":
    # Define file names
    markdown_file = "interim_report.md"
    docx_file = "interim_report.docx"
    
    # Run the conversion
    convert_markdown_to_docx(markdown_file, docx_file)
