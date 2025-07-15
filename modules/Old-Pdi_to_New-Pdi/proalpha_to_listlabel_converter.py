import xml.etree.ElementTree as ET
import os
from typing import List, Dict, Any, Optional
import logging
import re
import json

# Configure logging
logging.basicConfig(level=logging.INFO, filename='proalpha_conversion.log',
                    format='%(asctime)s - %(levelname)s - %(message)s')

class ProAlphaToListLabelConverter:
    """Converts proALPHA Internal templates to List & Label .lst format"""

    def __init__(self):
        self.preserve_attributes = True
        self.attribute_prefix = "@"
        self.text_key = "#text"
        self.list_tags = ["INFO", "FIELDOBJECT", "FIELDTEXT"]

    def convert_file(self, xml_file_path: str, output_path: str = None) -> str:
        """
        Convert proALPHA Internal XML file to List & Label .lst format

        Args:
            xml_file_path: Path to input proALPHA XML file
            output_path: Path for output .lst file (optional)

        Returns:
            Path to generated .lst file
        """
        try:
            # Parse XML
            tree = ET.parse(xml_file_path)
            root = tree.getroot()

            # Extract variant and formno from filename if possible
            filename = os.path.basename(xml_file_path)
            variant = 'UNKNOWN'
            formno_str = '00'
            if '$' in filename:
                parts = re.split(r'\$', filename)
                if len(parts) >= 3:
                    variant = parts[1]
                    formno_str = parts[2].split('_')[0]

            # Parse template
            layout = self.parse_proalpha_template(root)
            if not layout['metadata'] and not layout['fields'] and not layout['text']:
                raise ValueError(f"No valid data parsed from {xml_file_path}")

            # Override formno if parsed, add variant
            if 'main' in layout['metadata']:
                layout['metadata']['main']['VARIANT'] = variant.upper()

            logging.info(f"Extracted layout: {json.dumps(layout, indent=2)}")

            # Create List & Label XML
            output_path = self.create_list_label_xml(layout, xml_file_path, output_path)

            logging.info(f"Converted {xml_file_path} to {output_path}")
            return output_path

        except ET.ParseError as e:
            logging.error(f"XML parsing error in {xml_file_path}: {str(e)}")
            raise Exception(f"Failed to parse XML in {xml_file_path}: {str(e)}")
        except Exception as e:
            logging.error(f"Error converting {xml_file_path}: {str(e)}")
            raise Exception(f"Error converting XML to List & Label: {str(e)}")

    def parse_proalpha_template(self, root: ET.Element) -> Dict[str, Any]:
        """Parse proALPHA Internal template to extract metadata, fields, and text"""
        layout = {'metadata': {}, 'fields': [], 'text': []}

        for elem in root.iter():
            tag = elem.tag
            lines = [l.strip() for l in (elem.text or '').splitlines() if l.strip()]
            logging.debug(f"Parsing tag: {tag}, lines: {lines}")

            if tag.startswith('PA2087::'):
                if len(lines) >= 9:
                    # Main metadata
                    formno = lines[0]
                    font = lines[6]
                    orientation = lines[7]
                    opsys = lines[8]
                    layout['metadata']['main'] = {
                        'FORMNO': formno,
                        'FONT': font,
                        'ORIENTATION': orientation,
                        'OP': opsys,
                        'TITLE': 'Converted from proALPHA',
                        'ISOUTPUT': 'false',
                        'POSNO': '',
                        'FIELDNAME': '',
                        '@ID': 'main'
                    }
                    logging.debug(f"Parsed metadata: {layout['metadata']['main']}")

            elif tag.startswith('PA2090:'):
                if lines:
                    if len(lines) <= 5:
                        # Text/header
                        text_value = lines[0] if len(lines) > 0 else ''
                        formno = lines[1] if len(lines) > 1 else ''
                        var = lines[2] if len(lines) > 2 else ''
                        if var in ['C', 'D'] and text_value.strip():
                            text = {
                                '@ID': elem.tag,
                                'VARIABLE': text_value,
                                'FORMNO': formno,
                                'VARIANT': var
                            }
                            layout['text'].append(text)
                            logging.debug(f"Parsed text: {text}")
                    else:
                        # Field
                        field = {
                            '@ID': elem.tag,
                            'POSNO': lines[0] if len(lines) > 0 else '',
                            'PARENT': lines[1] if len(lines) > 1 else '',
                            'GROUP': lines[2] if len(lines) > 2 else '',
                            'TYPE': lines[3] if len(lines) > 3 else '',
                            'MASK': lines[5] if len(lines) > 5 else '',
                            'LENGTH': lines[6] if len(lines) > 6 else '',
                            'ISOUTPUT': lines[7] if len(lines) > 7 else 'false',
                            'ISMANDATORY': lines[8] if len(lines) > 8 else 'false',
                            'ISACTIVE': lines[9] if len(lines) > 9 else 'true',
                            'VARIABLE': lines[10] if len(lines) > 10 else '',
                            'FIELDNAME': lines[12] if len(lines) > 12 else '',
                            'FORMNO': lines[13] if len(lines) > 13 else ''
                        }
                        layout['fields'].append(field)
                        logging.debug(f"Parsed field: {field}")

        logging.info(f"Parsed template: {len(layout['metadata'])} metadata, {len(layout['fields'])} fields, {len(layout['text'])} text")
        return layout

    def create_list_label_xml(self, layout: Dict[str, Any], input_path: str, output_path: str = None) -> str:
        """Create List & Label XML (.lst) based on parsed proALPHA template"""
        try:
            # Create root element for List & Label XML
            root = ET.Element("FORM")
            root.set("FORMTYPE", "LLList")

            # Add INFO elements from metadata
            for metadata_id, metadata in layout['metadata'].items():
                info = ET.SubElement(root, "INFO")
                info.set("ID", metadata.get('@ID', metadata_id))
                for key, value in metadata.items():
                    if not key.startswith('@') and value:
                        ET.SubElement(info, key).text = str(value)

            # Add FIELDOBJECT elements
            for field in layout['fields']:
                field_elem = ET.SubElement(root, "FIELDOBJECT")
                for key, value in field.items():
                    if value:
                        field_elem.set(key[1:] if key.startswith('@') else key, str(value))
                # Set List & Label-specific attributes
                field_elem.set("TYPE", self.infer_field_type(field.get('MASK', '')))
                field_elem.set("NAME", field.get('FIELDNAME') or f"Field_{field.get('POSNO', '0')}")

            # Add FIELDTEXT elements for headers
            font = layout['metadata'].get('main', {}).get('FONT', 'Arial')
            fontsize = '7' if 'cour' in font.lower() else '10'
            for text in layout['text']:
                if text.get('VARIANT') == 'C':  # Column headers
                    text_elem = ET.SubElement(root, "FIELDTEXT")
                    text_elem.set("ID", text.get('@ID', ''))
                    text_elem.set("VARIABLE", text.get('VARIABLE', ''))
                    text_elem.set("FORMNO", text.get('FORMNO', ''))
                    text_elem.set("VARIANT", text.get('VARIANT', ''))
                    text_elem.set("FONT", font)
                    text_elem.set("FONTSIZE", fontsize)
                    text_elem.set("ALIGNMENT", "Left")  # Default alignment

            # Handle semicolon-separated headers (e.g., in 22_P_3)
            for text in layout['text']:
                if text.get('VARIANT') == 'C' and ';' in text.get('VARIABLE', ''):
                    headers = text['VARIABLE'].split(';')
                    for i, header in enumerate(headers):
                        if header.strip():
                            text_elem = ET.SubElement(root, "FIELDTEXT")
                            text_elem.set("ID", f"{text.get('@ID', '')}_{i}")
                            text_elem.set("VARIABLE", header.strip())
                            text_elem.set("FORMNO", text.get('FORMNO', ''))
                            text_elem.set("VARIANT", "C")
                            text_elem.set("FONT", font)
                            text_elem.set("FONTSIZE", fontsize)
                            text_elem.set("ALIGNMENT", "Left")

            # Determine output path
            if not output_path:
                output_path = input_path.rsplit('.', 1)[0] + '.lst'

            # Write to .lst file
            tree = ET.ElementTree(root)
            tree.write(output_path, encoding='utf-8', xml_declaration=True)
            logging.info(f"Created List & Label XML: {output_path}")
            return output_path

        except Exception as e:
            logging.error(f"Error creating List & Label XML: {str(e)}")
            raise

    def infer_field_type(self, mask: str) -> str:
        """Infer List & Label field type based on MASK attribute"""
        if not mask:
            return "String"
        mask = mask.lower()
        if "99.99.9999" in mask or "hh:mm" in mask:
            return "Date"
        elif "hh:mm" in mask:
            return "Time"
        elif any(char in mask for char in [">", "<", "9", ".", ","]):
            return "Number"
        elif "x(" in mask or "z" in mask:
            return "String"
        return "String"  # Default to String

    def set_options(self, preserve_attributes: bool = True,
                    attribute_prefix: str = "@",
                    text_key: str = "#text",
                    list_tags: List[str] = None):
        """Configure conversion options"""
        self.preserve_attributes = preserve_attributes
        self.attribute_prefix = attribute_prefix
        self.text_key = text_key
        self.list_tags = list_tags or ["INFO", "FIELDOBJECT", "FIELDTEXT"]

def convert(input_files: List[str], output_dir: str = None, **options) -> List[str]:
    """
    Main conversion function for the module system

    Args:
        input_files: List of proALPHA XML file paths to convert
        output_dir: Directory for output .lst files
        **options: Conversion options

    Returns:
        List of generated .lst file paths
    """
    converter = ProAlphaToListLabelConverter()

    # Apply options
    if options:
        converter.set_options(
            preserve_attributes=options.get('preserve_attributes', True),
            attribute_prefix=options.get('attribute_prefix', '@'),
            text_key=options.get('text_key', '#text'),
            list_tags=options.get('list_tags', ["INFO", "FIELDOBJECT", "FIELDTEXT"])
        )

    output_files = []

    for input_file in input_files:
        try:
            if not input_file.lower().endswith('.pdi'):
                logging.warning(f"Skipping non-.pdi file: {input_file}")
                continue

            if output_dir:
                filename = os.path.basename(input_file).rsplit('.', 1)[0] + '.lst'
                output_path = os.path.join(output_dir, filename)
            else:
                output_path = None

            result_path = converter.convert_file(input_file, output_path)
            output_files.append(result_path)

        except Exception as e:
            logging.error(f"Error converting {input_file}: {str(e)}")
            print(f"Error converting {input_file}: {str(e)}")

    return output_files

if __name__ == "__main__":
    # Test the converter
    test_files = [
        "reportlayouts_$vuusta$21_P_4.pdi",
        "reportlayouts_$vuusta$100_P_2.pdi",
        "reportlayouts_$vuusta$22_P_3.pdi",
        "reportlayouts_$vuusta$110_P.pdi"
    ]
    results = convert(test_files, output_dir="converted_templates")
    print(f"Converted files: {results}")