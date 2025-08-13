import os
import sys
import argparse
from logger import app_logger

def correct_ocr_line_breaks(input_file_path, output_file_path=None):
    """
    Corrects line breaks and removes metadata from an OCR-processed text file.
    This version supports multi-language punctuation and handles dialogue blocks.

    Args:
        input_file_path (str): The path to the text file to correct.
        output_file_path (str, optional): The path for the output file. Defaults to None.
    """
    if not os.path.exists(input_file_path):
        app_logger.error(f"File not found at '{input_file_path}'")
        return

    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        app_logger.error(f"Error reading file: {e}")
        return

    output_lines = []
    text_block_buffer = []
    sentence_enders = [
        # Japanese / CJK
        '。', '」', '』', '！', '？', '…', '―', '）',
        # English / Latin
        '.', '!', '?', '"', "'", ')', ']', '}'
    ]

    def process_text_block(buffer):
        if not buffer:
            return
        
        full_text = "".join(buffer)
        new_text_block = ""
        in_dialogue = False
        i = 0
        while i < len(full_text):
            char = full_text[i]
            new_text_block += char
            
            if char == '「':
                in_dialogue = True
            elif char == '」':
                in_dialogue = False
            
            if char in sentence_enders:
                if not in_dialogue:
                    if not (i + 1 < len(full_text) and full_text[i+1] in sentence_enders):
                        new_text_block += '\n'
            i += 1
        output_lines.extend(new_text_block.split('\n'))

    for line in lines:
        stripped_line = line.strip()
        
        is_deletable_metadata = (
            stripped_line.startswith('---') or
            stripped_line.startswith('[') or
            stripped_line.startswith('제목:')
        )

        if is_deletable_metadata:
            process_text_block(text_block_buffer)
            text_block_buffer = []
            continue

        if not stripped_line:
            process_text_block(text_block_buffer)
            text_block_buffer = []
            output_lines.append("")
            continue

        text_block_buffer.append(stripped_line)
            
    process_text_block(text_block_buffer)

    if output_file_path is None:
        dirname, basename = os.path.split(input_file_path)
        filename, ext = os.path.splitext(basename)
        output_file_path = os.path.join(dirname, f"{filename}_corrected_multilang{ext}")

    try:
        final_text_lines = []
        if output_lines:
            final_text_lines.append(output_lines[0])
            for i in range(1, len(output_lines)):
                if not (output_lines[i].strip() == "" and output_lines[i-1].strip() == ""):
                    final_text_lines.append(output_lines[i])

        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(final_text_lines))
        app_logger.info(f"Successfully processed file and saved to: {output_file_path}")
    except Exception as e:
        app_logger.error(f"Error writing file: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Corrects line breaks and removes metadata from an OCR-processed text file.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        'input_file', 
        type=str, 
        help="Path to the input text file to process."
    )
    
    parser.add_argument(
        '-o', '--output', 
        type=str, 
        default=None,
        help='''Optional: Path for the output file.
If not provided, it is saved next to the input file with a custom suffix.'''
    )

    args = parser.parse_args()
    
    correct_ocr_line_breaks(args.input_file, args.output)
