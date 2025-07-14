import xml.etree.ElementTree as ET
import os
from typing import List, Dict, Any, Optional
import logging

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

            # Parse template
            layout = self.parse_proalpha_template(root)

            # Create List & Label XML
            output_path = self.create_list_label_xml(layout, xml_file_path, output_path)

            logging.info(f"Converted {xml_file_path} to {output_path}")
            return output_path

        except Exception as e:
            logging.error(f"Error converting {xml_file_path}: {str(e)}")
            raise Exception(f"Error converting XML to List & Label: {str(e)}")

    def parse_proalpha_template(self, root: ET.Element) -> Dict[str, Any]:
        """Parse proALPHA Internal template XML to extract metadata, fields, and text"""
        layout = {'metadata': {}, 'fields': [], 'text': []}

        # Extract metadata from INFO elements
        for info in root.findall('.//INFO'):
            metadata = {
                '@ID': info.get('ID', ''),
                'FORMNO': info.find('FORMNO').text if info.find('FORMNO') is not None else '',
                'VARIANT': info.find('VARIANT').text if info.find('VARIANT') is not None else '',
                'TITLE': info.find('TITLE').text if info.find('TITLE') is not None else '',
                'FONT': info.find('FONT').text if info.find('FONT') is not None else 'Arial',
                'FIELDNAME': info.find('FIELDNAME').text if info.find('FIELDNAME') is not None else '',
                'POSNO': info.find('POSNO').text if info.find('POSNO') is not None else '',
                'ISOUTPUT': info.find('ISOUTPUT').text if info.find('ISOUTPUT') is not None else 'false',
                'OP': info.find('OP').text if info.find('OP') is not None else ''
            }
            layout['metadata'][metadata['@ID']] = metadata

        # Extract FIELDOBJECT elements
        for field in root.findall('.//FIELDOBJECT'):
            layout['fields'].append({
                '@ID': field.get('ID', ''),
                'POSNO': field.get('POSNO', ''),
                'PARENT': field.get('PARENT', ''),
                'GROUP': field.get('GROUP', ''),
                'MASK': field.get('MASK', ''),
                'LENGTH': field.get('LENGTH', ''),
                'ISOUTPUT': field.get('ISOUTPUT', 'false'),
                'ISMANDATORY': field.get('ISMANDATORY', 'false'),
                'ISACTIVE': field.get('ISACTIVE', 'true'),
                'FIELDNAME': field.get('FIELDNAME', ''),
                'FORMNO': field.get('FORMNO', ''),
                'VARIABLE': field.get('VARIABLE', ''),
                'TYPE': field.get('TYPE', '')
            })

        # Extract FIELDTEXT elements
        for text in root.findall('.//FIELDTEXT'):
            layout['text'].append({
                '@ID': text.get('ID', ''),
                'VARIABLE': text.get('VARIABLE', ''),
                'FORMNO': text.get('FORMNO', ''),
                'VARIANT': text.get('VARIANT', '')
            })

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
                info.set("ID", metadata_id)
                for key, value in metadata.items():
                    if not key.startswith('@') and value:
                        ET.SubElement(info, key).text = value

            # Add FIELDOBJECT elements
            for field in layout['fields']:
                field_elem = ET.SubElement(root, "FIELDOBJECT")
                for key, value in field.items():
                    if value:
                        field_elem.set(key[1:] if key.startswith('@') else key, value)
                # Set List & Label-specific attributes
                field_elem.set("TYPE", self.infer_field_type(field['MASK']))
                field_elem.set("NAME", field['FIELDNAME'] or f"Field_{field['POSNO']}")

            # Add FIELDTEXT elements for headers
            for text in layout['text']:
                if text['VARIANT'] == 'C':  # Column headers
                    text_elem = ET.SubElement(root, "FIELDTEXT")
                    text_elem.set("ID", text['@ID'])
                    text_elem.set("VARIABLE", text['VARIABLE'])
                    text_elem.set("FORMNO", text['FORMNO'])
                    text_elem.set("VARIANT", text['VARIANT'])
                    text_elem.set("FONT",
                                  layout['metadata'].get(list(layout['metadata'].keys())[0], {}).get('FONT', 'Arial'))
                    text_elem.set("FONTSIZE", "10")  # Default font size
                    text_elem.set("ALIGNMENT", "Left")  # Default alignment

            # Handle semicolon-separated headers (e.g., in 22_P_3)
            for text in layout['text']:
                if text['VARIANT'] == 'C' and ';' in text['VARIABLE']:
                    headers = text['VARIABLE'].split(';')
                    for i, header in enumerate(headers):
                        if header.strip():
                            text_elem = ET.SubElement(root, "FIELDTEXT")
                            text_elem.set("ID", f"{text['@ID']}_{i}")
                            text_elem.set("VARIABLE", header.strip())
                            text_elem.set("FORMNO", text['FORMNO'])
                            text_elem.set("VARIANT", "C")
                            text_elem.set("FONT",
                                          layout['metadata'].get(list(layout['metadata'].keys())[0], {}).get('FONT',
                                                                                                             'Arial'))
                            text_elem.set("FONTSIZE", "10")
                            text_elem.set("ALIGNMENT", "Left")

            # Determine output path
            if not output_path:
                output_path = input_path.rsplit('.', 1)[0] + '.lst'

            # Write to .lst file
            tree = ET.ElementTree(root)
            tree.write(output_path, encoding='utf-8', xml_declaration=True)
            return output_path

        except Exception as e:
            logging.error(f"Error creating List & Label XML: {str(e)}")
            raise

    def infer_field_type(self, mask: str) -> str:
        """Infer List & Label field type based on MASK attribute"""
        if not mask:
            return "String"
        mask = mask.lower()
        if "99.99.9999" in mask:
            return "Date"
        elif "hh:mm" in mask:
            return "Time"
        elif any(x in mask for x in ["9", ".", ",", "-", ">", "<", "z"]):
            return "Number"
        elif "x(" in mask:
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
        "reportlayouts_$vuusta$22_P_3.pdi"
    ]
    results = convert(test_files, output_dir="converted_templates")
    print(f"Converted files: {results}")
