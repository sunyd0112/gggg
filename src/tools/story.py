"""Story Tool - Plan narrative arc and assign atoms to slides.

Generates draft slides with:
- story: Narrative description of slide purpose
- atoms: List of atom IDs to use
- density: Information density level
- visual_design: Visual approach (hierarchical, grid, timeline, etc.)

Layout and widgets are empty - filled by ContentTool.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Dict, Any, ClassVar
from pydantic import Field

from src.common.tool_protocol import DirectTool, ToolContext, ToolPatch, register_tool

if TYPE_CHECKING:
    from src.generation.state import PipelineState


class StoryContext(ToolContext):
    """Context for story planning - holds source content and existing slides."""
    source_content: Optional[str] = Field(default=None, description="Raw source content for story generation")
    atoms_collection: Optional[Any] = Field(default=None, description="Optional atoms for enhanced refinement")
    existing_slides: Optional[List[Dict]] = Field(default=None, description="Existing slides for refinement")
    intent_guidance: str = Field(default="", description="Guidance from constitution")
    slide_count_target: Optional[int] = Field(default=None, description="Target slide count")


class StoryPatch(ToolPatch):
    """Patch containing draft slides with story/visual_design."""
    slides: List[Dict[str, Any]] = Field(default_factory=list, description="Draft slides")
    
    class Config:
        arbitrary_types_allowed = True


@register_tool
class StoryTool(DirectTool[StoryContext, StoryPatch]):
    """Plans the narrative arc and assigns atoms to slides.
    
    This is the first content generation step:
    1. Analyzes atoms to understand available content
    2. Plans a story arc across slides
    3. Assigns atoms to each slide
    4. Sets visual_design hints for each slide
    5. Outputs draft slides (layout/widgets empty)
    
    ContentTool depends on this to generate layouts/widgets.
    """
    
    name: ClassVar[str] = "story"
    description: ClassVar[str] = """Plan narrative arc and create draft slides directly from source content.

OUTPUT: Draft slides with story, density, visual_design populated.
Layout and widgets are EMPTY (filled by content tool).
Atoms field is EMPTY (atoms are generated separately and used by content tool).

MODES:
1. mode="generate": Plan complete story arc from source content
2. mode="refine": Modify existing story (merge/split/reorder slides)

WHEN TO USE REFINE:
- "merge page 3 and 4" → refine existing story
- "split slide 2 into multiple" → refine
- "remove the intro" → refine
- "add a conclusion slide" → refine
- "reorder slides" → refine

WHEN TO USE GENERATE:
- No slides exist yet
- "regenerate", "start over", "create new"
- Major restructuring"""

    query_description: ClassVar[str] = """Triggers on:
- Initial presentation creation (generate)
- Story restructuring: merge, split, reorder, add, remove slides (refine)
- Changing narrative flow or slide count"""

    args_description: ClassVar[List[str]] = [
        "mode: 'generate' for full creation, 'refine' for editing story",
        "instruction: user's request",
        "slide_count: target number of slides",
    ]
    requires: ClassVar[List[str]] = ["constitution"]
    produces: ClassVar[List[str]] = ["slides (draft state)"]
    examples: ClassVar[List[str]] = [
        '{"id": "story", "type": "story", "params": {"slide_count": 10, "mode": "generate"}, "depends_on": ["constitution"]}',
        '{"id": "story", "type": "story", "params": {"mode": "refine", "instruction": "merge page 3 and page 4"}}',
        '{"id": "story", "type": "story", "params": {"mode": "refine", "instruction": "add a conclusion slide"}}',
    ]
    
    def slice(self, state: "PipelineState", params: Optional[Dict[str, Any]] = None) -> StoryContext:
        """Extract context from state for story planning."""
        params = params or {}
        
        # Build intent guidance from constitution
        intent_guidance = ""
        constitution = state.get_constitution()
        if constitution:
            if hasattr(constitution, 'style_rules') and constitution.style_rules:
                intent_guidance = "\n".join(constitution.style_rules)
            if hasattr(constitution, 'content_exclusions') and constitution.content_exclusions:
                exclusions = "\n".join([f"- {e}" for e in constitution.content_exclusions])
                intent_guidance += f"\n\nContent to EXCLUDE:\n{exclusions}"
            if hasattr(constitution, 'content_requirements') and constitution.content_requirements:
                requirements = "\n".join([f"- {r}" for r in constitution.content_requirements])
                intent_guidance += f"\n\nContent REQUIRED:\n{requirements}"
        
        # Get slide count target
        slide_count_target = params.get("slide_count")
        if not slide_count_target and constitution:
            slide_count_target = getattr(constitution, 'slide_count_target', None)
        
        # Get existing slides for refinement
        existing_slides = None
        mode = params.get("mode", "generate")
        if mode == "refine" and state.slides:
            existing_slides = state.slides
        
        # Get source content
        source_content = None
        if state.source:
            from pathlib import Path
            source_path = Path(state.source.path)
            if source_path.exists():
                source_content = source_path.read_text(encoding='utf-8')
        
        # Get atoms (optional - used for refinement if available)
        atoms_collection = state.get_atoms() if mode == "refine" else None
        
        return StoryContext(
            source_content=source_content,
            atoms_collection=atoms_collection,
            existing_slides=existing_slides,
            intent_guidance=intent_guidance,
            slide_count_target=slide_count_target,
        )
    
    def transform(self, context: StoryContext, user_instruction: str) -> StoryPatch:
        """Execute story planning via LLM using source content."""
        from src.generation.content.story_generator import generate_story_from_source, refine_story_from_source
        
        if not context.source_content:
            raise ValueError("No source content available for story generation")
        
        # Build full guidance
        full_guidance = context.intent_guidance
        if user_instruction:
            if full_guidance:
                full_guidance += f"\n\nUser instruction: {user_instruction}"
            else:
                full_guidance = f"User instruction: {user_instruction}"
        
        if context.existing_slides:
            # Refinement mode - modify existing story structure
            self._log(f"Refining story for {len(context.existing_slides)} existing slides")
            if context.atoms_collection:
                # Use atoms for more structured refinement
                from src.generation.content.story_generator import refine_story
                atom_count = len(context.atoms_collection.list_contexts())
                self._log(f"Using {atom_count} atoms for refinement")
                draft_slides = refine_story(
                    existing_slides=context.existing_slides,
                    atoms=context.atoms_collection,
                    user_instruction=user_instruction,
                    intent_guidance=full_guidance,
                )
            else:
                # Fallback to source-based refinement
                self._log(f"Using source content for refinement")
                draft_slides = refine_story_from_source(
                    existing_slides=context.existing_slides,
                    source_content=context.source_content,
                    user_instruction=user_instruction,
                    intent_guidance=full_guidance,
                )
        else:
            # Generation mode - create new story from scratch
            self._log(f"Planning story from source content ({len(context.source_content)} chars)")
            draft_slides = generate_story_from_source(
                source_content=context.source_content,
                user_instruction=user_instruction,
                slide_count=context.slide_count_target,
                intent_guidance=full_guidance,
            )
        
        self._log(f"Planned {len(draft_slides)} draft slides")
        return StoryPatch(slides=draft_slides)
    
    def apply(self, state: "PipelineState", patch: StoryPatch) -> None:
        """Apply draft slides to state (replaces existing slides)."""
        if patch.slides:
            state.set_slides(patch.slides)
            self._log(f"Applied: {len(patch.slides)} draft slides")
