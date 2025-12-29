"""Layout generator - Generates layouts and widgets for draft slides.

Takes draft slides with story, atoms, visual_design and generates:
- layout: Appropriate layout name based on visual_design
- widgets: Widget content populated from atoms
- state: "active"
"""
from __future__ import annotations

import json
import os
import re
from typing import List, Dict, Any, Optional

from src.generation.atom.collection import AtomCollection
from src.utils.llm_client import call_llm


def _get_atom_content(atom) -> str:
    """Extract displayable content from any atom type."""
    if hasattr(atom, 'text') and atom.text:
        return atom.text
    if hasattr(atom, 'quote') and atom.quote:
        return atom.quote
    if hasattr(atom, 'description') and atom.description:
        return atom.description
    if hasattr(atom, 'name') and atom.name:
        parts = [atom.name]
        if hasattr(atom, 'role') and atom.role:
            parts.append(atom.role)
        if hasattr(atom, 'affiliation') and atom.affiliation:
            parts.append(atom.affiliation)
        return " - ".join(parts)
    if hasattr(atom, 'value') and hasattr(atom, 'label'):
        return f"{atom.value} ({atom.label})"
    if hasattr(atom, 'abstract') and atom.abstract:
        return atom.abstract
    return str(atom.id)


def _get_atom_type(atom) -> str:
    """Get the type name of an atom."""
    return type(atom).__name__


def _get_layout_prompt_from_content(
    draft_slides: List[Dict],
    context_before: List[Dict],
    context_after: List[Dict],
    theme_id: Optional[str],
    intent_guidance: str,
) -> str:
    """Build prompt for layout generation from SCQA content-based slides.
    
    These slides already have headline, subtitle, content.sections populated.
    Task is to select appropriate layout and convert content to proper widgets.
    """
    drafts_json = json.dumps(draft_slides, indent=2, ensure_ascii=False)
    
    # Build context section - only include layout info from context slides
    context_section = ""
    if context_before:
        context_slim = [{"id": s.get("id"), "layout": s.get("layout")} for s in context_before]
        context_section += f"## Slides Before (for layout flow)\n```json\n{json.dumps(context_slim, indent=2)}\n```\n\n"
    if context_after:
        context_slim = [{"id": s.get("id"), "layout": s.get("layout")} for s in context_after]
        context_section += f"## Slides After (for layout flow)\n```json\n{json.dumps(context_slim, indent=2)}\n```\n\n"
    
    guidance_section = f"\n\n## Guidance\n{intent_guidance}" if intent_guidance else ""
    
    return f"""# SLIDE LAYOUT GENERATION (Content-Based)

You are converting draft slides with populated content into active slides with layouts and widgets.

## Draft Slides
```json
{drafts_json}
```
{context_section}{guidance_section}

# TASK

For each slide:
1. **Select layout** based on `visual_design` description and `category`
2. **Generate widgets** by converting `content.sections` and `headline`/`subtitle` into proper widget structure
3. **Assign to slots** based on layout requirements and visual_design hints

# AVAILABLE LAYOUTS (name: slots)

**Custom Layouts:**
- **two-cols-header**: header, left, right (two columns with prominent header)
- **hero-split**: left, right (split layout, hero style)
- **smart-grid**: header, col1, col2, col3, col4 (grid layout, 4 columns)
- **timeline**: (chronological flow with timeline items)
- **comparison**: (before/after comparison layout)
- **dashboard**: (metrics dashboard layout)
- **feature-grid**: (grid of features/cards)
- **cards-grid**: (grid of card items)
- **spotlight**: default, subtitle (focused single message)
- **quote-hero**: quote, author, context (prominent quotes)
- **stats-showcase**: (showcase multiple statistics)
- **image-text**: (image with text combination)
- **magazine**: (magazine-style layout)
- **full-bleed**: (full-bleed image/content)
- **info-boxes**: (information boxes layout)

**Slidev Built-in Layouts:**
- **default**: default (simple centered content)
- **center**: default (centered content)
- **cover**: default (title slide)
- **end**: default (closing slide)
- **two-cols**: left, right (basic two columns)

# WIDGET TYPES

**Typography (Type.*):**
- `Type.Display`: Plain text for display (parameters: text)
- `Type.Heading`: Markdown heading (parameters: text, level 1-3)
- `Type.Body`: Paragraph text (parameters: text)
- `Type.List`: Bullet list (parameters: items [array of strings])
- `Type.Quote`: Blockquote (parameters: text)
- `Type.Code`: Code block (parameters: code, language)

**Data (Data.*):**
- `Data.BigNum`: Large number display (parameters: value, label, sublabel)
- `Data.Metric`: Metric with trend (parameters: value, label, change)
- `Data.Progress`: Progress bar (parameters: value, label)
- `Data.Table`: Markdown table (parameters: columns, rows)
- `Data.Chart`: Chart placeholder (parameters: chartType, title)

**Vue Components:**
- `TableWidget`: Interactive table (parameters: title, columns, rows, variant, showHeader)
- `ChartWidget`: Chart component (parameters: chartType, title, data, unit)
- `QuoteWidget`: Styled quote (parameters: quote, author)
- `MetricWidget`: Metric display (parameters: value, label, trend)

# CONVERSION RULES

1. **headline** → Header widget (Type.Heading level 1 or Data.BigNum if numeric)
2. **subtitle** → Subheader widget (Type.Body or Type.Heading level 2)
3. **content.sections** → Convert intelligently:
   - Section title → Type.Heading (level 2 or 3)
   - Bullets → Type.List with items array
   - Split sections across slots if multi-column layout
4. **visual_design keywords**:
   - "two-column", "split", "side-by-side" → two-cols or hero-left
   - "grid", "dashboard", "cards" → smart-grid or dashboard
   - "timeline", "chronological", "steps" → timeline
   - "comparison", "before/after" → comparison
   - "centered", "focus", "spotlight" → spotlight or center
   - "quote" → quote-hero
5. **Preserve fields**: Keep all original fields (headline, subtitle, content, category, visual_design, density, speaker_intent, density_tag, presenters, date, etc.)

# OUTPUT FORMAT

Return a JSON array of active slides. Each slide must have:
- `id`: Keep original
- `rank`: Keep original  
- `state`: Set to "active"
- `layout`: Selected layout name
- `widgets`: Object mapping slot names to widget objects
- **All original fields preserved** (headline, subtitle, content, category, visual_design, density, atoms, speaker_intent, density_tag, presenters, date, etc.)

Example:
```json
[
  {{
    "id": "slide_02",
    "rank": 2,
    "state": "active",
    "layout": "two-cols",
    "widgets": {{
      "left": {{
        "type": "Type.Heading",
        "parameters": {{"text": "Meetings drive outcomes", "level": 2}}
      }},
      "right": {{
        "type": "Type.List",
        "parameters": {{"items": ["Point 1", "Point 2"]}}
      }}
    }},
    "headline": "Manual doc creation is slowing execution",
    "subtitle": "High-value meetings require hours of post-processing",
    "category": "Situation",
    "content": {{...}},
    "visual_design": "Two-column framework...",
    "density": "moderate",
    "atoms": [],
    "speaker_intent": "Create urgency..."
  }}
]
```

**CRITICAL**: Return ONLY the JSON array, no explanation or markdown wrapper."""


def _get_layout_prompt(
    draft_slides: List[Dict],
    context_before: List[Dict],
    context_after: List[Dict],
    atoms: AtomCollection,
    theme_id: Optional[str],
    intent_guidance: str,
) -> str:
    """Build prompt for layout generation from atom-based slides (legacy)."""
    drafts_json = json.dumps(draft_slides, indent=2)
    
    # Only include atoms that are referenced by the draft slides
    referenced_atom_ids = set()
    for slide in draft_slides:
        for atom_id in slide.get("atoms", []):
            referenced_atom_ids.add(atom_id)
    
    # Filter atoms to only those referenced
    referenced_atoms = []
    for atom in atoms.list_contexts():
        if atom.id in referenced_atom_ids:
            content = _get_atom_content(atom)
            referenced_atoms.append({
                "id": atom.id,
                "type": _get_atom_type(atom),
                "content": content[:500] if len(content) > 500 else content,
                "rank": atom.rank,
            })
    
    atoms_json = json.dumps(referenced_atoms, indent=2)
    
    # Build context section - only include layout/widgets from context slides, not full content
    context_section = ""
    if context_before:
        context_slim = [{"id": s.get("id"), "layout": s.get("layout"), "story": s.get("story", "")[:100]} for s in context_before]
        context_section += f"## Slides Before (for flow reference)\n```json\n{json.dumps(context_slim, indent=2)}\n```\n\n"
    if context_after:
        context_slim = [{"id": s.get("id"), "layout": s.get("layout"), "story": s.get("story", "")[:100]} for s in context_after]
        context_section += f"## Slides After (for flow reference)\n```json\n{json.dumps(context_slim, indent=2)}\n```\n\n"
    
    return f"""# SLIDE LAYOUT GENERATION

## Draft Slides
```json
{drafts_json}
```

## Referenced Atoms
```json
{atoms_json}
```
{context_section}
# TASK
For each draft slide: select layout based on visual_design, populate widgets from atoms, set state="active".

# LAYOUTS (name: slots)
- hero-split: left, right
- smart-grid: header, col1-col4
- timeline: title, step1-step5
- comparison: title, beforeLabel, before, afterLabel, after
- dashboard: title, metric1-4, chart
- center: default
- spotlight: default, subtitle
- quote-hero: quote, author, context
- stats-showcase: title, stat-1 to stat-4

# WIDGET TYPES
- Type.Display (headline), Type.Heading, Type.Body, Type.List (items array), Type.Quote
- Data.BigNum (value, label, sublabel), Data.Metric (value, label, trend), Data.Chart

# OUTPUT
JSON array. Each slide must have: id, rank, state="active", story (keep), atoms (keep), density (keep), visual_design (keep), layout (new), widgets (new).

```json
[{{"id":"...", "rank":1, "state":"active", "story":"...", "atoms":[...], "density":"...", "visual_design":"...", "layout":"hero-split", "widgets":{{"left":{{"type":"Data.BigNum","parameters":{{"value":"14","label":"Years"}}}},"right":{{"type":"Type.Body","parameters":{{"text":"..."}}}}}}}}]
```

Return ONLY the JSON array, no explanation."""


def generate_layouts(
    draft_slides: List[Dict],
    context_before: List[Dict],
    context_after: List[Dict],
    atoms: Optional[AtomCollection],
    theme_id: Optional[str] = None,
    intent_guidance: str = "",
) -> List[Dict[str, Any]]:
    """Generate layouts and widgets for draft slides.
    
    Supports two modes:
    1. New SCQA format: Slides already have 'content' field with sections/bullets
       -> Use _generate_layouts_from_content (skip LLM)
    2. Old atom-based format: Slides have 'atoms' IDs only
       -> Generate content and widgets from atoms via LLM
    
    Args:
        draft_slides: Slides with story/atoms/visual_design but no layout/widgets
        context_before: Up to 2 active slides before for context
        context_after: Up to 2 active slides after for context
        atoms: AtomCollection for widget content
        theme_id: Active theme ID
        intent_guidance: Additional guidance
        
    Returns:
        List of active slides with layout and widgets populated
    """
    if not draft_slides:
        return []
    
    # Detect which format: check if slides have 'content' field already
    has_content = any(slide.get("content") for slide in draft_slides)
    
    if has_content:
        # New SCQA format: content already generated by story tool
        return _generate_layouts_from_content(
            draft_slides, context_before, context_after,
            theme_id, intent_guidance
        )
    
    # Old atom-based format
    if not atoms:
        # No atoms - can't populate widgets meaningfully
        # Return drafts with minimal layouts
        return _fallback_layouts(draft_slides)
    
    prompt = _get_layout_prompt(
        draft_slides, context_before, context_after,
        atoms, theme_id, intent_guidance
    )
    
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    response = call_llm(
        system_prompt="You are a slide designer. Output only valid JSON array.",
        user_prompt=prompt,
        deployment=deployment,
        temperature=0.7,
        max_tokens=16000,  # Need room for 10 slides with widgets
    )
    
    # Parse JSON from response
    active_slides = _parse_json_array(response)
    
    # Validate and normalize
    for slide in active_slides:
        slide["state"] = "active"
        if not slide.get("layout"):
            # Default fallback layout
            slide["layout"] = "center"
        if not slide.get("widgets"):
            slide["widgets"] = {}
    
    return active_slides


def _fallback_layouts(draft_slides: List[Dict]) -> List[Dict]:
    """Generate minimal layouts when no atoms available."""
    result = []
    for slide in draft_slides:
        active = dict(slide)
        active["state"] = "active"
        active["layout"] = "center"  # Simple default
        active["widgets"] = {
            "default": {
                "type": "Type.Body",
                "parameters": {"text": slide.get("story", "Slide content")}
            }
        }
        result.append(active)
    return result


def _generate_layouts_from_content(
    draft_slides: List[Dict],
    context_before: List[Dict],
    context_after: List[Dict],
    theme_id: Optional[str],
    intent_guidance: str,
) -> List[Dict[str, Any]]:
    """Generate layouts for slides that already have content populated (SCQA format).
    
    New SCQA format: Slides have headline, subtitle, content.sections populated.
    Uses LLM to:
    1. Select appropriate layout based on visual_design description
    2. Convert content sections/bullets to proper widget structure
    3. Preserve all original fields (citations, speaker_intent, etc.)
    """
    prompt = _get_layout_prompt_from_content(
        draft_slides, context_before, context_after,
        theme_id, intent_guidance
    )
    
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    response = call_llm(
        system_prompt="You are a presentation layout designer. Convert content-based slides to properly structured layouts with widgets. Output only valid JSON array.",
        user_prompt=prompt,
        deployment=deployment,
        temperature=0.7,
        max_tokens=16000,  # Need room for 10 slides with full content
    )
    
    # Parse JSON from response
    active_slides = _parse_json_array(response)
    
    # Validate and ensure all fields are present
    for slide in active_slides:
        slide["state"] = "active"
        if not slide.get("layout"):
            # Fallback layout selection
            category = slide.get("category", "")
            if category == "cover":
                slide["layout"] = "title"
            elif category == "ending":
                slide["layout"] = "ending"
            else:
                slide["layout"] = "center"
        if not slide.get("widgets"):
            slide["widgets"] = {}
    
    return active_slides


def _generate_layouts_from_atoms(
    draft_slides: List[Dict],
    context_before: List[Dict],
    context_after: List[Dict],
    atoms: AtomCollection,
    theme_id: Optional[str],
    intent_guidance: str,
) -> List[Dict[str, Any]]:
    """Generate layouts for slides using atom-based content (legacy mode)."""
    prompt = _get_layout_prompt(
        draft_slides, context_before, context_after, atoms, theme_id, intent_guidance
    )
    
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    response = call_llm(
        system_prompt="You are a presentation layout designer. Output only valid JSON array.",
        user_prompt=prompt,
        deployment=deployment,
        temperature=0.7,
        max_tokens=8000,
    )
    
    slides = _parse_json_array(response)
    
    # Ensure state is active
    for slide in slides:
        slide["state"] = "active"
        slide.setdefault("layout", "standard")
        slide.setdefault("widgets", {})
    
    return slides


def _parse_json_array(response: str) -> List[Dict]:
    """Extract JSON array from LLM response."""
    json_match = re.search(r'\[[\s\S]*\]', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse layout response as JSON: {e}")
