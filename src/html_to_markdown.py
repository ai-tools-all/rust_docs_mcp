import os
import subprocess
import glob
import sys # Import sys

def convert_html_to_markdown(data_dir, output_dir):
    """
    Converts HTML files from data_dir to Markdown files in output_dir
    using the html2markdown command-line tool.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    html_files = glob.glob(os.path.join(data_dir, "*.html"))

    for html_file_path in html_files:
        base_name = os.path.basename(html_file_path)
        markdown_file_name = os.path.splitext(base_name)[0] + ".md"
        markdown_file_path = os.path.join(output_dir, markdown_file_name)

        print(f"Converting {html_file_path} to {markdown_file_path}")
        try:
            with open(html_file_path, 'r') as f_in:
                process = subprocess.run(
                    ["html2markdown"],
                    stdin=f_in,
                    capture_output=True,
                    text=True,
                    check=True
                )
            with open(markdown_file_path, 'w') as f_out:
                f_out.write(process.stdout)
            print(f"Successfully converted {base_name}")
        except subprocess.CalledProcessError as e:
            print(f"Error converting {base_name}: {e}")
            print(f"Stderr: {e.stderr}")
        except FileNotFoundError:
            print("Error: html2markdown command not found. Please ensure it is installed and in your PATH.")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir) # Go up one level from src
    
    # Determine the data subfolder from command line arguments, default to "serde"
    data_subfolder = "serde"
    if len(sys.argv) > 1:
        data_subfolder = sys.argv[1]

    data_folder = os.path.join(project_root, "data", data_subfolder)
    output_folder = os.path.join(project_root, "examples", data_subfolder) # Output to a subfolder matching the input

    convert_html_to_markdown(data_folder, output_folder)