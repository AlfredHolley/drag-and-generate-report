from fpdf import FPDF
from fpdf.enums import XPos, YPos
import os
import json
import tempfile
try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False
try:
    from PIL import Image
    PIL_SUPPORT = True
except ImportError:
    PIL_SUPPORT = False

class PDFBuilder(FPDF):
    """PDF Builder with brutal minimalist aesthetic"""
    
    def __init__(self, patient_metadata=None):
        super().__init__()
        self.blue_accent = [22, 186, 222]  # RGB(22,186,222)
        self.black = [0, 0, 0]
        self.light_gray = [248, 252, 252]
        self.light_gray_2 = [242, 252, 252]

        self.white = [255, 255, 255]
        self.gray = [135, 135, 135]
        
        # Store patient metadata for header
        self.patient_metadata = patient_metadata or {}
        
        # Set margins to leave space for header
        # Top margin: 25mm to accommodate logo + text header
        self.set_margins(15, 25, 15)  # left, top, right
        
        # Logo path and aspect ratio
        self.logo_path = None
        self.logo_aspect_ratio = None
        self.logo_path = self._get_logo_path()
        
        # Register fonts
        self._register_fonts()
    
    def _get_logo_path(self):
        """Get logo path, convert SVG to PNG if needed"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Try multiple possible logo paths (for Docker and local development)
        possible_logo_paths = [
            "/app/logo_bw.svg",  # Docker container path
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'logo_bw.svg')),  # Absolute relative path
            os.path.join(os.path.dirname(__file__), '..', '..', 'logo_bw.svg'),  # Relative path
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'logo_bw.svg')),  # Frontend directory
            os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'logo_bw.svg'),  # Frontend directory relative
        ]
        
        logo_svg = None
        for logo_path in possible_logo_paths:
            if os.path.exists(logo_path):
                logo_svg = logo_path
                logger.info(f"Found logo at: {logo_svg}")
                break
        
        if not logo_svg:
            logger.warning(f"Logo not found in any of the expected locations: {possible_logo_paths}")
            return None
        
        # If SVG support is available, convert to PNG temporarily
        if SVG_SUPPORT:
            try:
                # Convert SVG to PNG in memory/temp file
                drawing = svg2rlg(logo_svg)
                if drawing:
                    # Create temporary PNG file
                    temp_png = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                    renderPM.drawToFile(drawing, temp_png.name, fmt='PNG', dpi=150)
                    
                    # Get actual dimensions from the PNG image
                    if PIL_SUPPORT:
                        try:
                            img = Image.open(temp_png.name)
                            width, height = img.size
                            if height > 0:
                                self.logo_aspect_ratio = width / height
                            else:
                                self.logo_aspect_ratio = None
                            img.close()
                        except Exception:
                            # Fallback: try to get from SVG drawing
                            if hasattr(drawing, 'width') and hasattr(drawing, 'height') and drawing.height > 0:
                                self.logo_aspect_ratio = drawing.width / drawing.height
                            else:
                                self.logo_aspect_ratio = None
                    else:
                        # Fallback: try to get from SVG drawing
                        if hasattr(drawing, 'width') and hasattr(drawing, 'height') and drawing.height > 0:
                            self.logo_aspect_ratio = drawing.width / drawing.height
                        else:
                            self.logo_aspect_ratio = None
                    
                    return temp_png.name
            except Exception:
                pass
        
        # Fallback: return SVG path (fpdf2 might handle it, or we'll skip)
        self.logo_aspect_ratio = None
        return logo_svg
    
    def _register_fonts(self):
        """Register custom fonts"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Try multiple possible font paths (for Docker and local development)
        possible_font_dirs = [
            "/app/fonts",  # Docker container path
            os.path.join(os.path.dirname(__file__), '..', '..', 'fonts'),  # Relative path
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'fonts')),  # Absolute relative path
        ]
        
        fonts_dir = None
        for font_dir in possible_font_dirs:
            if os.path.exists(font_dir) and os.path.exists(os.path.join(font_dir, 'VistaSansOT-Book.ttf')):
                fonts_dir = font_dir
                logger.info(f"Using fonts directory: {fonts_dir}")
                break
        
        if not fonts_dir:
            logger.error("Fonts directory not found in any of the expected locations")
            logger.error(f"Tried: {possible_font_dirs}")
            return
        
        # VistaSans fonts
        vista_book_path = os.path.join(fonts_dir, 'VistaSansOT-Book.ttf')
        vista_bold_path = os.path.join(fonts_dir, 'VistaSansOT-Bold.ttf')
        vista_italic_path = os.path.join(fonts_dir, 'VistaSansOT-BookItalic.ttf')
        
        # Helper function to register fonts silently (ignore "already added" warnings)
        def safe_add_font(name, style, path):
            """Add font, ignoring 'already added' warnings"""
            if not os.path.exists(path):
                return False
            try:
                self.add_font(name, style, path)
                return True
            except (ValueError, RuntimeError) as e:
                # Ignore "already added" warnings - this is expected behavior
                if "already added" in str(e).lower() or "already registered" in str(e).lower():
                    return True
                logger.warning(f"Font registration warning for {name} {style}: {e}")
                return True
            except Exception as e:
                logger.error(f"Failed to register font {name} {style}: {e}")
                return False
        
        if os.path.exists(vista_book_path):
            # Register with original case
            safe_add_font("VistaSansOTBook", "", vista_book_path)
            if os.path.exists(vista_bold_path):
                safe_add_font("VistaSansOTBook", "B", vista_bold_path)
            if os.path.exists(vista_italic_path):
                safe_add_font("VistaSansOTBook", "I", vista_italic_path)
            
            # Also register lowercase version for compatibility (fpdf2 may normalize to lowercase)
            safe_add_font("vistasansotbook", "", vista_book_path)
            if os.path.exists(vista_bold_path):
                safe_add_font("vistasansotbook", "B", vista_bold_path)
            if os.path.exists(vista_italic_path):
                safe_add_font("vistasansotbook", "I", vista_italic_path)
            
            logger.info("VistaSansOTBook fonts registered successfully")
        
        # VistaSans Regular fonts
        vista_reg_path = os.path.join(fonts_dir, 'VistaSansOT-Reg.ttf')
        if os.path.exists(vista_reg_path):
            safe_add_font("VistaSansReg", "", vista_reg_path)
            safe_add_font("vistasansreg", "", vista_reg_path)
        
        # VistaSans Light fonts
        vista_light_path = os.path.join(fonts_dir, 'VistaSansOT-Light.ttf')
        vista_light_italic_path = os.path.join(fonts_dir, 'VistaSansOT-LightItalic.ttf')
        if os.path.exists(vista_light_path):
            safe_add_font("vistaSansLight", "", vista_light_path)
            safe_add_font("vistasanslight", "", vista_light_path)
            if os.path.exists(vista_light_italic_path):
                safe_add_font("vistaSansLight", "I", vista_light_italic_path)
                safe_add_font("vistasanslight", "I", vista_light_italic_path)
        
        # Calibri fonts
        calibri_path = os.path.join(fonts_dir, 'Calibri.ttf')
        calibri_bold_path = os.path.join(fonts_dir, 'Calibri-Bold.ttf')
        if os.path.exists(calibri_path):
            safe_add_font("Calibri", "", calibri_path)
            safe_add_font("calibri", "", calibri_path)
            if os.path.exists(calibri_bold_path):
                safe_add_font("Calibri", "B", calibri_bold_path)
                safe_add_font("calibri", "B", calibri_bold_path)
            logger.info("Calibri fonts registered successfully")
        else:
            logger.warning(f"Calibri.ttf not found at {calibri_path}")
    
    def _safe_set_font(self, family, style="", size=10):
        """Safely set font with fallback to built-in fonts"""
        import logging
        logger = logging.getLogger(__name__)
        try:
            self.set_font(family, style, size)
        except Exception as e:
            logger.warning(f"Failed to set font {family} {style} {size}: {e}, falling back to Helvetica")
            # Fallback to built-in Helvetica font
            try:
                self.set_font("Helvetica", style, size)
            except Exception:
                # Last resort: use default font
                self.set_font("Arial", style, size)
    
    def header(self):
        """Page header - skip on title page"""
        if self.page_no() == 1:
            return
        
        # Logo in top left - smaller size
        import logging
        logger = logging.getLogger(__name__)
        
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                # Logo dimensions - reduced size, use proper aspect ratio to avoid distortion
                logo_height = 8  # Height in mm (reduced from 12)
                
                # Calculate width based on aspect ratio if available
                if self.logo_aspect_ratio:
                    logo_width = logo_height * self.logo_aspect_ratio
                else:
                    # Default aspect ratio (assume square-ish or slightly wider)
                    logo_width = logo_height * 1.2
                
                x_pos = 15  # 15mm from left edge (matches left margin)
                y_pos = 8  # 8mm from top
                
                # Add logo (should be PNG if conversion worked, or SVG as fallback)
                logger.debug(f"Adding logo to header from: {self.logo_path}")
                self.image(self.logo_path, x=x_pos, y=y_pos, w=logo_width, h=logo_height)
                
                # Adjust text position to be after logo
                text_x = x_pos + logo_width + 5  # 5mm spacing after logo
            except Exception as e:
                logger.warning(f"Failed to add logo to header: {e}", exc_info=True)
                # If logo fails, just continue without it
                text_x = 15
        else:
            logger.warning(f"Logo path not available for header: {self.logo_path}")
            text_x = 15
        
        # Add patient info on the right side - multiline, left-aligned
        if self.patient_metadata:
            sex = self.patient_metadata.get('sex', '')
            birthdate = self.patient_metadata.get('birthdate', '')
            sample_id = self.patient_metadata.get('sample_id', '')
            sample_date = self.patient_metadata.get('sample_date', '')
            
            if sex or birthdate or sample_id or sample_date:
                self.set_font("VistaSansOTBook", "", 9)
                self.set_text_color(*self.gray)
                
                # Position on the right side, but text aligned left
                page_width = self.w
                right_margin = self.r_margin
                line_height = 5  # Height between lines
                start_y = 8  # Start at same height as logo
                
                # Build all text lines
                lines = []
                if sample_id:
                    lines.append(f"Sample: {sample_id}")
                if sample_date:
                    lines.append(f"Date: {sample_date}")
                if sex:
                    sex_display = "Male" if sex.upper() == 'M' else "Female" if sex.upper() == 'F' else sex
                    lines.append(f"Sex: {sex_display}")
                if birthdate:
                    lines.append(f"Birthdate: {birthdate}")
                
                # Find the maximum width for alignment
                max_width = max([self.get_string_width(line) for line in lines]) if lines else 0
                
                # Position all lines starting from the same x position (right-aligned container, left-aligned text)
                info_x = page_width - right_margin - max_width
                
                # Render all lines
                for i, line in enumerate(lines):
                    self.set_xy(info_x, start_y + i * line_height)
                    self.cell(max_width, line_height, line, 0, 0, "L")
    
    def footer(self):
        """Page footer - skip on title page"""
        if self.page_no() == 1:
            return
        self.set_xy(0, -20)
        self.set_fill_color(*self.light_gray)
        self.rect(0, self.h - 20, self.w, 20, 'F')
        self.set_text_color(*self.gray)
        self.set_font("VistaSansOTBook", "", 9)
        self.set_xy(self.w - 30, self.h - 15)
        self.cell(0, 10, str(self.page_no()), 0, 0, "R")
    
    def add_title_page(self):
        """Add title page - unique design with Buchinger Wilhelmi logo"""
        self.add_page()
        
        # Unique asymmetric layout with logo
        page_width = self.w
        page_height = self.h
        
        # Add subtle background element - diagonal accent
        self.set_fill_color(*self.light_gray_2)
        # Create an asymmetric diagonal shape from top-left
        self.rect(0, page_height*0.618, page_width , page_height , 'F')
        
        # Logo placement - top left, smaller size
        import logging
        logger = logging.getLogger(__name__)
        
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                # Smaller logo for cover page
                logo_height = 15  # Height in mm (reduced from 25)
                
                # Calculate width based on aspect ratio
                if self.logo_aspect_ratio:
                    logo_width = logo_height * self.logo_aspect_ratio
                else:
                    logo_width = logo_height * 1.2
                
                # Position: top-left with generous spacing
                logo_x = 20  # 20mm from left edge
                logo_y = 30  # 30mm from top
                
                # Add logo
                logger.info(f"Adding logo to cover page from: {self.logo_path}")
                self.image(self.logo_path, x=logo_x, y=logo_y, w=logo_width, h=logo_height)
                logger.info(f"Logo added successfully to cover page at ({logo_x}, {logo_y})")
                
                # Add subtle line below logo for separation
                # self.set_draw_color(*self.gray)
                # self.set_line_width(0.3)
                # line_y = logo_y + logo_height + 8
                # self.line(logo_x, line_y, logo_x + logo_width, line_y)
            except Exception as e:
                logger.error(f"Failed to add logo to cover page: {e}", exc_info=True)
        else:
            logger.warning(f"Logo path not available for cover page: {self.logo_path}")
        
        # Main title - positioned asymmetrically, not centered
        self.set_text_color(*self.blue_accent)
        self.set_font("VistaSansOTBook", "", 36)
        
        # Position title to the right of logo area, or centered if no logo
        if self.logo_path and os.path.exists(self.logo_path):
            title_x = 20
            title_y = page_height*0.54
        else:
            title_x = 0
            title_y = 100
        
        self.set_xy(title_x, title_y)
        self.cell(0, 25, "Your Results    > ", 0, 0, "L")
        
        # Subtitle - lighter, positioned below title
        self.set_text_color(*self.black)
        self.set_font("vistaSansLight", "", 18)
        self.set_xy(120, title_y+3 )
        self.cell(50, 20, "Laboratory Analysis", 0, 0, "L")
        
        # Add elegant decorative element - thin horizontal line at bottom
        self.set_draw_color(*self.gray)
        self.set_line_width(0.5)
        bottom_line_y = page_height - 50
        # self.line(20, bottom_line_y, page_width - 20, bottom_line_y)
        
        # Optional: Add subtle text at bottom (e.g., year or clinic name)
        self.set_text_color(*self.gray)
        self.set_font("vistaSansLight", "", 10)
        self.set_xy(20, bottom_line_y + 8)
        # self.cell(0, 10, "Buchinger Wilhelmi", 0, 0, "L")
    
    def add_category_section(self, category_name, explanation, is_main_category=False, is_subcategory=False):
        """Add category section with title and explanation
        
        Args:
            category_name: Name of the category
            explanation: Explanation text for the category
            is_main_category: If True, this is a main category (like "ENDOCRINOLOGY")
            is_subcategory: If True, this is a subcategory (like "SEX HORMONES")
        """
        # Calculate effective width: page width minus left and right margins
        # Use epw (effective page width) which is already calculated by fpdf2
        effective_width = self.epw  # This is w - l_margin - r_margin
        
        # IMPORTANT: text measurement depends on the currently selected font.
        # Set the exact font used for the explanation BEFORE splitting into lines,
        # otherwise widths are measured with whatever font was active previously (tables, headers, etc.).
        self.set_font("vistaSansLight", "", 10)

        explanation = explanation or ""

        # Estimate space needed: title (10) + explanation (5 per line) + spacing (8)
        # Use fpdf2's internal splitter (multi_cell with split_only) for accurate wrapping.
        explanation_lines = self.multi_cell(
            w=effective_width,
            h=5,
            txt=explanation,
            border=0,
            align="L",
            split_only=True,
        )
        estimated_height = 10 + (len(explanation_lines) * 5) + 1
        
        # Check if we need a new page (with margin)
        # Always add title, even if we start on a new page
        if self.get_y() + estimated_height > self.h - 60:
            self.add_page()
            # Ensure we start below the header
            self.set_y(self.t_margin)
        
        # Normal flow: always add title and explanation
        # Ensure we're not too close to header - always start at least at margin
        if self.get_y() < self.t_margin:
            self.set_y(self.t_margin)
        self.ln(10)
        
        if is_subcategory:
            # Subcategory: smaller font, black color, no ">"
            self.set_text_color(*self.black)
            self.set_font("VistaSansOTBook", "", 12)  # Smaller font for subcategory
            self.cell(0, 8, category_name.upper(), 0, 1, "L")
            self.ln(2)  # Less spacing for subcategory
        else:
            # Main category: blue color, larger font, with ">"
            self.set_text_color(*self.blue_accent)
            self.set_font("VistaSansOTBook", "", 16)  # Regular weight instead of bold
            self.cell(0, 10, f"> {category_name.upper()}", 0, 1, "L")
            
            self.ln(3)
            self.set_text_color(*self.black)
            self.set_font("vistaSansLight", "", 10)
            
            # Render explanation text using fpdf2's wrapping at full effective width.
            # This avoids overflow and prevents "2/3 width" artifacts from pre-split text.
            self.set_x(self.l_margin)
            self.multi_cell(w=effective_width, h=5, txt=explanation, border=0, align="L")
        
    
    def _wrap_text(self, text, width):
        """Wrap text to fit width, handling long words properly"""
        if not text:
            return []
        
        words = text.split(' ')
        lines = []
        current_line = []
        current_width = 0
        space_width = self.get_string_width(' ')
        
        for word in words:
            word_width = self.get_string_width(word)
            
            # If word alone exceeds width, we need to break it
            if word_width > width:
                # For very long words, break them into chunks
                if len(word) > 50:
                    # Break into smaller chunks
                    chunk_size = 40
                    chunks = [word[i:i+chunk_size] for i in range(0, len(word), chunk_size)]
                    for i, chunk in enumerate(chunks):
                        chunk_width = self.get_string_width(chunk)
                        if current_width + chunk_width + (space_width if i > 0 and current_line else 0) > width and current_line:
                            lines.append(' '.join(current_line))
                            current_line = [chunk]
                            current_width = chunk_width
                        else:
                            if i > 0 and current_line:
                                current_width += space_width
                            current_line.append(chunk)
                            current_width += chunk_width
                else:
                    # Word is long but manageable - add it anyway (will wrap)
                    if current_line:
                        current_width += space_width
                    current_line.append(word)
                    current_width += word_width
            else:
                # Normal word - check if it fits on current line
                word_with_space_width = word_width + (space_width if current_line else 0)
                if current_width + word_with_space_width > width and current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_width = word_width
                else:
                    if current_line:
                        current_width += space_width
                    current_line.append(word)
                    current_width += word_width
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def generate(self, structured_data, output_path, doctor_comments='', patient_metadata=None):
        """Generate PDF from structured data"""
        # Update patient metadata if provided
        if patient_metadata:
            self.patient_metadata = patient_metadata
        
        from .table_generator import TableGenerator
        from .text_formatter import TextFormatter
        
        table_gen = TableGenerator(self, patient_metadata=patient_metadata)
        text_formatter = TextFormatter()
        
        # Add title page
        self.add_title_page()

        # Use all dates from the data (no limitation)
        all_dates = structured_data.get("dates", [])
        table_dates = all_dates

        # Always start content on page 2 (after title page)
        self.add_page()
        # Ensure we start below the header (header is ~20mm, margin is 25mm, so start at margin)
        self.set_y(self.t_margin)  # Start at top margin

        # Regroup Endocrinology, Biochemistry, Hematology, and Urine testing subcategories
        regrouped_categories = []
        current_endocrinology = None
        current_biochemistry = None
        current_hematology = None
        current_urine_testing = None
        
        # Mapping of old category names to Biochemistry subcategories
        biochemistry_subcategory_mapping = {
            'Carbohydrate Metabolism': 'Carbohydrate Metabolism',
            'Lipid Metabolism': 'Lipid Metabolism',
            'Proteins': 'Proteins',
            'Renal Function': 'Renal Function',
            'Ions': 'Ions',
            'Liver Function': 'Liver Function',
            'Iron Metabolism': 'Iron Metabolism',
            'Phosphocalcic Metabolism': 'Phosphocalcic Metabolism',
            'Vitamins': 'Vitamins'
        }
        
        # Mapping of section names to Hematology subcategories
        hematology_subcategory_mapping = {
            'Red series': 'Red series',
            'White series': 'White series',
            'Platelet series': 'Platelet series',
            'Erythrocyte sedimentation': 'Erythrocyte sedimentation'
        }
        
        # Mapping of old category names to Urine testing subcategories
        urine_subcategory_mapping = {
            'Urine Analysis': 'Chemical and urine sediment analysis',
            'Chemical and urine sediment analysis': 'Chemical and urine sediment analysis'
        }
        
        for category in structured_data['categories']:
            category_name = category.get('name', '')
            
            # Check if this is a Hematology subcategory
            if category_name.startswith('Hematology and Hemostasis - '):
                subcategory_name = category_name.replace('Hematology and Hemostasis - ', '')
                if current_hematology is None:
                    # Create main Hematology category
                    current_hematology = {
                        'name': 'Hematology and Hemostasis',
                        'spanish_name': 'Hematología y Hemostasia',
                        'subcategories': [],
                        'all_parameters': []
                    }
                # Find existing subcategory with same name or create new one
                existing_subcat = None
                for subcat in current_hematology['subcategories']:
                    if subcat['name'] == subcategory_name:
                        existing_subcat = subcat
                        break
                if existing_subcat:
                    existing_subcat['parameters'].extend(category.get('parameters', []))
                else:
                    current_hematology['subcategories'].append({
                        'name': subcategory_name,
                        'parameters': category.get('parameters', [])
                    })
                current_hematology['all_parameters'].extend(category.get('parameters', []))
            # Check if this is an Endocrinology subcategory
            elif category_name.startswith('Endocrinology - '):
                subcategory_name = category_name.replace('Endocrinology - ', '')
                if current_endocrinology is None:
                    # Create main Endocrinology category
                    current_endocrinology = {
                        'name': 'Endocrinology',
                        'spanish_name': 'Endocrinologie',
                        'subcategories': [],
                        'all_parameters': []
                    }
                # Find existing subcategory with same name or create new one
                existing_subcat = None
                for subcat in current_endocrinology['subcategories']:
                    if subcat['name'] == subcategory_name:
                        existing_subcat = subcat
                        break
                if existing_subcat:
                    existing_subcat['parameters'].extend(category.get('parameters', []))
                else:
                    current_endocrinology['subcategories'].append({
                        'name': subcategory_name,
                        'parameters': category.get('parameters', [])
                    })
                current_endocrinology['all_parameters'].extend(category.get('parameters', []))
            # Check if this is a Biochemistry subcategory (new format)
            elif category_name.startswith('Biochemistry (serum / plasma) - '):
                subcategory_name = category_name.replace('Biochemistry (serum / plasma) - ', '')
                if current_biochemistry is None:
                    # Create main Biochemistry category
                    current_biochemistry = {
                        'name': 'Biochemistry (serum / plasma)',
                        'spanish_name': 'Bioquímica (suero / plasma)',
                        'subcategories': [],
                        'all_parameters': []
                    }
                # Find existing subcategory with same name or create new one
                existing_subcat = None
                for subcat in current_biochemistry['subcategories']:
                    if subcat['name'] == subcategory_name:
                        existing_subcat = subcat
                        break
                if existing_subcat:
                    # Merge parameters into existing subcategory
                    existing_subcat['parameters'].extend(category.get('parameters', []))
                else:
                    # Add as new subcategory
                    current_biochemistry['subcategories'].append({
                        'name': subcategory_name,
                        'parameters': category.get('parameters', [])
                    })
                current_biochemistry['all_parameters'].extend(category.get('parameters', []))
            # Check if this is an old category that should be mapped to Biochemistry
            elif category_name in biochemistry_subcategory_mapping:
                subcategory_name = biochemistry_subcategory_mapping[category_name]
                if current_biochemistry is None:
                    # Create main Biochemistry category
                    current_biochemistry = {
                        'name': 'Biochemistry (serum / plasma)',
                        'spanish_name': 'Bioquímica (suero / plasma)',
                        'subcategories': [],
                        'all_parameters': []
                    }
                # Find existing subcategory with same name or create new one
                existing_subcat = None
                for subcat in current_biochemistry['subcategories']:
                    if subcat['name'] == subcategory_name:
                        existing_subcat = subcat
                        break
                if existing_subcat:
                    # Merge parameters into existing subcategory
                    existing_subcat['parameters'].extend(category.get('parameters', []))
                else:
                    # Add as new subcategory
                    current_biochemistry['subcategories'].append({
                        'name': subcategory_name,
                        'parameters': category.get('parameters', [])
                    })
                current_biochemistry['all_parameters'].extend(category.get('parameters', []))
            # Check if this is the main Hematology category (old format) - split by parameters
            elif category_name == 'Hematology and Hemostasis':
                # Only add if we DON'T already have subcategories with parameters
                # This prevents duplication when both main category and subcategories exist
                if current_hematology is None:
                    current_hematology = {
                        'name': 'Hematology and Hemostasis',
                        'spanish_name': 'Hematología y Hemostasia',
                        'subcategories': [],
                        'all_parameters': []
                    }
                    # Only add parameters if no subcategories exist yet
                    current_hematology['subcategories'].append({
                        'name': 'General',
                        'parameters': category.get('parameters', [])
                    })
                    current_hematology['all_parameters'].extend(category.get('parameters', []))
                # If current_hematology already exists (from subcategories), skip to avoid duplication
            # Check if this is a Urine testing subcategory
            elif category_name.startswith('Urine testing - '):
                subcategory_name = category_name.replace('Urine testing - ', '')
                if current_urine_testing is None:
                    # Create main Urine testing category
                    current_urine_testing = {
                        'name': 'Urine testing',
                        'spanish_name': 'Análisis de Orina',
                        'subcategories': [],
                        'all_parameters': []
                    }
                # Find existing subcategory with same name or create new one
                existing_subcat = None
                for subcat in current_urine_testing['subcategories']:
                    if subcat['name'] == subcategory_name:
                        existing_subcat = subcat
                        break
                if existing_subcat:
                    existing_subcat['parameters'].extend(category.get('parameters', []))
                else:
                    current_urine_testing['subcategories'].append({
                        'name': subcategory_name,
                        'parameters': category.get('parameters', [])
                    })
                current_urine_testing['all_parameters'].extend(category.get('parameters', []))
            # Check if this is an old Urine category that should be mapped
            elif category_name in urine_subcategory_mapping:
                subcategory_name = urine_subcategory_mapping[category_name]
                if current_urine_testing is None:
                    current_urine_testing = {
                        'name': 'Urine testing',
                        'spanish_name': 'Análisis de Orina',
                        'subcategories': [],
                        'all_parameters': []
                    }
                # Find existing subcategory with same name or create new one
                existing_subcat = None
                for subcat in current_urine_testing['subcategories']:
                    if subcat['name'] == subcategory_name:
                        existing_subcat = subcat
                        break
                if existing_subcat:
                    existing_subcat['parameters'].extend(category.get('parameters', []))
                else:
                    current_urine_testing['subcategories'].append({
                        'name': subcategory_name,
                        'parameters': category.get('parameters', [])
                    })
                current_urine_testing['all_parameters'].extend(category.get('parameters', []))
            else:
                # If we have accumulated categories, add them first
                if current_hematology is not None:
                    regrouped_categories.append(current_hematology)
                    current_hematology = None
                if current_endocrinology is not None:
                    regrouped_categories.append(current_endocrinology)
                    current_endocrinology = None
                if current_biochemistry is not None:
                    regrouped_categories.append(current_biochemistry)
                    current_biochemistry = None
                if current_urine_testing is not None:
                    regrouped_categories.append(current_urine_testing)
                    current_urine_testing = None
                # Add regular category
                regrouped_categories.append(category)
        
        # Don't forget the last groups
        if current_hematology is not None:
            regrouped_categories.append(current_hematology)
        if current_endocrinology is not None:
            regrouped_categories.append(current_endocrinology)
        if current_biochemistry is not None:
            regrouped_categories.append(current_biochemistry)
        if current_urine_testing is not None:
            regrouped_categories.append(current_urine_testing)
        
        # Sort regrouped categories to ensure correct order
        # Biochemistry should come before Endocrinology
        # Get order from categories.json via text_formatter
        def get_category_order(cat):
            cat_name = cat.get('name', '')
            # For regrouped categories with subcategories, use the main category name
            if 'subcategories' in cat:
                # Get order from categories.json
                for ref_cat in text_formatter.categories_config['categories']:
                    if ref_cat['name'] == cat_name:
                        return ref_cat.get('order', 999)
                return 999
            # For regular categories, get order from categories.json
            for ref_cat in text_formatter.categories_config['categories']:
                if ref_cat['name'] == cat_name:
                    return ref_cat.get('order', 999)
            return 999
        
        regrouped_categories.sort(key=get_category_order)
        
        # Process categories continuously (do NOT force 1 page per category)
        first_category = True
        for category in regrouped_categories:
            # Handle regrouped category with subcategories (Endocrinology or Biochemistry)
            if 'subcategories' in category:
                # Main category header
                main_category_name = category['name']
                explanation = text_formatter.get_category_explanation(main_category_name)
                self.add_category_section(main_category_name, explanation, is_main_category=True)
                
                # Sort subcategories by their order from categories.json
                # Get order for each subcategory
                def get_subcategory_order(subcat):
                    subcat_name = subcat.get('name', '')
                    # Try to find the order in categories.json
                    for ref_cat in text_formatter.categories_config['categories']:
                        # Check if this is a subcategory of the main category
                        if ref_cat['name'] == f"{main_category_name} - {subcat_name}":
                            return ref_cat.get('order', 9999)
                        # Also check old format (without prefix)
                        if ref_cat['name'] == subcat_name:
                            return ref_cat.get('order', 9999)
                    return 9999  # Default to end if not found
                
                sorted_subcategories = sorted(category['subcategories'], key=get_subcategory_order)
                
                # Process each subcategory
                for subcategory in sorted_subcategories:
                    subcategory_params = subcategory.get('parameters', [])
                    
                    # Filter parameters to only include those with values
                    parameters_with_values = []
                    for param in subcategory_params:
                        has_values = False
                        for val_obj in param.get('values', []):
                            value = val_obj.get('value')
                            if value and str(value).strip() and str(value).strip().lower() != 'nan':
                                has_values = True
                                break
                        if has_values:
                            parameters_with_values.append(param)
                    
                    if not parameters_with_values:
                        continue
                    
                    # Add subcategory header (without ">", smaller font, not blue)
                    self.add_category_section(subcategory['name'], '', is_subcategory=True)
                    
                    # Generate table for this subcategory
                    subcategory_for_table = {
                        'name': subcategory['name'],
                        'parameters': parameters_with_values
                    }
                    table_gen.generate_category_table(subcategory_for_table, table_dates)
                    
                    # Add parameter explanations
                    # Check if any parameter has explanation OR is a special parameter that will get one
                    has_explanations = self._has_or_needs_explanations(parameters_with_values)
                    if has_explanations:
                        current_y = self.get_y()
                        if current_y + 10 < self.h - 30:
                            self.ln(2)
                        self._add_parameter_explanations(parameters_with_values)
            else:
                # Regular category processing
                parameters = category.get("parameters", [])
                if not parameters:
                    continue
                
                # Filter parameters to only include those with values
                parameters_with_values = []
                for param in parameters:
                    has_values = False
                    for val_obj in param.get('values', []):
                        value = val_obj.get('value')
                        if value and str(value).strip() and str(value).strip().lower() != 'nan':
                            has_values = True
                            break
                    if has_values:
                        parameters_with_values.append(param)
                
                # Skip categories with no parameters that have values
                if not parameters_with_values:
                    continue
                
                # Update category with filtered parameters
                category['parameters'] = parameters_with_values

                first_category = False

                explanation = text_formatter.get_category_explanation(category['name'])
                self.add_category_section(category['name'], explanation)

                # Generate table for this category
                table_gen.generate_category_table(category, table_dates)

                # Add parameter explanations (compact) - only if there are explanations
                # Check if any parameter has explanation OR is a special parameter that will get one
                has_explanations = self._has_or_needs_explanations(category['parameters'])
                if has_explanations:
                    # Only add small spacing if there's enough room, otherwise explanations will handle page break
                    current_y = self.get_y()
                    if current_y + 10 < self.h - 30:  # Check if we have at least 10mm space
                        self.ln(2)
                    self._add_parameter_explanations(category['parameters'])
        
        # Add doctor comments section if provided
        if doctor_comments and doctor_comments.strip():
            self._add_doctor_comments(doctor_comments.strip())
        
        # Output PDF
        self.output(output_path)
    
    def _has_or_needs_explanations(self, parameters):
        """Check if any parameter has explanation or is a special parameter that will get one"""
        # List of special parameters that will always get explanations
        special_params = [
            'DHEA', 'DHYDROEPIANDROSTERONE', 'DEHYDROEPIANDROSTERONE',
            'FSH', 'FOLLICLE-STIMULATING HORMONE',
            'LH', 'LEUTENISING HORMONE', 'LUTEINIZING HORMONE',
            'SHBG', 'SEX HORMONE BINDING GLOBULIN', 'SEX HORMON BINDING GLOBULIN',
            'ESTRADIOL', '17-BETA', '17 BETA', 'BETA ESTRADIOL',
            'PROGESTERONE',
            'SOMATOMEDIN', 'IGF-1', 'IGF1',
            'TOTAL TESTOSTERONE', 'BIOAVAILABLE TESTOSTERONE',
            'CORTISOL', 'HYDROCORTISONE',
            'TSH', 'THYROTROPIN', 'TIROTROPIN',
            'FREE THYROXINE', 'THYROXINE',
            'T3', 'FREE T3', 'T3 FREE', 'TRIIODOTHYRONINE',
            'HGH', 'HUMAN GROWTH HORMONE', 'GROWTH HORMONE',
            'FREE PSA/TOTAL PSA', 'PSA INDEX', 'PSA RATIO',
            'ANDROSTENEDIONE', 'DELTA 4', 'DELTA-4',
            '25-HYDROXYVITAMIN D', 'VITAMIN D', '25-OH'
        ]
        
        for param in parameters:
            # Check if parameter already has explanation
            if param.get('explanation'):
                return True
            
            # Check if parameter is a special one that will get an explanation
            param_name = param.get('english_name', '').upper()
            for special in special_params:
                if special in param_name:
                    return True
        
        return False
    
    def _add_parameter_explanations(self, parameters):
        """Add explanations for parameters (grouped logically)"""
        # Group parameters by their explanation text (to avoid duplicates)
        explanation_groups = {}
        
        for param in parameters:
            explanation = param.get('explanation', '')
            
            # Replace explanation for DHEA (DHYDROEPIANDROSTERONE)
            param_name = param.get('english_name', '')
            param_unit = param.get('unit', '')
            if ('DHEA' in param_name.upper() or 'DHYDROEPIANDROSTERONE' in param_name.upper()) and '-S' not in param_name.upper():
                if 'ng/mL' in param_unit:
                    # Replace with fixed English text - update the param dict directly
                    param['explanation'] = "Men (adult): 1,87-15,01 ng/mL, Women (adult): 1,65-13,50 ng/mL"
                    explanation = param['explanation']  # Update local variable too
                elif 'nmol' in param_unit.lower():
                    # For nmol/L unit, clear the explanation to avoid duplicate note
                    param['explanation'] = ""
                    explanation = ""
            
            # Translate explanation for LDL oxidada (Spanish to English)
            if 'LDL OXIDADA' in param_name.upper() or 'OXIDADA' in param_name.upper():
                # Check if explanation contains Spanish text about diabetic patients
                if explanation and ('Pacientes diabéticos' in explanation or 'diabéticos tipo 2' in explanation or 'sin HTA' in explanation or 'con HTA' in explanation):
                    # Translate the Spanish note to English
                    param['explanation'] = """Type 2 diabetic patients: 92.5 - 192.2 ng/mL
Type 2 diabetic patients without hypertension: 77.7 - 144.6 ng/mL
Type 2 diabetic patients with hypertension: 107.5 - 207.3 ng/mL"""
                    explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for TSH with clear English text
            if 'TSH' in param_name.upper() or 'THYROTROPIN' in param_name.upper() or 'TIROTROPIN' in param_name.upper():
                # Always add explanation for TSH if it contains pregnancy info, or add it if missing
                if explanation and ('trimester' in explanation.lower() or 'pregnancy' in explanation.lower() or '1er' in explanation or '2º' in explanation or '3er' in explanation):
                    # Replace existing explanation
                    param['explanation'] = """Reference values during pregnancy:
• First trimester: up to 2.5 mU/L
• Second and third trimester: up to 3.5 mU/L"""
                    explanation = param['explanation']  # Update local variable too
                elif not explanation:
                    # Add explanation if it doesn't exist (for consistency, but may not always be needed)
                    # Only add if we want to always show pregnancy values
                    pass  # Don't add if no explanation exists - only replace if it does
            
            # Replace explanation for FREE THYROXINE with clear English text
            if 'FREE THYROXINE' in param_name.upper() or ('THYROXINE' in param_name.upper() and 'FREE' in param_name.upper()):
                # Always add explanation for FREE THYROXINE, even if not in PDF
                if explanation and ('Pregnant' in explanation or 'trimester' in explanation.lower() or 'pregnancy' in explanation.lower()):
                    # Replace existing explanation
                    param['explanation'] = """Reference values during pregnancy:
• First trimester: 0.52 - 1.10 ng/dL
• Second trimester: 0.45 - 0.99 ng/dL
• Third trimester: 0.48 - 0.95 ng/dL"""
                    explanation = param['explanation']  # Update local variable too
                elif not explanation:
                    # Add explanation if it doesn't exist
                    param['explanation'] = """Reference values during pregnancy:
• First trimester: 0.52 - 1.10 ng/dL
• Second trimester: 0.45 - 0.99 ng/dL
• Third trimester: 0.48 - 0.95 ng/dL"""
                    explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for T3 FREE (Free Triiodothyronine)
            if ('T3' in param_name.upper() and 'FREE' in param_name.upper()) or 'FREE T3' in param_name.upper() or 'T3 - FREE' in param_name.upper():
                param['explanation'] = """Free T3 (triiodothyronine) is the active thyroid hormone that regulates metabolism, energy, and body temperature. Elevated levels may indicate hyperthyroidism, while low levels suggest hypothyroidism or conversion issues from T4. Method: Radioimmunoassay."""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for 25-HYDROXYVITAMIN D with properly formatted text
            if '25-HYDROXYVITAMIN D' in param_name.upper() or ('VITAMIN D' in param_name.upper() and '25' in param_name.upper()) or 'VITAMIN D (25-OH)' in param_name.upper():
                param['explanation'] = """Vitamin D is essential for bone health, immune function, and calcium absorption. Levels reflect sun exposure, dietary intake, and metabolic status.

REFERENCE RANGES:
• Deficiency: less than 10 ng/mL
• Insufficiency: 10 to 30 ng/mL
• Sufficiency: 30 to 100 ng/mL
• Toxicity: greater than 100 ng/mL"""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for FSH with fixed description and reference ranges
            if 'FSH' in param_name.upper() or 'FOLLICLE-STIMULATING HORMONE' in param_name.upper():
                # Store fixed explanation with reference ranges
                param['explanation'] = """Follicle-Stimulating Hormone (FSH) is a key reproductive hormone produced by the pituitary gland. In women, FSH stimulates the growth and development of ovarian follicles and regulates estrogen production. In men, it supports sperm production. FSH levels vary significantly throughout the menstrual cycle in women and increase after menopause.
REFERENCE RANGES:
    • Women with normal menstrual cycle:
      - Follicular phase: 1-10 mIU/mL
      - Ovulatory phase: 6-33 mIU/mL
      - Luteal phase: 1-10 mIU/mL
    • Postmenopausal: 20-120 mIU/mL
    • Male: 1.0-15 mIU/mL
    • Child (1-12 years): <2 mIU/mL"""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for LH with fixed description and reference ranges
            if 'LH' in param_name.upper() or 'LEUTENISING HORMONE' in param_name.upper() or 'LUTEINIZING HORMONE' in param_name.upper():
                # Store fixed explanation with reference ranges
                param['explanation'] = """Luteinizing Hormone (LH) is a gonadotropin produced by the pituitary gland that plays a crucial role in reproductive function. In women, LH triggers ovulation and stimulates progesterone production. In men, it stimulates testosterone production in the testes. LH levels fluctuate throughout the menstrual cycle, with a surge during ovulation.

REFERENCE RANGES:
    • Women with normal menstrual cycle:
        - Follicular phase: 1-10 mIU/mL
        - Ovulatory phase: 12-75 mIU/mL
        - Luteal phase: 1-14 mIU/mL
    • Postmenopausal: 15-60 mIU/mL
    • Male: 1.5-8 mIU/mL
    • Child (1-12 years): <6 mIU/mL
"""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for SHBG with fixed description and reference ranges
            if 'SHBG' in param_name.upper() or 'SEX HORMONE BINDING GLOBULIN' in param_name.upper() or 'SEX HORMON BINDING GLOBULIN' in param_name.upper():
                # Store fixed explanation with reference ranges
                param['explanation'] = """Sex Hormone Binding Globulin (SHBG) is a protein produced by the liver that binds to sex hormones, primarily testosterone and estradiol, regulating their bioavailability. High SHBG levels reduce the amount of free (active) hormones, while low levels increase free hormone availability. SHBG levels vary with age, sex, hormonal status, and during pregnancy.

REFERENCE RANGES:
• Women with normal menstrual cycle:
  - Follicular phase: 26-103 nmol/L
  - Ovulatory phase: 11-97 nmol/L
  - Luteal phase: 28-112 nmol/L
• Postmenopausal: <37 nmol/L
• Male: 13-71 nmol/L
• Pregnancy 1st trimester: 26-241 nmol/L
• Pregnancy 2nd trimester: 85-491 nmol/L"""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for 17-BETA ESTRADIOL with fixed description and reference ranges
            if ('ESTRADIOL' in param_name.upper() or '17-BETA' in param_name.upper() or 
                '17 BETA' in param_name.upper() or 'BETA ESTRADIOL' in param_name.upper()):
                param['explanation'] = """17-Beta Estradiol is the primary form of estrogen in women, produced mainly by the ovaries. It plays a crucial role in reproductive health, bone density, and cardiovascular health. Estradiol levels vary significantly throughout the menstrual cycle, with peak levels during the ovulatory phase.

REFERENCE RANGES:
• Women with normal menstrual cycle:
  - Follicular phase: <100 pg/mL
  - Ovulatory phase: 100-400 pg/mL
  - Luteal phase: 50-150 pg/mL
• Postmenopausal: <40 pg/mL
• Male: <60 pg/mL
• Child (1-12 years): <15 pg/mL"""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for PROGESTERONE with fixed description and reference ranges
            if 'PROGESTERONE' in param_name.upper():
                param['explanation'] = """Progesterone is a steroid hormone produced by the ovaries (corpus luteum) in women and by the adrenal glands in both sexes. It plays a key role in the menstrual cycle, pregnancy, and maintaining the uterine lining. Progesterone levels are highest during the luteal phase of the menstrual cycle.

REFERENCE RANGES:
• Women with normal menstrual cycle:
  - Follicular phase: <1.5 µg/L
  - Luteal phase: 5.5-26 µg/L
• Postmenopausal: <0.7 µg/L
• Male: <1 µg/L
• Child (1-12 years): <0.6 µg/L"""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for TOTAL TESTOSTERONE with fixed description and reference ranges
            if 'TOTAL TESTOSTERONE' in param_name.upper() or (param_name.upper() == 'TESTOSTERONE' and 'TOTAL' not in param_name.upper() and 'FREE' not in param_name.upper() and 'BIOAVAILABLE' not in param_name.upper() and 'ESTIMATED' not in param_name.upper()):
                param['explanation'] = """Total Testosterone is the primary male sex hormone, also present in smaller amounts in women. It plays a crucial role in muscle mass, bone density, libido, and overall well-being. Testosterone levels are measured to assess hypogonadism, infertility, and hormonal imbalances.

REFERENCE RANGES:
• Adult Male: 2.4 - 8.7 ng/mL
• Adult Female: 0.10 - 0.40 ng/mL"""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for BIOAVAILABLE TESTOSTERONE
            if 'BIOAVAILABLE' in param_name.upper() and 'TESTOSTERONE' in param_name.upper():
                param['explanation'] = """Bioavailable testosterone (also called bioactive testosterone) represents the sum of free testosterone and testosterone bound to albumin. These two fractions represent the testosterone that can be used by tissues, making it the best marker of biological activity. Bioavailable testosterone is calculated from total testosterone concentration, its transport proteins (SHBG and albumin), and the circulating free fraction."""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for BASAL CORTISOL (HYDROCORTISONE)
            if 'CORTISOL' in param_name.upper() or 'HYDROCORTISONE' in param_name.upper():
                param['explanation'] = """Basal cortisol, also known as hydrocortisone, is the primary stress hormone produced by the adrenal cortex. It plays a crucial role in regulating metabolism, immune function, blood pressure, and the body's response to stress. Cortisol levels follow a diurnal rhythm, with peak levels in the morning and lowest levels in the evening. Values after 17:00 (5 PM): 2.9-17.3 µg/dL."""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for HUMAN GROWTH HORMONE (HGH)
            if 'HGH' in param_name.upper() or 'HUMAN GROWTH HORMONE' in param_name.upper() or 'GROWTH HORMONE' in param_name.upper():
                param['explanation'] = """Human Growth Hormone (HGH) is produced by the pituitary gland and is essential for growth, cell repair, and metabolism. Fasting significantly increases HGH secretion, which promotes fat burning and muscle preservation during periods of caloric restriction.
REFERENCE RANGES: Children: <10.0 ng/mL ; Adults: <6.8 ng/mL. Method: Chemiluminescence."""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for FREE PSA/TOTAL PSA INDEX
            if 'FREE PSA/TOTAL PSA' in param_name.upper() or 'PSA INDEX' in param_name.upper() or 'PSA RATIO' in param_name.upper():
                param['explanation'] = """The Free PSA/Total PSA ratio helps distinguish between benign prostatic conditions and prostate cancer. A ratio above 0.2 (20%) suggests a probably benign prostatic process, while lower ratios may indicate increased cancer risk. This interpretation is applicable when total PSA levels are between 4 and 10 ng/mL."""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for ANDROSTENEDIONE DELTA 4
            if 'ANDROSTENEDIONE' in param_name.upper() or 'DELTA 4' in param_name.upper() or 'DELTA-4' in param_name.upper():
                param['explanation'] = """Androstenedione (delta-4-androstenedione) is a steroid hormone produced by the adrenal glands and gonads. It serves as a precursor to testosterone and estrogen, and is used to evaluate adrenal function and androgen excess conditions.
REFERENCE RANGES:
• Adults - Males: 0.5 - 3.5 ng/mL
• Adults - Pre-menopausal women: 0.4 - 3.4 ng/mL
• Adults - Post-menopausal women: < 2.1 ng/mL
• Young Adults (17-21 years) - Males: 0.44 - 2.65 ng/mL
• Young Adults (17-21 years) - Females: 0.70 - 4.31 ng/mL"""
                explanation = param['explanation']  # Update local variable too
            
            # Replace explanation for SOMATOMEDIN C (IGF-1) with fixed description and table
            if ('SOMATOMEDIN' in param_name.upper() or 'IGF-1' in param_name.upper() or 'IGF1' in param_name.upper()) and 'ng/mL' in param_unit:
                # Store special marker for IGF-1 to render table
                param['explanation'] = """Insulin-like Growth Factor 1 (IGF-1), also known as Somatomedin C, is a hormone produced primarily by the liver in response to growth hormone (GH) stimulation. It plays a crucial role in growth and development, particularly during childhood and adolescence. IGF-1 levels are age and sex-dependent, with peak levels occurring during puberty. It is used clinically to assess growth hormone deficiency, acromegaly, and other growth-related disorders.

In longevity science, IGF-1 is measured to identify the "Goldilocks zone" where levels are high enough to maintain muscle and brain health, yet low enough to minimize cancer risk and promote cellular repair. This biomarker acts as a metabolic thermostat, helping to monitor how fasting or protein intake triggers autophagy, the body's essential internal cleanup process. Tracking it ensures that anti-aging interventions optimize your biological clock without pushing the body into an unsafe state of excessive cellular growth.

__IGF1_TABLE__"""
                explanation = param['explanation']  # Update local variable too
            
            if explanation:
                # Use explanation as key to group parameters with same explanation
                if explanation not in explanation_groups:
                    explanation_groups[explanation] = []
                explanation_groups[explanation].append(param)
        
        # Only proceed if we have explanations to add
        if not explanation_groups:
            return
        
        # Add explanations
        for explanation, param_group in explanation_groups.items():
            # Calculate actual height needed for this group
            # Set font temporarily to calculate text height accurately
            self.set_font("vistaSansLight", "", 8)
            total_height = 3  # Initial ln(3)
            
            # If multiple parameters share the same explanation, show them together
            if len(param_group) > 1:
                # Group header: list all parameter names
                param_names = ", ".join([p['english_name'] for p in param_group])
                total_height += 5  # Param names line (Calibri B, 9)
            else:
                # Single parameter
                total_height += 5  # Param name line (Calibri B, 9)
            
            # Calculate actual lines needed for explanation
            explanation_lines = self._wrap_text(explanation, self.w - 30)
            total_height += len(explanation_lines) * 4  # Each line is 4mm
            total_height += 2  # ln(2) after explanation
            
            # Check if we need a new page - use more accurate calculation
            # Add buffer for bottom margin (20mm) and some extra space (10mm)
            if self.get_y() + total_height > self.h - 30:
                self.add_page()
                self.set_y(self.t_margin)
            
            self.ln(3)
            self.set_text_color(*self.black)
            self.set_font("VistaSansOTBook", "", 9)
            
            # If multiple parameters share the same explanation, show them together
            if len(param_group) > 1:
                # Group header: list all parameter names
                param_names = ", ".join([p['english_name'] for p in param_group])
                self.set_font("Calibri", "B", 9)
                self.cell(0, 5, f"{param_names}:", 0, 1, "L")
            else:
                # Single parameter
                param_name = param_group[0]['english_name']
                self.set_font("Calibri", "B", 9)
                self.cell(0, 5, f"{param_name}:", 0, 1, "L")
            
            # Add the explanation (same for all in group)
            self.set_font("vistaSansLight", "", 8)
            
            # Check if this is DHEA (DHYDROEPIANDROSTERONE) with ng/mL - render fixed text
            param_name = param_group[0]['english_name'] if param_group else ''
            param_unit = param_group[0].get('unit', '') if param_group else ''
            
            # Check for DHEA (DHYDROEPIANDROSTERONE) with ng/mL unit
            if ('DHEA' in param_name.upper() or 'DHYDROEPIANDROSTERONE' in param_name.upper()) and 'ng/mL' in param_unit:
                # Render fixed text in English (exact format as requested)
                self.cell(0, 4, "Men (adult): 1,87-15,01 ng/mL, Women (adult): 1,65-13,50 ng/mL", 0, 1, "L")
                self.ln(2)
                continue
            
            # Check if this is DEHYDROEPIANDROSTERONE-S - render fixed reference table
            if 'DEHYDROEPIANDROSTERONE-S' in param_name.upper() or 'DHEA-S' in param_name.upper():
                # Check if it has the expected unit (µmol/L or similar)
                if 'µmol' in param_unit or 'mcmol' in param_unit.lower():
                    # Add explanatory text with method
                    self.set_font("vistaSansLight", "", 8)
                    self.set_text_color(*self.black)  # Ensure consistent black color
                    explanation_text = "DEHYDROEPIANDROSTERONE-S (DHEA-S) is a sulfated form of DHEA, primarily produced by the adrenal glands. It serves as a stable marker of adrenal androgen production and is evaluated to assess adrenal function, hormonal balance, and age-related hormonal decline. Method: Radioimmunoassay."
                    explanation_lines = self._wrap_text(explanation_text, self.w - 30)
                    for line in explanation_lines:
                        self.cell(0, 4, line, 0, 1, "L")
                    self.ln(4)  # Spacing after text before REFERENCE RANGES
                    self._render_dhea_s_reference_table()
                    self.ln(2)
                    continue
            
            # Check if explanation contains IGF-1 table marker
            if "__IGF1_TABLE__" in explanation:
                # Split text and table marker
                text_part = explanation.replace("__IGF1_TABLE__", "").strip()
                if text_part:
                    # Render text part first
                    explanation_lines = self._wrap_text(text_part, self.w - 30)
                    for line in explanation_lines:
                        self.cell(0, 4, line, 0, 1, "L")
                    self.ln(2)
                # Render IGF-1 reference table
                self._render_igf1_reference_table()
                self.ln(2)
                continue
            
            # Check if explanation contains a reference table
            if explanation.startswith("__REF_TABLE__") and explanation.endswith("__END_TABLE__"):
                # Extract and render table
                import json
                table_json = explanation[13:-13]  # Remove markers
                try:
                    table_data = json.loads(table_json)
                    # Check if this is for Androstenedione - force IGF-1 style if applicable
                    param_name_check = param_group[0]['english_name'] if param_group else ''
                    if 'ANDROSTENEDIONE' in param_name_check.upper():
                        rows = table_data.get('rows', [])
                        if rows:
                            # Group rows by group
                            grouped_rows = {}
                            for row in rows:
                                group = row.get('group', '')
                                if group.lower() in ['children', 'girls', 'boys', 'niños', 'niñas']:
                                    continue
                                if group not in grouped_rows:
                                    grouped_rows[group] = []
                                grouped_rows[group].append(row)
                            
                            # Find Men and Women groups
                            men_group = None
                            women_group = None
                            for group_name in grouped_rows.keys():
                                if group_name.lower() in ['men', 'hombres']:
                                    men_group = group_name
                                elif group_name.lower() in ['women', 'mujeres']:
                                    women_group = group_name
                            
                            # If no explicit groups but we have rows with age ranges,
                            # detect pattern: repeated age ranges = first half Men, second half Women
                            if not men_group and not women_group:
                                # Get all rows (including those with empty group)
                                all_rows = []
                                for group_list in grouped_rows.values():
                                    all_rows.extend(group_list)
                                
                                rows_with_age = [r for r in all_rows if r.get('age_range')]
                                if len(rows_with_age) >= 4:
                                    # Check if age ranges repeat (pattern: same ages appear twice)
                                    age_ranges_list = [r.get('age_range', '') for r in rows_with_age]
                                    unique_ages = list(set(age_ranges_list))
                                    
                                    # If we have repeated age ranges, split in half
                                    if len(unique_ages) <= len(rows_with_age) / 2:
                                        # Split: first half = Men, second half = Women
                                        mid_point = len(rows_with_age) // 2
                                        men_rows = rows_with_age[:mid_point]
                                        women_rows = rows_with_age[mid_point:]
                                        
                                        # Verify they have matching age ranges
                                        men_ages = [r.get('age_range', '') for r in men_rows]
                                        women_ages = [r.get('age_range', '') for r in women_rows]
                                        
                                        if men_ages == women_ages:  # Same age ranges in same order
                                            # Create grouped structure
                                            grouped_rows = {
                                                'Men': men_rows,
                                                'Women': women_rows
                                            }
                                            men_group = 'Men'
                                            women_group = 'Women'
                            
                            # If we have both Men and Women with age ranges, use IGF-1 style
                            if men_group and women_group:
                                men_rows = grouped_rows.get(men_group, [])
                                women_rows = grouped_rows.get(women_group, [])
                                men_with_age = [r for r in men_rows if r.get('age_range')]
                                women_with_age = [r for r in women_rows if r.get('age_range')]
                                
                                if men_with_age and women_with_age:
                                    self._render_age_reference_table_igf1_style(grouped_rows, men_group, women_group)
                                    self.ln(2)
                                    continue
                    
                    # Default rendering for other cases
                    self._render_reference_table(table_data)
                except json.JSONDecodeError:
                    # Fallback to text if JSON parsing fails
                    explanation_lines = self._wrap_text(explanation, self.w - 30)
                    for line in explanation_lines:
                        self.cell(0, 4, line, 0, 1, "L")
            # Check if explanation contains formatted list (has bullet points or newlines)
            elif '\n' in explanation or '•' in explanation:
                # Check if there's a "REFERENCE RANGES" section to format uniformly
                ref_ranges_pattern = 'REFERENCE RANGES'
                if ref_ranges_pattern in explanation:
                    # Split at "REFERENCE RANGES" to handle separately
                    parts = explanation.split(ref_ranges_pattern, 1)
                    descriptive_text = parts[0].strip()
                    reference_section = parts[1].strip() if len(parts) > 1 else ''
                    
                    # Remove leading colon from reference section if present
                    if reference_section.startswith(':'):
                        reference_section = reference_section[1:].strip()
                    
                    # Render descriptive text first
                    if descriptive_text:
                        for paragraph in descriptive_text.split('\n'):
                            if paragraph.strip():
                                wrapped_lines = self._wrap_text(paragraph, self.w - 30)
                                for line in wrapped_lines:
                                    self.cell(0, 4, line, 0, 1, "L")
                    
                    # Add spacing before REFERENCE RANGES (uniform with tables)
                    self.ln(4)
                    
                    # Render "REFERENCE RANGES" with Calibri font (uniform with tables)
                    self.set_font("Calibri", "", 8)
                    self.set_text_color(*self.black)
                    self.cell(0, 5, "REFERENCE RANGES", 0, 1, "L")
                    self.ln(1)
                    
                    # Switch back to vistaSansLight for bullet points
                    self.set_font("vistaSansLight", "", 8)
                    
                    # Render reference section (bullet points)
                    if reference_section:
                        for paragraph in reference_section.split('\n'):
                            if paragraph.strip():
                                # Handle indented lines (sub-bullets)
                                if paragraph.strip().startswith('-'):
                                    self.set_x(20)  # Indent sub-bullets
                                    self.cell(0, 3.5, paragraph.strip(), 0, 1, "L")
                                else:
                                    wrapped_lines = self._wrap_text(paragraph, self.w - 30)
                                    for line in wrapped_lines:
                                        self.cell(0, 3.5, line, 0, 1, "L")
                else:
                    # No REFERENCE RANGES section - render normally
                    for paragraph in explanation.split('\n'):
                        if paragraph.strip():
                            # Handle indented lines (sub-bullets)
                            if paragraph.strip().startswith('-'):
                                # Indented sub-bullet
                                self.set_x(20)  # Indent sub-bullets
                                self.cell(0, 3.5, paragraph.strip(), 0, 1, "L")
                            else:
                                # Regular bullet or text
                                wrapped_lines = self._wrap_text(paragraph, self.w - 30)
                                for line in wrapped_lines:
                                    self.cell(0, 3.5, line, 0, 1, "L")
            else:
                # Normal text wrapping
                explanation_lines = self._wrap_text(explanation, self.w - 30)
                for line in explanation_lines:
                    self.cell(0, 4, line, 0, 1, "L")
            self.ln(2)
    
    def _render_dhea_s_reference_table(self):
        """
        Render DEHYDROEPIANDROSTERONE-S reference table.
        Age ranges as columns, sex as rows, right-aligned, no external borders.
        Same format as IGF-1 table.
        """
        # Age ranges data with "years" suffix
        age_ranges = [
            "16 - 19 years", "20 - 24 years", "25 - 34 years", "35 - 44 years",
            "45 - 54 years", "55 - 64 years", "65 - 70 years", "> 70 years"
        ]
        
        # Reference values: [women_val, men_val] for each age range
        # Format: (women_min-max, men_min-max)
        reference_values = [
            ("3,96 - 15,50", "3,36 - 18,20"),  # 16 - 19
            ("3,60 - 11,10", "6,50 - 14,60"),  # 20 - 24
            ("2,60 - 13,90", "4,60 - 16,10"),  # 25 - 34
            ("2,00 - 11,10", "3,80 - 13,10"),  # 35 - 44
            ("1,50 - 7,70", "3,70 - 12,10"),  # 45 - 54
            ("0,80 - 4,90", "1,30 - 9,80"),   # 55 - 64
            ("0.70 - 3.80", "1.20 - 7.00"),   # 65 - 70
            ("0.50 - 2.50", "0.70 - 5.50")    # > 70
        ]
        
        # Calculate table dimensions
        # Available width: page width - margins (15mm each side)
        available_width = self.w - 30
        n_cols = len(age_ranges)
        
        # Column width for age headers (wider to accommodate "years")
        age_col_width = 20
        # Column width for value columns
        value_col_width = 18
        
        # Total table width
        table_width = age_col_width + (value_col_width * n_cols)
        # Aligner la table à gauche
        x_start = 15  # Aligné à gauche (marge gauche standard)
        
        # Small font for table - use Calibri for better readability
        self.set_font("Calibri", "", 7)
        row_height = 4
        
        # Calculate total table height
        title_height = 6  # "REFERENCE RANGES" title + spacing
        header_height = row_height  # Age range headers
        men_row_height = row_height
        women_row_height = row_height
        total_table_height = title_height + header_height + men_row_height + women_row_height + 4  # +4 for spacing
        
        # Check if table fits on current page, if not, add new page
        if self.get_y() + total_table_height > self.h - 20:
            self.add_page()
            self.set_y(self.t_margin)
        
        # No external borders - only internal separators
        self.set_draw_color(200, 200, 200)  # Light gray
        self.set_line_width(0.1)  # Very thin lines
        
        y_start = self.get_y()
        current_y = y_start
        
        # Table title: "REFERENCE RANGES" - uniform spacing and color
        self.set_font("Calibri", "", 8)
        self.set_text_color(*self.black)  # Ensure same black color as text
        self.set_xy(x_start, current_y)
        self.cell(table_width, 5, "REFERENCE RANGES", 0, 1, "L")
        current_y += 5
        self.ln(1)  # Small margin after title
        current_y += 1
        
        # Store the Y position where the table actually starts (after title)
        table_start_y = current_y
        
        # Header row: Age ranges
        self.set_font("Calibri", "", 7)
        x = x_start
        
        # Empty cell for row header column
        self.set_xy(x, current_y)
        self.cell(age_col_width, row_height, "", 0, 0, "R")
        x += age_col_width
        
        # Age range headers (right-aligned)
        for age_range in age_ranges:
            self.set_xy(x, current_y)
            self.cell(value_col_width, row_height, age_range, 0, 0, "R")
            x += value_col_width
        
        current_y += row_height
        
        # Draw horizontal line after header (internal border only)
        self.line(x_start + age_col_width, current_y, x_start + table_width, current_y)
        
        # Men row
        self.set_font("Calibri", "", 7)
        x = x_start
        
        # Row label: "Men"
        self.set_xy(x, current_y)
        self.cell(age_col_width, row_height, "Men", 0, 0, "R")
        x += age_col_width
        
        # Men values (right-aligned)
        for women_val, men_val in reference_values:
            self.set_xy(x, current_y)
            self.cell(value_col_width, row_height, men_val, 0, 0, "R")
            x += value_col_width
        
        current_y += row_height
        
        # Draw horizontal line after men row (internal border only)
        self.line(x_start + age_col_width, current_y, x_start + table_width, current_y)
        
        # Women row
        x = x_start
        
        # Row label: "Women"
        self.set_xy(x, current_y)
        self.cell(age_col_width, row_height, "Women", 0, 0, "R")
        x += age_col_width
        
        # Women values (right-aligned)
        self.set_font("Calibri", "", 7)
        for women_val, men_val in reference_values:
            self.set_xy(x, current_y)
            self.cell(value_col_width, row_height, women_val, 0, 0, "R")
            x += value_col_width
        
        current_y += row_height
        
        # Draw vertical lines (internal borders only, no external borders)
        # Start from table_start_y (after title), not y_start (before title)
        # Vertical line after row header column
        self.line(x_start + age_col_width, table_start_y, x_start + age_col_width, current_y)
        
        # Vertical lines between value columns
        x = x_start + age_col_width
        for _ in age_ranges:
            x += value_col_width
            self.line(x, table_start_y, x, current_y)
        
        # Update Y position
        self.set_y(current_y)
    
    def _render_igf1_reference_table(self):
        """
        Render minimalistic IGF-1 reference table.
        Age ranges as columns, sex as rows, right-aligned, no external borders.
        """
        # Age ranges data with "years" suffix
        age_ranges = [
            "0-5 years", "12-15 years", "16-20 years", "21-24 years", 
            "25-29 years", "30-39 years", "40-49 years", "50-59 years", ">60 years"
        ]
        
        # Reference values: [men_min, men_max, women_min, women_max] for each age range
        reference_values = [
            [11, 233, 8, 251],      # 0-5
            [49, 520, 90, 596],     # 12-15
            [119, 511, 109, 524],   # 16-20
            [105, 364, 102, 351],   # 21-24
            [84, 283, 91, 311],     # 25-29
            [82, 246, 78, 290],     # 30-39
            [69, 237, 59, 271],     # 40-49
            [55, 225, 44, 240],     # 50-59
            [17, 206, 17, 241]      # >60
        ]
        
        # Calculate table dimensions
        # Available width: page width - margins (15mm each side)
        available_width = self.w - 30
        n_cols = len(age_ranges)
        
        # Column width for age headers (wider to accommodate "years")
        age_col_width = 20
        # Column width for value columns
        value_col_width = 18
        
        # Total table width
        table_width = age_col_width + (value_col_width * n_cols)
        # Aligner la table à gauche
        x_start = 15  # Aligné à gauche (marge gauche standard)
        
        # Small font for table
        self.set_font("vistaSansLight", "", 7)
        row_height = 4
        
        # Calculate total table height
        title_height = 6  # "REFERENCE RANGES" title + spacing
        header_height = row_height  # Age range headers
        men_row_height = row_height
        women_row_height = row_height
        total_table_height = title_height + header_height + men_row_height + women_row_height + 4  # +4 for spacing
        
        # Check if table fits on current page, if not, add new page
        if self.get_y() + total_table_height > self.h - 20:
            self.add_page()
            self.set_y(self.t_margin)
        
        # No external borders - only internal separators
        self.set_draw_color(200, 200, 200)  # Light gray
        self.set_line_width(0.1)  # Very thin lines
        
        y_start = self.get_y()
        current_y = y_start
        
        # Table title: "REFERENCE RANGES" - uniform spacing and color
        self.set_font("Calibri", "", 8)
        self.set_text_color(*self.black)  # Ensure same black color as text
        self.set_xy(x_start, current_y)
        self.cell(table_width, 5, "REFERENCE RANGES", 0, 1, "L")
        current_y += 5
        self.ln(1)  # Small margin after title
        current_y += 1
        
        # Store the Y position where the table actually starts (after title)
        table_start_y = current_y
        
        # Header row: Age ranges
        self.set_font("Calibri", "", 7)
        x = x_start
        
        # Empty cell for row header column
        self.set_xy(x, current_y)
        self.cell(age_col_width, row_height, "", 0, 0, "R")
        x += age_col_width
        
        # Age range headers (right-aligned)
        for age_range in age_ranges:
            self.set_xy(x, current_y)
            self.cell(value_col_width, row_height, age_range, 0, 0, "R")
            x += value_col_width
        
        current_y += row_height
        
        # Draw horizontal line after header (internal border only)
        self.line(x_start + age_col_width, current_y, x_start + table_width, current_y)
        
        # Men row
        self.set_font("Calibri", "", 7)
        x = x_start
        
        # Row label: "Men"
        self.set_xy(x, current_y)
        self.cell(age_col_width, row_height, "Men", 0, 0, "R")
        x += age_col_width
        
        # Men values (right-aligned)
        for i, (men_min, men_max, _, _) in enumerate(reference_values):
            value_str = f"{men_min} - {men_max}"
            self.set_xy(x, current_y)
            self.cell(value_col_width, row_height, value_str, 0, 0, "R")
            x += value_col_width
        
        current_y += row_height
        
        # Draw horizontal line after men row (internal border only)
        self.line(x_start + age_col_width, current_y, x_start + table_width, current_y)
        
        # Women row
        x = x_start
        
        # Row label: "Women"
        self.set_xy(x, current_y)
        self.cell(age_col_width, row_height, "Women", 0, 0, "R")
        x += age_col_width
        
        # Women values (right-aligned)
        self.set_font("Calibri", "", 7)
        for i, (_, _, women_min, women_max) in enumerate(reference_values):
            value_str = f"{women_min} - {women_max}"
            self.set_xy(x, current_y)
            self.cell(value_col_width, row_height, value_str, 0, 0, "R")
            x += value_col_width
        
        current_y += row_height
        
        # Draw vertical lines (internal borders only, no external borders)
        # Start from table_start_y (after title), not y_start (before title)
        # Vertical line after row header column
        self.line(x_start + age_col_width, table_start_y, x_start + age_col_width, current_y)
        
        # Vertical lines between value columns
        x = x_start + age_col_width
        for _ in age_ranges:
            x += value_col_width
            self.line(x, table_start_y, x, current_y)
        
        # Update Y position
        self.set_y(current_y)
    
    def _render_age_reference_table_igf1_style(self, grouped_rows, men_group, women_group):
        """
        Render age reference table in IGF-1 style: age ranges as columns, Men/Women as rows.
        """
        men_rows = grouped_rows.get(men_group, [])
        women_rows = grouped_rows.get(women_group, [])
        
        # Extract unique age ranges from men rows (assuming same age ranges for both)
        age_ranges = []
        men_values = {}
        women_values = {}
        
        # Only process rows that have age_range
        for row in men_rows:
            age_range = row.get('age_range', '')
            if not age_range:
                continue  # Skip rows without age_range
            if age_range not in age_ranges:
                age_ranges.append(age_range)
            value_range = row.get('value_range', '')
            men_values[age_range] = value_range
        
        for row in women_rows:
            age_range = row.get('age_range', '')
            if not age_range:
                continue  # Skip rows without age_range
            value_range = row.get('value_range', '')
            women_values[age_range] = value_range
        
        if not age_ranges:
            return
        
        # Calculate table dimensions
        n_cols = len(age_ranges)
        age_col_width = 20
        value_col_width = 18
        
        # Total table width
        table_width = age_col_width + (value_col_width * n_cols)
        x_start = 15  # Aligned to left
        
        # Small font for table
        self.set_font("vistaSansLight", "", 7)
        row_height = 4
        
        # Calculate total table height
        title_height = 6  # "REFERENCE RANGES" title + spacing
        header_height = row_height  # Age range headers
        men_row_height = row_height
        women_row_height = row_height
        total_table_height = title_height + header_height + men_row_height + women_row_height + 4  # +4 for spacing
        
        # Check if table fits on current page, if not, add new page
        if self.get_y() + total_table_height > self.h - 20:
            self.add_page()
            self.set_y(self.t_margin)
        
        # No external borders - only internal separators
        self.set_draw_color(200, 200, 200)  # Light gray
        self.set_line_width(0.1)  # Very thin lines
        
        y_start = self.get_y()
        current_y = y_start
        
        # Table title: "REFERENCE RANGES" - uniform spacing and color
        self.set_font("Calibri", "", 8)
        self.set_text_color(*self.black)  # Ensure same black color as text
        self.set_xy(x_start, current_y)
        self.cell(table_width, 5, "REFERENCE RANGES", 0, 1, "L")
        current_y += 5
        self.ln(1)  # Small margin after title
        current_y += 1
        
        # Store the Y position where the table actually starts (after title)
        table_start_y = current_y
        
        # Header row: Age ranges
        self.set_font("Calibri", "", 7)
        x = x_start
        
        # Empty cell for row header column
        self.set_xy(x, current_y)
        self.cell(age_col_width, row_height, "", 0, 0, "R")
        x += age_col_width
        
        # Age range headers (right-aligned)
        for age_range in age_ranges:
            self.set_xy(x, current_y)
            self.cell(value_col_width, row_height, age_range, 0, 0, "R")
            x += value_col_width
        
        current_y += row_height
        
        # Draw horizontal line after header (internal border only)
        self.line(x_start + age_col_width, current_y, x_start + table_width, current_y)
        
        # Men row
        self.set_font("Calibri", "", 7)
        x = x_start
        
        # Row label: "Men"
        self.set_xy(x, current_y)
        self.cell(age_col_width, row_height, men_group, 0, 0, "R")
        x += age_col_width
        
        # Men values (right-aligned)
        for age_range in age_ranges:
            value_str = men_values.get(age_range, '')
            self.set_xy(x, current_y)
            self.cell(value_col_width, row_height, value_str, 0, 0, "R")
            x += value_col_width
        
        current_y += row_height
        
        # Draw horizontal line after men row (internal border only)
        self.line(x_start + age_col_width, current_y, x_start + table_width, current_y)
        
        # Women row
        x = x_start
        
        # Row label: "Women"
        self.set_xy(x, current_y)
        self.cell(age_col_width, row_height, women_group, 0, 0, "R")
        x += age_col_width
        
        # Women values (right-aligned)
        self.set_font("Calibri", "", 7)
        for age_range in age_ranges:
            value_str = women_values.get(age_range, '')
            self.set_xy(x, current_y)
            self.cell(value_col_width, row_height, value_str, 0, 0, "R")
            x += value_col_width
        
        current_y += row_height
        
        # Draw vertical lines (internal borders only, no external borders)
        # Start from table_start_y (after title), not y_start (before title)
        # Vertical line after row header column
        self.line(x_start + age_col_width, table_start_y, x_start + age_col_width, current_y)
        
        # Vertical lines between value columns
        x = x_start + age_col_width
        for _ in age_ranges:
            x += value_col_width
            self.line(x, table_start_y, x, current_y)
        
        # Update Y position
        self.set_y(current_y)
    
    def _render_reference_table(self, table_data, param_name=None):
        """
        Render a minimalistic reference table for age-based reference ranges.
        
        Style: Very subtle borders, small font, compact layout.
        If data has age ranges and Men/Women groups, use IGF-1 style (age ranges as columns).
        
        Args:
            table_data: Dictionary with 'rows' containing table data
            param_name: Optional parameter name for specific handling (e.g., Androstenedione)
        """
        if not table_data or not table_data.get('rows'):
            return
        
        rows = table_data['rows']
        if not rows:
            return
        
        # Group rows by group (Children, Girls, Men, Women) if applicable
        # FILTER OUT Children and Girls groups
        grouped_rows = {}
        for row in rows:
            group = row.get('group', '')
            # Skip children groups
            if group.lower() in ['children', 'girls', 'boys', 'niños', 'niñas']:
                continue
            if group not in grouped_rows:
                grouped_rows[group] = []
            grouped_rows[group].append(row)
        
        # If no rows left after filtering, don't render table
        if not grouped_rows:
            return
        
        # Normalize group names
        men_group = None
        women_group = None
        for group_name in grouped_rows.keys():
            if group_name.lower() in ['men', 'hombres']:
                men_group = group_name
            elif group_name.lower() in ['women', 'mujeres']:
                women_group = group_name
        
        # Check if we have both Men and Women groups with age ranges
        # Allow some rows without age_range (be more flexible)
        men_rows = grouped_rows.get(men_group, []) if men_group else []
        women_rows = grouped_rows.get(women_group, []) if women_group else []
        
        # Check if at least some rows have age_range (need at least 2 age ranges to make sense)
        men_with_age = [r for r in men_rows if r.get('age_range')]
        women_with_age = [r for r in women_rows if r.get('age_range')]
        
        can_use_igf1_style = (men_group and women_group and 
                             len(men_with_age) >= 2 and len(women_with_age) >= 2)
        
        # For Androstenedione or if no explicit groups but we have repeated age ranges,
        # detect pattern: repeated age ranges = first half Men, second half Women
        if (param_name and 'ANDROSTENEDIONE' in param_name.upper()) or (not men_group and not women_group):
            if men_group and women_group and (len(men_with_age) > 0 or len(women_with_age) > 0):
                # Try to use IGF-1 style even if not all rows have age_range
                # We'll filter out rows without age_range in the rendering function
                can_use_igf1_style = True
            elif not men_group and not women_group:
                # Try to detect pattern: repeated age ranges = first half Men, second half Women
                all_rows_list = []
                for group_list in grouped_rows.values():
                    all_rows_list.extend(group_list)
                
                rows_with_age_check = [r for r in all_rows_list if r.get('age_range')]
                if len(rows_with_age_check) >= 4:
                    age_ranges_check = [r.get('age_range', '') for r in rows_with_age_check]
                    unique_ages_check = list(set(age_ranges_check))
                    
                    # If we have repeated age ranges, split in half
                    if len(unique_ages_check) <= len(rows_with_age_check) / 2:
                        mid_point = len(rows_with_age_check) // 2
                        men_rows_check = rows_with_age_check[:mid_point]
                        women_rows_check = rows_with_age_check[mid_point:]
                        
                        men_ages_check = [r.get('age_range', '') for r in men_rows_check]
                        women_ages_check = [r.get('age_range', '') for r in women_rows_check]
                        
                        if men_ages_check == women_ages_check:
                            # Create grouped structure
                            grouped_rows = {
                                'Men': men_rows_check,
                                'Women': women_rows_check
                            }
                            men_group = 'Men'
                            women_group = 'Women'
                            can_use_igf1_style = True
        
        if can_use_igf1_style:
            # Use IGF-1 style: age ranges as columns, Men/Women as rows
            self._render_age_reference_table_igf1_style(grouped_rows, men_group, women_group)
            return
        
        # Calculate table width (compact, about 60% of page width)
        table_width = (self.w - 30) * 0.6
        x_start = 15 + (self.w - 30 - table_width) / 2  # Center the table
        
        # Column widths
        if any(row.get('group') for row in rows):
            # Has groups, need group column
            col_group = table_width * 0.25
            col_age = table_width * 0.25
            col_value = table_width * 0.35
            col_unit = table_width * 0.15
        else:
            # No groups
            col_group = 0
            col_age = table_width * 0.35
            col_value = table_width * 0.45
            col_unit = table_width * 0.20
        
        # Small font for table - use Calibri for better readability
        self.set_font("Calibri", "", 7)
        row_height = 4
        
        # Very subtle gray for borders
        self.set_draw_color(200, 200, 200)  # Light gray
        self.set_line_width(0.1)  # Very thin lines
        
        # Render table
        y_start = self.get_y()
        current_y = y_start
        
        # Group and render rows
        for group_name, group_rows in grouped_rows.items():
            # Group header if applicable
            if group_name:
                self.set_font("Calibri", "", 7)
                self.set_xy(x_start, current_y)
                self.cell(table_width, row_height, group_name, 0, 1, "L")
                current_y = self.get_y()
                self.set_font("Calibri", "", 7)
            
            # Render rows in this group
            for row in group_rows:
                x = x_start
                
                # Group column (if applicable)
                if col_group > 0:
                    self.set_xy(x, current_y)
                    self.cell(col_group, row_height, row.get('group', ''), 0, 0, "L")
                    x += col_group
                
                # Age range column
                self.set_xy(x, current_y)
                self.cell(col_age, row_height, row.get('age_range', ''), 0, 0, "L")
                x += col_age
                
                # Value range column
                self.set_xy(x, current_y)
                self.cell(col_value, row_height, row.get('value_range', ''), 0, 0, "L")
                x += col_value
                
                # Unit column
                self.set_xy(x, current_y)
                self.cell(col_unit, row_height, row.get('unit', ''), 0, 0, "L")
                
                # Draw subtle borders
                self.set_xy(x_start, current_y)
                # Top border (very subtle)
                if current_y == y_start or (group_name and group_rows.index(row) == 0):
                    self.line(x_start, current_y, x_start + table_width, current_y)
                # Bottom border
                self.line(x_start, current_y + row_height, x_start + table_width, current_y + row_height)
                # Left border
                self.line(x_start, current_y, x_start, current_y + row_height)
                # Right border
                self.line(x_start + table_width, current_y, x_start + table_width, current_y + row_height)
                
                # Vertical separators (very subtle)
                if col_group > 0:
                    self.line(x_start + col_group, current_y, x_start + col_group, current_y + row_height)
                self.line(x_start + col_group + col_age, current_y, x_start + col_group + col_age, current_y + row_height)
                self.line(x_start + col_group + col_age + col_value, current_y, x_start + col_group + col_age + col_value, current_y + row_height)
                
                current_y += row_height
            
            # Small spacing between groups
            if group_name and group_name != list(grouped_rows.keys())[-1]:
                current_y += 2
        
        # Update Y position
        self.set_y(current_y)
        self.ln(3)  # Small spacing after table
    
    def _add_doctor_comments(self, comments):
        """Add doctor comments section at the end of the report"""
        # Check if we need a new page
        if self.get_y() > self.h - 80:
            self.add_page()
            self.set_y(self.t_margin)
            self.ln(5)  # Small spacing after margin
        
        self.ln(20)
        
        # Elegant black line to mark end of results
        self.set_draw_color(*self.gray)
        self.set_line_width(0.05)
        line_y = self.get_y()
        self.line(15, line_y, self.w - 15, line_y)
        
        self.ln(15)
        
        # Section title (not bold, like other section titles)
        self.set_text_color(*self.blue_accent)
        self.set_font("VistaSansOTBook", "", 16)  # Regular weight instead of bold
        self.cell(0, 10, "Doctor comments", 0, 1, "L")
        
        self.ln(5)
        
        # Comments text
        self.set_text_color(*self.black)
        self.set_font("vistaSansLight", "", 10)
        
        # Wrap and add comments
        comment_lines = self._wrap_text(comments, self.w - 30)
        for line in comment_lines:
            self.cell(0, 5, line, 0, 1, "L")
        
        self.ln(5)