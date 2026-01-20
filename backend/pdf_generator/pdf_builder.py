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
        
        # Add patient info (sex and birthdate) on the right side - multiline, left-aligned
        if self.patient_metadata:
            sex = self.patient_metadata.get('sex', '')
            birthdate = self.patient_metadata.get('birthdate', '')
            
            if sex or birthdate:
                self.set_font("VistaSansOTBook", "", 9)
                self.set_text_color(*self.gray)
                
                # Position on the right side, but text aligned left
                page_width = self.w
                right_margin = self.r_margin
                line_height = 5  # Height between lines
                start_y = 8  # Start at same height as logo
                
                # Calculate max width needed for both lines to align them properly
                if sex:
                    sex_display = "Male" if sex.upper() == 'M' else "Female" if sex.upper() == 'F' else sex
                    sex_text = f"Sex: {sex_display}"
                else:
                    sex_text = ""
                
                if birthdate:
                    birthdate_text = f"Birthdate: {birthdate}"
                else:
                    birthdate_text = ""
                
                # Find the maximum width
                max_width = max(
                    self.get_string_width(sex_text) if sex_text else 0,
                    self.get_string_width(birthdate_text) if birthdate_text else 0
                )
                
                # Position both lines starting from the same x position (right-aligned container, left-aligned text)
                info_x = page_width - right_margin - max_width
                
                # First line: Sex
                if sex:
                    self.set_xy(info_x, start_y)
                    self.cell(max_width, line_height, sex_text, 0, 0, "L")
                
                # Second line: Birthdate
                if birthdate:
                    self.set_xy(info_x, start_y + line_height)
                    self.cell(max_width, line_height, birthdate_text, 0, 0, "L")
    
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
    
    def add_category_section(self, category_name, explanation):
        """Add category section with title and explanation"""
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
        estimated_height = 10 + (len(explanation_lines) * 5) + 8
        
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
        
        self.ln(5)
    
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

        # Process categories continuously (do NOT force 1 page per category)
        first_category = True
        for category in structured_data['categories']:
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
            has_explanations = any(p.get('explanation') for p in category['parameters'])
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
    
    def _add_parameter_explanations(self, parameters):
        """Add explanations for parameters (grouped logically)"""
        # Group parameters by their explanation text (to avoid duplicates)
        explanation_groups = {}
        
        for param in parameters:
            explanation = param.get('explanation', '')
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
            explanation_lines = self._wrap_text(explanation, self.w - 30)
            for line in explanation_lines:
                self.cell(0, 4, line, 0, 1, "L")
            self.ln(2)
    
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