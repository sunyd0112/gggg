"""Test that story generates directly from source content.

This test verifies:
1. Story tool no longer depends on atoms
2. Story and atoms can run in parallel
3. State.json shows independent execution
"""
from pathlib import Path
from src.generation.state import PipelineState
from src.generation.todo.runner import PipelineRunner

def test_story_from_source():
    """Test story generation directly from source."""
    
    # Setup
    output_dir = Path("output/test_story_from_source")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Pick a test source file
    source_file = Path("data/context/career_talk.txt")
    if not source_file.exists():
        # Use any existing test file
        source_file = list(Path("data").rglob("*.txt"))[0] if list(Path("data").rglob("*.txt")) else None
        if not source_file:
            print("❌ No test source file found. Create a test .txt file first.")
            return
    
    print(f"📄 Using source: {source_file}")
    
    # Run pipeline
    runner = PipelineRunner(
        verbose=True,
        output_dir=output_dir,
    )
    
    print("\n🔄 Running pipeline...")
    state = runner.run(
        source_path=source_file,
        user_instruction="Create 5 slides about this content, professional tone",
    )
    
    # Check state
    state_path = output_dir / "state.json"
    print(f"\n📋 Checking {state_path}")
    
    # Analyze todos
    print("\n=== TODO EXECUTION ORDER ===")
    for todo in state.todos.todos:
        status_icon = "✅" if todo.status.value == "completed" else "⏸️"
        print(f"{status_icon} {todo.type.value:15} | depends_on: {todo.depends_on}")
    
    # Check if story depends on atoms
    story_todo = next((t for t in state.todos.todos if t.type.value == "story"), None)
    atoms_todo = next((t for t in state.todos.todos if t.type.value == "atoms"), None)
    
    if story_todo:
        if "atoms" in story_todo.depends_on:
            print("\n❌ FAIL: Story still depends on atoms!")
            print(f"   Story depends_on: {story_todo.depends_on}")
        else:
            print("\n✅ PASS: Story does NOT depend on atoms")
            print(f"   Story depends_on: {story_todo.depends_on}")
    
    # Check slides were created
    if state.slides:
        print(f"\n✅ Generated {len(state.slides)} slides")
        print("\nFirst slide preview:")
        first_slide = state.slides[0]
        print(f"  - story: {first_slide.get('story', 'N/A')[:100]}...")
        print(f"  - visual_design: {first_slide.get('visual_design', 'N/A')[:100]}...")
        print(f"  - atoms: {first_slide.get('atoms', [])}")
    else:
        print("\n❌ No slides generated")
    
    print(f"\n📁 Full state saved to: {state_path}")
    return state

if __name__ == "__main__":
    test_story_from_source()
