"""Slidev markdown renderer implementation."""
import yaml
import subprocess
import tempfile
import shutil
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def resolve_theme(primary_color: str | None) -> str:
    """Resolve hex color to semantic theme name.
    
    Maps primary colors from slide JSON to Slidev theme names:
    - #2563eb (blue) → "business"
    - #00ffa3 (neon green) → "cyber"
    - Unknown/None → "business" (default)
    
    Args:
        primary_color: Hex color string (e.g., "#2563eb") or None
        
    Returns:
        str: Theme name ("business" or "cyber")
        
    Examples:
        >>> resolve_theme("#2563eb")
        'business'
        >>> resolve_theme("#00ffa3")
        'cyber'
        >>> resolve_theme(None)
        'business'
    """
    if not primary_color:
        return "business"
    
    # Normalize to lowercase for case-insensitive matching
    color_lower = primary_color.lower()
    
    # Theme color mappings
    THEME_COLORS = {
        "#2563eb": "business",  # Blue primary
        "#00ffa3": "cyber",     # Neon green primary
    }
    
    return THEME_COLORS.get(color_lower, "business")


class SlidevRenderer:
    """Renderer for transforming slide JSON to Slidev markdown format.
    
    Converts slide JSON (from content generation) to Slidev-compatible
    markdown with frontmatter and slot syntax.
    
    Architecture:
    - Source: slidev-project/ (layouts, components - source controlled)
    - Build: slidev_build/ (temporary directory, auto-generated)
    
    Supports:
    - Custom Vue layouts (slidev-project/layouts/*.vue):
      smart-grid, hero-split, full-bleed, feature-grid, comparison, timeline, dashboard
    
    - Custom Vue components (slidev-project/components/*.vue):
      ChartWidget, TableWidget, QuoteWidget, MetricWidget
    
    - Slidev built-in layouts:
      default, center, cover, end, fact, image, image-left, image-right,
      intro, quote, section, statement, two-cols, two-cols-header
    """
    
    # Class-level source directory (src/paged/slidev-project)
    # Path from src/paged/render/slidev -> parent.parent.parent = src/paged
    SOURCE_DIR = Path(__file__).parent.parent.parent / "slidev-project"
    
    def __init__(self, output_dir: Path = None):
        """Initialize renderer with Jinja2 templates and build directory.
        
        Args:
            output_dir: Output directory for build. If provided, uses output_dir/slidev_build.
                       If None, uses project root/slidev_build (for backwards compatibility).
        """
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            cache_size=100  # Performance optimization
        )
        
        # Load templates
        self.frontmatter_template = self.env.get_template("frontmatter.j2")
        self.slot_template = self.env.get_template("slot.j2")
        self.slide_template = self.env.get_template("slide.j2")
        
        # Setup build directory
        # If output_dir provided, use output_dir/slidev_build
        # Otherwise fallback to project root/slidev_build
        if output_dir:
            self.build_dir = Path(output_dir) / "slidev_build"
        else:
            # Fallback to project root for backwards compatibility
            self.build_dir = Path(__file__).parent.parent.parent.parent.parent / "slidev_build"
        
        self._ensure_build_env()
    
    def _ensure_build_env(self):
        """Ensure Slidev build environment is set up (run once)."""
        package_json = self.build_dir / "package.json"
        
        # Copy layouts and components from source (src/paged/slidev-project)
        self._copy_layouts_and_components(self.SOURCE_DIR)
        
        # Skip npm install if already initialized
        if package_json.exists():
            return
        
        print(f"Setting up Slidev build environment in {self.build_dir}...")
        self.build_dir.mkdir(parents=True, exist_ok=True)
        
        # Create package.json with bundling tools
        package_data = {
            "name": "slidev-build-env",
            "type": "module",
            "dependencies": {
                "@slidev/cli": "latest",
                "@slidev/theme-default": "latest",
                "playwright-chromium": "latest",
                "vue": "^3"
            },
            "devDependencies": {
                "inline-source-cli": "latest"
            }
        }
        package_json.write_text(
            __import__('json').dumps(package_data, indent=2),
            encoding='utf-8'
        )
        
        # Install dependencies
        npm_cmd = "npm.cmd" if Path("C:\\Windows").exists() else "npm"
        print("Installing dependencies (this may take a minute)...")
        result = subprocess.run(
            [npm_cmd, "install"],
            cwd=self.build_dir,
            capture_output=True,
            timeout=300
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"npm install failed: {result.stderr.decode()}")
        
        print("Build environment ready")
    
    def _copy_layouts_and_components(self, source_dir: Path):
        """Copy layouts, components, and styles from slidev-project to build directory.
        
        Args:
            source_dir: Path to slidev-project directory
        """
        if not source_dir.exists():
            print(f"Warning: Source directory {source_dir} not found, skipping layout/component copy")
            return
        
        # Copy layouts
        source_layouts = source_dir / "layouts"
        if source_layouts.exists():
            dest_layouts = self.build_dir / "layouts"
            dest_layouts.mkdir(parents=True, exist_ok=True)
            
            for layout_file in source_layouts.glob("*.vue"):
                shutil.copy2(layout_file, dest_layouts / layout_file.name)
        
        # Copy components
        source_components = source_dir / "components"
        if source_components.exists():
            dest_components = self.build_dir / "components"
            dest_components.mkdir(parents=True, exist_ok=True)
            
            for component_file in source_components.glob("*.vue"):
                shutil.copy2(component_file, dest_components / component_file.name)
            
            # Also copy README if present
            readme = source_components / "README.md"
            if readme.exists():
                shutil.copy2(readme, dest_components / "README.md")
        
        # Copy styles (for global CSS like disabling animations)
        source_styles = source_dir / "styles"
        if source_styles.exists():
            dest_styles = self.build_dir / "styles"
            dest_styles.mkdir(parents=True, exist_ok=True)
            
            for style_file in source_styles.glob("*.css"):
                shutil.copy2(style_file, dest_styles / style_file.name)
    
    def render(self, renderable):
        """Render slide JSON to full HTML via Slidev build process.
        
        Args:
            renderable: Single slide dict or list of slide dicts
            
        Returns:
            str: Complete HTML page built by Slidev/Vue
        """
        # Generate markdown content
        markdown_content = self.render_to_markdown(renderable)
        
        # Build HTML using Slidev toolchain
        return self.render_to_html(markdown_content)
    
    def render_to_markdown(self, renderable, theme: dict = None):
        """Render slide JSON to Slidev markdown (intermediate format).
        
        Args:
            renderable: Single slide dict or list of slide dicts
            theme: Optional theme dict with colors/typography to override slide themes
            
        Returns:
            str: Slidev markdown content
        """
        if isinstance(renderable, list):
            return self.render_multi_slide(renderable, theme)
        else:
            return self.render_single_slide(renderable)
    
    def render_single_slide(self, slide: dict) -> str:
        """Render single slide to markdown.
        
        Args:
            slide: Slide JSON dict with layout, widgets, theme
            
        Returns:
            str: Markdown for one slide
        
        Raises:
            ValueError: If layout or widgets fields are missing
        """
        # Validation
        if "layout" not in slide:
            raise ValueError("Slide JSON must include 'layout' field")
        if "widgets" not in slide:
            raise ValueError("Slide JSON must include 'widgets' field")
        
        # Generate frontmatter
        frontmatter = self._generate_frontmatter(slide)
        
        # Render widgets - different handling based on layout
        widgets = slide.get("widgets", {})
        layout = slide.get("layout", "default")
        
        # Layouts with named slots (use slot syntax)
        # Include both legacy kebab-case and new dot-notation layouts
        SLOT_LAYOUTS = {
            # Legacy kebab-case layouts
            "two-cols", "two-cols-header", "hero-split", 
            "smart-grid", "feature-grid", "comparison", "timeline", "dashboard",
            "spotlight", "magazine", "quote-hero", "stats-showcase", "image-text", "cards-grid",
            # New dot-notation layouts (LLM-generated)
            "Cinematic.Split_50_50", "Cinematic.Split_30_70", "Cinematic.FullBleed",
            "Comparison.TwoColumn", "Comparison.BeforeAfter",
            "Bento.HeroLeft", "Bento.HeroTop", "Bento.Standard", "Bento.Quarter",
            "Matrix.Timeline", "Matrix.Feature", "Matrix.Dashboard",
            "Swiss.Poster", "Swiss.Asymmetry", "Swiss.SplitTypo",
        }
        
        # Use slots if layout is in the list OR if there are multiple widgets
        use_slots = layout in SLOT_LAYOUTS or len(widgets) > 1
        
        if use_slots:
            # Render each widget with its slot name
            slots_content = []
            for slot_name, widget_data in widgets.items():
                widget_content = self._render_widget_or_array(widget_data)
                # Sanitize content to avoid Slidev parsing issues
                widget_content = self._sanitize_content(widget_content)
                
                # Use slot syntax (::slotname::) - note the blank line after
                slot_md = f"::{slot_name}::\n\n{widget_content}"
                slots_content.append(slot_md)
            
            # Join slots without extra separators (each already has ::slotname::)
            slots_combined = "\n\n".join(slots_content)
        else:
            # For layouts without slots (cover, quote, etc.), combine all widgets
            widget_contents = []
            for slot_name, widget_data in widgets.items():
                widget_content = self._render_widget_or_array(widget_data)
                # Sanitize content to avoid Slidev parsing issues
                widget_content = self._sanitize_content(widget_content)
                widget_contents.append(widget_content)
            slots_combined = "\n\n".join(widget_contents)
        
        # Combine frontmatter + slots
        return f"{frontmatter}\n\n{slots_combined}"
    
    def render_multi_slide(self, slides: list, theme: dict = None) -> str:
        """Render multiple slides to markdown.
        
        Args:
            slides: List of slide JSON dicts
            theme: Optional theme dict to use (overrides slide theme)
            
        Returns:
            str: Complete multi-slide markdown with slide separators
        """
        if not slides:
            return ""
        
        # Use provided theme first, then fall back to slide theme
        theme_data = theme
        if theme_data is None:
            # Extract theme from first slide (can be dict, string, or None)
            theme_data = slides[0].get("theme") if slides else None
        
        # Handle None, dict, or string theme
        if theme_data is None:
            # Try getting theme from parameters
            params = slides[0].get("parameters", {}) or {}
            theme_data = params.get("theme", "default")
        
        if isinstance(theme_data, str):
            # Theme is just a name - use defaults
            theme_id = theme_data
            primary_color = "#2563eb"
            background_color = "#0f172a"  # Default dark
            text_color = "#ffffff"
            font_family = "Arial, sans-serif"
            heading_font = font_family
            typography = {}
        else:
            # Theme is a full dict
            theme_id = theme_data.get("id", "default")
            primary_color = theme_data.get("primary_color", "#2563eb")
            background_color = theme_data.get("background_color", "#ffffff")
            text_color = theme_data.get("text_color", "#1f2937")
            typography = theme_data.get("typography", {})
            font_family = theme_data.get("font_family", "Arial, sans-serif")
            heading_font = theme_data.get("heading_font") or font_family
        
        # Generate CSS for theme - no frontmatter, just styles
        theme_css = f"""<style>
:root {{
  --slidev-theme-primary: {primary_color};
  --slidev-theme-background: {background_color};
  --slidev-theme-text: {text_color};
}}

/* Apply theme colors */
.slidev-layout {{
  background-color: var(--slidev-theme-background);
  color: var(--slidev-theme-text);
  font-family: {font_family};
}}

/* Primary color accents */
h1, h2, h3, h4, h5, h6 {{
  color: var(--slidev-theme-primary);
  font-family: {heading_font};
}}

/* Links */
a {{
  color: var(--slidev-theme-primary);
}}

/* Code blocks */
.shiki {{
  background-color: rgba(0, 0, 0, 0.05) !important;
}}

/* Custom layout backgrounds */
.smart-grid .grid-column,
.feature-grid .feature-box,
.comparison .comparison-side,
.timeline .step-marker,
.dashboard .metric-card {{
  border-color: var(--slidev-theme-primary);
}}

.timeline .step-marker {{
  background-color: var(--slidev-theme-primary);
}}

/* Prevent scrollbars in grid cells */
.grid-cell,
.smart-grid .grid-column,
.feature-grid .feature-box,
.dashboard .metric-card {{
  overflow: hidden;
}}
</style>
"""
        
        # Render each slide individually
        rendered_slides = [self.render_single_slide(slide) for slide in slides]
        
        # Join slides - each already ends with --- from frontmatter, so just use blank lines
        # Slidev separates slides with "---" on its own line, which is the closing of one
        # frontmatter and works as separator to the next slide's opening "---"
        slides_content = "\n\n".join(rendered_slides)
        
        # In Slidev, first slide MUST start with ---
        # Global styles go AFTER the first slide's frontmatter or as a separate style slide
        # Option: Create a hidden first slide that contains global styles
        # Better option: Add global styles using Slidev's global-top.vue or inline in first slide
        
        # Create a proper Slidev file structure:
        # 1. First slide with global frontmatter (headmatter)
        # 2. Style block (goes in global scope after first ---)
        # 3. Rest of slides
        
        # Slidev expects: --- frontmatter --- then content
        # Global styles can be in <style> tag after the first ---
        
        # Build proper structure: --- \n headmatter \n --- \n <style> \n rest
        global_headmatter = f"""---
theme: default
title: Presentation
info: Generated by UCE Render
class: text-center
highlighter: shiki
drawings:
  persist: false
transition: slide-left
mdc: true
---

{theme_css}
"""
        
        return global_headmatter + "\n" + slides_content
    
    def render_to_html(self, markdown_content: str, base_path: str = "./") -> str:
        """Build HTML using Slidev/Vue toolchain.
        
        Uses persistent build environment, writes markdown to temp file,
        exports single HTML file, and returns the content.
        
        Args:
            markdown_content: Slidev markdown with frontmatter and slots
            base_path: Base path for assets (e.g., "/static/session_id/" for FastAPI mount)
            
        Returns:
            str: Complete single-file HTML page built by Slidev/Vue
            
        Raises:
            RuntimeError: If Slidev build/export fails
        """
        # Write markdown to temp slides.md in build directory
        slides_md = self.build_dir / "slides.md"
        slides_md.write_text(markdown_content, encoding='utf-8')
        
        # Save markdown to output directory for debugging
        output_dir = Path(__file__).parent.parent.parent.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        markdown_output_path = output_dir / "debug_markdown.md"
        markdown_output_path.write_text(markdown_content, encoding='utf-8')
        
        # Clean dist directory if exists
        dist_dir = self.build_dir / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        
        try:
            # Use npx.cmd on Windows, npx on Unix
            npx_cmd = "npx.cmd" if Path("C:\\Windows").exists() else "npx"
            
            print(f"Building slides with Slidev (base: {base_path})...")
            # Build SPA with configured base path
            result = subprocess.run(
                [npx_cmd, "@slidev/cli", "build", "slides.md", "--base", base_path, "--out", "dist"],
                cwd=self.build_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=120
            )
            
            if result.returncode != 0:
                print(f"Slidev build stderr: {result.stderr}")
                raise RuntimeError(f"Slidev build failed with exit code {result.returncode}")
            
            # Read built HTML from dist/index.html
            index_html = dist_dir / "index.html"
            if not index_html.exists():
                raise RuntimeError("Slidev build did not produce dist/index.html")
            
            # Inline all assets into single HTML file
            print("Inlining assets into single HTML file...")
            inlined_html = dist_dir / "index.inlined.html"
            
            # Slidev uses dynamic ES module imports (code splitting) which cannot be fully inlined
            # We need to copy the entire dist directory for the imports to work
            
            # Option 1: Try inline-source (will inline CSS/JS but not dynamic imports)
            # node_cmd = "node.exe" if Path("C:\\Windows").exists() else "node"
            # inline_script = self.build_dir / "inline.mjs"
            
            # For now, just use the built dist directory as-is
            # User must serve via HTTP server or copy entire dist folder
            
            html_content = index_html.read_text(encoding='utf-8')
            print(f"Generated Slidev HTML ({len(html_content)} chars)")
            print(f"Note: Slidev uses ES modules and requires serving via HTTP server")
            print(f"   To view: python -m http.server 8000 --directory '{dist_dir}' then open http://localhost:8000/")
            print(f"   Or copy entire '{dist_dir}' folder to web server")
            
            return html_content
            
        except FileNotFoundError:
            raise RuntimeError(
                "npx not found. Please install Node.js and ensure npx is in PATH."
            )
    
    def _sanitize_content(self, content: str) -> str:
        """Sanitize content to avoid Slidev parsing issues.
        
        Slidev uses '---' as a slide separator, so any '---' in content
        will break parsing. This method replaces problematic patterns.
        
        Args:
            content: Raw markdown content
            
        Returns:
            str: Sanitized content safe for Slidev
        """
        if not content:
            return content
        
        import re
        
        # Ensure content is a string
        if not isinstance(content, str):
            content = str(content) if content is not None else ""
        
        # Replace standalone '---' (horizontal rule) with alternative
        # Must be on its own line (with optional whitespace)
        # Use '***' instead which is also valid Markdown horizontal rule but not a Slidev separator
        content = re.sub(r'^---\s*$', '***', content, flags=re.MULTILINE)
        
        # Also handle '- - -' and '-- -' variations
        content = re.sub(r'^-\s+-\s+-\s*$', '***', content, flags=re.MULTILINE)
        
        # Handle case where '---' appears at start of a line followed by content
        # This could be mistaken for frontmatter start
        # Only replace if it's clearly not meant as frontmatter (e.g., "---text")
        content = re.sub(r'^---(?=[^\s\n])', '—', content, flags=re.MULTILINE)
        
        return content
    
    def _generate_frontmatter(self, slide: dict) -> str:
        """Generate YAML frontmatter from slide JSON.
        
        Args:
            slide: Slide JSON dict
            
        Returns:
            str: YAML frontmatter wrapped in ---
        """
        frontmatter_data = {}
        
        # Use layout name directly - supports both custom Vue layouts and Slidev built-ins
        layout = slide.get("layout", "default")
        frontmatter_data["layout"] = layout
        
        # Add theme for SlideShell (map from style/theme name to our predefined themes)
        # The Vue layouts expect: business, cyber, minimal, academic, creative, dark
        slide_theme = slide.get("theme", "")
        # Handle both string and dict theme values
        if isinstance(slide_theme, dict):
            # If theme is a dict, try to get theme_name from it
            slide_theme = slide_theme.get("theme_name", "") or slide_theme.get("name", "")
        
        if slide_theme and isinstance(slide_theme, str):
            # Map common theme patterns to our 6 predefined themes
            theme_map = {
                "professional": "business",
                "corporate": "business",
                "business": "business",
                "cyber": "cyber",
                "tech": "cyber",
                "dark": "dark",
                "minimal": "minimal",
                "clean": "minimal",
                "academic": "academic",
                "formal": "academic",
                "creative": "creative",
                "fun": "creative",
                "playful": "creative"
            }
            # Try to find a matching theme
            matched_theme = None
            theme_lower = slide_theme.lower()
            for key, value in theme_map.items():
                if key in theme_lower:
                    matched_theme = value
                    break
            frontmatter_data["theme"] = matched_theme or "business"
        else:
            frontmatter_data["theme"] = "business"
        
        # Add background color from slide's theme (ensures each slide uses the theme)
        theme_data = slide.get("theme", {})
        if isinstance(theme_data, dict) and "background_color" in theme_data:
            frontmatter_data["background"] = theme_data["background_color"]
        
        # Add header and footer as frontmatter properties
        if "header" in slide and slide["header"]:
            header_widget = slide["header"]
            if "parameters" in header_widget and "text" in header_widget["parameters"]:
                frontmatter_data["header"] = header_widget["parameters"]["text"]
        
        if "footer" in slide and slide["footer"]:
            footer_widget = slide["footer"]
            if "parameters" in footer_widget and "text" in footer_widget["parameters"]:
                frontmatter_data["footer"] = footer_widget["parameters"]["text"]
        
        # Add parameters (cols, ratio, align, etc.)
        if "parameters" in slide:
            params = slide["parameters"].copy()
            
            # Remove reserved keys that shouldn't be in frontmatter params
            # "layout" in parameters is a layout variant (e.g., "sidebar" for dashboard layout)
            # Not the actual slide layout
            reserved_keys = {"layout"}  # Can add more reserved keys here if needed
            for key in reserved_keys:
                if key in params:
                    # Rename to avoid collision with actual frontmatter layout
                    params[f"variant_{key}"] = params.pop(key)
            
            # Map vibe from LLM output to our predefined vibes
            # The Vue layouts expect: none, calm, dynamic, playful, professional, minimal, dramatic
            if "vibe" in params:
                vibe_map = {
                    "aurora": "dynamic",
                    "waves": "calm", 
                    "mesh": "playful",
                    "noise": "dramatic",
                    "none": "none",
                    "calm": "calm",
                    "dynamic": "dynamic",
                    "playful": "playful",
                    "professional": "professional",
                    "minimal": "minimal",
                    "dramatic": "dramatic"
                }
                params["vibe"] = vibe_map.get(params["vibe"], "none")
            
            frontmatter_data.update(params)
        
        # Auto-detect cols for smart-grid based on widget slots
        layout = slide.get("layout", "")
        if layout == "smart-grid" and "cols" not in frontmatter_data:
            widgets = slide.get("widgets", {})
            # Count col1, col2, col3, col4 slots
            col_count = sum(1 for k in widgets.keys() if k.startswith("col") and k[3:].isdigit())
            if col_count > 0:
                frontmatter_data["cols"] = min(4, max(2, col_count))
        
        # Ensure vibe has a default
        if "vibe" not in frontmatter_data:
            frontmatter_data["vibe"] = "none"
        
        # Convert to YAML (use literal style for multi-line strings)
        yaml_content = yaml.dump(frontmatter_data, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return f"---\n{yaml_content}---"
    
    def _render_widget_or_array(self, widget_data) -> str:
        """Render widget or array of widgets.
        
        Args:
            widget_data: Widget object, dict, or list of widgets
            
        Returns:
            str: Rendered markdown
        """
        # Handle arrays of widgets
        if isinstance(widget_data, list):
            rendered_widgets = [self._render_widget(w) for w in widget_data]
            return "\n\n".join(rendered_widgets)
        else:
            return self._render_widget(widget_data)
    
    def _render_widget(self, widget_data) -> str:
        """Dispatch widget rendering based on type.
        
        Args:
            widget_data: Widget object or dict
            
        Returns:
            str: Rendered markdown or Vue component
        """
        # Handle widget objects (from existing codebase)
        if hasattr(widget_data, "widget_type"):
            widget_type = widget_data.widget_type
            parameters = widget_data.parameters if hasattr(widget_data, "parameters") else {}
        # Handle plain dicts (for testing)
        elif isinstance(widget_data, dict):
            widget_type = widget_data.get("type", "")
            # Handle both nested parameters and flat structure
            if "parameters" in widget_data:
                parameters = widget_data["parameters"]
            else:
                # Flat structure - params are directly in widget_data
                parameters = widget_data
        else:
            return str(widget_data)
        
        # Dispatch based on type prefix or component name
        if widget_type.startswith("Type."):
            return self._render_typography_widget(widget_type, parameters, widget_data)
        elif widget_type.startswith("Data."):
            return self._render_data_widget(widget_type, parameters)
        elif widget_type in ["TableWidget", "ChartWidget", "MetricWidget", "QuoteWidget"]:
            # Direct component names - render as Vue components
            return self._render_vue_component(widget_type, parameters)
        else:
            # Fallback: return text if available
            return str(parameters.get("text", ""))
    
    def _render_typography_widget(self, widget_type: str, parameters: dict, widget_data) -> str:
        """Render typography widgets as markdown.
        
        Args:
            widget_type: Widget type string (e.g., "Type.Display")
            parameters: Widget parameters dict
            widget_data: Original widget object
            
        Returns:
            str: Markdown text
        """
        text = str(parameters.get("text", ""))
        
        if widget_type == "Type.Display":
            # Plain text for display
            return text
        
        elif widget_type == "Type.Heading":
            # Markdown heading
            level = parameters.get("level", 1)
            prefix = "#" * level
            return f"{prefix} {text}"
        
        elif widget_type == "Type.Body":
            # Paragraph with markdown preserved
            return text
        
        elif widget_type == "Type.List":
            # Bullet list
            items = parameters.get("items", [])
            return "\n".join([f"- {str(item)}" for item in items])
        
        elif widget_type == "Type.Quote":
            # Blockquote
            return f"> {text}"
        
        elif widget_type == "Type.Code":
            # Code block
            code = str(parameters.get("code", text))
            language = parameters.get("language", "")
            return f"```{language}\n{code}\n```"
        
        else:
            # Fallback
            return text
    
    def _render_data_widget(self, widget_type: str, parameters: dict) -> str:
        """Render data widgets as markdown.
        
        Args:
            widget_type: Widget type string (e.g., "Data.BigNum")
            parameters: Widget parameters dict
            
        Returns:
            str: Markdown representation of the data widget
        """
        if widget_type == "Data.BigNum":
            # Big number display - value with label
            value = parameters.get("value", "")
            label = parameters.get("label", "")
            sublabel = parameters.get("sublabel", "")
            
            result = f"## {value}\n\n**{label}**"
            if sublabel:
                result += f"\n\n{sublabel}"
            return result
        
        elif widget_type == "Data.Metric":
            # Metric with optional change indicator
            value = parameters.get("value", "")
            label = parameters.get("label", "")
            change = parameters.get("change", "")
            
            result = f"### {value}"
            if change:
                result += f" ({change})"
            if label:
                result += f"\n\n{label}"
            return result
        
        elif widget_type == "Data.Progress":
            # Progress indicator
            value = parameters.get("value", 0)
            label = parameters.get("label", "")
            
            return f"**{label}**: {value}%"
        
        elif widget_type == "Data.Table":
            # Table data
            columns = parameters.get("columns", [])
            rows = parameters.get("rows", [])
            
            if not columns:
                return ""
            
            # Build markdown table
            header = "| " + " | ".join(str(c) for c in columns) + " |"
            separator = "| " + " | ".join("---" for _ in columns) + " |"
            body_rows = []
            for row in rows:
                if isinstance(row, list):
                    body_rows.append("| " + " | ".join(str(cell) for cell in row) + " |")
                elif isinstance(row, dict):
                    body_rows.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")
            
            return "\n".join([header, separator] + body_rows)
        
        elif widget_type == "Data.Chart":
            # Chart placeholder
            chart_type = parameters.get("chartType", "bar")
            title = parameters.get("title", "Chart")
            
            return f"📊 **{title}** ({chart_type} chart)"
        
        else:
            # Fallback - try to get value or text
            return parameters.get("value", parameters.get("text", ""))

    def _render_vue_component(self, component_name: str, parameters: dict) -> str:
        """Render Vue components directly from component names.
        
        Args:
            component_name: Component name (e.g., "TableWidget", "ChartWidget")
            parameters: Component parameters dict
            
        Returns:
            str: Vue component tag with props
        """
        import json
        
        if component_name == "TableWidget":
            title = parameters.get("title", "")
            variant = parameters.get("variant", "default")
            columns = json.dumps(parameters.get("columns", []))
            rows = json.dumps(parameters.get("rows", []))
            show_header = str(parameters.get("showHeader", True)).lower()
            
            return f'<TableWidget title="{title}" variant="{variant}" :columns=\'{columns}\' :rows=\'{rows}\' :showHeader="{show_header}" />'
        
        elif component_name == "ChartWidget":
            chart_type = parameters.get("chartType", "bar")
            title = parameters.get("title", "")
            data = json.dumps(parameters.get("data", []))
            unit = parameters.get("unit", "")
            
            return f'<ChartWidget chartType="{chart_type}" title="{title}" :data=\'{data}\' unit="{unit}" />'
        
        elif component_name == "MetricWidget":
            label = parameters.get("label", "")
            value = parameters.get("value", "")
            change = parameters.get("change", None)
            change_label = parameters.get("changeLabel", "")
            subtitle = parameters.get("subtitle", "")
            icon = parameters.get("icon", "")
            variant = parameters.get("variant", "default")
            
            props = [f'label="{label}"', f'value="{value}"']
            # change must be a number for MetricWidget - skip if invalid
            if change is not None:
                try:
                    change_num = float(change)
                    props.append(f':change="{int(change_num) if change_num == int(change_num) else change_num}"')
                except (ValueError, TypeError):
                    # If change is not a valid number (e.g., "+tools, +LLMs"), skip it
                    pass
            if change_label:
                props.append(f'changeLabel="{change_label}"')
            if subtitle:
                props.append(f'subtitle="{subtitle}"')
            if icon:
                props.append(f'icon="{icon}"')
            if variant != "default":
                props.append(f'variant="{variant}"')
            
            return f'<MetricWidget {" ".join(props)} />'
        
        elif component_name == "QuoteWidget":
            text = parameters.get("text", "")
            author = parameters.get("author", "")
            attribution = parameters.get("attribution", "")
            variant = parameters.get("variant", "default")
            show_icon = str(parameters.get("showIcon", True)).lower()
            
            props = [f'text="{text}"']
            if author:
                props.append(f'author="{author}"')
            if attribution:
                props.append(f'attribution="{attribution}"')
            if variant != "default":
                props.append(f'variant="{variant}"')
            props.append(f':showIcon="{show_icon}"')
            
            return f'<QuoteWidget {" ".join(props)} />'
        
        else:
            # Unknown component - return empty
            return ""
